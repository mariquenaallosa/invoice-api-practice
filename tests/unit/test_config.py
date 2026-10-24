from app.core.config import Settings


def test_cors_origins_defaults_to_an_empty_list() -> None:
    assert Settings(cors_origins="").cors_origins == []


def test_cors_origins_accepts_a_comma_separated_list() -> None:
    settings = Settings(cors_origins="http://a.example.com, http://b.example.com")

    assert settings.cors_origins == ["http://a.example.com", "http://b.example.com"]


def test_cors_origins_accepts_an_actual_list() -> None:
    settings = Settings(cors_origins=["http://a.example.com"])

    assert settings.cors_origins == ["http://a.example.com"]


def test_cors_origins_ignores_blank_entries() -> None:
    settings = Settings(cors_origins="http://a.example.com, ,")

    assert settings.cors_origins == ["http://a.example.com"]
