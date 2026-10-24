# Comandos frecuentes del proyecto.
#
# `make help` lista todo lo disponible.
#
# Hay dos ambientes y no se mezclan:
#
#   development  base de datos local y la API corriendo en tu máquina o en
#                contenedores. Sin Terraform.
#
#   staging      el emulador de AWS (Floci) con la infraestructura de
#                Terraform aplicada encima. La base de datos es el RDS
#                emulado, no el Postgres local.

.DEFAULT_GOAL := help
.PHONY: help install dev dev-down dev-logs dev-migrate \
        staging staging-down staging-plan staging-apply staging-image staging-deploy staging-verify \
        test test-unit test-integration coverage lint fmt check build tf-validate tf-test

help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Instala las dependencias (uv sync --extra dev)
	uv sync --extra dev

# ------------------------------------------------------------------ development

dev: ## DEVELOPMENT: levanta la base local y aplica las migraciones
	docker compose up -d postgres
	uv run alembic upgrade head
	@echo ""
	@echo "Base de datos local en localhost:5433."
	@echo "Para correr la API: make dev-api"

dev-api: ## DEVELOPMENT: corre la API en local con recarga
	uv run uvicorn app.main:app --reload --port 8010

dev-down: ## DEVELOPMENT: apaga la base de datos local
	docker compose down

dev-logs: ## DEVELOPMENT: logs de la API en contenedores
	docker compose logs -f api

dev-migrate: ## DEVELOPMENT: aplica las migraciones en la base local
	uv run alembic upgrade head

# --------------------------------------------------------------------- staging
#
# Each environment keeps its own state file. Without that, applying staging
# would destroy the dev resources: Terraform compares the code against the
# state, and the resource names contain the environment.
#
# In a real setup this is the same idea with a different mechanism: one state
# per environment, in a different key of the S3 backend.

staging: ## STAGING: levanta el emulador de AWS
	docker compose --profile aws-emulator up -d floci

staging-down: ## STAGING: apaga el emulador y borra su estado
	docker compose --profile aws-emulator down -v

staging-init: ## STAGING: inicializa Terraform con el state de staging
	cd infra/terraform && terraform init -reconfigure \
		-backend-config="path=floci.staging.tfstate" -input=false

staging-plan: ## STAGING: muestra el plan de Terraform contra el emulador
	cd infra/terraform && terraform plan -var-file=environments/staging.tfvars

staging-apply: ## STAGING: aplica la infraestructura de Terraform en el emulador
	cd infra/terraform && terraform apply -auto-approve -var-file=environments/staging.tfvars

staging-image: ## STAGING: publica la imagen en el ECR emulado
	docker buildx build \
		--output type=image,name=localhost:5100/000000000000/us-east-1/invoice-api-practice-staging:$$(git rev-parse --short HEAD),compression=gzip,oci-mediatypes=false,push=true \
		.

staging-deploy: ## STAGING: publica la imagen y actualiza el service
	$(MAKE) staging-image
	cd infra/terraform && terraform apply -auto-approve -var-file=environments/staging.tfvars \
		-var image_tag=$$(git rev-parse --short HEAD)

staging-verify: ## STAGING: muestra el estado de las tasks del service
	aws ecs list-tasks --cluster invoice-api-practice-staging --service-name invoice-api-practice-staging-api

# ---------------------------------------------------------------------- checks

test: ## Corre toda la suite (necesita la base local)
	uv run pytest

test-unit: ## Corre solo los tests unitarios (no necesitan base de datos)
	uv run pytest tests/unit -v --no-cov

test-integration: ## Corre solo los tests de integración (necesitan la base local)
	uv run pytest tests/integration -v --no-cov

coverage: ## Corre la suite con el reporte de cobertura
	uv run pytest --cov=app --cov-report=term-missing --cov-report=xml

lint: ## Revisa el estilo con ruff
	uv run ruff check .

fmt: ## Formatea el código
	uv run ruff format .

check: ## Corre lint, tests y validación de Terraform
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest
	cd infra/terraform && terraform fmt -check -recursive && terraform validate

build: ## Construye la imagen Docker
	docker build -t invoice-api-practice:local .

tf-validate: ## Valida la configuración de Terraform
	cd infra/terraform && terraform fmt -check -recursive && terraform validate

tf-test: ## Corre los tests de Terraform (offline, sin credenciales)
	cd infra/terraform && terraform test
