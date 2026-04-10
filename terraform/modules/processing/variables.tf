variable "project_id" {
  type = string
}

variable "project_number" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "environment" {
  type = string
}

variable "labels" {
  type = map(string)
}

variable "network_id" {
  type = string
}

variable "subnetwork_id" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "pubsub_subscription_id" {
  type = string
}

variable "raw_bucket_name" {
  type = string
}

variable "dataproc_cluster_workers" {
  type = number
}

variable "dataproc_machine_type" {
  type = string
}

variable "redis_memory_size_gb" {
  type = number
}

variable "bigtable_num_nodes" {
  type = number
}

variable "batch_schedule_cron" {
  type = string
}
