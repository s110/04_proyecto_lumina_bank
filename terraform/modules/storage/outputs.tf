output "distribution_topic_id" {
  description = "ID del tópico de distribución fan-out"
  value       = google_pubsub_topic.distribution.id
}

output "distribution_topic_name" {
  description = "Nombre del tópico de distribución"
  value       = google_pubsub_topic.distribution.name
}

output "bank_subscription_ids" {
  description = "IDs de las suscripciones por entidad bancaria"
  value       = { for k, v in google_pubsub_subscription.bank_entity : k => v.id }
}

output "bigquery_streaming_dataset_id" {
  description = "ID del dataset streaming de BigQuery"
  value       = google_bigquery_dataset.streaming.dataset_id
}

output "bigquery_batch_dataset_id" {
  description = "ID del dataset batch de BigQuery"
  value       = google_bigquery_dataset.batch.dataset_id
}

output "datalake_bucket_name" {
  description = "Nombre del bucket del data lake"
  value       = google_storage_bucket.datalake.name
}
