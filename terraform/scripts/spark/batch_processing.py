"""
Lumina Bank - Procesamiento Batch con PySpark (Dataproc)
========================================================
Calcula tendencias de movimientos, pronósticos de liquidez,
entrena modelo GBT con Spark ML, y procesa métricas por sucursal.

Uso (se ejecuta en Dataproc):
    spark-submit \
        --master yarn \
        --deploy-mode cluster \
        --jars gs://spark-lib/bigquery/spark-bigquery-with-dependencies_2.12-0.36.1.jar \
        batch_processing.py \
        --project_id=PROJECT_ID \
        --raw_bucket=gs://PROJECT_ID-lumina-raw-landing \
        --bq_dataset=lumina_batch \
        --lookback_days=90
"""

import argparse
import logging
from datetime import datetime, timedelta

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    TimestampType, IntegerType, BooleanType
)
from pyspark.ml.feature import VectorAssembler, StringIndexer
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml import Pipeline

logger = logging.getLogger(__name__)


def create_spark_session(project_id):
    """Crea sesión de Spark con conectores de BigQuery y GCS."""
    return (
        SparkSession.builder
        .appName("LuminaBank-BatchProcessing")
        .config("spark.jars.packages",
                "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.36.1")
        .config("parentProject", project_id)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )


