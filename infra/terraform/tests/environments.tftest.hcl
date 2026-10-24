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

  override_resource {
    target = aws_db_instance.main

    values = {
      endpoint = "mock-db.abcdefg.us-east-1.rds.amazonaws.com"
      address  = "mock-db.abcdefg.us-east-1.rds.amazonaws.com"
      arn      = "arn:aws:rds:us-east-1:123456789012:db:mock-db"
      id       = "mock-db"
    }
  }

  override_resource {
    target = aws_lb.main

    values = {
      arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/mock-alb/0123456789abcdef"
    }
  }

  override_resource {
    target = aws_lb_target_group.api

    values = {
      arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/mock-api/0123456789abcdef"
    }
  }
}

variables {
  project_name      = "invoice-api-practice"
  aws_region        = "us-east-1"
  database_password = "not-a-real-password"
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

  assert {
    condition     = aws_db_instance.main.identifier == "invoice-api-practice-dev-db"
    error_message = "The database identifier must be prefixed with the environment."
  }

  assert {
    condition     = aws_db_instance.main.publicly_accessible == false
    error_message = "The database must not be reachable from the internet."
  }

  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_subnet.private) == 2
    error_message = "The VPC needs one public and one private subnet per availability zone."
  }

  assert {
    condition     = aws_ecs_service.api.desired_count == 1
    error_message = "The service must keep one task running."
  }
}

# The container definitions depend on a sensitive value, so they are only known
# after the plan is applied. With `mock_provider` the apply is still completely
# offline: no API call, no credentials, no cost.
run "task_definition_reads_the_secret_instead_of_the_password" {
  command = apply

  variables {
    environment = "dev"
  }

  assert {
    condition = contains(
      jsondecode(aws_ecs_task_definition.app.container_definitions)[0].secrets,
      { name = "DATABASE_SECRET", valueFrom = aws_secretsmanager_secret.database.arn }
    )
    error_message = "The task definition must read the database secret from Secrets Manager."
  }

  assert {
    condition = !strcontains(
      jsonencode(jsondecode(aws_ecs_task_definition.app.container_definitions)),
      "not-a-real-password"
    )
    error_message = "The database password must never appear in the task definition."
  }

  assert {
    condition     = aws_secretsmanager_secret.database.name == "invoice-api-practice-dev/database"
    error_message = "The secret name must be prefixed with the environment."
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
    condition     = aws_db_instance.main.identifier == "invoice-api-practice-prod-db"
    error_message = "Each environment must get its own database."
  }
}
