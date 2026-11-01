import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import data, loader
from app.db import DEFAULT_SQLITE_PATH, DataUnavailableError, database_url, normalize_url, readings
from app.main import app
from app.tools import run_tool

client = TestClient(app)


def sqlite_url(path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_loader_puts_35040_rows_and_is_safe_to_run_twice(tmp_path):
    url = sqlite_url(tmp_path / "twice.db")
    assert loader.load(url) == 35040
    assert loader.load(url) == 35040
    with create_engine(url).connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM energy_readings")).scalar() == 35040
        assert conn.execute(text("SELECT COUNT(DISTINCT interval_start) FROM energy_readings")).scalar() == 35040


def test_ensure_loaded_fills_only_when_empty(tmp_path):
    url = sqlite_url(tmp_path / "once.db")
    assert loader.ensure_loaded(url) is True
    assert loader.ensure_loaded(url) is False
    assert len(data._read(url)) == 35040


def test_loader_command_failure_does_not_leak_the_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:SECRETPW123@127.0.0.1:1/db")
    monkeypatch.setattr("sys.argv", ["loader", "--if-missing"])
    with pytest.raises(SystemExit) as exit_info:
        loader.main()
    assert "SECRETPW123" not in str(exit_info.value)
    assert "데이터베이스에 데이터를 넣지 못했습니다" in str(exit_info.value)


def test_postgres_table_definition_and_lock_statement_are_valid():
    """Supabase에 접속하지 않고도 만들 SQL이 올바른지 확인한다."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    ddl = str(CreateTable(readings).compile(dialect=postgresql.dialect()))
    assert "CREATE TABLE energy_readings" in ddl
    assert "interval_start TIMESTAMP WITHOUT TIME ZONE NOT NULL" in ddl
    assert "is_weekend BOOLEAN NOT NULL" in ddl
    assert "PRIMARY KEY (interval_start)" in ddl


def test_missing_sqlite_file_is_reported_and_not_created(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(DataUnavailableError, match="파일이 없습니다"):
        data._read(sqlite_url(missing))
    assert not missing.exists()


def test_empty_table_is_reported(tmp_path):
    path = tmp_path / "empty.db"
    engine = create_engine(sqlite_url(path))
    readings.create(engine)
    engine.dispose()
    with pytest.raises(DataUnavailableError, match="데이터가 없습니다"):
        data._read(sqlite_url(path))


def test_database_without_the_table_is_reported(tmp_path):
    path = tmp_path / "notable.db"
    create_engine(sqlite_url(path)).connect().close()
    with pytest.raises(DataUnavailableError, match="읽지 못했습니다"):
        data._read(sqlite_url(path))


def test_without_setting_the_sqlite_file_in_database_folder_is_used(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() == f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    assert DEFAULT_SQLITE_PATH.parent.name == "database"


@pytest.mark.parametrize(
    "given, expected",
    [
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///a.db", "sqlite:///a.db"),
    ],
)
def test_supabase_style_addresses_are_normalized(given, expected):
    assert normalize_url(given) == expected


@pytest.fixture
def broken_database(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", sqlite_url(tmp_path / "gone.db"))
    yield


def test_api_answers_503_not_400_when_database_is_down(broken_database):
    for path in ("/api/dashboard", "/api/anomalies", "/api/report/2018-12-16"):
        response = client.get(path)
        assert response.status_code == 503, path
        assert "데이터베이스" in response.json()["detail"]
    assert client.get("/api/status").status_code == 200


def test_api_recovers_when_database_is_back():
    assert client.get("/api/dashboard").status_code == 200


def test_tool_reports_database_problem_to_the_model(broken_database):
    content, chart, is_error = run_tool("summarize_period", {"start": "2018-01-01", "end": "2018-01-31"})
    assert is_error and "데이터베이스" in content and chart is None


def test_connection_failure_does_not_leak_the_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:SECRETPW123@127.0.0.1:1/db")
    response = client.get("/api/dashboard")
    assert response.status_code == 503
    assert "SECRETPW123" not in response.text
