variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "together_api_key" {
  description = "Together AI API key"
  type        = string
  sensitive   = true
}

variable "firebase_project_id" {
  description = "Firebase project ID for token verification"
  type        = string
}
