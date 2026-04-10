"""
Lumina Bank - Generador de Datos de Prueba
==========================================
Genera datos simulados de transacciones para las 12 entidades bancarias
y los envía al endpoint de Cloud Run o los guarda como CSV para batch.

Uso:
    # Enviar al endpoint de Cloud Run (streaming)
    python generate_test_data.py --mode streaming --url https://CLOUD_RUN_URL --count 100

    # Generar CSV para batch (se sube a GCS)
    python generate_test_data.py --mode batch --output ./test_data/ --count 10000
"""

import argparse
import csv
import json
import os
import random
import uuid
from datetime import datetime, timedelta

import requests

BANK_ENTITIES = [
    "banco-central-datalandia",
    "banco-norte-metropolitano",
    "banco-sur-cooperativo",
    "banco-este-comercial",
    "banco-oeste-industrial",
    "banco-union-popular",
    "banco-progreso-digital",
    "banco-herencia-nacional",
    "banco-innovacion-fintech",
    "banco-solidario-regional",
    "banco-mercantil-datalandia",
    "banco-federal-integrado",
]

TRANSACTION_TYPES = ["TRANSFER", "PAYMENT", "WITHDRAWAL", "DEPOSIT"]
CHANNELS = ["APP", "ATM", "BRANCH", "CORRESPONDENT"]
CURRENCIES = ["DLD", "USD", "EUR"]  # DLD = Dólar de DataLandia
STATUSES = ["APPROVED", "REJECTED", "PENDING", "BLOCKED"]


def generate_transaction(days_back=0):
    """Genera una transacción aleatoria."""
    bank = random.choice(BANK_ENTITIES)
    dest_bank = random.choice(BANK_ENTITIES)
    txn_type = random.choice(TRANSACTION_TYPES)
    channel = random.choice(CHANNELS)

    # Montos con distribución realista
    if txn_type == "WITHDRAWAL":
        amount = round(random.uniform(10, 500), 2)
    elif txn_type == "PAYMENT":
        amount = round(random.uniform(5, 2000), 2)
    elif txn_type == "TRANSFER":
        amount = round(random.lognormvariate(6, 2), 2)
    else:
        amount = round(random.uniform(50, 10000), 2)

    timestamp = datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

    is_fraud = 1 if random.random() < 0.03 else 0  # 3% fraude

    return {
        "transaction_id": str(uuid.uuid4()),
        "bank_entity": bank,
        "customer_id": f"CLI-{random.randint(100000, 999999)}",
        "transaction_type": txn_type,
        "amount": amount,
        "currency": random.choice(CURRENCIES),
        "source_account": f"{bank[:3].upper()}-{random.randint(10000000, 99999999)}",
        "destination_account": f"{dest_bank[:3].upper()}-{random.randint(10000000, 99999999)}",
        "destination_bank": dest_bank,
        "channel": channel,
        "status": "BLOCKED" if is_fraud else random.choices(
            STATUSES[:3], weights=[85, 5, 10]
        )[0],
        "fraud_score": round(random.uniform(0.8, 1.0), 4) if is_fraud else round(random.uniform(0.0, 0.3), 4),
        "latitude": round(random.uniform(4.5, 11.0), 6),
        "longitude": round(random.uniform(-75.0, -67.0), 6),
        "device_id": f"DEV-{random.randint(1000, 9999)}" if channel == "APP" else None,
        "transaction_timestamp": timestamp.isoformat(),
        "branch_id": f"SUC-{bank[:3].upper()}-{random.randint(1, 50):03d}" if channel in ["BRANCH", "ATM", "CORRESPONDENT"] else None,
        "is_fraud": is_fraud,
    }


def send_streaming(url, count):
    """Envía transacciones al endpoint de Cloud Run."""
    print(f"Enviando {count} transacciones a {url}...")
    success = 0
    errors = 0

    for i in range(count):
        txn = generate_transaction()
        try:
            resp = requests.post(
                f"{url}/api/v1/transactions",
                json=txn,
                timeout=10,
            )
            if resp.status_code == 202:
                success += 1
            else:
                errors += 1
                print(f"  Error [{resp.status_code}]: {resp.text}")
        except Exception as e:
            errors += 1
            print(f"  Error de conexión: {e}")

        if (i + 1) % 50 == 0:
            print(f"  Progreso: {i + 1}/{count} (OK: {success}, Err: {errors})")

    print(f"\nResultado: {success} exitosas, {errors} errores de {count} total")


def generate_batch_csv(output_dir, count, days_back=90):
    """Genera archivos CSV para procesamiento batch."""
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, "transactions.csv")
    print(f"Generando {count} transacciones en {filepath}...")

    fieldnames = [
        "transaction_id", "bank_entity", "customer_id", "transaction_type",
        "amount", "currency", "source_account", "destination_account",
        "destination_bank", "channel", "status", "fraud_score",
        "latitude", "longitude", "transaction_timestamp", "branch_id", "is_fraud",
    ]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(count):
            txn = generate_transaction(days_back=days_back)
            row = {k: txn.get(k, "") for k in fieldnames}
            writer.writerow(row)

            if (i + 1) % 5000 == 0:
                print(f"  Progreso: {i + 1}/{count}")

    print(f"Archivo generado: {filepath} ({count} registros)")
    print(f"\nPara subir a GCS:")
    print(f"  gsutil cp {filepath} gs://PROJECT_ID-lumina-raw-landing/historical/transactions/")


def main():
    parser = argparse.ArgumentParser(description="Generador de datos de prueba Lumina Bank")
    parser.add_argument("--mode", choices=["streaming", "batch"], required=True)
    parser.add_argument("--url", help="URL del Cloud Run (para modo streaming)")
    parser.add_argument("--output", default="./test_data", help="Directorio de salida (para modo batch)")
    parser.add_argument("--count", type=int, default=100, help="Número de transacciones")
    parser.add_argument("--days-back", type=int, default=90, help="Días hacia atrás para batch")
    args = parser.parse_args()

    if args.mode == "streaming":
        if not args.url:
            print("Error: --url es requerido para modo streaming")
            return
        send_streaming(args.url, args.count)
    else:
        generate_batch_csv(args.output, args.count, args.days_back)


if __name__ == "__main__":
    main()
