# =============================================================================
# Lumina Bank - Módulo de Almacenamiento (Fase 3)
# =============================================================================

# =============================================================================
# PUB/SUB FAN-OUT: Distribución a 12 entidades bancarias
# =============================================================================

# --- Dead Letter Topic para distribución ---
resource "google_pubsub_topic" "distribution_dlt" {
  name    = "lumina-distribution-dead-letter"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = var.pubsub_message_retention
}

resource "google_pubsub_subscription" "distribution_dlt_sub" {
  name    = "lumina-distribution-dlt-subscription"
  project = var.project_id
  topic   = google_pubsub_topic.distribution_dlt.id

  message_retention_duration = var.pubsub_message_retention
  retain_acked_messages      = true
  ack_deadline_seconds       = 60

  expiration_policy {
    ttl = ""
  }
}

# --- Tópico principal de distribución ---
resource "google_pubsub_topic" "distribution" {
  name    = "lumina-transactions-distribution"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = var.pubsub_message_retention
}

# --- 12 Suscripciones independientes (una por entidad bancaria) ---
resource "google_pubsub_subscription" "bank_entity" {
  for_each = toset(var.bank_entities)

  name    = "lumina-sub-${each.value}"
  project = var.project_id
  topic   = google_pubsub_topic.distribution.id

  message_retention_duration = var.pubsub_message_retention
  retain_acked_messages      = false
  ack_deadline_seconds       = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.distribution_dlt.id
    max_delivery_attempts = var.pubsub_max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Filtro por atributo de entidad bancaria
  filter = "attributes.bank_entity = \"${each.value}\""

  expiration_policy {
    ttl = ""
  }
}

# =============================================================================
# BIGQUERY: Data Warehouse
# =============================================================================

