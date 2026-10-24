# invoice-api-practice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una API REST de facturas con FastAPI + PostgreSQL + SQLAlchemy 2 + Docker + CI + Terraform, lista para usar como pieza de portfolio.

**Architecture:** Capas estricto — Router (HTTP) → Service (reglas de negocio) → Repository (acceso a datos) → Model (tabla). Los schemas de Pydantic validan entrada y serializan salida. Las excepciones de dominio viven en `core/errors.py` y se traducen a respuestas HTTP uniformes mediante handlers registrados en `main.py`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 (sync) + psycopg3, Alembic, PostgreSQL 16, pytest + pytest-cov, ruff, Docker, GitHub Actions, Terraform + AWS provider.

**Spec:** `docs/superpowers/specs/2026-10-23-invoice-api-practice-design.md`

---

## Global Constraints

- Python **3.12**. Base de datos **PostgreSQL 16**. Driver **psycopg3** (sync). SQLAlchemy **2.x** con estilo `Mapped`/`mapped_column`.
- Dinero **siempre** `Numeric(12, 2)` / `Decimal`. Prohibido `float` para montos.
- `invoice_number` es la clave **UNIQUE** en la base de datos (no solo en Python).
- Toda respuesta de error usa el contrato `{"error": {"code", "message", "details"}}`.
- Ningún secreto dentro de la imagen Docker. El contenedor corre como usuario no-root.
- **No** se ejecuta `terraform apply`. **No** se crean buckets S3 ni tablas DynamoDB.
- Cobertura mínima **80%**, medida solo sobre `app/`. El pipeline falla si baja.
- Código, comentarios, nombres de test, CI y Terraform en **inglés**. Documentación (README) en **español**.
- Puerto de Postgres en compose: **5433** (host) → 5432 (contenedor).
- Commits por tarea, formato **Conventional Commits**.

## Review Focus

Condiciones que la spec implies pero que ningún test cubre todavía. Cada línea tiene su test en la tarea dueña.

1. **`limit` fuera de rango** (`0`, `101`, `abc`) y **`offset` negativo** → 422 con el contrato de error unificado, no un 422 crudo de FastAPI.
2. **`invoice_number` con espacios o minúsculas** (`" inv-1 "`, `"INV-1"`) → el service normaliza a `strip()` + `upper()`, y `" inv-1 "` colisiona con `"INV-1"` devolviendo **409**, no 201.
3. **`amount` con más de 2 decimales** (`10.999`) o **12+ dígitos enteros** → 422 (Pydantic `condecimal`).
4. **`status` fuera del enum** (`"cancelled"`) → 422; `"issued"`, `"paid"`, `"void"` → 201.
5. **Campos extra no declarados** en el payload (ej. `"total": 99`) → se ignoran silenciosamente (Pydantic `extra="ignore"`), no rompen la creación.

---

## File Structure

| Archivo | Responsabilidad única |
|---|---|
| `app/main.py` | Fábrica de la app: routers, handlers de excepción, lifespan. |
| `app/core/config.py` | Objeto `Settings` (pydantic-settings). |
| `app/core/errors.py` | Jerarquía `AppError` → `InvoiceNotFoundError` / `DuplicateInvoiceError`. |
| `app/db/base.py` | `Base` declarativo. |
| `app/db/session.py` | `engine`, `SessionLocal`, generador `get_db`. |
| `app/models/invoice.py` | Tabla `invoices`. |
| `app/schemas/invoice.py` | `InvoiceCreate`, `InvoiceRead`, `InvoiceList`. |
| `app/repositories/invoice.py` | Queries de `Invoice`. |
| `app/services/invoice.py` | Reglas de negocio y control de transacción. |
| `app/api/deps.py` | `get_db`, `get_invoice_service`. |
| `app/api/routes/health.py` | `GET /health`. |
| `app/api/routes/invoices.py` | `GET/POST /invoices`, `GET /invoices/{id}`. |
| `tests/conftest.py` | Fixtures: engine, sesión, limpieza, `TestClient`. |
| `tests/unit/test_invoice_service.py` | Tests del service con repository fake. |
| `tests/integration/test_health.py` | Test de healthcheck. |
| `tests/integration/test_invoices_api.py` | Tests de la API contra Postgres real. |

---

