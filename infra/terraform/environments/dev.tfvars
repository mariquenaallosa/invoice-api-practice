# Values for the development environment.
#
# This file contains NO secrets. Sensitive values must come from the
# environment as TF_VAR_<name> variables, never from a committed file.

aws_region   = "us-east-1"
environment  = "dev"
project_name = "invoice-api-practice"

container_cpu    = 256
container_memory = 512

tags = {
  Owner = "platform"
}
