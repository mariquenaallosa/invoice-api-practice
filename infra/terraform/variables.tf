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

variable "image_tag" {
  description = <<-EOT
    Tag of the image the task runs. The ECR repository is IMMUTABLE, so the
    tag has to change on every deployment: reusing one would be rejected by
    the registry. In a real pipeline this is the git SHA of the commit, passed
    with `-var image_tag=$(git rev-parse --short HEAD)`.
  EOT
  type        = string
  default     = "latest"
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones used for the public and private subnets."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks of the public subnets, one per availability zone."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks of the private subnets, one per availability zone."
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "app_port" {
  description = "Port the API listens on inside the container."
  type        = number
  default     = 8000
}

variable "service_desired_count" {
  description = "Number of tasks the ECS service keeps running."
  type        = number
  default     = 1
}

variable "rds_instance_class" {
  description = "Instance class of the PostgreSQL instance."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  description = "Storage of the PostgreSQL instance, in GiB."
  type        = number
  default     = 20
}

variable "rds_engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16"
}

variable "database_name" {
  description = "Name of the application database."
  type        = string
  default     = "invoice"
}

variable "database_username" {
  description = "User of the application database."
  type        = string
  default     = "invoice"
}

variable "database_password" {
  description = <<-EOT
    Password of the application database. Sensitive, with no default: it must
    arrive through TF_VAR_database_password and never from a committed file.

    It is used to build the Secrets Manager secret. Terraform stores it in the
    state file, which is the known limitation this project documents.
  EOT
  type        = string
  sensitive   = true
}
