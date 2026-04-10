variable "project_id" {
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

variable "bank_entities" {
  type = list(string)
}

variable "pubsub_message_retention" {
  type = string
}

variable "pubsub_max_delivery_attempts" {
  type = number
}

variable "service_account_email" {
  type = string
}