### Task 1: Scaffolding, configuración, modelo y Alembic

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `app/__init__.py`, `app/core/__init__.py`, `app/core/config.py`, `app/db/__init__.py`, `app/db/base.py`, `app/db/session.py`, `app/models/__init__.py`, `app/models/invoice.py`, `alembic.ini`
- Create: `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_create_invoices.py`
- Test: ninguno (tarea de configuración; se valida con `alembic upgrade head`)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `core.config.Settings` con campos `database_url: str`, `test_database_url: str`, `app_env: str`, `log_level: str`, `cors_origins: list[str]`; instancia módulo-level `settings = Settings()`.
  - `db.base.Base` (declarativo, `DeclarativeBase`).
  - `db.session.engine`, `db.session.SessionLocal`, `db.session.get_db()` (generador).
  - `models.invoice.Invoice` (tabla `invoices`) y `models.invoice.InvoiceStatus` (str enum con `issued`/`paid`/`void`).

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "invoice-api-practice"
version = "0.1.0"
description = "Invoice management API built for full-stack interview practice"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "email-validator>=2.2.0",
    "sqlalchemy>=2.0.36",
    "psycopg[binary]>=3.2.3",
    "alembic>=1.14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "C4", "RUF"]
```

- [ ] **Step 2: Crear `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
.pytest_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/
*.egg-info/
```

- [ ] **Step 3: Crear `.env.example`**

```dotenv
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5433/invoice
TEST_DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5433/invoice_test
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=
```

- [ ] **Step 4: Crear `app/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5433/invoice"
    test_database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5433/invoice_test"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 5: Crear `app/db/base.py` y `app/db/session.py`**

```python
# app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
```

```python
# app/db/session.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Crear `app/models/invoice.py`**

```python
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceStatus(StrEnum):
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('issued', 'paid', 'void')",
            name="ck_invoices_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default="USD"
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, validate_strings=True, length=10),
        nullable=False,
        default=InvoiceStatus.ISSUED,
        server_default=InvoiceStatus.ISSUED.value,
    )
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
```

- [ ] **Step 7: Instalar dependencias y generar el lockfile**

Run: `uv sync --extra dev`
Expected: `.venv` creado, `uv.lock` escrito, sin errores.

- [ ] **Step 8: Inicializar Alembic y crear la migración**

Run: `uv run alembic init -t generic alembic`

Edit `alembic/env.py` para que use la configuración del proyecto:

```python
from app.core.config import settings
from app.db.base import Base
from app.models import invoice  # noqa: F401  (registra el modelo)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

Run: `uv run alembic revision --autogenerate -m "create invoices table"`
Expected: crea `alembic/versions/<hash>_create_invoices_table.py` con `create_table("invoices", ...)`.

- [ ] **Step 9: Aplicar la migración**

Run: `docker run -d --name invoice-practice-pg -e POSTGRES_USER=invoice -e POSTGRES_PASSWORD=invoice -e POSTGRES_DB=invoice -p 5433:5432 postgres:16-alpine`
Then: `uv run alembic upgrade head`
Expected: `Running upgrade -> ... create invoices table`. Verificar con `docker exec invoice-practice-pg psql -U invoice -d invoice -c '\d invoices'`.

- [ ] **Step 10: Lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` / `13 files already formatted`.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml uv.lock .gitignore .env.example app/ alembic/ alembic.ini
git commit -m "feat: scaffold project with config, session, invoice model and alembic"
```

---

### Task 2: Schemas, repository, service, errores y dependencias

**Files:**
- Create: `app/schemas/__init__.py`, `app/schemas/invoice.py`, `app/repositories/__init__.py`, `app/repositories/invoice.py`, `app/services/__init__.py`, `app/services/invoice.py`, `app/api/__init__.py`, `app/api/deps.py`
- Modify: `app/core/errors.py` (crear), `app/core/__init__.py`
- Test: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/test_invoice_service.py`

**Interfaces:**
- Consumes: `models.invoice.Invoice`, `models.invoice.InvoiceStatus`, `db.session.SessionLocal`.
- Produces:
  - `schemas.invoice.InvoiceCreate` — `invoice_number: str`, `customer_name: str`, `customer_email: EmailStr`, `amount: condecimal(gt=0, max_digits=12, decimal_places=2)`, `currency: str = "USD"` (len 3), `status: InvoiceStatus = InvoiceStatus.ISSUED`, `issued_at: date`, `notes: str | None = None`.
  - `schemas.invoice.InvoiceRead` — `model_config = ConfigDict(from_attributes=True)` con `id`, `invoice_number`, `customer_name`, `customer_email`, `amount`, `currency`, `status`, `issued_at`, `notes`, `created_at`.
  - `schemas.invoice.InvoiceList` — `items: list[InvoiceRead]`, `total: int`, `limit: int`, `offset: int`.
  - `core.errors.AppError(status_code, code, message, details=None)`, `InvoiceNotFoundError`, `DuplicateInvoiceError`.
  - `repositories.invoice.InvoiceRepository(session)` con `create(invoice) -> Invoice`, `get_by_id(id) -> Invoice | None`, `get_by_number(number) -> Invoice | None`, `list(limit, offset) -> list[Invoice]`, `count() -> int`.
  - `services.invoice.InvoiceService(repository)` con `create_invoice(payload: InvoiceCreate) -> Invoice`, `get_invoice(invoice_id: int) -> Invoice`, `list_invoices(limit, offset) -> tuple[list[Invoice], int]`.
  - `api.deps.get_db()`, `api.deps.get_invoice_service(session: Session = Depends(get_db)) -> InvoiceService`.

- [ ] **Step 1: Escribir los tests del service**

```python
# tests/unit/test_invoice_service.py
from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import DuplicateInvoiceError, InvoiceNotFoundError
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.invoice import InvoiceCreate
from app.services.invoice import InvoiceService


