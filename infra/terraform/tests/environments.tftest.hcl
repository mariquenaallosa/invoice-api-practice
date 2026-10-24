# Terraform tests, run with `terraform test`.
#
# These run completely offline: `mock_provider` replaces the AWS provider with
# a fake that never makes an API call, so there are no credentials, no AWS
# account and no cost involved. What is verified is the *plan*: the shape of
# the infrastructure and the values that each environment produces.

mock_provider "aws" {
  # The mock provider fills computed attributes with random strings, which do
  # not look like ARNs and are rejected by the ECS validation. These overrides
  # give the mocked resources plausible values.
  override_resource {
    target = aws_iam_role.task_execution

    values = {
      arn = "arn:aws:iam::123456789012:role/mock-task-execution"
    }
  }

  override_resource {
    target = aws_ecs_cluster.main

    values = {
      arn = "arn:aws:ecs:us-east-1:123456789012:cluster/mock-cluster"
    }
  }
}

variables {
  project_name = "invoice-api-practice"
  aws_region   = "us-east-1"
  database_url = "postgresql+psycopg://user:password@database:5432/invoice"
}

run "dev_environment" {
  command = plan

  variables {
    environment = "dev"
  }

  assert {
    condition     = aws_ecr_repository.app.name == "invoice-api-practice-dev"
    error_message = "The ECR repository name must be prefixed with the environment."
  }

  assert {
    condition     = aws_ecs_cluster.main.name == "invoice-api-practice-dev"
    error_message = "The ECS cluster name must be prefixed with the environment."
  }

  assert {
    condition     = aws_cloudwatch_log_group.app.name == "/ecs/invoice-api-practice-dev"
    error_message = "The log group name must be prefixed with the environment."
  }

  assert {
    condition     = aws_ecr_repository.app.image_tag_mutability == "IMMUTABLE"
    error_message = "Image tags must be immutable."
  }
}

# The container definitions depend on a sensitive variable, so they are only
# known after the plan is applied. With `mock_provider` the apply is still
# completely offline: no API call, no credentials, no cost.
run "task_definition_passes_the_database_url" {
  command = apply

  variables {
    environment = "dev"
  }

  assert {
    condition = contains(
      jsondecode(aws_ecs_task_definition.app.container_definitions)[0].environment,
      { name = "DATABASE_URL", value = "postgresql+psycopg://user:password@database:5432/invoice" }
    )
    error_message = "The task definition must pass DATABASE_URL to the container."
  }
}

run "staging_environment" {
  command = plan

  variables {
    environment = "staging"
  }

  assert {
    condition     = aws_ecr_repository.app.name == "invoice-api-practice-staging"
    error_message = "Each environment must get its own ECR repository."
  }

  assert {
    condition     = aws_ecs_cluster.main.name == "invoice-api-practice-staging"
    error_message = "Each environment must get its own ECS cluster."
  }
}

run "prod_environment" {
  command = plan

  variables {
    environment = "prod"
  }

  assert {
    condition     = aws_ecr_repository.app.name == "invoice-api-practice-prod"
    error_message = "Each environment must get its own ECR repository."
  }

  assert {
    condition     = aws_ecs_cluster.main.name == "invoice-api-practice-prod"
    error_message = "Each environment must get its own ECS cluster."
  }
}
