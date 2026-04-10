output "network_id" {
  description = "ID de la VPC"
  value       = google_compute_network.lumina_vpc.id
}

output "network_name" {
  description = "Nombre de la VPC"
  value       = google_compute_network.lumina_vpc.name
}

output "subnetwork_id" {
  description = "ID de la subred"
  value       = google_compute_subnetwork.lumina_subnet.id
}

output "subnetwork_name" {
  description = "Nombre de la subred"
  value       = google_compute_subnetwork.lumina_subnet.name
}

output "vpc_connector_id" {
  description = "ID del VPC Access Connector para Cloud Run"
  value       = google_vpc_access_connector.connector.id
}

output "service_account_email" {
  description = "Email del service account principal"
  value       = google_service_account.lumina_sa.email
}
