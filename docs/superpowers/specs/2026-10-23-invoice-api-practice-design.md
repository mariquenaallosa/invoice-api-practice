# Design Spec — invoice-api-practice

- **Fecha:** 2026-10-23
- **Estado:** aprobado por el usuario
- **Tipo:** proyecto nuevo (arquitectónico), no cambio sobre código existente

---

## 1. Propósito

`invoice-api-practice` es una API REST para gestionar facturas. No es un producto: es una pieza de portfolio cuyo objetivo es **permitir practicar y defender decisiones de arquitectura en una entrevista técnica de Full Stack Engineer con foco en Python**.

Criterio de éxito: alguien que no conoce el proyecto debe poder leerlo en cinco minutos, entender qué resuelve, y el autor debe poder defender cada decisión técnica sin recurrir a experiencia laboral inexistente.

## 2. Alcance

### Incluido

- API CRUD parcial sobre facturas: crear, leer por ID, listar con paginación.
- Validación de entrada, restricción de unicidad, códigos HTTP correctos.
- Endpoint `/health` con verificación real de base de datos.
- Manejo global de errores con contrato de respuesta uniforme.
- Tests unitarios y de integración, con gate de cobertura ≥ 80%.
- Imagen Docker, `docker-compose.yml` con Postgres.
- Pipeline de GitHub Actions (lint, test, docker build, terraform validate).
- Terraform declarativo para AWS (ECR + base ECS Fargate). **Nunca aplicado.**

### Fuera de alcance (explícitamente)

- Autenticación / autorización.
- Multi-tenant, usuarios, roles.
- Frontend.
- Integraciones de pago, email, PDF.
- Múltiples monedas con tabla de conversión (el `currency` es un código ISO informative, sin conversión).
- Paginación por cursor (solo offset/limit).
- Alembic como servicio, ni despliegue de la app a AWS.

### Restricciones

- No agregar tecnologías fuera de la lista acordada.
- No inventar experiencia laboral en el README.
- No ejecutar `terraform apply` ni crear recursos de AWS.
- No tocar `openapi/` ni `invoices/` (proyectos vecinos del usuario).

## 3. Decisiones confirmadas

| Decisión | Alternativas descartadas | Motivo |
|---|---|---|
| SQLAlchemy 2 **sync** con psycopg3 | async (psycopg async / asyncpg) | Menos boilerplate, más legible, es lo esperado en la mayoría de entrevistas Python. El async se puede agregar después sin cambiar los contratos. |
| **Alembic** para el esquema | `metadata.create_all()` en el arranque | Versionado real del esquema; `alembic revision --autogenerate` es un tema clásico de entrevista. `create_all` no permite evolucionar datos existentes. |
| **`invoice_number` UNIQUE** | compuesto (email + fecha), idempotency key | Clave de negocio natural; lo que un contador real esperaría. La idempotency key es el patrón correcto para APIs públicas pero suma un concepto a un proyecto que ya tiene mucho. |
| Tests contra **PostgreSQL real** | SQLite en memoria | SQLite no reproduce fielmente `Numeric`, `Enum` ni constraints: un test verde en SQLite puede fallar en Postgres. |
| Dinero en `Numeric(12,2)` / `Decimal` | `float` | `float` acumula error de redondeo en operaciones monetarias. |
| Multi-stage Docker, usuario no-root | imagen simple con root | Requisito de seguridad básico; un contenedor que corre como root es un hallazgo fácil en una entrevista de seguridad. |
| Terraform sin ALB/VPC/NAT | stack completo | Cada componente adicional cuesta plata o abre puertos. La base ECS queda completa y el ALB documentado como siguiente paso. |

## 4. Modelo de dominio

Entidad `Invoice` mapeada con SQLAlchemy 2 declarativo (`Mapped` / `mapped_column`).

| Columna | Tipo SQLAlchemy | Restricciones | Nota |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `invoice_number` | `String(50)` | NOT NULL, UNIQUE, INDEX | Clave de negocio. Índice redundante con el UNIQUE en Postgres, pero explícito para legibilidad. |
| `customer_name` | `String(120)` | NOT NULL | |
| `customer_email` | `String(255)` | NOT NULL | Validado como email en la capa de schemas. |
| `amount` | `Numeric(12, 2)` | NOT NULL, `> 0` | `Decimal`. |
| `currency` | `String(3)` | NOT NULL, default `"USD"` | Código ISO 4217, sin conversión. |
| `status` | `Enum` (nativo=False) | NOT NULL, default `"issued"`, CHECK | Valores: `issued`, `paid`, `void`. `native_enum=False` genera VARCHAR + CHECK, portable y visible en el DDL. |
| `issued_at` | `Date` | NOT NULL | Fecha de emisión. |
| `notes` | `Text` | nullable | |
| `created_at` | `DateTime(timezone=True)` | NOT NULL, server default `now()` | |

