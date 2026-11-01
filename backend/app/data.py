"""데이터베이스에서 전력 데이터를 읽어 분석 가능한 형태로 만든다."""
from functools import lru_cache

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .db import DataUnavailableError, database_url, ensure_sqlite_file, get_engine, readings

INTERVAL_MINUTES = 15
INTERVALS_PER_HOUR = 60 // INTERVAL_MINUTES

# 데이터에는 달력 정보가 없어서 직접 넣는다. 평일 휴일을 이상으로 오판하지 않기 위해 필요하다.
HOLIDAYS_2018 = {
    "2018-01-01": "신정",
    "2018-02-15": "설 연휴",
    "2018-02-16": "설날",
    "2018-02-17": "설 연휴",
    "2018-03-01": "삼일절",
    "2018-05-05": "어린이날",
    "2018-05-07": "어린이날 대체공휴일",
    "2018-05-22": "부처님오신날",
    "2018-06-06": "현충일",
    "2018-06-13": "지방선거일",
    "2018-08-15": "광복절",
    "2018-09-23": "추석 연휴",
    "2018-09-24": "추석",
    "2018-09-25": "추석 연휴",
    "2018-09-26": "추석 대체공휴일",
    "2018-10-03": "개천절",
    "2018-10-09": "한글날",
    "2018-12-25": "성탄절",
}


@lru_cache(maxsize=4)
def _read(url: str) -> pd.DataFrame:
    try:
        ensure_sqlite_file(url)
        frame = pd.read_sql(select(readings).order_by(readings.c.interval_start), get_engine(url))
    except DataUnavailableError:
        raise
    except ImportError as exc:
        raise DataUnavailableError("데이터베이스 드라이버가 설치되어 있지 않습니다.") from exc
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:
        raise DataUnavailableError(
            "데이터베이스에서 전력 데이터를 읽지 못했습니다. 연결 설정과 데이터 적재 여부를 확인하세요."
        ) from exc

    if frame.empty:
        raise DataUnavailableError("데이터베이스에 전력 데이터가 없습니다. 먼저 `python -m app.loader`로 데이터를 넣으세요.")

    frame["interval_start"] = pd.to_datetime(frame["interval_start"])
    frame = frame.set_index("interval_start")
    frame["is_weekend"] = frame["is_weekend"].astype(bool)
    frame["peak_kw"] = frame["usage_kwh"] * INTERVALS_PER_HOUR
    return frame


def load_data() -> pd.DataFrame:
    return _read(database_url())
