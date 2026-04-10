# =============================================================================
# Lumina Bank - Provider Configuration
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Habilitar las APIs necesarias de GCP
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudfunctions.googleapis.com",
    "composer.googleapis.com",
    "storage.googleapis.com",
    "dataflow.googleapis.com",
    "dataproc.googleapis.com",
    "redis.googleapis.com",
    "bigtable.googleapis.com",
    "bigtableadmin.googleapis.com",
    "bigquery.googleapis.com",
    "aiplatform.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Esperar a que las APIs se propaguen en GCP antes de crear recursos
resource "time_sleep" "wait_for_apis" {
  depends_on      = [google_project_service.apis]
  create_duration = "60s"
}