**Implicancia conocida:** Pydantic v2 serializa `Decimal` como **string** en JSON (`"1250.50"`), no como número. Es intencional (preserva precisión) y se documenta en el README.

**Implicancia conocida:** `invoice_number` es UNIQUE en el nivel de base, no solo en Python. La deduplicación se apoya en la base, no en una verificación previa sola.

## 5. Arquitectura

### Estructura de directorios

```
app/
├── main.py                  # create_app(), routers, exception handlers, lifespan
├── api/
│   ├── deps.py              # get_db, get_invoice_service
│   └── routes/
│       ├── health.py
│       └── invoices.py
├── core/
│   ├── config.py            # Settings (pydantic-settings)
│   └── errors.py            # excepciones de dominio + contrato de error
├── db/
│   ├── base.py              # Base declarativo + metadata
│   └── session.py           # engine, SessionLocal, get_db
├── models/
│   └── invoice.py
├── schemas/
│   └── invoice.py           # InvoiceCreate, InvoiceRead, InvoiceList
├── repositories/
│   └── invoice.py           # InvoiceRepository
└── services/
    └── invoice.py           # InvoiceService
```

`app/api/routes/__init__.py` y los demás `__init__.py` vacíos, salvo `app/main.py` que expone `app`.

### Flujo de una request

```
HTTP → Router → Service → Repository → Session → PostgreSQL
         │         │          │
      Schema   excepciones  queries
```

- **Router** — solo HTTP: status code, `response_model`, `Depends`. Sin reglas de negocio, sin acceso a la base.
- **Schema** (Pydantic) — `InvoiceCreate` (entrada), `InvoiceRead` (salida), `InvoiceList` (paginación). Valida y serializa.
- **Service** — reglas de negocio: detecta duplicados, distingue 404 de 409, controla la transacción (commit / rollback).
- **Repository** — **todo** acceso a datos: `create`, `get_by_id`, `get_by_number`, `list(limit, offset)`, `count`.
- **Model** — mapeo de tabla. Sin lógica.
- **Core** — configuración y errores.

### Dependencias de FastAPI

- `get_db` — generador con `yield` que hace `session.close()` en el `finally`. El rollback ante excepción se hace en el service.
- `get_invoice_service` — construye `InvoiceService(get_db())` vía `Depends`.

### Configuración

`Settings` con `pydantic-settings`, leído de variables de entorno y de `.env`:

| Variable | Default | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://invoice:invoice@localhost:5433/invoice` | Cadena de conexión SQLAlchemy. |
| `TEST_DATABASE_URL` | `postgresql+psycopg://invoice:invoice@localhost:5433/invoice_test` | Base usada por los tests. |
| `APP_ENV` | `development` | `development` / `test` / `production`. |
| `LOG_LEVEL` | `INFO` | |
| `CORS_ORIGINS` | `[]` | Lista separada por comas. |

La URL se construye por partes en desarrollo y se pasa completa en producción (URL de RDS).

## 6. API

### Endpoints

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| `GET` | `/health` | 200 `{"status":"ok","database":"ok"}` | 503 `{"status":"degraded","database":"unavailable"}` |
| `POST` | `/invoices` | 201 + header `Location` | 409 duplicado, 422 payload inválido |
| `GET` | `/invoices/{invoice_id}` | 200 `InvoiceRead` | 404 |
| `GET` | `/invoices?limit=&offset=` | 200 `InvoiceList` | 422 `limit`/`offset` inválidos |

- `limit`: default 20, mínimo 1, máximo 100.
- `offset`: default 0, mínimo 0.
- `InvoiceList` = `{items: InvoiceRead[], total: int, limit: int, offset: int}`.

`/health` ejecuta un `SELECT 1` real. Si la base no responde, devuelve 503: un health check que reporta "ok" con la base caída es peor que no tener health check.

Sin prefijo de versión (`/v1`). Decisión consciente: mantiene el proyecto chico y la URL de los ejemplos simple. Se documenta como simplificación, no como error.

### Contrato de error

Todas las respuestas de error tienen la misma forma:

