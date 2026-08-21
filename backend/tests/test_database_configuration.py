from backend.app import database


def test_database_url_uses_local_host_and_port_defaults(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "groundsignal_test")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    database_url = database._build_database_url()

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.host == "localhost"
    assert database_url.port == 5432
    assert database_url.database == "groundsignal_test"
    assert database_url.username == "test_user"
    assert database_url.password == "test_password"


def test_database_url_uses_environment_host_and_port(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "groundsignal")
    monkeypatch.setenv("POSTGRES_USER", "groundsignal")
    monkeypatch.setenv("POSTGRES_PASSWORD", "development-only")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    database_url = database._build_database_url()

    assert database_url.host == "db"
    assert database_url.port == 6543


def test_database_url_environment_variable_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://url_user:url_password@managed-db:5439/url_database",
    )
    monkeypatch.setenv("POSTGRES_HOST", "ignored-host")

    database_url = database._build_database_url()

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.host == "managed-db"
    assert database_url.port == 5439
    assert database_url.database == "url_database"
    assert database_url.username == "url_user"
    assert database_url.password == "url_password"