def load_historical_transactions(spark, raw_bucket, lookback_days):
    """Carga transacciones históricas de los últimos N días desde GCS."""
    schema = StructType([
        StructField("transaction_id", StringType(), False),
        StructField("bank_entity", StringType(), False),
        StructField("customer_id", StringType(), False),
        StructField("transaction_type", StringType(), False),
        StructField("amount", DoubleType(), False),
        StructField("currency", StringType(), False),
        StructField("source_account", StringType(), True),
        StructField("destination_account", StringType(), True),
        StructField("destination_bank", StringType(), True),
        StructField("channel", StringType(), False),
        StructField("status", StringType(), False),
        StructField("fraud_score", DoubleType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("transaction_timestamp", TimestampType(), False),
        StructField("branch_id", StringType(), True),
        StructField("is_fraud", IntegerType(), True),
    ])

    cutoff_date = datetime.now() - timedelta(days=lookback_days)

    df = (
        spark.read
        .option("header", "true")
        .schema(schema)
        .csv(f"{raw_bucket}/historical/transactions/")
        .filter(F.col("transaction_timestamp") >= cutoff_date)
    )

    return df


def calculate_movement_trends(df, project_id, bq_dataset):
    """Calcula tendencias de movimiento y días festivos."""
    trends = (
        df
        .withColumn("date", F.to_date("transaction_timestamp"))
        .withColumn("hour", F.hour("transaction_timestamp"))
        .withColumn("day_of_week", F.dayofweek("transaction_timestamp"))
        .withColumn("is_weekend", F.when(
            F.col("day_of_week").isin(1, 7), True
        ).otherwise(False))
        .groupBy("bank_entity", "date", "day_of_week", "is_weekend")
        .agg(
            F.count("*").alias("total_transactions"),
            F.sum("amount").alias("total_amount"),
            F.avg("amount").alias("avg_amount"),
            F.countDistinct("customer_id").alias("unique_customers"),
            F.sum(F.when(F.col("status") == "APPROVED", 1).otherwise(0))
                .alias("approved_count"),
            F.sum(F.when(F.col("status") == "BLOCKED", 1).otherwise(0))
                .alias("blocked_count"),
        )
        .withColumn("approval_rate",
                     F.col("approved_count") / F.col("total_transactions"))
    )

    return trends


def calculate_liquidity_forecast(df, project_id, bq_dataset):
    """Calcula pronóstico de liquidez por entidad bancaria."""
    liquidity = (
        df
        .withColumn("date", F.to_date("transaction_timestamp"))
        .withColumn("is_inflow", F.when(
            F.col("transaction_type").isin("DEPOSIT", "TRANSFER_IN"), True
        ).otherwise(False))
        .groupBy("bank_entity", "date")
        .agg(
            F.sum(F.when(F.col("is_inflow"), F.col("amount")).otherwise(0))
                .alias("total_inflow"),
            F.sum(F.when(~F.col("is_inflow"), F.col("amount")).otherwise(0))
                .alias("total_outflow"),
        )
        .withColumn("net_liquidity",
                     F.col("total_inflow") - F.col("total_outflow"))
        .withColumn("day_of_week", F.dayofweek("date"))
        .withColumn("day_of_month", F.dayofmonth("date"))
        .withColumn("is_payday", F.when(
            F.col("day_of_month").isin(1, 15, 30), True
        ).otherwise(False))
    )

    # Escribir en BigQuery
    (
        liquidity
        .withColumn("forecast_id", F.expr("uuid()"))
        .withColumn("forecast_date", F.current_timestamp())
        .withColumnRenamed("total_inflow", "predicted_inflow")
        .withColumnRenamed("total_outflow", "predicted_outflow")
        .select(
            "forecast_id", "bank_entity", "forecast_date",
            "predicted_inflow", "predicted_outflow", "net_liquidity",
            "is_payday"
        )
        .write
        .format("bigquery")
        .option("table", f"{project_id}.{bq_dataset}.liquidity_forecast")
        .option("temporaryGcsBucket",
                f"{project_id}-lumina-dataflow-temp")
        .mode("append")
        .save()
    )

    logger.info("Pronóstico de liquidez escrito en BigQuery")
    return liquidity


def train_fraud_model(df):
    """Entrena modelo GBT (Gradient Boosted Trees) para detección de fraude."""
    # Preparar features
    training_df = (
        df
        .filter(F.col("is_fraud").isNotNull())
        .withColumn("hour", F.hour("transaction_timestamp"))
        .withColumn("day_of_week", F.dayofweek("transaction_timestamp"))
        .withColumn("day_of_month", F.dayofmonth("transaction_timestamp"))
        .na.fill(0.0)
    )

    # Indexar variables categóricas
    type_indexer = StringIndexer(
        inputCol="transaction_type", outputCol="type_index"
    )
    channel_indexer = StringIndexer(
        inputCol="channel", outputCol="channel_index"
    )
    bank_indexer = StringIndexer(
        inputCol="bank_entity", outputCol="bank_index"
    )

    # Assembler de features numéricas
    feature_cols = [
        "amount", "type_index", "channel_index", "bank_index",
        "hour", "day_of_week", "day_of_month"
    ]
    assembler = VectorAssembler(
        inputCols=feature_cols, outputCol="features"
    )

    # Modelo GBT
    gbt = GBTClassifier(
        labelCol="is_fraud",
        featuresCol="features",
        maxIter=50,
        maxDepth=5,
        stepSize=0.1,
        subsamplingRate=0.8,
    )

    pipeline = Pipeline(stages=[
        type_indexer, channel_indexer, bank_indexer, assembler, gbt
    ])

    # Split train/test
    train_df, test_df = training_df.randomSplit([0.8, 0.2], seed=42)

    logger.info(
        f"Entrenando modelo GBT: {train_df.count()} train, "
        f"{test_df.count()} test"
    )

    model = pipeline.fit(train_df)

    # Evaluar
    predictions = model.transform(test_df)
    evaluator = BinaryClassificationEvaluator(
        labelCol="is_fraud", metricName="areaUnderROC"
    )
    auc = evaluator.evaluate(predictions)
    logger.info(f"Modelo GBT - AUC-ROC: {auc:.4f}")

    return model, auc


def calculate_branch_metrics(df, project_id, bq_dataset):
    """Procesa métricas de volumen por sucursal/cajero."""
    metrics = (
        df
        .filter(F.col("branch_id").isNotNull())
        .withColumn("metric_date", F.to_date("transaction_timestamp"))
        .groupBy("bank_entity", "branch_id", "channel", "metric_date")
        .agg(
            F.count("*").alias("total_transactions"),
            F.sum("amount").alias("total_amount"),
            F.expr("percentile_approx(amount, 0.5)").alias("median_amount"),
            F.max(F.hour("transaction_timestamp")).alias("peak_hour"),
        )
        .withColumn("metric_id", F.expr("uuid()"))
        .withColumn("metric_date", F.to_timestamp("metric_date"))
        .withColumnRenamed("channel", "channel_type")
    )

    # Escribir en BigQuery
    (
        metrics
        .select(
            "metric_id", "bank_entity", "branch_id", "channel_type",
            "metric_date", "total_transactions", "total_amount", "peak_hour"
        )
        .write
        .format("bigquery")
        .option("table",
                f"{project_id}.{bq_dataset}.branch_volume_metrics")
        .option("temporaryGcsBucket",
                f"{project_id}-lumina-dataflow-temp")
        .mode("append")
        .save()
    )

    logger.info("Métricas de sucursal escritas en BigQuery")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", required=True)
    parser.add_argument("--raw_bucket", required=True)
    parser.add_argument("--bq_dataset", default="lumina_batch")
    parser.add_argument("--lookback_days", type=int, default=90)
    parser.add_argument("--model_output_path", default=None)
    args = parser.parse_args()

    spark = create_spark_session(args.project_id)

    try:
        logger.info("="*60)
        logger.info("LUMINA BANK - Procesamiento Batch Iniciado")
        logger.info(f"Proyecto: {args.project_id}")
        logger.info(f"Lookback: {args.lookback_days} días")
        logger.info("="*60)

        # 1. Cargar datos históricos
        logger.info("Paso 1: Cargando transacciones históricas...")
        df = load_historical_transactions(
            spark, args.raw_bucket, args.lookback_days
        )
        df.cache()
        total_records = df.count()
        logger.info(f"Registros cargados: {total_records}")

        # 2. Calcular tendencias
        logger.info("Paso 2: Calculando tendencias de movimiento...")
        trends = calculate_movement_trends(
            df, args.project_id, args.bq_dataset
        )

        # 3. Pronóstico de liquidez
        logger.info("Paso 3: Generando pronóstico de liquidez...")
        liquidity = calculate_liquidity_forecast(
            df, args.project_id, args.bq_dataset
        )

        # 4. Entrenar modelo GBT
        logger.info("Paso 4: Entrenando modelo GBT de fraude...")
        model, auc = train_fraud_model(df)

        # Guardar modelo
        model_path = args.model_output_path or (
            f"gs://{args.project_id}-lumina-datalake"
            f"/models/fraud_detection/"
            f"gbt_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        model.write().overwrite().save(model_path)
        logger.info(f"Modelo guardado en: {model_path}")

        # 5. Métricas por sucursal
        logger.info("Paso 5: Procesando métricas por sucursal...")
        calculate_branch_metrics(
            df, args.project_id, args.bq_dataset
        )

        logger.info("="*60)
        logger.info("PROCESAMIENTO BATCH COMPLETADO EXITOSAMENTE")
        logger.info(f"Registros procesados: {total_records}")
        logger.info(f"Modelo GBT AUC: {auc:.4f}")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Error en procesamiento batch: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    main()