```json
{
  "error": {
    "code": "invoice_not_found",
    "message": "Invoice with id 42 was not found.",
    "details": null
  }
}
```

| Código HTTP | `code` | Origen |
|---|---|---|
| 404 | `invoice_not_found` | `InvoiceNotFoundError` (service) |
| 409 | `invoice_duplicate` | `DuplicateInvoiceError` (service) |
| 409 | `invoice_duplicate` | `IntegrityError` (handler, red de seguridad ante carrera) |
| 422 | `validation_error` | `RequestValidationError` (handler) |
| 500 | `internal_error` | `Exception` (handler genérico, sin filtrar internals) |

`core/errors.py` define la jerarquía: `AppError` (base, con `status_code` y `code`) → `InvoiceNotFoundError`, `DuplicateInvoiceError`. `main.py` registra los handlers.

El log de la excepción 500 incluye el traceback en el servidor; la respuesta HTTP no lo expone.

## 7. Docker

### Dockerfile (multi-stage)

1. **Stage `builder`** — `python:3.12-slim`, instala las dependencias con `uv` en un virtualenv, genera wheels.
2. **Stage `runtime`** — `python:3.12-slim`, copia únicamente el virtualenv y el código. Crea un usuario `app` (uid 10001) sin privilegios. `USER app`.
3. `EXPOSE 8000`, `HEALTHCHECK` contra `/health`.
4. `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`.

Ninguna credencial se hornea en la imagen: la configuración llega por variables de entorno en tiempo de ejecución.

### `.dockerignore`

`.git`, `.venv`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.ruff_cache`, `htmlcov`, `.coverage`, `.env`, `tests/`, `docs/`, `infra/`, `.github/`, `odd/`.

### `docker-compose.yml`

Servicio `postgres` (imagen `postgres:16-alpine`, volumen `pgdata`, `healthcheck` con `pg_isready`, puerto host **5433** → 5432). Servicio `api` (`build: .`, `depends_on: postgres: condition: service_healthy`, puerto 8000, variables de entorno).

El puerto 5433 evita conflicto con los contenedores Postgres que ya corren en la máquina del usuario.

## 8. Testing

### Estructura

```
tests/
├── conftest.py          # engine, sesión, limpieza, TestClient, fixtures
├── unit/
│   └── test_invoice_service.py
└── integration/
    ├── test_health.py
    └── test_invoices_api.py
```

- **Unit** — `InvoiceService` con `InvoiceRepository` mockeado (repository fake en memoria). Cubre: duplicado detectado, no encontrado, validaciones de negocio. Sin base de datos.
- **Integration** — API completa contra PostgreSQL real. Cubre: health 200, create 201, get 200, list con paginación, payload inválido 422, duplicado 409, inexistente 404.

### Configuración

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80"
```

- Cobertura medida solo sobre `app/`, no sobre `tests/`.
- `--cov-fail-under=80` → el comando falla si la cobertura baja del 80%.
- Fixtures de sesión con rollback / truncate entre tests para aislamiento.

### Instalación de dependencias

`pyproject.toml` (PEP 621) como fuente de verdad + `uv.lock`. `uv sync` para el entorno de desarrollo. `pip install -e .` también funciona, porque el pyproject tiene metadata PEP 621.

## 9. CI/CD — GitHub Actions

`.github/workflows/ci.yml`, disparado en `push` y `pull_request` contra `main`. Cuatro jobs independientes:

| Job | Pasos |
|---|---|
| `lint` | checkout → setup-python 3.12 → instalar ruff → `ruff check` → `ruff format --check` |
| `test` | checkout → setup-python 3.12 → **servicio postgres** → `alembic upgrade head` → `pytest` con cobertura |
| `docker` | checkout → `docker build` (sin push) |
| `terraform` | checkout → setup-terraform → `terraform fmt -check -recursive` → `terraform init -backend=false` → `terraform validate` |

El job `test` declara un `services.postgres` con `POSTGRES_DB=invoice_test` y `healthcheck` con `pg_isready`, y expone el puerto 5432.

## 10. Terraform

Ruta: `infra/terraform/`.

