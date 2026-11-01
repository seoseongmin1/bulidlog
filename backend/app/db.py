"""데이터베이스 연결 설정. DATABASE_URL이 없으면 database/energy.db(SQLite)를 쓴다."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, DateTime, Float, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine, make_url

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "database" / "steel_industry_data.csv"
DEFAULT_SQLITE_PATH = ROOT / "database" / "energy.db"

metadata = MetaData()
readings = Table(
    "energy_readings",
    metadata,
    Column("interval_start", DateTime, primary_key=True),
    Column("usage_kwh", Float, nullable=False),
    Column("lag_kvarh", Float, nullable=False),
    Column("lead_kvarh", Float, nullable=False),
    Column("co2_t", Float, nullable=False),
    Column("load_type", String(10), nullable=False),
    Column("is_weekend", Boolean, nullable=False),
)


class DataUnavailableError(ValueError):
    """데이터베이스에서 데이터를 읽을 수 없을 때 쓴다. 메시지에는 접속 정보를 넣지 않는다."""


def normalize_url(url: str) -> str:
    """Supabase가 알려 주는 postgresql:// 주소를 psycopg 드라이버 주소로 바꾼다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    return normalize_url(url)


def ensure_sqlite_file(url: str) -> None:
    """없는 SQLite 파일을 연결하면 빈 파일이 새로 생기므로, 연결 전에 먼저 확인한다."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return
    path = parsed.database
    if path and path != ":memory:" and not Path(path).is_file():
        raise DataUnavailableError("데이터베이스 파일이 없습니다. 먼저 `python -m app.loader`로 데이터를 넣으세요.")


@lru_cache(maxsize=4)
def get_engine(url: str) -> Engine:
    options = {}
    if url.startswith("postgresql"):
        options["connect_args"] = {"connect_timeout": 10}
    return create_engine(url, pool_pre_ping=True, **options)
