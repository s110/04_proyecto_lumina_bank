# =============================================================================
# Lumina Bank - Módulo de Ingesta (Fase 1)
# =============================================================================

# =============================================================================
# FLUJO STREAMING
# =============================================================================

# --- Pub/Sub: Dead Letter Topic ---
resource "google_pubsub_topic" "ingestion_dlt" {
  name    = "lumina-ingestion-dead-letter"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = var.pubsub_message_retention
}

resource "google_pubsub_subscription" "ingestion_dlt_sub" {
  name    = "lumina-ingestion-dlt-subscription"
  project = var.project_id
  topic   = google_pubsub_topic.ingestion_dlt.id

  message_retention_duration = var.pubsub_message_retention
  retain_acked_messages      = true
  ack_deadline_seconds       = 60

  expiration_policy {
    ttl = ""
  }
}

# --- Pub/Sub: Tópico principal de ingesta streaming ---
resource "google_pubsub_topic" "ingestion_streaming" {
  name    = "lumina-transactions-ingestion"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = var.pubsub_message_retention
}

# --- Pub/Sub: Suscripción para Dataflow ---
resource "google_pubsub_subscription" "ingestion_dataflow" {
  name    = "lumina-ingestion-dataflow-subscription"
  project = var.project_id
  topic   = google_pubsub_topic.ingestion_streaming.id

  message_retention_duration = var.pubsub_message_retention
  retain_acked_messages      = false
  ack_deadline_seconds       = 120

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.ingestion_dlt.id
    max_delivery_attempts = var.pubsub_max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""
  }
}

# --- IAM: Permitir que Pub/Sub publique al DLT ---
resource "google_pubsub_topic_iam_member" "dlt_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.ingestion_dlt.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dlt_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.ingestion_dataflow.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# --- Cloud Run: Microservicio de Ingesta ---
resource "google_cloud_run_v2_service" "ingestion_api" {
  name     = "lumina-ingestion-api"
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
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.ingestion_streaming.id
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
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

# Permitir invocación pública (las 12 entidades envían datos)
resource "google_cloud_run_v2_service_iam_member" "ingestion_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.ingestion_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# FLUJO BATCH
# =============================================================================

# --- Cloud Storage: Bucket Raw/Landing ---
resource "google_storage_bucket" "raw_landing" {
  name          = "${var.project_id}-lumina-raw-landing"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# --- Cloud Storage: Bucket para código de Cloud Function ---
resource "google_storage_bucket" "functions_source" {
  name          = "${var.project_id}-lumina-functions-source"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true
}

# --- Cloud Function: Orquestador batch (reemplaza Composer por costo) ---
resource "google_storage_bucket_object" "function_source" {
  name   = "batch-orchestrator/function-source.zip"
  bucket = google_storage_bucket.functions_source.name
  source = "${path.root}/scripts/cloud_function/function-source.zip"
}

resource "google_cloudfunctions2_function" "batch_orchestrator" {
  name     = "lumina-batch-orchestrator"
  project  = var.project_id
  location = var.region
  labels   = var.labels

  build_config {
    runtime     = "python312"
    entry_point = "orchestrate_batch"

    source {
      storage_source {
        bucket = google_storage_bucket.functions_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "512Mi"
    timeout_seconds       = 540
    service_account_email = var.service_account_email

    environment_variables = {
      PROJECT_ID       = var.project_id
      RAW_BUCKET       = google_storage_bucket.raw_landing.name
      REGION           = var.region
      DATAPROC_CLUSTER = "lumina-batch-cluster"
    }
  }
}

# --- Cloud Scheduler: Cron diario a las 2 AM ---
resource "google_cloud_scheduler_job" "batch_trigger" {
  name      = "lumina-batch-daily-trigger"
  project   = var.project_id
  region    = var.region
  schedule  = var.batch_schedule_cron
  time_zone = "America/Bogota"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.batch_orchestrator.service_config[0].uri

    oidc_token {
      service_account_email = var.service_account_email
    }
  }
}
