output "streaming_topic_id" {
  description = "ID del tópico Pub/Sub de ingesta"
  value       = google_pubsub_topic.ingestion_streaming.id
}

output "streaming_topic_name" {
  description = "Nombre del tópico Pub/Sub de ingesta"
  value       = google_pubsub_topic.ingestion_streaming.name
}

output "streaming_subscription_id" {
  description = "ID de la suscripción de Dataflow"
  value       = google_pubsub_subscription.ingestion_dataflow.id
}

output "dead_letter_topic_id" {
  description = "ID del dead letter topic"
  value       = google_pubsub_topic.ingestion_dlt.id
}

output "cloud_run_ingestion_url" {
  description = "URL del servicio Cloud Run de ingesta"
  value       = google_cloud_run_v2_service.ingestion_api.uri
}

output "raw_bucket_name" {
  description = "Nombre del bucket raw/landing"
  value       = google_storage_bucket.raw_landing.name
}

output "batch_function_uri" {
  description = "URI de la Cloud Function batch orchestrator"
  value       = google_cloudfunctions2_function.batch_orchestrator.service_config[0].uri
}