class FakeInvoiceRepository:
    """In-memory stand-in for InvoiceRepository used in unit tests."""

    def __init__(self) -> None:
        self.invoices: dict[int, Invoice] = {}
        self._next_id = 1

    def create(self, invoice: Invoice) -> Invoice:
        invoice.id = self._next_id
        self._next_id += 1
        self.invoices[invoice.id] = invoice
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.invoices.get(invoice_id)

    def get_by_number(self, invoice_number: str) -> Invoice | None:
        return next(
            (i for i in self.invoices.values() if i.invoice_number == invoice_number),
            None,
        )

    def list(self, limit: int, offset: int) -> list[Invoice]:
        return list(self.invoices.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.invoices)


@pytest.fixture
def repository() -> FakeInvoiceRepository:
    return FakeInvoiceRepository()


@pytest.fixture
def service(repository: FakeInvoiceRepository) -> InvoiceService:
    return InvoiceService(repository)


def make_payload(invoice_number: str = "INV-001") -> InvoiceCreate:
    return InvoiceCreate(
        invoice_number=invoice_number,
        customer_name="Ada Lovelace",
        customer_email="ada@example.com",
        amount=Decimal("1250.50"),
        issued_at=date(2026, 1, 15),
    )


def test_create_invoice_persists_and_returns_invoice(service: InvoiceService) -> None:
    invoice = service.create_invoice(make_payload())

    assert invoice.id is not None
    assert invoice.invoice_number == "INV-001"
    assert invoice.amount == Decimal("1250.50")
    assert invoice.status == InvoiceStatus.ISSUED


def test_create_invoice_normalizes_invoice_number(service: InvoiceService) -> None:
    invoice = service.create_invoice(make_payload("  inv-001  "))

    assert invoice.invoice_number == "INV-001"


def test_create_invoice_raises_on_duplicate_number(service: InvoiceService) -> None:
    service.create_invoice(make_payload("INV-001"))

    with pytest.raises(DuplicateInvoiceError):
        service.create_invoice(make_payload("INV-001"))


def test_create_invoice_raises_on_duplicate_number_case_insensitive(
    service: InvoiceService,
) -> None:
    service.create_invoice(make_payload("INV-001"))

    with pytest.raises(DuplicateInvoiceError):
        service.create_invoice(make_payload("inv-001"))


def test_get_invoice_raises_when_not_found(service: InvoiceService) -> None:
    with pytest.raises(InvoiceNotFoundError):
        service.get_invoice(999)


def test_get_invoice_returns_existing_invoice(service: InvoiceService) -> None:
    created = service.create_invoice(make_payload())

    assert service.get_invoice(created.id).id == created.id


def test_list_invoices_returns_items_and_total(service: InvoiceService) -> None:
    for index in range(3):
        service.create_invoice(make_payload(f"INV-{index:03d}"))

    items, total = service.list_invoices(limit=2, offset=0)

    assert len(items) == 2
    assert total == 3
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `uv run pytest tests/unit/test_invoice_service.py -v --no-cov`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.schemas'`.

- [ ] **Step 3: Crear `app/core/errors.py`**

```python
from typing import Any


class AppError(Exception):
    """Base class for domain errors that map to an HTTP response."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class InvoiceNotFoundError(AppError):
    status_code = 404
    code = "invoice_not_found"

    def __init__(self, invoice_id: int) -> None:
        super().__init__(f"Invoice with id {invoice_id} was not found.")


class DuplicateInvoiceError(AppError):
    status_code = 409
    code = "invoice_duplicate"

    def __init__(self, invoice_number: str) -> None:
        super().__init__(f"Invoice number '{invoice_number}' already exists.")
```

- [ ] **Step 4: Crear `app/schemas/invoice.py`**

