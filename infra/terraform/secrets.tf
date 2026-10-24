# Secrets Manager.
#
# The database password never travels in the task definition: the task reads
# the secret at runtime through the Secrets Manager API, using the permission
# granted in `ecs.tf`.
#
# IMPORTANT AND HONEST: the secret value is built here from a Terraform
# variable, so it ends up in the state file. In a real project the secret is
# created OUTSIDE Terraform (by hand or by a separate bootstrap pipeline), and
# Terraform only references its ARN. That way the state never holds the
# password. Keeping it in Terraform is a deliberate simplification for a
# practice project, and it is exactly the trade-off that gets asked about in
# an interview.

resource "aws_secretsmanager_secret" "database" {
  name = "${local.name_prefix}/database"

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-database" })
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id

  secret_string = jsonencode({
    username = var.database_username
    password = var.database_password
    host     = aws_db_instance.main.endpoint
    port     = aws_db_instance.main.port
    dbname   = var.database_name
  })
}
