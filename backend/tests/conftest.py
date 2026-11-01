"""앱을 불러오기 전에 임시 SQLite 데이터베이스를 만들어 연결한다.

실제 database/energy.db나 Supabase를 건드리지 않고, 테스트가 끝나도 남지 않는 임시 폴더만 쓴다.
"""
import os
import tempfile
from pathlib import Path

_test_db = Path(tempfile.mkdtemp(prefix="energy-test-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.as_posix()}"

from app import loader  # noqa: E402

loader.load()
