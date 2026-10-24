# Feature: invoice-api-practice

Tracking interno del orquestador (ODD). El diseño vive en `docs/superpowers/specs/` y el plan ejecutable en `docs/superpowers/plans/`.

## Objective

API REST de facturas que sirva como pieza de portfolio para practicar y defender decisiones de arquitectura en una entrevista técnica de Full Stack Engineer con foco en Python.

## Problem

El usuario ya tiene un practice project de FastAPI (`openapi/`, fuera de este repo) con almacenamiento en memoria, sin capas, sin base de datos, sin Docker, sin tests y sin CI. Ese proyecto demuestra que sabe la sintaxis, pero no que sabe diseñar. En una entrevista, la diferencia entre "sé usar FastAPI" y "sé construir un servicio" está en las decisiones: dónde vive la lógica, cómo se manejan los errores, cómo se testea, cómo se despliega.

Este proyecto cubre esa diferencia con un dominio acotado (facturas) que permite mostrar el camino completo sin agregar complejidad artificial.

## Why now

El usuario está en una etapa de capacitación (`~/Documentos/capacitaciones/`) y quiere un repositorio publicable en GitHub que sirva como carta de presentación técnica.

## Scope

**Incluido:** API de facturas (crear / leer por ID / listar paginado), validación, restricción UNIQUE, contrato de error uniforme, `/health`, tests unitarios e de integración con gate de cobertura, Dockerfile multi-stage no-root, docker-compose con Postgres, GitHub Actions, Terraform para AWS (ECR + base ECS Fargate), README completo.

**Excluido:** autenticación, autorización, multi-tenant, frontend, pagos/email/PDF, conversión de moneda, prefijo de versión de API, VPC/ALB/NAT en Terraform, y **cualquier `terraform apply`**.

## Constraints

- Python 3.12, SQLAlchemy 2 sync + psycopg3, Alembic, PostgreSQL 16.
- Dinero en `Numeric(12,2)` / `Decimal`. Prohibido `float` para montos.
- `invoice_number` UNIQUE a nivel de base de datos.
- Toda respuesta de error: `{"error": {"code", "message", "details"}}`.
- Contenedor sin root, sin secretos en la imagen.
- Cobertura ≥ 80% sobre `app/`; el pipeline falla si baja.
- Código/CI/Terraform en inglés; documentación en español.
- No tocar `openapi/` ni `invoices/`.
- No crear recursos de AWS.

## Accepted decisions

| Decision | Choice | Rejected alternative |
|---|---|---|
| Driver | SQLAlchemy 2 **sync** + psycopg3 | async (psycopg async / asyncpg) |
| Esquema | **Alembic** | `metadata.create_all()` |
| Anti-duplicado | **`invoice_number` UNIQUE** | compuesto email+fecha, idempotency key |
| Base de tests | **PostgreSQL real** | SQLite en memoria |
| Dinero | **`Numeric(12,2)`** | `float` |
| Normalización | `invoice_number` → `strip()` + `upper()` | case-sensitive |
| Terraform | ECR + ECS cluster/task def/role/log group | stack completo con ALB/VPC/NAT |

## Routes

| Task | Route | Trigger evidence |
|---|---|---|
| 1 | inline | Archivos nuevos de configuración, sin diseño pendiente. Escritura mecánica y ya entendida. |
| 2 | delegated (writer) | 7 archivos no triviales (schemas, repository, service, errors, deps) → dispara *writer trigger*. |
| 3 | delegated (writer) | 4 archivos + 2 suites de tests → dispara *writer trigger*. |
| 4 | inline | Ajuste de suite y verificación de cobertura; sin archivos nuevos de producción. |
| 5 | inline | Dockerfile + compose: mechanical, sin diseño pendiente. |
| 6 | inline | Workflow YAML: mechanical. |
| 7 | delegated (writer) | 7 archivos Terraform con contratos entre ellos → *writer trigger*. |
| 8 | inline | README + `.gitignore`. |

## Tasks

- [x] **T1 — Spec y plan escritos y commiteados.** Acceptance: spec en `docs/superpowers/specs/`, plan en `docs/superpowers/plans/`, commit `docs:`.
- [ ] **T2 — Scaffolding, config, modelo, Alembic.** Acceptance: `alembic upgrade head` crea la tabla `invoices`; `ruff check` limpio.
- [ ] **T3 — Schemas, repository, service, errors, deps.** Acceptance: tests unitarios del service verdes.
- [ ] **T4 — Routers, main, handlers, health.** Acceptance: `TestClient` devuelve 201 / 200 / 404 / 409 / 422.
- [ ] **T5 — Suite completa + gate de cobertura.** Acceptance: `pytest` verde y cobertura ≥ 80%; `--cov-fail-under=99` falla.
- [ ] **T6 — Docker.** Acceptance: `docker compose up --build` levanta api + postgres; `curl /health` responde 200; el contenedor corre como uid 10001.
- [ ] **T7 — CI.** Acceptance: YAML válido; los mismos comandos del pipeline pasan en local.
- [ ] **T8 — Terraform.** Acceptance: `terraform fmt -check`, `init -backend=false` y `validate` en verde.
- [ ] **T9 — README y preparación para push.** Acceptance: los comandos del README se ejecutan y pasan; repo limpio, 9 commits.

## Checks

| Check | Comando | Etapa |
|---|---|---|
| Lint | `uv run ruff check . && uv run ruff format --check .` | T2–T9 |
| Unit | `uv run pytest tests/unit -v --no-cov` | T3 |
| Integration | `uv run pytest tests/integration -v --no-cov` | T4 |
| Coverage | `uv run pytest --cov=app --cov-fail-under=80` | T5 |
| Container | `docker compose up -d --build && curl -fsS localhost:8000/health` | T6 |
| Terraform | `terraform fmt -check -recursive && terraform init -backend=false && terraform validate` | T8 |

## Progress

| Task | Estado | Commit | Notas |
|---|---|---|---|
| T1 | done | `d1c3893` | Spec + plan |
| T2 | done | `5fa4b4c`, `94d033d` | Bug del enum `ISSUED`/`issued` corregido antes de migrar. Python pineado a 3.12 con `.python-version` (uv elegía 3.13). |
| T3 | done | `418ff25` | **Bug del plan corregido**: `Annotated[Decimal, condecimal(...)]` anidado descartaba TODAS las constraints en silencio. Verificado empíricamente. El repository ahora hace rollback en IntegrityError. |
| T4 | done | `2bccfe6` | Routers + `main.py` + handlers globales + `/health`. Dos bugs de CI encontrados: `httpx2` faltaba en dev extras (Starlette 1.9 lo exige) y `alembic/env.py` pisaba la URL del conftest → ahora solo usa settings si no le pasan ninguna. |
| T5 | done | `394fb36` | 35 tests, **100% cobertura**. Gate verificado que corta (exit 1 con umbral 90%). El harness necesitó `join_transaction_mode="create_savepoint"` para que `session.rollback()` se comportara como en producción. Smoke test real con uvicorn: 201+Location, 409, 409 normalizado, 200, 404, 422, paginado, 422 en `limit=0`, `/docs` + `/redoc` + `/openapi.json` OK. |
| T6 | pending | | |
| T7 | pending | | |
| T8 | pending | | |
| T9 | pending | | |

## Next step

Ejecutar T2 (scaffolding, configuración, modelo SQLAlchemy y migración inicial de Alembic).

## Open questions

Ninguna. Todas las decisiones ambiguas fueron resueltas y documentadas arriba.
