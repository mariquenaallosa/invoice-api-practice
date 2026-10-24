import json
from typing import Any
from urllib.parse import quote

from app.core.config import Settings

REQUIRED_SECRET_FIELDS = frozenset({"username", "password", "host", "dbname"})


class ConfigurationError(Exception):
    """Raised when the application configuration cannot be used.

    It is deliberately not an `AppError`: it happens before the application
    serves any request, so there is no client to answer.
    """


def build_database_url(payload: dict[str, Any]) -> str:
    """Build a SQLAlchemy URL from the payload of the database secret.

    This is a pure function: no AWS, no settings, no environment. That makes
    it trivial to test and impossible to break from the outside.
    """
    username = quote(str(payload["username"]), safe="")
    password = quote(str(payload["password"]), safe="")
    database = quote(str(payload["dbname"]), safe="")

    host = str(payload["host"])
    port = payload.get("port")

    # The host may already carry the port ("10.0.0.1:5432") or not ("db.internal").
    if ":" in host and host.rsplit(":", 1)[1].isdigit():
        address = host
    elif port:
        address = f"{host}:{port}"
    else:
        address = host

    return f"postgresql+psycopg://{username}:{password}@{address}/{database}"


def resolve_database_url(settings: Settings) -> str:
    """Return the database URL the application must use.

    The secret wins when there is one: the platform (the ECS agent) resolved it
    and injected it as `DATABASE_SECRET`. Without a secret the plain
    `DATABASE_URL` is used, which is what local development and the tests
    rely on.

    A malformed secret raises instead of falling back: silently connecting to
    another database is worse than not starting at all.
    """
    raw_secret = settings.database_secret

    # An empty environment variable means "not configured", not "broken".
    if raw_secret is None or not raw_secret.strip():
        return settings.database_url

    try:
        payload = json.loads(raw_secret)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"DATABASE_SECRET is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConfigurationError(
            f"DATABASE_SECRET must be a JSON object, got {type(payload).__name__}."
        )

    missing = REQUIRED_SECRET_FIELDS - payload.keys()
    if missing:
        raise ConfigurationError(
            f"DATABASE_SECRET is missing required fields: {', '.join(sorted(missing))}."
        )

    return build_database_url(payload)
