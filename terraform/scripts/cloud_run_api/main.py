"""
Lumina Bank - Cloud Run: API Backend
=====================================
API de consulta conectada a BigQuery. Sirve pronósticos de liquidez,
KPIs en tiempo real, y datos para Looker Studio.
Protegida con IAM (solo el frontend/BFF puede invocar).
"""

import os
import json
import logging
from datetime import datetime

from flask import Flask, request, jsonify
from google.cloud import bigquery

app = Flask(__name__)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
BQ_DATASET_STREAMING = os.environ.get("BQ_DATASET_STREAMING", "lumina_streaming")
BQ_DATASET_BATCH = os.environ.get("BQ_DATASET_BATCH", "lumina_batch")

bq_client = bigquery.Client(project=PROJECT_ID)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "lumina-api-backend"}), 200


@app.route("/api/v1/liquidity/forecast", methods=["GET"])
def get_liquidity_forecast():
    """Devuelve el pronóstico de liquidez por entidad bancaria."""
    bank_entity = request.args.get("bank_entity")
    days = int(request.args.get("days", 30))

    query = f"""
        SELECT
            bank_entity,
            forecast_date,
            predicted_inflow,
            predicted_outflow,
            net_liquidity,
            is_payday
        FROM `{PROJECT_ID}.{BQ_DATASET_BATCH}.liquidity_forecast`
        WHERE forecast_date >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        {"AND bank_entity = @bank_entity" if bank_entity else ""}
        ORDER BY bank_entity, forecast_date DESC
        LIMIT 1000
    """

    job_config = bigquery.QueryJobConfig()
    if bank_entity:
        job_config.query_parameters = [
            bigquery.ScalarQueryParameter("bank_entity", "STRING", bank_entity)
        ]

    results = bq_client.query(query, job_config=job_config)
    rows = [dict(row) for row in results]

    return jsonify({"data": rows, "count": len(rows)}), 200


@app.route("/api/v1/transactions/kpis", methods=["GET"])
def get_kpis():
    """Devuelve KPIs en tiempo real."""
    bank_entity = request.args.get("bank_entity")
    hours = int(request.args.get("hours", 24))

    query = f"""
        SELECT
            bank_entity,
            kpi_name,
            kpi_value,
            window_start,
            window_end
        FROM `{PROJECT_ID}.{BQ_DATASET_STREAMING}.kpis_realtime`
        WHERE window_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        {"AND bank_entity = @bank_entity" if bank_entity else ""}
        ORDER BY window_start DESC
        LIMIT 500
    """

    job_config = bigquery.QueryJobConfig()
    if bank_entity:
        job_config.query_parameters = [
            bigquery.ScalarQueryParameter("bank_entity", "STRING", bank_entity)
        ]

    results = bq_client.query(query, job_config=job_config)
    rows = [dict(row) for row in results]

    return jsonify({"data": rows, "count": len(rows)}), 200


@app.route("/api/v1/transactions/summary", methods=["GET"])
def get_transactions_summary():
    """Resumen de transacciones por entidad."""
    bank_entity = request.args.get("bank_entity")

    query = f"""
        SELECT
            bank_entity,
            COUNT(*) as total_transactions,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount,
            COUNTIF(status = 'APPROVED') as approved,
            COUNTIF(status = 'BLOCKED') as blocked,
            COUNTIF(status = 'PENDING') as pending,
            AVG(fraud_score) as avg_fraud_score,
            MIN(transaction_timestamp) as first_txn,
            MAX(transaction_timestamp) as last_txn
        FROM `{PROJECT_ID}.{BQ_DATASET_STREAMING}.transactions`
        WHERE DATE(transaction_timestamp) = CURRENT_DATE()
        {"AND bank_entity = @bank_entity" if bank_entity else ""}
        GROUP BY bank_entity
        ORDER BY total_transactions DESC
    """

    job_config = bigquery.QueryJobConfig()
    if bank_entity:
        job_config.query_parameters = [
            bigquery.ScalarQueryParameter("bank_entity", "STRING", bank_entity)
        ]

    results = bq_client.query(query, job_config=job_config)
    rows = [dict(row) for row in results]

    return jsonify({"data": rows, "count": len(rows)}), 200


@app.route("/api/v1/branches/metrics", methods=["GET"])
def get_branch_metrics():
    """Métricas de volumen por sucursal/cajero."""
    bank_entity = request.args.get("bank_entity")
    days = int(request.args.get("days", 7))

    query = f"""
        SELECT
            bank_entity,
            branch_id,
            channel_type,
            SUM(total_transactions) as total_transactions,
            SUM(total_amount) as total_amount,
            AVG(utilization_rate) as avg_utilization,
            AVG(avg_wait_time_minutes) as avg_wait_time
        FROM `{PROJECT_ID}.{BQ_DATASET_BATCH}.branch_volume_metrics`
        WHERE metric_date >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        {"AND bank_entity = @bank_entity" if bank_entity else ""}
        GROUP BY bank_entity, branch_id, channel_type
        ORDER BY total_transactions DESC
        LIMIT 500
    """

    job_config = bigquery.QueryJobConfig()
    if bank_entity:
        job_config.query_parameters = [
            bigquery.ScalarQueryParameter("bank_entity", "STRING", bank_entity)
        ]

    results = bq_client.query(query, job_config=job_config)
    rows = [dict(row) for row in results]

    return jsonify({"data": rows, "count": len(rows)}), 200


@app.route("/api/v1/exchange-rates", methods=["GET"])
def get_exchange_rates():
    """Tipos de cambio más recientes."""
    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{BQ_DATASET_BATCH}.exchange_rates`
        ORDER BY timestamp DESC
        LIMIT 100
    """
    results = bq_client.query(query)
    rows = [dict(row) for row in results]

    return jsonify({"data": rows, "count": len(rows)}), 200


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
