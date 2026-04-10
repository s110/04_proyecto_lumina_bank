# =============================================================================
# Lumina Bank - Módulo de Servicio y Consumo (Fase 4)
# =============================================================================

# --- Artifact Registry para imágenes Docker ---
resource "google_artifact_registry_repository" "lumina_repo" {
  location      = var.region
  project       = var.project_id
  repository_id = "lumina-bank-images"
  format        = "DOCKER"
  description   = "Repositorio de imágenes Docker para Lumina Bank"
  labels        = var.labels
}

# =============================================================================
# Cloud Run: Frontend / BFF (Backend for Frontend)
# =============================================================================

resource "google_cloud_run_v2_service" "frontend_bff" {
  name     = "lumina-frontend-bff"
  project  = var.project_id
  location = var.region
  labels   = var.labels

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "API_BACKEND_URL"
        value = "https://lumina-api-backend-${var.region}.run.app"
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Permitir acceso público al frontend
resource "google_cloud_run_v2_service_iam_member" "frontend_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend_bff.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Cloud Run: API Backend (conectado a BigQuery)
# =============================================================================

resource "google_cloud_run_v2_service" "api_backend" {
  name     = "lumina-api-backend"
  project  = var.project_id
  location = var.region
  labels   = var.labels

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "BQ_DATASET_STREAMING"
        value = var.bigquery_dataset_id
      }

      env {
        name  = "BQ_DATASET_BATCH"
        value = var.bigquery_batch_dataset_id
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# API Backend protegido por IAM (solo el frontend puede invocarlo)
resource "google_cloud_run_v2_service_iam_member" "api_invoker_sa" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api_backend.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}

# =============================================================================
# Vertex AI: Endpoint para modelos de fraude y scoring
# =============================================================================

resource "google_vertex_ai_endpoint" "fraud_endpoint" {
  name         = "lumina-fraud-detection-endpoint"
  display_name = "Lumina Bank - Fraud Detection Endpoint"
  project      = var.project_id
  location     = var.region
  labels       = var.labels
}

resource "google_vertex_ai_endpoint" "liquidity_endpoint" {
  name         = "lumina-liquidity-forecast-endpoint"
  display_name = "Lumina Bank - Liquidity Forecast Endpoint"
  project      = var.project_id
  location     = var.region
  labels       = var.labels
}
