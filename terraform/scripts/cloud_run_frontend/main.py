"""
Lumina Bank - Cloud Run: Frontend / BFF (Backend for Frontend)
===============================================================
Servicio de enrutado que orquesta llamadas al API Backend y
devuelve la respuesta de transacción aprobada/bloqueada al usuario.
"""

import os
import json
import logging

import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
API_BACKEND_URL = os.environ.get("API_BACKEND_URL", "http://localhost:8081")

# Template HTML básico para el dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lumina Bank - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a1628; color: #e0e6ed; }
        .header { background: linear-gradient(135deg, #1a237e, #0d47a1); padding: 1.5rem 2rem; }
        .header h1 { font-size: 1.8rem; color: #fff; }
        .header p { color: #90caf9; margin-top: 0.3rem; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
        .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
        .card h3 { color: #60a5fa; margin-bottom: 1rem; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px; }
        .metric { font-size: 2.5rem; font-weight: bold; color: #fff; }
        .metric-label { color: #94a3b8; font-size: 0.9rem; margin-top: 0.3rem; }
        .status-approved { color: #4ade80; }
        .status-blocked { color: #f87171; }
        .status-pending { color: #fbbf24; }
        .banks-list { list-style: none; }
        .banks-list li { padding: 0.5rem 0; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; }
        .btn { background: #2563eb; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; font-size: 0.9rem; }
        .btn:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Lumina Bank</h1>
        <p>Sistema Financiero Unificado de DataLandia - Dashboard en Tiempo Real</p>
    </div>
    <div class="container">
        <div class="grid">
            <div class="card">
                <h3>Transacciones Hoy</h3>
                <div class="metric" id="total-txn">--</div>
                <div class="metric-label">Total procesadas</div>
            </div>
            <div class="card">
                <h3>Estado de Transacciones</h3>
                <p><span class="status-approved">Aprobadas:</span> <span id="approved">--</span></p>
                <p><span class="status-blocked">Bloqueadas:</span> <span id="blocked">--</span></p>
                <p><span class="status-pending">Pendientes:</span> <span id="pending">--</span></p>
            </div>
            <div class="card">
                <h3>Score de Fraude Promedio</h3>
                <div class="metric" id="fraud-score">--</div>
                <div class="metric-label">Valor entre 0.0 - 1.0</div>
            </div>
            <div class="card">
                <h3>Entidades Bancarias</h3>
                <div class="metric">12</div>
                <div class="metric-label">Bancos integrados en DataLandia</div>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "lumina-frontend-bff"}), 200


@app.route("/bff/transactions/summary", methods=["GET"])
def bff_summary():
    """Proxy al API backend para obtener resumen de transacciones."""
    try:
        bank_entity = request.args.get("bank_entity", "")
        resp = requests.get(
            f"{API_BACKEND_URL}/api/v1/transactions/summary",
            params={"bank_entity": bank_entity} if bank_entity else {},
            timeout=10,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        logger.error(f"Error consultando API backend: {e}")
        return jsonify({"error": "Servicio no disponible"}), 503


@app.route("/bff/liquidity", methods=["GET"])
def bff_liquidity():
    """Proxy al API backend para pronóstico de liquidez."""
    try:
        resp = requests.get(
            f"{API_BACKEND_URL}/api/v1/liquidity/forecast",
            params=request.args,
            timeout=10,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        logger.error(f"Error consultando liquidez: {e}")
        return jsonify({"error": "Servicio no disponible"}), 503


@app.route("/bff/transaction/status/<transaction_id>", methods=["GET"])
def get_transaction_status(transaction_id):
    """Consulta el estado de una transacción (aprobada/bloqueada)."""
    try:
        # En producción, consultaría Redis primero (baja latencia)
        # y luego BigQuery si no está en cache
        return jsonify({
            "transaction_id": transaction_id,
            "status": "APPROVED",
            "message": "Transacción procesada exitosamente",
        }), 200
    except Exception as e:
        logger.error(f"Error consultando transacción: {e}")
        return jsonify({"error": "Error interno"}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
