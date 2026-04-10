output "cloud_run_frontend_url" {
  description = "URL del servicio frontend/BFF"
  value       = google_cloud_run_v2_service.frontend_bff.uri
}

output "cloud_run_api_url" {
  description = "URL del API backend"
  value       = google_cloud_run_v2_service.api_backend.uri
}

output "artifact_registry_url" {
  description = "URL del Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.lumina_repo.repository_id}"
}

output "fraud_endpoint_id" {
  description = "ID del endpoint de detección de fraude"
  value       = google_vertex_ai_endpoint.fraud_endpoint.name
}

output "liquidity_endpoint_id" {
  description = "ID del endpoint de pronóstico de liquidez"
  value       = google_vertex_ai_endpoint.liquidity_endpoint.name
}
