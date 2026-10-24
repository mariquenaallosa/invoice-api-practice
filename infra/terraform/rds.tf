# Managed PostgreSQL.
#
# The instance lives in the private subnets and is not publicly accessible:
# only the security group of the tasks can reach it.

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-db" })
}

resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-db"

  engine         = "postgres"
  engine_version = var.rds_engine_version
  instance_class = var.rds_instance_class

  allocated_storage = var.rds_allocated_storage
  storage_type      = "gp2"
  storage_encrypted = true

  db_name  = var.database_name
  username = var.database_username
  password = var.database_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  # The database is disposable: the schema is recreated by the migrations.
  skip_final_snapshot = true
  deletion_protection = false

  backup_retention_period = 0

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-db" })
}
