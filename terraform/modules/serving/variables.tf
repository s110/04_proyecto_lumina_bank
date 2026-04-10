variable "project_id" {
  type = string
}

variable "project_number" {
  type = string
}

variable "region" {
  type = string
}

variable "environment" {
  type = string
}

variable "labels" {
  type = map(string)
}

variable "vpc_connector_id" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "bigquery_dataset_id" {
  type = string
}

variable "bigquery_batch_dataset_id" {
  type = string
}
