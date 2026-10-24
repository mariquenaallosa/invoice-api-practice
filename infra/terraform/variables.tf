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
  description = <<-EOT
    Deployment environment. This variable has NO default on purpose: making it
    required means a `terraform plan` without an explicit value fails instead
    of silently targeting the development environment.
  EOT
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "database_url" {
  description = <<-EOT
    Connection string handed to the container. It is marked sensitive and has
    NO default on purpose: it must arrive through TF_VAR_database_url (a CI
    secret, Secrets Manager, or a local environment variable) and never from a
    committed tfvars file.

    Note that Terraform still stores variable values in the state file in
    clear text. That is a known limitation of the tool, and the reason why a
    production setup would read the secret from Secrets Manager inside the
    task definition instead of passing it as a variable.
  EOT
  type        = string
  sensitive   = true
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
