"""에너지 분석 함수. 에이전트와 대시보드가 보는 모든 숫자는 여기서 계산한다."""
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import HOLIDAYS_2018, INTERVALS_PER_HOUR, load_data
from .db import database_url

LOAD_TYPE_KO = {"Light": "경부하", "Medium": "중부하", "Maximum": "최대부하"}
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
METRICS = ("usage_kwh", "co2_t", "peak_kw", "power_factor")
METRIC_LABELS = {
    "usage_kwh": ("전력 사용량", "kWh"),
    "co2_t": ("CO2 배출량", "tCO2"),
    "peak_kw": ("최대 수요전력", "kW"),
    "power_factor": ("지상 역률", "%"),
}
MAX_ROWS = 400

# 이상 판정 기준: 주변 ±28일의 같은 요일 유형과 비교한 강건 Z-점수와 편차율을 모두 넘어야 한다.
ANOMALY_WINDOW_DAYS = 28
ANOMALY_MIN_DEVIATION_PCT = 30.0
MAD_TO_SIGMA = 1.4826


def _slice(start: str, end: str) -> pd.DataFrame:
    df = load_data()
    first, last = df.index[0].normalize(), df.index[-1].normalize()
    try:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
    except ValueError as exc:
        raise ValueError(f"날짜 형식이 잘못되었습니다: {start}, {end}. YYYY-MM-DD로 입력하세요.") from exc
    if s > e:
        raise ValueError(f"시작일({start})이 종료일({end})보다 늦습니다.")
    if s < first or e > last:
        raise ValueError(f"데이터 범위는 {first.date()} ~ {last.date()}입니다. 입력: {start} ~ {end}")
    return df.loc[s : e + pd.Timedelta(days=1, minutes=-1)]


def _power_factor(frame: pd.DataFrame) -> float | None:
    kwh, kvarh = frame["usage_kwh"].sum(), frame["lag_kvarh"].sum()
    apparent = float(np.hypot(kwh, kvarh))
    return round(kwh / apparent * 100, 2) if apparent else None


def _metric(group, metric: str) -> pd.Series:
    if metric == "usage_kwh":
        return group["usage_kwh"].sum()
    if metric == "co2_t":
        return group["co2_t"].sum()
    if metric == "peak_kw":
        return group["peak_kw"].max()
    if metric == "power_factor":
        return group.apply(_power_factor)
    raise ValueError(f"지원하지 않는 지표입니다: {metric}")


def _rows(series: pd.Series, labels: list[str] | None = None) -> list[dict]:
    keys = labels if labels is not None else [str(k) for k in series.index]
    return [
        {"label": key, "value": None if pd.isna(v) else round(float(v), 2)}
        for key, v in zip(keys, series)
    ]


def dataset_info() -> dict:
    df = load_data()
    return {
        "출처": "UCI Steel Industry Energy Consumption (CC BY 4.0), 대우스틸 광양공장 실측",
        "기간": f"{df.index[0].date()} ~ {df.index[-1].date()}",
        "측정_간격": "15분",
        "행_수": len(df),
        "지표": list(METRICS),
        "없는_정보": "설비별 전력, 생산량, 제품, 기상, 전기요금",
    }


def summarize(start: str, end: str) -> dict:
    frame = _slice(start, end)
    peak_at = frame["peak_kw"].idxmax()
    energy_by_load = frame.groupby("load_type")["usage_kwh"].sum()
    total = float(frame["usage_kwh"].sum())
    return {
        "기간": f"{start} ~ {end}",
        "usage_kwh": round(total, 2),
        "일평균_kwh": round(total / frame.index.normalize().nunique(), 2),
        "co2_t": round(float(frame["co2_t"].sum()), 2),
        "peak_kw": round(float(frame["peak_kw"].max()), 2),
        "peak_at": peak_at.strftime("%Y-%m-%d %H:%M"),
        "power_factor": _power_factor(frame),
        "부하별_사용량_비중_pct": {
            LOAD_TYPE_KO[k]: round(float(v) / total * 100, 1) if total else 0.0
            for k, v in energy_by_load.items()
        },
    }


def timeseries(start: str, end: str, freq: str, metric: str) -> dict:
    formats = {"hour": ("h", "%m-%d %H시"), "day": ("D", "%m-%d"), "week": ("W-SUN", "~%m-%d"), "month": ("MS", "%Y-%m")}
    if freq not in formats:
        raise ValueError(f"지원하지 않는 단위입니다: {freq}")
    rule, fmt = formats[freq]
    frame = _slice(start, end)
    group = frame.groupby(pd.Grouper(freq=rule, label="left" if freq != "week" else "right"))
    series = _metric(group, metric)
    if len(series) > MAX_ROWS:
        raise ValueError(f"결과가 {len(series)}행입니다. 기간을 줄이거나 더 큰 단위를 사용하세요.")
    return {"metric": metric, "freq": freq, "rows": _rows(series, [k.strftime(fmt) for k in series.index])}