```python
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, condecimal

from app.models.invoice import InvoiceStatus

# `condecimal` already returns an Annotated type. Wrapping it in another
# `Annotated[Decimal, ...]` nests the metadata instead of merging it, and
# Pydantic v2 then silently ignores every constraint.
Amount = condecimal(gt=0, max_digits=12, decimal_places=2)


class InvoiceCreate(BaseModel):
    """Payload accepted when creating an invoice."""

    invoice_number: str = Field(min_length=1, max_length=50)
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    amount: Amount
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: InvoiceStatus = InvoiceStatus.ISSUED
    issued_at: date
    notes: str | None = None


class InvoiceRead(BaseModel):
    """Invoice representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    customer_name: str
    customer_email: str
    amount: Decimal
    currency: str
    status: InvoiceStatus
    issued_at: date
    notes: str | None
    created_at: datetime


class InvoiceList(BaseModel):
    """Paginated collection of invoices."""

    items: list[InvoiceRead]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 5: Crear `app/repositories/invoice.py`**

```python
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.invoice import Invoice


class InvoiceRepository:
    """All database access for invoices lives here."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(invoice)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        return self.session.get(Invoice, invoice_id)

    def get_by_number(self, invoice_number: str) -> Invoice | None:
        statement = select(Invoice).where(Invoice.invoice_number == invoice_number)
        return self.session.execute(statement).scalar_one_or_none()

    def list(self, limit: int, offset: int) -> list[Invoice]:
        statement = select(Invoice).order_by(Invoice.id).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all())

    def count(self) -> int:
        statement = select(func.count()).select_from(Invoice)
        return int(self.session.execute(statement).scalar_one())
```

- [ ] **Step 6: Crear `app/services/invoice.py`**

```python
from decimal import Decimal

from app.core.errors import DuplicateInvoiceError, InvoiceNotFoundError
from app.models.invoice import Invoice
from app.repositories.invoice import InvoiceRepository
from app.schemas.invoice import InvoiceCreate


class InvoiceService:
    """Business rules for invoices."""

    def __init__(self, repository: InvoiceRepository) -> None:
        self.repository = repository

    def create_invoice(self, payload: InvoiceCreate) -> Invoice:
        invoice_number = payload.invoice_number.strip().upper()

        if self.repository.get_by_number(invoice_number) is not None:
            raise DuplicateInvoiceError(invoice_number)

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_name=payload.customer_name.strip(),
            customer_email=payload.customer_email,
            amount=Decimal(payload.amount),
            currency=payload.currency.upper(),
            status=payload.status,
            issued_at=payload.issued_at,
            notes=payload.notes,
        )
        return self.repository.create(invoice)

    def get_invoice(self, invoice_id: int) -> Invoice:
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(invoice_id)
        return invoice

    def list_invoices(self, limit: int, offset: int) -> tuple[list[Invoice], int]:
        return self.repository.list(limit=limit, offset=offset), self.repository.count()
```

- [ ] **Step 7: Crear `app/api/deps.py`**

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.invoice import InvoiceRepository
from app.services.invoice import InvoiceService


def get_invoice_service(session: Session = Depends(get_db)) -> InvoiceService:  # noqa: B008
    """Build the invoice service for a request."""
    return InvoiceService(InvoiceRepository(session))
```

- [ ] **Step 8: Correr los tests para verificar que pasan**

Run: `uv run pytest tests/unit/test_invoice_service.py -v --no-cov`
Expected: 7 passed.

- [ ] **Step 9: Lint**

Run: `uv run ruff check . && uv run ruff format .`
Expected: sin errores.

- [ ] **Step 10: Commit**

```bash
git add app/ tests/
git commit -m "feat: add invoice schemas, repository, service and domain errors"
```

---

### Task 3: Routers, aplicación, handlers de error y healthcheck

**Files:**
- Create: `app/api/routes/__init__.py`, `app/api/routes/health.py`, `app/api/routes/invoices.py`, `app/main.py`
- Test: `tests/conftest.py`, `tests/integration/__init__.py`, `tests/integration/test_health.py`, `tests/integration/test_invoices_api.py`

**Interfaces:**
- Consumes: `api.deps.get_invoice_service`, `schemas.invoice.*`, `core.errors.AppError`, `db.session.SessionLocal`.
- Produces: `app.main.app` — instancia `FastAPI` con título "Invoice API", `docs_url="/docs"`, `redoc_url="/redoc"`, lifespan que cierra el engine.

- [ ] **Step 1: Crear `tests/conftest.py`**

```python
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = settings.test_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)


def upgrade_test_database() -> None:
    """Apply the Alembic migrations to the test database.

    Alembic is the only source of truth for the schema: the test database is
    migrated exactly like the application database instead of being built from
    the SQLAlchemy metadata.
    """
    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Generator[None, None, None]:
    upgrade_test_database()
    yield
    engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Session bound to a connection wrapped in an outer transaction.

    Every statement runs inside that outer transaction, so whatever the test
    commits is rolled back when the test ends and tests stay isolated.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_raising(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client that turns unhandled exceptions into HTTP responses."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Escribir los tests de health**

```python
# tests/integration/test_health.py
def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
```

- [ ] **Step 3: Escribir los tests de la API de facturas**

```python
# tests/integration/test_invoices_api.py
from decimal import Decimal

VALID_PAYLOAD = {
    "invoice_number": "INV-001",
    "customer_name": "Ada Lovelace",
    "customer_email": "ada@example.com",
    "amount": "1250.50",
    "currency": "USD",
    "issued_at": "2026-01-15",
}


def test_create_invoice_returns_201(client) -> None:
    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["invoice_number"] == "INV-001"
    assert body["amount"] == "1250.50"
    assert body["status"] == "issued"
    assert response.headers["location"].endswith(f"/invoices/{body['id']}")


def test_create_invoice_returns_409_on_duplicate(client) -> None:
    client.post("/invoices", json=VALID_PAYLOAD)

    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_duplicate"


def test_create_invoice_returns_409_on_duplicate_ignoring_case_and_spaces(client) -> None:
    client.post("/invoices", json=VALID_PAYLOAD)

    response = client.post("/invoices", json={**VALID_PAYLOAD, "invoice_number": " inv-001 "})

    assert response.status_code == 409


def test_create_invoice_returns_422_on_invalid_payload(client) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "amount": "not-a-number"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_invoice_returns_422_on_amount_with_three_decimals(client) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "amount": "10.999"})

    assert response.status_code == 422


def test_create_invoice_returns_422_on_invalid_status(client) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "status": "cancelled"})

    assert response.status_code == 422


def test_create_invoice_ignores_unknown_fields(client) -> None:
    response = client.post("/invoices", json={**VALID_PAYLOAD, "total": 99})

    assert response.status_code == 201


def test_get_invoice_returns_200(client) -> None:
    created = client.post("/invoices", json=VALID_PAYLOAD).json()

    response = client.get(f"/invoices/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_invoice_returns_404_when_not_found(client) -> None:
    response = client.get("/invoices/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invoice_not_found"


def test_list_invoices_returns_paginated_items(client) -> None:
    for index in range(3):
        client.post("/invoices", json={**VALID_PAYLOAD, "invoice_number": f"INV-{index:03d}"})

    response = client.get("/invoices", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_list_invoices_returns_422_on_invalid_limit(client) -> None:
    assert client.get("/invoices", params={"limit": 0}).status_code == 422
    assert client.get("/invoices", params={"limit": 101}).status_code == 422
    assert client.get("/invoices", params={"limit": "abc"}).status_code == 422


def test_list_invoices_returns_422_on_negative_offset(client) -> None:
    assert client.get("/invoices", params={"offset": -1}).status_code == 422
```

- [ ] **Step 4: Correr los tests para verificar que fallan**

Run: `uv run pytest tests/integration -v --no-cov`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 5: Crear `app/api/routes/health.py`**

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> JSONResponse:
    """Report service and database availability."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
