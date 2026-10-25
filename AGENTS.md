# AGENTS.md

Instructions for AI coding agents working on this repository.

## What this project is

`invoice-api-practice` is an invoice management API built as a portfolio piece
for full-stack interview practice. It is not a client project and it is not in
production. Read `README.md` first, and `docs/terraform-guide.md` before
touching anything under `infra/terraform/`.

## Environment

- Python 3.12 (pinned in `.python-version`), dependencies managed with `uv`.
- Docker for PostgreSQL and for the AWS emulator.
- Terraform 1.16 for the infrastructure under `infra/terraform/`.

```bash
make install      # uv sync --extra dev
make dev          # local PostgreSQL + migrations
make dev-api      # run the API on port 8010
make check        # lint + unit tests + terraform validation (no database needed)
make check-all    # the above plus integration tests (needs the database)
make help         # every available target
```

Always run commands through `make` when a target exists, or through `uv run`
for Python tools. Never install packages with plain `pip` into the project
venv.

## Architecture rules

These are invariants. A change that breaks one of them needs a reason written
in the commit message.

1. **Layers only depend downwards.** `api` → `services` → `repositories` →
   `models`. A router must never import a repository; a service must never
   import a router.
2. **All domain SQL lives in `app/repositories/`.** If a service or a router
   needs a query, it calls the repository. The one exception is the
   `SELECT 1` probe in the health route: that is an infrastructure check, not
   data access, and it stays where it is.
3. **`app/api/deps.py` is the composition root.** It is the one place allowed
   to import both a repository and a service, because its job is to wire them
   together. Do not "clean up" that import.
4. **Business rules live in `app/services/`.** Routers translate HTTP to
   service calls and back. No validation beyond the schema belongs in a
   router.
5. **HTTP errors are raised as domain exceptions** (`app/core/errors.py`) and
   translated by the global handlers in `app/main.py`. Every error response
   uses the same shape: `{"error": {"code", "message", "details"}}`.
6. **The database URL is resolved by `app/core/secrets.py`.** The application
   must not know that AWS exists: no AWS SDK, no IAM calls, no secret lookups.
7. **The ORM model and the API schema are different types.** Never return an
   ORM instance directly from an endpoint.

## Conventions

- **Code, comments, identifiers, tests, CI and Terraform in English.**
  Documentation (README, docs/) in Spanish.
- Line length 100. `ruff` formats and lints everything; `ruff format` decides.
- Every function that has a branch gets a test for each branch.
- Commits follow Conventional Commits. One logical change per commit.
- Test names describe the behaviour, not the function: `test_create_invoice_
  returns_409_on_duplicate`, not `test_create_invoice_2`.

## Known traps

These cost real debugging time. Do not reintroduce them.

- **`condecimal` already returns an `Annotated`.** Wrapping it in another
  `Annotated[Decimal, condecimal(...)]` nests the metadata and Pydantic v2
  **silently discards every constraint** — no error, no warning. Use
  `Amount = condecimal(gt=0, max_digits=12, decimal_places=2)`.
- **`model_copy(update=...)` skips validation.** A test that uses it to build an
  invalid model will never fail. Construct the model inside
  `pytest.raises(ValidationError)`.
- **SQLAlchemy `Enum` stores the member *name*** (`ISSUED`), not the value
  (`issued`). With a `CHECK` constraint on the values, every insert fails. Use
  `values_callable=lambda enum_cls: [m.value for m in enum_cls]`.
- **Passwords break URLs.** `quote(password, safe="")`, otherwise an `@` in the
  password produces a misleading authentication error.
- **The host in a secret may already carry the port.** Handle both shapes.
- **A malformed secret must raise, never fall back** to another database.
- **`ruff` formats Python inside Markdown.** `*.md` is excluded from ruff on
  purpose; do not remove that exclusion.

## Infrastructure

- **Never run `terraform apply` against real AWS.** No credentials exist in
  this repository and there are no resources. The only sanctioned target is the
  local emulator.
- The emulator is Floci, in the `aws-emulator` compose profile. `make staging`
  starts it.
- **Each environment has its own state file.** Applying `staging` with the
  `development` state would destroy the development resources, because the
  resource names contain the environment.
- `environment` and `database_password` have **no default on purpose**. Never
  add one: a plan without `--var-file` must fail instead of silently pointing
  at development.
- The ECR repository is immutable, so the image tag must change on every
  deployment (`image_tag`).
- Run migrations as a separate one-shot task, never from the API entrypoint.

## Verifying before claiming something works

- Run the command. Paste the real output. Never describe a result that was not
  observed.
- `make check-all` before proposing a change as finished.
- The CI must be green before a change is considered done.
- If a check cannot run, say so explicitly instead of implying it passed.

## Boundaries

- Do not touch `openapi/` or `invoices/` (sibling directories of this project).
- Do not add dependencies without saying why. The dependency list is short on
  purpose.
- Do not invent experience: this repository documents practice, and the README
  is explicit about what was and was not applied.
