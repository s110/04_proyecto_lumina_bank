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

variable "pubsub_message_retention" {
  type = string
}

variable "pubsub_max_delivery_attempts" {
  type = number
}

variable "batch_schedule_cron" {
  type = string
}

variable "vpc_connector_id" {
  type = string
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