# --- Dataset Streaming ---
resource "google_bigquery_dataset" "streaming" {
  dataset_id    = "lumina_streaming"
  project       = var.project_id
  location      = var.region
  friendly_name = "Lumina Bank - Streaming Data"
  description   = "Dataset para datos en tiempo real: transacciones, KPIs, reportes y productos de datos"
  labels        = var.labels

  default_table_expiration_ms = null

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }

  access {
    role          = "WRITER"
    user_by_email = var.service_account_email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

# Tabla: Transacciones
resource "google_bigquery_table" "transactions" {
  dataset_id          = google_bigquery_dataset.streaming.dataset_id
  table_id            = "transactions"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "transaction_timestamp"
  }

  clustering = ["bank_entity", "transaction_type", "status"]

  schema = jsonencode([
    { name = "transaction_id", type = "STRING", mode = "REQUIRED", description = "ID único de la transacción" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED", description = "Entidad bancaria origen" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "ID del cliente" },
    { name = "transaction_type", type = "STRING", mode = "REQUIRED", description = "Tipo: TRANSFER, PAYMENT, WITHDRAWAL, DEPOSIT" },
    { name = "amount", type = "NUMERIC", mode = "REQUIRED", description = "Monto de la transacción" },
    { name = "currency", type = "STRING", mode = "REQUIRED", description = "Moneda ISO 4217" },
    { name = "source_account", type = "STRING", mode = "NULLABLE", description = "Cuenta origen" },
    { name = "destination_account", type = "STRING", mode = "NULLABLE", description = "Cuenta destino" },
    { name = "destination_bank", type = "STRING", mode = "NULLABLE", description = "Banco destino" },
    { name = "channel", type = "STRING", mode = "REQUIRED", description = "Canal: APP, ATM, BRANCH, CORRESPONDENT" },
    { name = "status", type = "STRING", mode = "REQUIRED", description = "Estado: APPROVED, REJECTED, PENDING, BLOCKED" },
    { name = "fraud_score", type = "FLOAT64", mode = "NULLABLE", description = "Score de fraude de Vertex AI (0.0 - 1.0)" },
    { name = "latitude", type = "FLOAT64", mode = "NULLABLE", description = "Latitud de la transacción" },
    { name = "longitude", type = "FLOAT64", mode = "NULLABLE", description = "Longitud de la transacción" },
    { name = "device_id", type = "STRING", mode = "NULLABLE", description = "ID del dispositivo" },
    { name = "transaction_timestamp", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp de la transacción" },
    { name = "processing_timestamp", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp de procesamiento" },
    { name = "metadata", type = "JSON", mode = "NULLABLE", description = "Metadatos adicionales" },
  ])
}

# Tabla: KPIs en tiempo real
resource "google_bigquery_table" "kpis" {
  dataset_id          = google_bigquery_dataset.streaming.dataset_id
  table_id            = "kpis_realtime"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "HOUR"
    field = "window_start"
  }

  schema = jsonencode([
    { name = "kpi_id", type = "STRING", mode = "REQUIRED" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED" },
    { name = "kpi_name", type = "STRING", mode = "REQUIRED", description = "Nombre del KPI: TPS, avg_latency, fraud_rate, approval_rate" },
    { name = "kpi_value", type = "FLOAT64", mode = "REQUIRED" },
    { name = "window_start", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "window_end", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "dimensions", type = "JSON", mode = "NULLABLE" },
  ])
}

# Tabla: Reportes consolidados
resource "google_bigquery_table" "reports" {
  dataset_id          = google_bigquery_dataset.streaming.dataset_id
  table_id            = "reports"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "report_date"
  }

  schema = jsonencode([
    { name = "report_id", type = "STRING", mode = "REQUIRED" },
    { name = "report_type", type = "STRING", mode = "REQUIRED" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED" },
    { name = "report_date", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "total_transactions", type = "INT64", mode = "NULLABLE" },
    { name = "total_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "fraud_blocked_count", type = "INT64", mode = "NULLABLE" },
    { name = "fraud_blocked_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "avg_processing_time_ms", type = "FLOAT64", mode = "NULLABLE" },
    { name = "details", type = "JSON", mode = "NULLABLE" },
  ])
}

# Tabla: Productos de datos
resource "google_bigquery_table" "data_products" {
  dataset_id          = google_bigquery_dataset.streaming.dataset_id
  table_id            = "data_products"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  schema = jsonencode([
    { name = "product_id", type = "STRING", mode = "REQUIRED" },
    { name = "product_name", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED" },
    { name = "recommendation_score", type = "FLOAT64", mode = "NULLABLE" },
    { name = "product_type", type = "STRING", mode = "REQUIRED", description = "MICRO_CREDIT, SAVINGS, INSURANCE, INVESTMENT" },
    { name = "generated_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "features", type = "JSON", mode = "NULLABLE" },
  ])
}

# --- Dataset Batch ---
resource "google_bigquery_dataset" "batch" {
  dataset_id    = "lumina_batch"
  project       = var.project_id
  location      = var.region
  friendly_name = "Lumina Bank - Batch Analytics"
  description   = "Dataset batch: pronósticos de liquidez, tasas de interés, tipos de cambio"
  labels        = var.labels

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }

  access {
    role          = "WRITER"
    user_by_email = var.service_account_email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

# Tabla: Pronóstico de liquidez por entidad
resource "google_bigquery_table" "liquidity_forecast" {
  dataset_id          = google_bigquery_dataset.batch.dataset_id
  table_id            = "liquidity_forecast"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "forecast_date"
  }

  schema = jsonencode([
    { name = "forecast_id", type = "STRING", mode = "REQUIRED" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED" },
    { name = "forecast_date", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "predicted_inflow", type = "NUMERIC", mode = "REQUIRED" },
    { name = "predicted_outflow", type = "NUMERIC", mode = "REQUIRED" },
    { name = "net_liquidity", type = "NUMERIC", mode = "REQUIRED" },
    { name = "confidence_interval_lower", type = "NUMERIC", mode = "NULLABLE" },
    { name = "confidence_interval_upper", type = "NUMERIC", mode = "NULLABLE" },
    { name = "model_version", type = "STRING", mode = "NULLABLE" },
    { name = "is_holiday", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "is_payday", type = "BOOLEAN", mode = "NULLABLE" },
  ])
}

# Tabla: Tasas de interés por país
resource "google_bigquery_table" "interest_rates" {
  dataset_id          = google_bigquery_dataset.batch.dataset_id
  table_id            = "interest_rates"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  schema = jsonencode([
    { name = "rate_id", type = "STRING", mode = "REQUIRED" },
    { name = "country_code", type = "STRING", mode = "REQUIRED" },
    { name = "rate_type", type = "STRING", mode = "REQUIRED", description = "LENDING, SAVINGS, MORTGAGE, INTERBANK" },
    { name = "rate_value", type = "FLOAT64", mode = "REQUIRED" },
    { name = "effective_date", type = "DATE", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
  ])
}

# Tabla: Tipos de cambio
resource "google_bigquery_table" "exchange_rates" {
  dataset_id          = google_bigquery_dataset.batch.dataset_id
  table_id            = "exchange_rates"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  schema = jsonencode([
    { name = "pair_id", type = "STRING", mode = "REQUIRED" },
    { name = "base_currency", type = "STRING", mode = "REQUIRED" },
    { name = "quote_currency", type = "STRING", mode = "REQUIRED" },
    { name = "rate", type = "FLOAT64", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
  ])
}

# Tabla: Métricas de volumen por sucursal/cajero
resource "google_bigquery_table" "branch_volume_metrics" {
  dataset_id          = google_bigquery_dataset.batch.dataset_id
  table_id            = "branch_volume_metrics"
  project             = var.project_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "metric_date"
  }

  schema = jsonencode([
    { name = "metric_id", type = "STRING", mode = "REQUIRED" },
    { name = "bank_entity", type = "STRING", mode = "REQUIRED" },
    { name = "branch_id", type = "STRING", mode = "REQUIRED" },
    { name = "channel_type", type = "STRING", mode = "REQUIRED", description = "ATM, BRANCH, CORRESPONDENT" },
    { name = "metric_date", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "total_transactions", type = "INT64", mode = "REQUIRED" },
    { name = "total_amount", type = "NUMERIC", mode = "REQUIRED" },
    { name = "avg_wait_time_minutes", type = "FLOAT64", mode = "NULLABLE" },
    { name = "utilization_rate", type = "FLOAT64", mode = "NULLABLE" },
    { name = "peak_hour", type = "INT64", mode = "NULLABLE" },
  ])
}

# =============================================================================
# DATA LAKE: Cloud Storage
# =============================================================================

resource "google_storage_bucket" "datalake" {
  name          = "${var.project_id}-lumina-datalake"
  project       = var.project_id
  location      = var.region
  force_destroy = true
  labels        = var.labels

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

# Carpetas lógicas en el data lake
resource "google_storage_bucket_object" "datalake_folders" {
  for_each = toset([
    "historical/transactions/",
    "historical/accounts/",
    "historical/balances/",
    "market_data/interest_rates/",
    "market_data/exchange_rates/",
    "models/fraud_detection/",
    "models/liquidity_forecast/",
  ])

  name    = each.value
  bucket  = google_storage_bucket.datalake.name
  content = " "
}
