output "dataproc_cluster_name" {
  description = "Nombre del clúster Dataproc"
  value       = google_dataproc_cluster.batch_cluster.name
}

output "redis_host" {
  description = "Host de Redis"
  value       = google_redis_instance.cache.host
}

output "redis_port" {
  description = "Puerto de Redis"
  value       = google_redis_instance.cache.port
}

output "bigtable_instance_id" {
  description = "ID de la instancia Bigtable"
  value       = google_bigtable_instance.user_profiles.name
}

output "dataflow_staging_bucket" {
  description = "Bucket staging de Dataflow"
  value       = google_storage_bucket.dataflow_staging.name
}

output "dataflow_temp_bucket" {
  description = "Bucket temp de Dataflow"
  value       = google_storage_bucket.dataflow_temp.name
}

output "spark_scripts_bucket" {
  description = "Bucket para scripts de Spark"
  value       = google_storage_bucket.spark_scripts.name
}

output "vertex_ai_dataset_id" {
  description = "ID del dataset de Vertex AI"
  value       = google_vertex_ai_dataset.fraud_dataset.name
}
