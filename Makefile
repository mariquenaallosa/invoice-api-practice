# Comandos frecuentes del proyecto.
#
# `make help` lista todo lo disponible.

.DEFAULT_GOAL := help
.PHONY: help install up down logs migrate test test-unit test-integration coverage lint fmt check emulator emulator-down tf-validate tf-test tf-plan build

help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala las dependencias (uv sync --extra dev)
	uv sync --extra dev

up: ## Levanta la base de datos y aplica las migraciones
	docker compose up -d postgres
	uv run alembic upgrade head

down: ## Apaga los servicios
	docker compose down

logs: ## Muestra los logs de la API
	docker compose logs -f api

migrate: ## Aplica las migraciones
	uv run alembic upgrade head

test: ## Corre toda la suite
	uv run pytest

test-unit: ## Corre solo los tests unitarios (no necesitan base de datos)
	uv run pytest tests/unit -v --no-cov

test-integration: ## Corre solo los tests de integración (necesitan la base)
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

emulator: ## Levanta el emulador de AWS (Floci)
	docker compose --profile aws-emulator up -d floci

emulator-down: ## Apaga el emulador
	docker compose --profile aws-emulator down

tf-validate: ## Valida la configuración de Terraform
	cd infra/terraform && terraform fmt -check -recursive && terraform validate

tf-test: ## Corre los tests de Terraform (offline, sin credenciales)
	cd infra/terraform && terraform test

tf-plan: ## Muestra el plan de Terraform (contra el emulador, si está levantado)
	cd infra/terraform && terraform plan -var-file=environments/dev.tfvars
