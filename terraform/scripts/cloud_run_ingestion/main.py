"""
Lumina Bank - Cloud Run: Microservicio de Ingesta Streaming
===========================================================
Recibe transacciones vía HTTPS desde las 12 entidades bancarias,
valida los datos y los encola en Pub/Sub.
"""

import os
import json
import uuid
import logging
from datetime import datetime

from flask import Flask, request, jsonify
from google.cloud import pubsub_v1

app = Flask(__name__)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", f"projects/{PROJECT_ID}/topics/lumina-transactions-ingestion")

publisher = pubsub_v1.PublisherClient()

VALID_TRANSACTION_TYPES = {"TRANSFER", "PAYMENT", "WITHDRAWAL", "DEPOSIT"}
VALID_CHANNELS = {"APP", "ATM", "BRANCH", "CORRESPONDENT"}
VALID_BANKS = {
    "banco-central-datalandia", "banco-norte-metropolitano",
    "banco-sur-cooperativo", "banco-este-comercial",
    "banco-oeste-industrial", "banco-union-popular",
    "banco-progreso-digital", "banco-herencia-nacional",
    "banco-innovacion-fintech", "banco-solidario-regional",
    "banco-mercantil-datalandia", "banco-federal-integrado",
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "lumina-ingestion-api"}), 200


@app.route("/api/v1/transactions", methods=["POST"])
def ingest_transaction():
    """Recibe y valida una transacción, luego la encola en Pub/Sub."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body vacío"}), 400

        # Validar campos requeridos
        errors = validate_transaction(data)
        if errors:
            return jsonify({"error": "Validación fallida", "details": errors}), 400

        # Enriquecer
        data["transaction_id"] = data.get("transaction_id", str(uuid.uuid4()))
        data["ingestion_timestamp"] = datetime.utcnow().isoformat()
        data["status"] = "PENDING"

        # Publicar en Pub/Sub
        message = json.dumps(data).encode("utf-8")
        attributes = {
            "bank_entity": data["bank_entity"],
            "transaction_type": data["transaction_type"],
            "channel": data["channel"],
        }

        future = publisher.publish(
            PUBSUB_TOPIC, data=message, **attributes
        )
        message_id = future.result()

        return jsonify({
            "transaction_id": data["transaction_id"],
            "message_id": message_id,
            "status": "ACCEPTED",
            "timestamp": data["ingestion_timestamp"],
        }), 202

    except Exception as e:
        logger.error(f"Error en ingesta: {e}")
        return jsonify({"error": "Error interno", "details": str(e)}), 500


@app.route("/api/v1/transactions/batch", methods=["POST"])
def ingest_batch():
    """Recibe un lote de transacciones."""
    try:
        data = request.get_json()
        if not data or "transactions" not in data:
            return jsonify({"error": "Campo 'transactions' requerido"}), 400

        results = []
        for txn in data["transactions"]:
            errors = validate_transaction(txn)
            if errors:
                results.append({
                    "transaction_id": txn.get("transaction_id", "unknown"),
                    "status": "REJECTED",
                    "errors": errors,
                })
                continue

            txn["transaction_id"] = txn.get("transaction_id", str(uuid.uuid4()))
            txn["ingestion_timestamp"] = datetime.utcnow().isoformat()
            txn["status"] = "PENDING"

            message = json.dumps(txn).encode("utf-8")
            attributes = {
                "bank_entity": txn["bank_entity"],
                "transaction_type": txn["transaction_type"],
                "channel": txn["channel"],
            }
            future = publisher.publish(PUBSUB_TOPIC, data=message, **attributes)
            message_id = future.result()

            results.append({
                "transaction_id": txn["transaction_id"],
                "message_id": message_id,
                "status": "ACCEPTED",
            })

        accepted = sum(1 for r in results if r["status"] == "ACCEPTED")
        return jsonify({
            "total": len(results),
            "accepted": accepted,
            "rejected": len(results) - accepted,
            "results": results,
        }), 202

    except Exception as e:
        logger.error(f"Error en ingesta batch: {e}")
        return jsonify({"error": "Error interno"}), 500


def validate_transaction(data):
    """Valida los campos de una transacción."""
    errors = []
    required = ["bank_entity", "customer_id", "transaction_type", "amount", "currency", "channel"]
    for field in required:
        if field not in data:
            errors.append(f"Campo requerido faltante: {field}")

    if not errors:
        if data["bank_entity"] not in VALID_BANKS:
            errors.append(f"Entidad bancaria inválida: {data['bank_entity']}")
        if data["transaction_type"] not in VALID_TRANSACTION_TYPES:
            errors.append(f"Tipo de transacción inválido: {data['transaction_type']}")
        if data["channel"] not in VALID_CHANNELS:
            errors.append(f"Canal inválido: {data['channel']}")
        try:
            amount = float(data["amount"])
            if amount <= 0:
                errors.append("El monto debe ser positivo")
        except (ValueError, TypeError):
            errors.append("Monto inválido")

    return errors


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