def profile(start: str, end: str, by: str, metric: str) -> dict:
    frame = _slice(start, end)
    days = max(frame.index.normalize().nunique(), 1)
    if by == "hour_of_day":
        group = frame.groupby(frame.index.hour)
        labels = [f"{h:02d}시" for h in sorted(frame.index.hour.unique())]
        divisor = days
    elif by == "weekday":
        group = frame.groupby(frame.index.day_of_week)
        keys = sorted(frame.index.day_of_week.unique())
        labels = [WEEKDAY_KO[d] for d in keys]
        divisor = pd.Series(frame.index.normalize().unique().day_of_week).value_counts().reindex(keys).to_numpy()
    elif by == "load_type":
        group = frame.groupby("load_type")
        labels = [LOAD_TYPE_KO[k] for k in sorted(frame["load_type"].unique())]
        divisor = days
    else:
        raise ValueError(f"지원하지 않는 기준입니다: {by}")
    series = _metric(group, metric)
    if metric in ("usage_kwh", "co2_t"):
        series = series / divisor
    return {"metric": metric, "by": by, "note": "사용량과 CO2는 일평균 값", "rows": _rows(series, labels)}


def compare_periods(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    a, b = summarize(a_start, a_end), summarize(b_start, b_end)
    changes = {}
    for key in ("일평균_kwh", "peak_kw", "power_factor"):
        if a[key] and b[key] is not None:
            changes[key] = {"A": a[key], "B": b[key], "변화율_pct": round((b[key] - a[key]) / a[key] * 100, 1)}
    return {"A": a, "B": b, "A대비_B": changes}


def _daily_table() -> pd.DataFrame:
    return _daily_for(database_url())


@lru_cache(maxsize=4)
def _daily_for(url: str) -> pd.DataFrame:
    """데이터베이스 주소별로 하루 단위 표를 한 번만 만든다."""
    df = load_data()
    daily = df.resample("D").agg(usage_kwh=("usage_kwh", "sum"), peak_kw=("peak_kw", "max"), is_weekend=("is_weekend", "first"))
    daily["holiday"] = [HOLIDAYS_2018.get(d.strftime("%Y-%m-%d")) for d in daily.index]

    baselines, sigmas = [], []
    for day, row in daily.iterrows():
        near = (daily.index - day).days
        peers = daily[
            (abs(near) <= ANOMALY_WINDOW_DAYS)
            & (near != 0)
            & (daily["is_weekend"] == row["is_weekend"])
            & daily["holiday"].isna()
        ]["usage_kwh"]
        median = peers.median()
        baselines.append(median)
        sigmas.append(MAD_TO_SIGMA * (peers - median).abs().median())
    daily["baseline_kwh"] = baselines
    daily["sigma"] = sigmas
    daily["deviation_pct"] = (daily["usage_kwh"] - daily["baseline_kwh"]) / daily["baseline_kwh"] * 100
    daily["score"] = (daily["usage_kwh"] - daily["baseline_kwh"]) / daily["sigma"].replace(0, np.nan)
    return daily


def _holiday(row: pd.Series) -> str | None:
    return None if pd.isna(row["holiday"]) else row["holiday"]


def detect_anomalies(start: str, end: str, top_n: int, min_score: float) -> dict:
    _slice(start, end)
    daily = _daily_table().loc[start:end]
    hits = daily[(daily["score"].abs() >= min_score) & (daily["deviation_pct"].abs() >= ANOMALY_MIN_DEVIATION_PCT)]
    hits = hits.reindex(hits["score"].abs().sort_values(ascending=False).index).head(top_n)

    frame = load_data()
    items = []
    for day, row in hits.iterrows():
        one_day = frame.loc[day.strftime("%Y-%m-%d")]
        items.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "요일": WEEKDAY_KO[day.day_of_week],
                "방향": "높음" if row["score"] > 0 else "낮음",
                "usage_kwh": round(float(row["usage_kwh"]), 1),
                "기준선_kwh": round(float(row["baseline_kwh"]), 1),
                "편차_pct": round(float(row["deviation_pct"]), 1),
                "점수": round(float(row["score"]), 2),
                "최대수요_시각": one_day["peak_kw"].idxmax().strftime("%H:%M"),
                "휴일": _holiday(row),
            }
        )
    return {
        "기준": f"주변 ±{ANOMALY_WINDOW_DAYS}일 같은 요일 유형의 중앙값 대비, 점수 {min_score} 이상이고 편차 {ANOMALY_MIN_DEVIATION_PCT:.0f}% 이상",
        "개수": len(items),
        "목록": items,
    }


