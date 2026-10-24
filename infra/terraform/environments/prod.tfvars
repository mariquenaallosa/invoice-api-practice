# Values for the production environment.
#
# This file contains NO secrets. Sensitive values must come from the
# environment as TF_VAR_<name> variables, never from a committed file.
#
# Note that this environment is the most expensive one: the task size below
# is what drives the Fargate bill. See the cost section in the README.

aws_region   = "us-east-1"
environment  = "prod"
project_name = "invoice-api-practice"

container_cpu    = 512
container_memory = 1024

tags = {
  Owner       = "platform"
  CostCenter  = "engineering"
  Compliance  = "required"
  Environment = "production"
}
