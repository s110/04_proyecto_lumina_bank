"""
Lumina Bank - Pipeline de Streaming con Apache Beam (Dataflow)
==============================================================
Lee transacciones de Pub/Sub, las procesa, evalúa fraude con Vertex AI,
y escribe en BigQuery y Bigtable.

Uso:
    python streaming_pipeline.py \
        --project=PROJECT_ID \
        --region=us-central1 \
        --input_subscription=projects/PROJECT_ID/subscriptions/lumina-ingestion-dataflow-subscription \
        --output_table=PROJECT_ID:lumina_streaming.transactions \
        --distribution_topic=projects/PROJECT_ID/topics/lumina-transactions-distribution \
        --runner=DataflowRunner \
        --temp_location=gs://PROJECT_ID-lumina-dataflow-temp/tmp \
        --staging_location=gs://PROJECT_ID-lumina-dataflow-staging/staging \
        --streaming
"""

import argparse
import json
import logging
import uuid
from datetime import datetime

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.pubsub import ReadFromPubSub, WriteToPubSub
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition

logger = logging.getLogger(__name__)


class ParseTransaction(beam.DoFn):
    """Parsea y valida el mensaje JSON de la transacción."""

    def process(self, element):
        try:
            data = json.loads(element.decode("utf-8"))

            required_fields = [
                "bank_entity", "customer_id", "transaction_type",
                "amount", "currency", "channel"
            ]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Campo requerido faltante: {field}")
                    return

            data["transaction_id"] = data.get(
                "transaction_id", str(uuid.uuid4())
            )
            data["processing_timestamp"] = datetime.utcnow().isoformat()

            if "transaction_timestamp" not in data:
                data["transaction_timestamp"] = data["processing_timestamp"]

            data["amount"] = float(data["amount"])

            yield data

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
        except Exception as e:
            logger.error(f"Error procesando transacción: {e}")


class EnrichWithFraudScore(beam.DoFn):
    """Consulta Vertex AI para obtener el score de fraude."""

    def setup(self):
        from google.cloud import aiplatform
        self.endpoint = None

    def process(self, element):
        try:
            # Simulación del score de fraude
            # En producción, se invoca el endpoint de Vertex AI:
            #   response = self.endpoint.predict(instances=[features])
            #   element["fraud_score"] = response.predictions[0]

            import hashlib
            hash_val = int(
                hashlib.md5(
                    element["transaction_id"].encode()
                ).hexdigest(), 16
            )
            element["fraud_score"] = (hash_val % 100) / 100.0

            if element["fraud_score"] > 0.85:
                element["status"] = "BLOCKED"
            elif element["fraud_score"] > 0.7:
                element["status"] = "PENDING"
            else:
                element["status"] = "APPROVED"

            yield element

        except Exception as e:
            logger.error(f"Error evaluando fraude: {e}")
            element["fraud_score"] = None
            element["status"] = "PENDING"
            yield element


class WriteToBigtable(beam.DoFn):
    """Escribe perfiles actualizados en Cloud Bigtable."""

    def setup(self):
        from google.cloud import bigtable
        self.client = bigtable.Client(admin=True)
        self.instance = self.client.instance("lumina-user-profiles")
        self.table = self.instance.table("user_profiles")

    def process(self, element):
        try:
            row_key = f"{element['bank_entity']}#{element['customer_id']}"
            row = self.table.direct_row(row_key)

            row.set_cell(
                "financial_data",
                "last_transaction_amount",
                str(element["amount"]),
            )
            row.set_cell(
                "financial_data",
                "last_transaction_type",
                element["transaction_type"],
            )
            row.set_cell(
                "financial_data",
                "last_channel",
                element["channel"],
            )
            row.set_cell(
                "risk_score",
                "fraud_score",
                str(element.get("fraud_score", 0.0)),
            )
            row.set_cell(
                "risk_score",
                "last_status",
                element["status"],
            )
            row.commit()

            yield element
        except Exception as e:
            logger.error(f"Error escribiendo en Bigtable: {e}")
            yield element


class WriteToRedis(beam.DoFn):
    """Escribe cache en Memorystore Redis para consultas de baja latencia."""

    def setup(self):
        import redis
        import os
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True
        )

    def process(self, element):
        try:
            key = f"txn:{element['transaction_id']}"
            self.redis_client.setex(key, 3600, json.dumps(element))

            customer_key = (
                f"customer:{element['bank_entity']}:"
                f"{element['customer_id']}:last_txn"
            )
            self.redis_client.set(customer_key, json.dumps(element))

            yield element
        except Exception as e:
            logger.error(f"Error escribiendo en Redis: {e}")
            yield element


class FormatForDistribution(beam.DoFn):
    """Formatea el mensaje para el tópico de distribución fan-out."""

    def process(self, element):
        message = json.dumps({
            "transaction_id": element["transaction_id"],
            "bank_entity": element["bank_entity"],
            "customer_id": element["customer_id"],
            "status": element["status"],
            "amount": element["amount"],
            "currency": element["currency"],
            "fraud_score": element.get("fraud_score"),
            "processing_timestamp": element["processing_timestamp"],
        }).encode("utf-8")

        attributes = {"bank_entity": element["bank_entity"]}

        yield beam.pvalue.TaggedOutput("messages", message)
        yield beam.pvalue.TaggedOutput("attributes", attributes)


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_subscription", required=True)
    parser.add_argument("--output_table", required=True)
    parser.add_argument("--distribution_topic", required=True)
    parser.add_argument("--bigtable_enabled", default="true")
    parser.add_argument("--redis_enabled", default="true")

    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=pipeline_options) as p:
        # 1. Leer de Pub/Sub
        raw_messages = (
            p
            | "ReadFromPubSub" >> ReadFromPubSub(
                subscription=known_args.input_subscription
            )
        )

        # 2. Parsear y validar
        parsed = (
            raw_messages
            | "ParseTransaction" >> beam.ParDo(ParseTransaction())
        )

        # 3. Enriquecer con score de fraude (Vertex AI)
        enriched = (
            parsed
            | "EnrichFraudScore" >> beam.ParDo(EnrichWithFraudScore())
        )

        # 4. Escribir en Bigtable (perfiles de usuario)
        if known_args.bigtable_enabled == "true":
            bigtable_written = (
                enriched
                | "WriteBigtable" >> beam.ParDo(WriteToBigtable())
            )
        else:
            bigtable_written = enriched

        # 5. Escribir en Redis (cache)
        if known_args.redis_enabled == "true":
            redis_written = (
                bigtable_written
                | "WriteRedis" >> beam.ParDo(WriteToRedis())
            )
        else:
            redis_written = bigtable_written

        # 6. Escribir en BigQuery
        _ = (
            redis_written
            | "WriteBigQuery" >> WriteToBigQuery(
                table=known_args.output_table,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_NEVER,
            )
        )

        # 7. Publicar en tópico de distribución (fan-out a 12 bancos)
        distribution_messages = (
            redis_written
            | "FormatDistribution" >> beam.ParDo(
                FormatForDistribution()
            ).with_outputs("messages", "attributes")
        )

        _ = (
            distribution_messages.messages
            | "PublishDistribution" >> WriteToPubSub(
                topic=known_args.distribution_topic
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