```

- [ ] **Step 6: Crear `app/api/routes/invoices.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_invoice_service
from app.schemas.invoice import InvoiceCreate, InvoiceList, InvoiceRead
from app.services.invoice import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InvoiceRead)
def create_invoice(
    payload: InvoiceCreate,
    response: Response,
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceRead:
    """Create an invoice."""
    invoice = service.create_invoice(payload)
    response.headers["Location"] = f"/invoices/{invoice.id}"
    return InvoiceRead.model_validate(invoice)


@router.get("", response_model=InvoiceList)
def list_invoices(
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoiceList:
    """List invoices with simple offset/limit pagination."""
    items, total = service.list_invoices(limit=limit, offset=offset)
    return InvoiceList(
        items=[InvoiceRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceRead:
    """Fetch a single invoice by id."""
    invoice = service.get_invoice(invoice_id)
    return InvoiceRead.model_validate(invoice)
```

- [ ] **Step 7: Crear `app/main.py`**

```python
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import health, invoices
from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, details: object = None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "details": details}}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Invoice API",
        description="Invoice management API built for full-stack interview practice.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(invoices.router)

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                "validation_error", "Request payload failed validation.", details
            ),
        )

    @application.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Integrity error while handling %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload("invoice_duplicate", "Invoice already exists."),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while handling %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_payload("internal_error", "An unexpected error occurred."),
        )

    return application


