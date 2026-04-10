# =============================================================================
# Lumina Bank - Variables Globales
# =============================================================================

variable "project_id" {
  description = "ID del proyecto GCP"
  type        = string
  default     = "project-413a2817-068f-425d-b1d"
}

variable "project_number" {
  description = "Número del proyecto GCP"
  type        = string
  default     = "251068454544"
}

variable "project_name" {
  description = "Nombre del proyecto"
  type        = string
  default     = "LuminaBank"
}

variable "region" {
  description = "Región principal de despliegue"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona principal de despliegue"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Ambiente de despliegue (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "bank_entities" {
  description = "Lista de las 12 entidades bancarias de DataLandia"
  type        = list(string)
  default = [
    "banco-central-datalandia",
    "banco-norte-metropolitano",
    "banco-sur-cooperativo",
    "banco-este-comercial",
    "banco-oeste-industrial",
    "banco-union-popular",
    "banco-progreso-digital",
    "banco-herencia-nacional",
    "banco-innovacion-fintech",
    "banco-solidario-regional",
    "banco-mercantil-datalandia",
    "banco-federal-integrado"
  ]
}

variable "pubsub_message_retention" {
  description = "Retención de mensajes en Pub/Sub (en segundos). 31 días = 2678400s"
  type        = string
  default     = "2678400s"
}

variable "pubsub_max_delivery_attempts" {
  description = "Intentos máximos de entrega antes de enviar al dead-letter topic"
  type        = number
  default     = 5
}

variable "dataproc_cluster_workers" {
  description = "Número de workers en el clúster Dataproc"
  type        = number
  default     = 2
}

variable "dataproc_machine_type" {
  description = "Tipo de máquina para nodos Dataproc"
  type        = string
  default     = "n1-standard-4"
}

variable "redis_memory_size_gb" {
  description = "Tamaño de memoria para Memorystore Redis (GB)"
  type        = number
  default     = 1
}

variable "bigtable_num_nodes" {
  description = "Número de nodos para Cloud Bigtable"
  type        = number
  default     = 1
}

variable "batch_schedule_cron" {
  description = "Expresión cron para el procesamiento batch diario (2 AM)"
  type        = string
  default     = "0 2 * * *"
}

variable "labels" {
  description = "Labels comunes para todos los recursos"
  type        = map(string)
  default = {
    project     = "lumina-bank"
    managed_by  = "terraform"
    environment = "dev"
  }
}
