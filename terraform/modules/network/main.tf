# =============================================================================
# Lumina Bank - Módulo de Red y Seguridad
# =============================================================================

# --- VPC ---
resource "google_compute_network" "lumina_vpc" {
  name                    = "lumina-bank-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
}

# --- Subred principal ---
resource "google_compute_subnetwork" "lumina_subnet" {
  name          = "lumina-bank-subnet"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.lumina_vpc.id
  ip_cidr_range = "10.0.0.0/20"

  secondary_ip_range {
    range_name    = "pods-range"
    ip_cidr_range = "10.4.0.0/14"
  }

  secondary_ip_range {
    range_name    = "services-range"
    ip_cidr_range = "10.8.0.0/20"
  }

  private_ip_google_access = true
}

# --- Subred para servicios gestionados (Redis, etc.) ---
resource "google_compute_global_address" "private_ip_range" {
  name          = "lumina-private-ip-range"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.lumina_vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.lumina_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# --- Firewall: permitir tráfico interno ---
resource "google_compute_firewall" "allow_internal" {
  name    = "lumina-allow-internal"
  project = var.project_id
  network = google_compute_network.lumina_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8"]
}

# --- Firewall: permitir SSH para Dataproc ---
resource "google_compute_firewall" "allow_ssh" {
  name    = "lumina-allow-ssh"
  project = var.project_id
  network = google_compute_network.lumina_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["dataproc-node"]
}

# --- VPC Connector para Cloud Run ---
resource "google_vpc_access_connector" "connector" {
  name    = "lumina-vpc-connector"
  project = var.project_id
  region  = var.region

  subnet {
    name = google_compute_subnetwork.lumina_subnet.name
  }

  min_instances = 2
  max_instances = 3
  machine_type  = "e2-micro"
}

# --- Cloud NAT (para que recursos privados accedan a internet) ---
resource "google_compute_router" "router" {
  name    = "lumina-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.lumina_vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "lumina-nat"
  project                            = var.project_id
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# =============================================================================
# Service Account Principal
# =============================================================================

resource "google_service_account" "lumina_sa" {
  account_id   = "lumina-bank-sa"
  display_name = "Lumina Bank Service Account"
  project      = var.project_id
}

# Roles amplios para el trial de 90 días (progress over perfection)
locals {
  sa_roles = [
    "roles/editor",
    "roles/pubsub.admin",
    "roles/bigquery.admin",
    "roles/storage.admin",
    "roles/dataflow.admin",
    "roles/dataproc.admin",
    "roles/bigtable.admin",
    "roles/redis.admin",
    "roles/run.admin",
    "roles/aiplatform.admin",
    "roles/composer.admin",
    "roles/cloudfunctions.admin",
    "roles/iam.serviceAccountUser",
    "roles/iam.serviceAccountTokenCreator",
    "roles/cloudscheduler.admin",
    "roles/logging.admin",
    "roles/monitoring.admin",
  ]
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset(local.sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.lumina_sa.email}"
}