app = create_app()
```

- [ ] **Step 8: Correr los tests para verificar que pasan**

Run: `uv run pytest tests/integration -v --no-cov`
Expected: todos PASS.

- [ ] **Step 9: Lint y format**

Run: `uv run ruff check . && uv run ruff format .`
Expected: sin errores.

- [ ] **Step 10: Commit**

```bash
git add app/ tests/
git commit -m "feat: add invoice and health routes with global error handling"
```

---

### Task 4: Suite de tests completa y gate de cobertura

**Files:**
- Modify: `tests/conftest.py`, `tests/unit/test_invoice_service.py`
- Test: `tests/unit/test_invoice_service.py`, `tests/integration/test_invoices_api.py`

**Interfaces:**
- Consumes: todo lo producido por Tasks 1–3.
- Produces: suite con cobertura ≥ 80% sobre `app/`.

- [ ] **Step 1: Agregar tests de borde del service**

Agregar a `tests/unit/test_invoice_service.py`:

```python
def test_create_invoice_normalizes_currency(service: InvoiceService) -> None:
    payload = make_payload().model_copy(update={"currency": "usd"})

    assert service.create_invoice(payload).currency == "USD"


def test_list_invoices_applies_offset(service: InvoiceService) -> None:
    for index in range(3):
        service.create_invoice(make_payload(f"INV-{index:03d}"))

    items, total = service.list_invoices(limit=10, offset=2)

    assert len(items) == 1
    assert total == 3
    assert items[0].invoice_number == "INV-002"
```

- [ ] **Step 2: Agregar test del handler de IntegrityError**

Agregar a `tests/integration/test_invoices_api.py`:

```python
def test_create_invoice_returns_409_on_unique_constraint_race(client, monkeypatch) -> None:
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    def boom(*args, **kwargs):
        raise SAIntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr("app.repositories.invoice.InvoiceRepository.create", boom)

    response = client.post("/invoices", json=VALID_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_duplicate"
```

- [ ] **Step 3: Correr la suite completa**

Run: `uv run pytest -v`
Expected: todos PASS y el gate de cobertura activo. Si la cobertura queda en 79%, agregar tests para las líneas sin cubrir que reporte `--cov-report=term-missing` hasta superar 80%.

- [ ] **Step 4: Verificar el gate de cobertura**

Run: `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80`
Expected: exit code 0 y `TOTAL ... ≥ 80%`.
Verificar el gate: `uv run pytest --cov=app --cov-fail-under=99` → debe fallar con exit code 1.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: complete suite and enforce 80 percent coverage gate"
```

---

### Task 5: Docker

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- Modify: nada

**Interfaces:**
- Consumes: `app.main:app`, `pyproject.toml`.
- Produces: imagen `invoice-api-practice:local`, compose con servicios `api` y `postgres`.

- [ ] **Step 1: Crear `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /build/.venv /app/.venv
COPY --chown=app:app app /app/app
COPY --chown=app:app alembic.ini /app/alembic.ini
COPY --chown=app:app alembic /app/alembic

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Crear `.dockerignore`**

```
.git
.gitignore
.venv
__pycache__
*.pyc
*.egg-info
.pytest_cache
.ruff_cache
.coverage
coverage.xml
htmlcov
.env
tests
docs
odd
infra
.github
```

- [ ] **Step 3: Crear `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: invoice
      POSTGRES_PASSWORD: invoice
      POSTGRES_DB: invoice
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U invoice -d invoice"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 5s

  api:
    build:
      context: .
    environment:
      DATABASE_URL: postgresql+psycopg://invoice:invoice@postgres:5432/invoice
      APP_ENV: development
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 4: Levantar el stack y verificar**

Run: `docker compose up -d --build`
Then: `docker compose ps` → ambos servicios `healthy`/`running`.
Then: `curl -fsS http://localhost:8000/health` → `{"status":"ok","database":"ok"}`.

- [ ] **Step 5: Verificar los códigos HTTP contra la API real**

```bash
curl -i -X POST http://localhost:8000/invoices \
  -H 'Content-Type: application/json' \
  -d '{"invoice_number":"INV-001","customer_name":"Ada Lovelace","customer_email":"ada@example.com","amount":"1250.50","issued_at":"2026-01-15"}'
```
Esperado: `HTTP/1.1 201 Created`.

Repetir el mismo POST → `409`. `curl -i http://localhost:8000/invoices/999999` → `404`. `curl -i -X POST ... -d '{"amount": -1}'` → `422`.

- [ ] **Step 6: Verificar que el contenedor corre como no-root**

Run: `docker compose exec api id` → esperado `uid=10001(app) gid=10001(app)`.

- [ ] **Step 7: Verificar que la imagen no contiene secretos ni `.env`**

Run: `docker run --rm invoice-api-practice sh -c "ls -a /app | grep -c '^\.env$' || true"` → esperado `0`.

- [ ] **Step 8: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml
git commit -m "build: add multi-stage Dockerfile and docker compose stack"
```

---

### Task 6: CI con GitHub Actions

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: nada

**Interfaces:**
- Consumes: `pyproject.toml`, `alembic.ini`, `Dockerfile`, `infra/terraform/`.
- Produces: workflow con jobs `lint`, `test`, `docker`, `terraform`.

- [ ] **Step 1: Crear `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

env:
  PYTHON_VERSION: "3.12"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --frozen --extra dev
      - name: Ruff check
        run: uv run ruff check .
      - name: Ruff format check
        run: uv run ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: invoice
          POSTGRES_PASSWORD: invoice
          POSTGRES_DB: invoice_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U invoice -d invoice_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql+psycopg://invoice:invoice@localhost:5432/invoice_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --frozen --extra dev
      - name: Apply migrations
        run: uv run alembic upgrade head
        env:
          DATABASE_URL: postgresql+psycopg://invoice:invoice@localhost:5432/invoice_test
      - name: Run tests with coverage
        run: uv run pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t invoice-api-practice:ci .

  terraform:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: infra/terraform
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.16.2
      - name: Terraform fmt check
        run: terraform fmt -check -recursive
      - name: Terraform init
        run: terraform init -backend=false -input=false
      - name: Terraform validate
        run: terraform validate
```

- [ ] **Step 2: Validar el YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 3: Reproducir localmente los comandos del pipeline**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pytest --cov=app --cov-fail-under=80 && docker build -t invoice-api-practice:ci .`
Expected: todos en verde.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions pipeline for lint, test, docker and terraform"
```

---

### Task 7: Terraform

**Files:**
- Create: `infra/terraform/versions.tf`, `providers.tf`, `variables.tf`, `ecr.tf`, `ecs.tf`, `outputs.tf`, `backend.tf.example`, `README.md`
- Modify: nada

**Interfaces:**
- Consumes: variables `aws_region`, `project_name`, `environment`, `tags`.
- Produces: outputs `ecr_repository_url`, `ecr_repository_arn`, `ecs_cluster_name`, `ecs_task_definition_arn`, `log_group_name`.

- [ ] **Step 1: Crear `versions.tf` y `providers.tf`**

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

```hcl
# providers.tf
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
```

- [ ] **Step 2: Crear `variables.tf` y `locals`**

```hcl
# variables.tf
variable "aws_region" {
  description = "AWS region where the resources are created."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used to prefix resource names."
  type        = string
  default     = "invoice-api-practice"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "tags" {
  description = "Additional tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "container_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 256
}

variable "container_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 512
}
```

```hcl
# locals
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}
```

- [ ] **Step 3: Crear `ecr.tf`**

```hcl
resource "aws_ecr_repository" "app" {
  name                 = local.name_prefix
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 10 images and expire untagged ones after 7 days."
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
```

- [ ] **Step 4: Crear `ecs.tf`**

```hcl
resource "aws_ecs_cluster" "main" {
  name = local.name_prefix

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = local.common_tags
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name_prefix}-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "task_execution" {
  name = "${local.name_prefix}-task-execution"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.app.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer"]
        Resource = "${aws_ecr_repository.app.arn}*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 14

  tags = local.common_tags
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name_prefix
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_execution.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "APP_ENV"
          value = var.environment
        },
        {
          name  = "DATABASE_URL"
          value = "postgresql+psycopg://invoice:invoice@postgres:5432/invoice"
        }
      ]
      healthCheck = {
        command  = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)\""]
        interval = 30
        timeout  = 5
        retries  = 3
        startPeriod = 10
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])

  tags = local.common_tags
}
```

- [ ] **Step 5: Crear `outputs.tf`**

```hcl
output "ecr_repository_url" {
  description = "URL of the ECR repository where the API image is pushed."
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.app.arn
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.main.name
}

