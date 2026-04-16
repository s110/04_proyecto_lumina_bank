# =============================================================================
# Lumina Bank - Módulo de Procesamiento (Fase 2)
# =============================================================================

# =============================================================================
# FLUJO STREAMING
# =============================================================================

# --- Bucket para templates y staging de Dataflow ---
resource "google_storage_bucket" "dataflow_staging" {
  name          = "${var.project_id}-lumina-dataflow-staging"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "dataflow_temp" {
  name          = "${var.project_id}-lumina-dataflow-temp"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true
}

# --- Cloud Dataflow: Job de streaming ---
# NOTA: El job de Dataflow se despliega via gcloud/script, aquí se define el
# bucket de staging y la configuración. El job real usa un template Flex o
# se lanza con el script Python de Apache Beam.

# --- Cloud Memorystore (Redis): Cache de baja latencia ---
resource "google_redis_instance" "cache" {
  name               = "lumina-redis-cache"
  project            = var.project_id
  region             = var.region
  tier               = "BASIC"
  memory_size_gb     = var.redis_memory_size_gb
  authorized_network = var.network_id
  redis_version      = "REDIS_7_0"
  display_name       = "Lumina Bank - Redis Cache"
  labels             = var.labels

  connect_mode = "PRIVATE_SERVICE_ACCESS"
}

# --- Cloud Bigtable: Perfiles de usuario de baja latencia ---
resource "google_bigtable_instance" "user_profiles" {
  name                = "lumina-user-profiles"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  cluster {
    cluster_id   = "lumina-bigtable-cluster"
    zone         = var.zone
    num_nodes    = var.bigtable_num_nodes
    storage_type = "SSD"
  }
}

resource "google_bigtable_table" "user_profiles" {
  name          = "user_profiles"
  instance_name = google_bigtable_instance.user_profiles.name
  project       = var.project_id

  column_family {
    family = "personal_info"
  }

  column_family {
    family = "financial_data"
  }

  column_family {
    family = "risk_score"
  }

  column_family {
    family = "transaction_history"
  }
}

resource "google_bigtable_table" "fraud_signals" {
  name          = "fraud_signals"
  instance_name = google_bigtable_instance.user_profiles.name
  project       = var.project_id

  column_family {
    family = "signals"
  }

  column_family {
    family = "scores"
  }
}

# =============================================================================
# FLUJO BATCH
# =============================================================================

# --- Bucket para scripts de Spark ---
resource "google_storage_bucket" "spark_scripts" {
  name          = "${var.project_id}-lumina-spark-scripts"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true
}

# --- Cloud Dataproc: Clúster batch ---
resource "google_dataproc_cluster" "batch_cluster" {
  name    = "lumina-batch-cluster"
  project = var.project_id
  region  = var.region
  labels  = var.labels

  cluster_config {
    staging_bucket = google_storage_bucket.spark_scripts.name

    master_config {
      num_instances = 1
      machine_type  = var.dataproc_machine_type

      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 50
      }
    }

    worker_config {
      num_instances = var.dataproc_cluster_workers
      machine_type  = var.dataproc_machine_type

      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 50
      }
    }

    software_config {
      image_version = "2.1-debian11"

      override_properties = {
        "spark:spark.jars.packages" = "com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.36.1"
        "spark:spark.dynamicAllocation.enabled" = "true"
      }
    }

    gce_cluster_config {
      subnetwork = var.subnetwork_id
      tags       = ["dataproc-node"]

      service_account        = var.service_account_email
      service_account_scopes = ["cloud-platform"]

      internal_ip_only = false

      shielded_instance_config {
        enable_secure_boot = true
      }
    }

  }
}

# =============================================================================
# VERTEX AI: Feature Store y Modelo de Fraude
# =============================================================================

# --- Vertex AI: Dataset para entrenamiento ---
resource "google_vertex_ai_dataset" "fraud_dataset" {
  display_name        = "lumina-fraud-detection-dataset"
  project             = var.project_id
  region              = var.region
  metadata_schema_uri = "gs://google-cloud-aiplatform/schema/dataset/metadata/tabular_1.0.0.yaml"
  labels              = var.labels
}
