"""
Lumina Bank - Cloud Function: Orquestador Batch
================================================
Se ejecuta diariamente a las 2 AM via Cloud Scheduler.
Conecta a sistemas legacy, extrae datos, los descomprime
y los deposita en Cloud Storage (Raw/Landing).
Luego lanza el job de Dataproc.
"""

import os
import json
import logging
import functions_framework
from datetime import datetime

from google.cloud import storage, dataproc_v1

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID")
RAW_BUCKET = os.environ.get("RAW_BUCKET")
REGION = os.environ.get("REGION", "us-central1")
DATAPROC_CLUSTER = os.environ.get("DATAPROC_CLUSTER", "lumina-batch-cluster")


@functions_framework.http
def orchestrate_batch(request):
    """Orquesta el flujo batch diario de Lumina Bank."""
    execution_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    logger.info(f"Iniciando ejecución batch: {execution_id}")

    try:
        # Paso 1: Simular extracción de 12 bancos legacy
        extracted_files = extract_from_legacy_systems(execution_id)
        logger.info(
            f"Archivos extraídos de sistemas legacy: {len(extracted_files)}"
        )

        # Paso 2: Subir a GCS (Raw/Landing)
        upload_to_gcs(extracted_files, execution_id)

        # Paso 3: Lanzar job de Dataproc
        job_id = submit_dataproc_job(execution_id)

        return json.dumps({
            "status": "SUCCESS",
            "execution_id": execution_id,
            "files_processed": len(extracted_files),
            "dataproc_job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
        }), 200

    except Exception as e:
        logger.error(f"Error en ejecución batch: {e}")
        return json.dumps({
            "status": "ERROR",
            "execution_id": execution_id,
            "error": str(e),
        }), 500


def extract_from_legacy_systems(execution_id):
    """
    Simula la extracción de datos de los 12 sistemas bancarios legacy.
    En producción, se conectaría vía SFTP/API a cada banco.
    """
    bank_entities = [
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

    files = []
    for bank in bank_entities:
        # Simulación de datos extraídos (cierres bancarios)
        data = {
            "bank_entity": bank,
            "extraction_date": datetime.utcnow().isoformat(),
            "execution_id": execution_id,
            "records_type": "daily_close",
            "accounts_summary": {
                "total_accounts": 750000,
                "active_accounts": 680000,
                "total_balance": 15000000000.00,
            },
            "transactions_summary": {
                "total_count": 125000,
                "total_amount": 890000000.00,
            },
        }
        files.append({
            "bank": bank,
            "filename": f"{bank}/daily_close_{execution_id}.json",
            "data": json.dumps(data),
        })

    return files


def upload_to_gcs(files, execution_id):
    """Sube los archivos extraídos al bucket Raw/Landing."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(RAW_BUCKET)

    for file_info in files:
        blob_path = f"batch/{execution_id}/{file_info['filename']}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_info["data"], content_type="application/json")
        logger.info(f"Archivo subido: gs://{RAW_BUCKET}/{blob_path}")


def submit_dataproc_job(execution_id):
    """Envía un job de PySpark al clúster Dataproc."""
    client = dataproc_v1.JobControllerClient(
        client_options={
            "api_endpoint": f"{REGION}-dataproc.googleapis.com:443"
        }
    )

    job = {
        "placement": {"cluster_name": DATAPROC_CLUSTER},
        "pyspark_job": {
            "main_python_file_uri": (
                f"gs://{PROJECT_ID}-lumina-spark-scripts"
                f"/scripts/batch_processing.py"
            ),
            "args": [
                f"--project_id={PROJECT_ID}",
                f"--raw_bucket=gs://{RAW_BUCKET}",
                "--bq_dataset=lumina_batch",
                "--lookback_days=90",
            ],
            "properties": {
                "spark.executor.memory": "4g",
                "spark.executor.cores": "2",
                "spark.dynamicAllocation.enabled": "true",
            },
        },
        "labels": {
            "execution_id": execution_id,
            "pipeline": "lumina-batch",
        },
    }

    operation = client.submit_job_as_operation(
        request={
            "project_id": PROJECT_ID,
            "region": REGION,
            "job": job,
        }
    )

    logger.info(f"Job Dataproc enviado: {operation.metadata.job_id}")
    return operation.metadata.job_id
