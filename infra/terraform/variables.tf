variable "aws_region" {
  description = "AWS region where the resources are created."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used to prefix resource names."
  type        = string
  default     = "invoice-api-practice"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "tags" {
  description = "Additional tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "container_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 256
}

variable "container_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 512
}