output "ecs_task_definition_arn" {
  description = "ARN of the Fargate task definition."
  value       = aws_ecs_task_definition.app.arn
}

output "log_group_name" {
  description = "CloudWatch log group used by the container."
  value       = aws_cloudwatch_log_group.app.name
}
```

- [ ] **Step 6: Crear `backend.tf.example`**

```hcl
terraform {
  backend "s3" {
    bucket       = "REPLACE_ME-your-terraform-state-bucket"
    key          = "invoice-api-practice/dev/terraform.tfstate"
    region       = "us-east-1"
    dynamodb_table = "REPLACE_ME-your-terraform-locks-table"
    encrypt      = true
  }
}
```

- [ ] **Step 7: Crear `infra/terraform/README.md`**

Documentar: propósito del directorio, `terraform init` (local), `terraform fmt`, `terraform validate`, `terraform plan`, cómo habilitar el backend remoto (copiar `backend.tf.example` a `backend.tf` y crear el bucket y la tabla **a mano**), qué recursos crea, y la tabla de riesgo de costo.

- [ ] **Step 8: Formatear y validar**

Run: `cd infra/terraform && terraform fmt -recursive && terraform init -backend=false -input=false && terraform validate`
Expected: `Success! The configuration is valid.`

- [ ] **Step 9: Commit**

```bash
git add infra/
git commit -m "feat: add terraform configuration for ECR and ECS Fargate base"
```

---

### Task 8: README, `.env.example` final y preparación para push

**Files:**
- Create: `README.md`
- Modify: `.gitignore` (agregar `.terraform/`, `*.tfstate*`)

**Interfaces:**
- Consumes: todo lo construido en Tasks 1–7.
- Produces: README completo en español con las 10 secciones acordadas.

- [ ] **Step 1: Escribir `README.md`**

Debe cubrir, con comandos reales y verificados:

1. **Qué problema resuelve** — API de facturas para practicar entrevistas; no es un producto.
2. **Arquitectura** — diagrama ASCII de capas + flujo de request + por qué cada capa existe.
3. **Ejecución local** — `uv sync --extra dev`, `docker compose up -d postgres`, `uv run alembic upgrade head`, `uv run uvicorn app.main:app --reload`.
4. **Ejecución con Docker Compose** — `docker compose up --build`.
5. **Tests** — `uv run pytest`, `uv run pytest --cov=app --cov-report=term-missing`, gate del 80%.
6. **Swagger** — `/docs`, `/redoc`, `/openapi.json`.
7. **Decisiones técnicas** — tabla con la decisión, la alternativa y el porqué (Decimal, UNIQUE en base, sync vs async, Alembic, Postgres real en tests, health con `SELECT 1`, shape de error único).
8. **Qué es práctica personal y qué no** — código de la app, tests y Docker = práctica personal. Terraform y CI = configuración declarativa, **no** experiencia operando infraestructura en producción. Sin afirmaciones de experiencia laboral.
9. **Cómo funciona Terraform** — init/fmt/validate/plan, qué crea, por qué no se aplicó, backend remoto explicado y manual, riesgo de costo.
10. **Qué preguntas de entrevista permite practicar** — lista de 10–12 preguntas tipo con la parte del repo donde está la respuesta.
11. **Estructura de directorios**.

- [ ] **Step 2: Actualizar `.gitignore`**

Agregar al final:

```gitignore
.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl
crash.log
```

- [ ] **Step 3: Verificar que los comandos del README funcionan**

Ejecutar, en orden: `uv sync --extra dev`, `docker compose up -d postgres`, `uv run alembic upgrade head`, `uv run pytest -q`, `docker compose up -d --build`, `curl -fsS http://localhost:8000/health`.
Expected: todos en verde. Si algún comando del README falla, corregir el README (no al revés).