def power_factor_report(start: str, end: str, threshold: float) -> dict:
    frame = _slice(start, end)
    active = frame[frame["usage_kwh"] > 0]
    if active.empty:
        raise ValueError("해당 기간에 전력 사용 기록이 없습니다.")
    pf = active["usage_kwh"] / np.hypot(active["usage_kwh"], active["lag_kvarh"]) * 100
    below = active[pf < threshold]
    hourly = active.groupby(active.index.hour).apply(_power_factor)
    by_load = active.groupby("load_type").apply(_power_factor)
    worst = hourly.dropna().nsmallest(3)
    return {
        "기간": f"{start} ~ {end}",
        "기준_pct": threshold,
        "가중_평균_역률": _power_factor(active),
        "기준_미달_구간_비율_pct": round(len(below) / len(active) * 100, 1),
        "기준_미달_구간의_사용량_비중_pct": round(float(below["usage_kwh"].sum() / active["usage_kwh"].sum() * 100), 1),
        "부하별_역률": {LOAD_TYPE_KO[k]: v for k, v in by_load.items()},
        "역률이_가장_낮은_시간대": [f"{h:02d}시 ({v}%)" for h, v in worst.items()],
        "rows": _rows(hourly, [f"{h:02d}시" for h in hourly.index]),
    }


def simulate_peak_cap(start: str, end: str, reduction_pct: float) -> dict:
    if not 0 < reduction_pct < 100:
        raise ValueError("감축률은 0보다 크고 100보다 작아야 합니다.")
    frame = _slice(start, end)
    current_peak = float(frame["peak_kw"].max())
    cap_kw = current_peak * (1 - reduction_pct / 100)
    hours = 1 / INTERVALS_PER_HOUR

    excess = ((frame["peak_kw"] - cap_kw).clip(lower=0) * hours).groupby(frame.index.date).sum()
    headroom = ((cap_kw - frame["peak_kw"]).clip(lower=0) * hours).groupby(frame.index.date).sum()
    days_over = excess[excess > 0]
    feasible = int((days_over <= headroom[days_over.index]).sum())
    return {
        "기간": f"{start} ~ {end}",
        "현재_최대수요_kw": round(current_peak, 2),
        "목표_상한_kw": round(cap_kw, 2),
        "상한_초과_일수": len(days_over),
        "초과_구간_수": int((frame["peak_kw"] > cap_kw).sum()),
        "옮겨야_할_총_사용량_kwh": round(float(days_over.sum()), 1),
        "하루_안에_옮길_수_있는_일수": feasible,
        "주의": "같은 날 여유 시간대로 옮긴다는 산술 계산입니다. 공정 제약과 설비 가동 조건은 반영하지 않았습니다.",
    }


def daily_report(date: str) -> dict:
    day = pd.Timestamp(date)
    stats = summarize(date, date)
    table = _daily_table()
    row = table.loc[day]
    hourly = profile(date, date, "hour_of_day", "usage_kwh")["rows"]
    anomalies = detect_anomalies(date, date, 1, 3.0)["목록"]
    return {
        "date": date,
        "요일": WEEKDAY_KO[day.day_of_week],
        "휴일": _holiday(row),
        "summary": stats,
        "기준선_kwh": round(float(row["baseline_kwh"]), 1),
        "기준선_대비_pct": round(float(row["deviation_pct"]), 1),
        "이상_판정": anomalies[0] if anomalies else None,
        "rows": hourly,
    }


def report_markdown(report: dict) -> str:
    s = report["summary"]
    holiday = f" · {report['휴일']}" if report["휴일"] else ""
    shares = ", ".join(f"{k} {v}%" for k, v in s["부하별_사용량_비중_pct"].items())
    anomaly = report["이상_판정"]
    verdict = (
        f"{anomaly['방향']} (점수 {anomaly['점수']}, 기준선 대비 {anomaly['편차_pct']:+}%)"
        if anomaly
        else "이상 없음"
    )
    return "\n".join(
        [
            f"# 일일 에너지 보고서: {report['date']} ({report['요일']}{holiday})",
            "",
            "| 항목 | 값 |",
            "|---|---|",
            f"| 전력 사용량 | {s['usage_kwh']:,} kWh |",
            f"| 기준선 대비 | {report['기준선_대비_pct']:+}% (기준선 {report['기준선_kwh']:,} kWh) |",
            f"| 최대 수요전력 | {s['peak_kw']:,} kW ({s['peak_at'][-5:]}) |",
            f"| 지상 역률 | {s['power_factor']}% |",
            f"| CO2 배출량 | {s['co2_t']} tCO2 |",
            f"| 부하별 사용량 비중 | {shares} |",
            f"| 이상 판정 | {verdict} |",
        ]
    )


def dashboard() -> dict:
    first, last = "2018-01-01", "2018-12-31"
    return {
        "summary": summarize(first, last),
        "monthly": timeseries(first, last, "month", "usage_kwh")["rows"],
        "daily": timeseries(first, last, "day", "usage_kwh")["rows"],
        "hourly_profile": profile(first, last, "hour_of_day", "usage_kwh")["rows"],
    }


def top_anomalies(count: int = 8) -> list[dict]:
    return detect_anomalies("2018-01-01", "2018-12-31", count, 3.0)["목록"]