| Archivo | Contenido |
|---|---|
| `versions.tf` | `required_version >= 1.6.0`, provider `aws ~> 5.0` |
| `providers.tf` | provider `aws` con `region = var.aws_region` |
| `variables.tf` | `aws_region`, `project_name`, `environment` (validación `dev`/`staging`/`prod`), `tags` |
| `ecr.tf` | `aws_ecr_repository` + `aws_ecr_lifecycle_policy` |
| `ecs.tf` | `aws_ecs_cluster`, `aws_ecs_task_definition`, `aws_iam_role` (task execution), `aws_cloudwatch_log_group` |
| `outputs.tf` | URL y ARN del ECR, nombre del cluster, ARN de la task definition, nombre del log group |
| `backend.tf.example` | Backend S3 + DynamoDB, **no aplicado** |
| `README.md` | Instrucciones `init` / `fmt` / `validate` / `plan` y análisis de costo |

**Exclusiones deliberadas:** sin VPC, sin ALB, sin NAT gateway, sin `aws_ecs_service`. El servicio ECS necesita un balanceador y una red con NAT para funcionar de verdad, y eso encarece. Se documenta como siguiente paso.

**Backend remoto:** el archivo real se llama `backend.tf` cuando el usuario decide crearlo. `backend.tf.example` documenta el bloque S3 con `dynamodb_table`. El bucket y la tabla **no se crean automáticamente**.

**Riesgo de costo (si algún día se aplica):** ECR ~USD 0.10 por GB-mes; CloudWatch Logs centavos; **Fargate cobra únicamente mientras haya una task corriendo**. Con el estado de recursos definido, una task detenida cuesta aproximadamente cero. El `terraform plan` debe revisarse siempre antes de un apply.

## 11. Documentación

`README.md` raíz, en español (el lector es el usuario y su audiencia de entrevista), con estas secciones:

1. Qué problema resuelve el proyecto
2. Arquitectura (diagrama de capas y flujo de request)
3. Ejecución local (venv + uv + Postgres vía Docker)
4. Ejecución con Docker Compose
5. Tests y cobertura
6. Swagger / OpenAPI (`/docs`, `/redoc`, `/openapi.json`)
7. Decisiones técnicas (con el "por qué")
8. Qué es práctica personal y qué no es experiencia real
9. Cómo funciona Terraform (y por qué no se aplicó)
10. Qué preguntas de entrevista permite practicar
11. Estructura de directorios

**Honestidad (sección 8):** se distingue explícitamente entre lo que es práctica personal —todo el código de la aplicación, los tests, el Dockerfile— y lo que es práctica de herramientas declarativas: la configuración de Terraform y el workflow de CI, que no implican haber operado infraestructura en producción. No se afirma experiencia laboral que no existe.

## 12. Etapas de implementación

Cada etapa cierra con su validación y un commit independiente (Conventional Commits).

| # | Etapa | Validación de cierre |
|---|---|---|
| 1 | Scaffolding: `pyproject.toml`, `uv.lock`, `.gitignore`, `core/config.py`, `db/base.py`, `db/session.py`, `models/invoice.py`, Alembic inicializado + migración | `alembic upgrade head` crea la tabla · `ruff check` limpio |
| 2 | Schemas, repository, service, `core/errors.py`, `api/deps.py` | Tests unitarios del service verdes |
| 3 | Routers, `main.py`, exception handlers, `/health` | `TestClient` devuelve 201 / 200 / 404 / 409 / 422 |
| 4 | Suite de tests completa + gate de cobertura | `pytest` verde, cobertura ≥ 80% |
| 5 | `Dockerfile`, `.dockerignore`, `docker-compose.yml` | `docker compose up` + `curl` real contra la API |
| 6 | `.github/workflows/ci.yml` | Comandos equivalentes ejecutados en local + YAML validado |
| 7 | `infra/terraform/` completo + README de infra | `terraform fmt -check` + `init -backend=false` + `validate` |
| 8 | README raíz, `.env.example`, tags, cleanup final | README revisado, repo listo para push |

La etapa 1 inicializa el repositorio git, de modo que los commits quedan limpios desde el comienzo.

## 13. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cobertura < 80% y pipeline rojo | La suite de la etapa 4 se escribe junto a la implementación, no después. |
| Tests dependientes de Postgres local | `docker compose up -d postgres` documentado; CI usa service container. |
| Divergencia entre `TEST_DATABASE_URL` y la base real | Variable de entorno explícita y separada; documentada en el README. |
| Serialización de `Decimal` como string confunde a un cliente | Documentado en el README y en la spec del endpoint. |
| Terraform crea recursos con costo | Sin `apply`; análisis de costo en el README de infra. |
| Confundir práctica con experiencia profesional | Sección 8 del README, escrita sin exageraciones. |
