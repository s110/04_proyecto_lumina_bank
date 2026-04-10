# =============================================================================
# Lumina Bank - Outputs Globales
# =============================================================================

# --- Red ---
output "network_id" {
  description = "ID de la VPC"
  value       = module.network.network_id
}

output "service_account_email" {
  description = "Service account principal"
  value       = module.network.service_account_email
}

# --- Ingesta ---
output "ingestion_pubsub_topic" {
  description = "Tópico Pub/Sub de ingesta streaming"
  value       = module.ingestion.streaming_topic_id
}

output "cloud_run_ingestion_url" {
  description = "URL del servicio Cloud Run de ingesta"
  value       = module.ingestion.cloud_run_ingestion_url
}

output "raw_bucket_name" {
  description = "Bucket GCS de landing/raw"
  value       = module.ingestion.raw_bucket_name
}

# --- Procesamiento ---
output "dataproc_cluster_name" {
  description = "Nombre del clúster Dataproc"
  value       = module.processing.dataproc_cluster_name
}

output "redis_host" {
  description = "Host de Memorystore Redis"
  value       = module.processing.redis_host
}

output "bigtable_instance_id" {
  description = "ID de la instancia Bigtable"
  value       = module.processing.bigtable_instance_id
}

# --- Almacenamiento ---
output "bigquery_streaming_dataset" {
  description = "Dataset de BigQuery para streaming"
  value       = module.storage.bigquery_streaming_dataset_id
}

output "bigquery_batch_dataset" {
  description = "Dataset de BigQuery para batch"
  value       = module.storage.bigquery_batch_dataset_id
}

output "distribution_topic_id" {
  description = "Tópico Pub/Sub de distribución fan-out"
  value       = module.storage.distribution_topic_id
}

output "datalake_bucket_name" {
  description = "Bucket del Data Lake"
  value       = module.storage.datalake_bucket_name
}

# --- Servicio ---
output "cloud_run_frontend_url" {
  description = "URL del frontend/BFF Cloud Run"
  value       = module.serving.cloud_run_frontend_url
}

output "cloud_run_api_url" {
  description = "URL del API backend Cloud Run"
  value       = module.serving.cloud_run_api_url
}