- [ ] **Step 4: Commit final**

```bash
git add README.md .gitignore
git commit -m "docs: add project README with architecture, decisions and interview questions"
```

- [ ] **Step 5: Preparar para push**

Run: `git log --oneline` → 8 commits, uno por tarea.
Run: `git status` → limpio.
Run: `git remote -v` → vacío (el usuario agrega el remoto).

Sugerir tags: `git tag -a v0.1.0 -m "First release of invoice-api-practice"`.

---

## Self-Review

**Spec coverage:**

| Sección de la spec | Tarea |
|---|---|
| 4. Modelo de dominio | Task 1 (model) + Task 2 (schemas) |
| 5. Arquitectura (capas, deps, config) | Tasks 1–3 |
| 6. API (endpoints, errores, health) | Task 3 |
| 7. Docker | Task 5 |
| 8. Testing | Tasks 2–4 |
| 9. CI/CD | Task 6 |
| 10. Terraform | Task 7 |
| 11. Documentación | Task 8 |
| 12. Etapas | Tasks 1–8 |

**Review Focus coverage:**

| # | Test | Tarea |
|---|---|---|
| 1 | `test_list_invoices_returns_422_on_invalid_limit`, `test_list_invoices_returns_422_on_negative_offset` | Task 3 |
| 2 | `test_create_invoice_returns_409_on_duplicate_ignoring_case_and_spaces`, `test_create_invoice_normalizes_invoice_number` | Tasks 2 y 3 |
| 3 | `test_create_invoice_returns_422_on_amount_with_three_decimals` | Task 3 |
| 4 | `test_create_invoice_returns_422_on_invalid_status` | Task 3 |
| 5 | `test_create_invoice_ignores_unknown_fields` | Task 3 |

**Type consistency:** `InvoiceService.create_invoice(payload: InvoiceCreate) -> Invoice`, `get_invoice(invoice_id: int) -> Invoice`, `list_invoices(limit: int, offset: int) -> tuple[list[Invoice], int]` — idénticos en el service, en los routers y en los tests. `InvoiceRepository.create/get_by_id/get_by_number/list/count` — los mismos nombres en el repository real y en `FakeInvoiceRepository`.

**Placeholders:** ninguno. Todos los pasos de código contienen el contenido literal a escribir.
