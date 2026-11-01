"""CSV 원본을 데이터베이스에 넣는다. 사용법: python -m app.loader

DATABASE_URL이 없으면 database/energy.db(SQLite)에 넣고, 있으면 그 데이터베이스(예: Supabase)에 넣는다.
여러 번 실행해도 데이터가 중복되지 않는다. 실행할 때마다 표를 지우고 다시 만든다.
"""
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from . import data
from .db import CSV_PATH, DataUnavailableError, database_url, get_engine, readings


def build_frame(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    raw = pd.read_csv(csv_path)

    # 원본의 시각은 구간 종료 기준이고, 매일 마지막 구간이 다음 날이 아닌 그날 00:00으로 찍혀 있다.
    # 시각으로 정렬하면 이 행이 하루의 맨 앞으로 밀려나므로, 파일의 줄 순서로 구간 시작 시각을 다시 계산한다.
    start = pd.Timestamp("2018-01-01")
    interval_start = start + pd.to_timedelta(raw.index * data.INTERVAL_MINUTES, unit="min")

    labeled_date = pd.to_datetime(raw["date"], format="%d/%m/%Y %H:%M").dt.normalize()
    if not (labeled_date.to_numpy() == interval_start.normalize().to_numpy()).all():
        raise ValueError("파일의 행 순서가 예상과 달라 시각을 복원할 수 없습니다.")

    frame = pd.DataFrame(
        {
            "usage_kwh": raw["Usage_kWh"],
            "lag_kvarh": raw["Lagging_Current_Reactive.Power_kVarh"],
            "lead_kvarh": raw["Leading_Current_Reactive_Power_kVarh"],
            "co2_t": raw["CO2(tCO2)"],
            "load_type": raw["Load_Type"].str.replace("_Load", "", regex=False),
            "is_weekend": raw["WeekStatus"].eq("Weekend"),
        }
    )
    frame.index = pd.DatetimeIndex(interval_start, name="interval_start")
    return frame


def load(url: str | None = None, csv_path: Path = CSV_PATH) -> int:
    url = url or database_url()
    frame = build_frame(csv_path).reset_index()
    engine = get_engine(url)
    with engine.begin() as conn:
        readings.drop(conn, checkfirst=True)
        readings.create(conn)
        if engine.dialect.name == "postgresql":
            # Supabase는 표를 외부 주소로도 열어 두므로, 서버 접속만 허용하도록 잠근다.
            conn.execute(text(f"ALTER TABLE {readings.name} ENABLE ROW LEVEL SECURITY"))
        frame.to_sql(readings.name, conn, if_exists="append", index=False, chunksize=5000)
    data._read.cache_clear()
    return len(frame)


def ensure_loaded(url: str | None = None) -> bool:
    """데이터가 없을 때만 넣는다. 새로 넣었으면 True, 이미 있어 그대로 뒀으면 False."""
    url = url or database_url()
    try:
        data._read(url)
        return False
    except DataUnavailableError:
        load(url)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV 원본을 데이터베이스에 넣습니다.")
    parser.add_argument("--if-missing", action="store_true", help="데이터가 이미 있으면 아무것도 하지 않습니다.")
    args = parser.parse_args()

    url = database_url()
    try:
        if args.if_missing:
            if not ensure_loaded(url):
                print("데이터베이스에 이미 데이터가 있어 그대로 둡니다.")
                return
            count = len(data.load_data())
        else:
            count = load(url)
    except SQLAlchemyError as exc:
        # 오류 내용에는 접속 정보가 섞일 수 있어 종류만 알려 준다.
        raise SystemExit(
            f"데이터베이스에 데이터를 넣지 못했습니다 ({type(exc).__name__}). 연결 주소와 네트워크를 확인하세요."
        ) from None
    print(f"{count:,}건을 데이터베이스({get_engine(url).dialect.name})에 넣었습니다.")


if __name__ == "__main__":
    main()
