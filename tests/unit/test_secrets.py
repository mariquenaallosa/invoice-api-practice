import pytest

from app.core.config import Settings
from app.core.secrets import ConfigurationError, build_database_url, resolve_database_url

# The exact shape the ECS agent injects, taken from a real secret.
SECRET_PAYLOAD = {
    "dbname": "invoice",
    "host": "10.200.18.2:7001",
    "password": "S3cret-pass-123",
    "port": 7001,
    "username": "invoice",
}


def test_build_database_url_returns_the_expected_url() -> None:
    url = build_database_url(SECRET_PAYLOAD)

    assert url == "postgresql+psycopg://invoice:S3cret-pass-123@10.200.18.2:7001/invoice"


def test_build_database_url_encodes_special_characters() -> None:
    """An unencoded password would be parsed as part of the userinfo."""
    payload = {**SECRET_PAYLOAD, "password": "S3cret@pass/2026"}

    url = build_database_url(payload)

    assert url == "postgresql+psycopg://invoice:S3cret%40pass%2F2026@10.200.18.2:7001/invoice"


def test_build_database_url_does_not_duplicate_the_port() -> None:
    """The host already carries the port, and there is a `port` field too."""
    url = build_database_url(SECRET_PAYLOAD)

    assert url.count(":7001") == 1


def test_build_database_url_appends_the_port_when_the_host_has_none() -> None:
    payload = {**SECRET_PAYLOAD, "host": "db.internal"}

    url = build_database_url(payload)

    assert url == "postgresql+psycopg://invoice:S3cret-pass-123@db.internal:7001/invoice"


def test_build_database_url_works_without_a_port_field() -> None:
    payload = {**SECRET_PAYLOAD, "host": "db.internal"}
    del payload["port"]

    url = build_database_url(payload)

    assert url == "postgresql+psycopg://invoice:S3cret-pass-123@db.internal/invoice"


def test_resolve_database_url_uses_the_plain_url_without_a_secret() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/db", database_secret=None
    )

    assert resolve_database_url(settings) == "postgresql+psycopg://u:p@localhost:5432/db"


def test_resolve_database_url_treats_an_empty_secret_as_not_configured() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/db", database_secret="  "
    )

    assert resolve_database_url(settings) == "postgresql+psycopg://u:p@localhost:5432/db"


def test_resolve_database_url_uses_the_secret_when_there_is_one() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/db",
        database_secret='{"username":"invoice","password":"pw","host":"db.internal","port":5432,"dbname":"invoice"}',
    )

    url = resolve_database_url(settings)

    assert url == "postgresql+psycopg://invoice:pw@db.internal:5432/invoice"


def test_resolve_database_url_raises_on_invalid_json() -> None:
    settings = Settings(database_secret="{not json")

    with pytest.raises(ConfigurationError, match="not valid JSON"):
        resolve_database_url(settings)


def test_resolve_database_url_raises_when_the_secret_is_not_an_object() -> None:
    settings = Settings(database_secret="[1, 2, 3]")

    with pytest.raises(ConfigurationError, match="must be a JSON object"):
        resolve_database_url(settings)


def test_resolve_database_url_raises_when_a_field_is_missing() -> None:
    settings = Settings(database_secret='{"username":"invoice","password":"pw"}')

    with pytest.raises(ConfigurationError, match="missing required fields"):
        resolve_database_url(settings)


def test_resolve_database_url_never_falls_back_when_the_secret_is_broken() -> None:
    """A broken secret must stop the application, not connect somewhere else."""
    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost:5432/db",
        database_secret="{broken",
    )

    with pytest.raises(ConfigurationError):
        resolve_database_url(settings)
