# =============================================================================
# Lumina Bank - Orquestación Principal de Módulos
# =============================================================================

# --- Módulo de Red y Seguridad ---
module "network" {
  source = "./modules/network"

  project_id     = var.project_id
  project_number = var.project_number
  region         = var.region
  labels         = var.labels

  depends_on = [time_sleep.wait_for_apis]
}

# --- Módulo de Ingesta (Fase 1) ---
module "ingestion" {
  source = "./modules/ingestion"

  project_id                   = var.project_id
  project_number               = var.project_number
  region                       = var.region
  zone                         = var.zone
  environment                  = var.environment
  labels                       = var.labels
  pubsub_message_retention     = var.pubsub_message_retention
  pubsub_max_delivery_attempts = var.pubsub_max_delivery_attempts
  batch_schedule_cron          = var.batch_schedule_cron
  vpc_connector_id             = module.network.vpc_connector_id
  network_id                   = module.network.network_id
  subnetwork_id                = module.network.subnetwork_id
  service_account_email        = module.network.service_account_email

  depends_on = [time_sleep.wait_for_apis, module.network]
}

# --- Módulo de Procesamiento (Fase 2) ---
module "processing" {
  source = "./modules/processing"

  project_id              = var.project_id
  project_number          = var.project_number
  region                  = var.region
  zone                    = var.zone
  environment             = var.environment
  labels                  = var.labels
  network_id              = module.network.network_id
  subnetwork_id           = module.network.subnetwork_id
  service_account_email   = module.network.service_account_email
  pubsub_subscription_id  = module.ingestion.streaming_subscription_id
  raw_bucket_name         = module.ingestion.raw_bucket_name
  dataproc_cluster_workers = var.dataproc_cluster_workers
  dataproc_machine_type   = var.dataproc_machine_type
  redis_memory_size_gb    = var.redis_memory_size_gb
  bigtable_num_nodes      = var.bigtable_num_nodes
  batch_schedule_cron     = var.batch_schedule_cron

  depends_on = [time_sleep.wait_for_apis, module.network, module.ingestion]
}

# --- Módulo de Almacenamiento (Fase 3) ---
module "storage" {
  source = "./modules/storage"

  project_id                   = var.project_id
  region                       = var.region
  environment                  = var.environment
  labels                       = var.labels
  bank_entities                = var.bank_entities
  pubsub_message_retention     = var.pubsub_message_retention
  pubsub_max_delivery_attempts = var.pubsub_max_delivery_attempts
  service_account_email        = module.network.service_account_email

  depends_on = [time_sleep.wait_for_apis, module.network]
}

# --- Módulo de Servicio y Consumo (Fase 4) ---
module "serving" {
  source = "./modules/serving"

  project_id            = var.project_id
  project_number        = var.project_number
  region                = var.region
  environment           = var.environment
  labels                = var.labels
  vpc_connector_id      = module.network.vpc_connector_id
  service_account_email = module.network.service_account_email
  bigquery_dataset_id   = module.storage.bigquery_streaming_dataset_id
  bigquery_batch_dataset_id = module.storage.bigquery_batch_dataset_id

  depends_on = [time_sleep.wait_for_apis, module.network, module.storage]
}
