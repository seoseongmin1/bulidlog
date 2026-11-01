import json

import pandas as pd
import pytest

from app import analysis, loader
from app.data import load_data
from app.db import CSV_PATH
from app.tools import TOOLS, run_tool


def test_midnight_row_stays_at_end_of_its_day():
    df = load_data()
    assert len(df) == 35040
    assert df.index.is_monotonic_increasing
    # 원본 01/01 "00:00" 행(3.42kWh)은 1월 1일의 마지막 구간이다.
    assert df.loc["2018-01-01 23:45", "usage_kwh"] == 3.42
    assert df.loc["2018-01-01 00:00", "usage_kwh"] == 3.17


def test_database_matches_the_csv_it_was_loaded_from():
    from_db = load_data()
    from_csv = loader.build_frame(CSV_PATH)
    assert from_db.index.equals(from_csv.index)
    for column in ("usage_kwh", "lag_kvarh", "lead_kvarh", "co2_t"):
        assert from_db[column].to_numpy() == pytest.approx(from_csv[column].to_numpy())
    assert (from_db["load_type"].to_numpy() == from_csv["load_type"].to_numpy()).all()
    assert (from_db["is_weekend"].to_numpy() == from_csv["is_weekend"].to_numpy()).all()


def test_annual_total_matches_raw_file():
    raw = pd.read_csv(CSV_PATH)
    assert analysis.summarize("2018-01-01", "2018-12-31")["usage_kwh"] == pytest.approx(raw["Usage_kWh"].sum(), abs=0.01)


def test_power_factor_matches_definition():
    frame = pd.DataFrame({"usage_kwh": [3.0], "lag_kvarh": [4.0]})
    assert analysis._power_factor(frame) == 60.0
    assert analysis._power_factor(pd.DataFrame({"usage_kwh": [0.0], "lag_kvarh": [0.0]})) is None


def test_every_day_of_year_is_a_full_day():
    assert (load_data().resample("D").size() == 96).all()


def test_chuseok_is_flagged_low_and_labeled_as_holiday():
    hits = analysis.detect_anomalies("2018-09-24", "2018-09-26", 10, 3.0)["목록"]
    assert hits
    assert all(hit["방향"] == "낮음" and hit["휴일"] for hit in hits)


def test_top_anomalies_are_eight_days_led_by_december_16():
    top = analysis.top_anomalies()
    assert len(top) == 8
    assert top[0]["date"] == "2018-12-16"
    assert top[0]["방향"] == "높음"
    new_year = next(item for item in top if item["date"] == "2018-01-01")
    assert new_year["방향"] == "낮음" and new_year["휴일"] == "신정"
    scores = [abs(item["점수"]) for item in top]
    assert scores == sorted(scores, reverse=True)


def test_normal_day_has_no_holiday_or_nan_in_report():
    report = analysis.daily_report("2018-01-18")
    assert report["휴일"] is None
    assert "nan" not in analysis.report_markdown(report)


def test_december_16_report_matches_spec():
    report = analysis.daily_report("2018-12-16")
    assert report["summary"]["usage_kwh"] == pytest.approx(2014.66, abs=0.01)
    assert report["기준선_대비_pct"] == pytest.approx(450.0, abs=0.05)


def test_dashboard_has_twelve_months_and_365_days():
    data = analysis.dashboard()
    assert len(data["monthly"]) == 12
    assert len(data["daily"]) == 365
    assert len(data["hourly_profile"]) == 24
    assert data["summary"]["usage_kwh"] == pytest.approx(959636.71, abs=0.01)


def test_weekday_profile_averages_per_day():
    rows = analysis.profile("2018-01-01", "2018-01-14", "weekday", "usage_kwh")["rows"]
    daily = load_data().loc["2018-01-01":"2018-01-14", "usage_kwh"].resample("D").sum()
    assert rows[0]["value"] == pytest.approx(daily[daily.index.day_of_week == 0].mean(), abs=0.01)


def test_peak_cap_is_below_current_peak():
    result = analysis.simulate_peak_cap("2018-01-01", "2018-12-31", 0.01)
    assert result["상한_초과_일수"] >= 1
    assert result["목표_상한_kw"] < result["현재_최대수요_kw"]


@pytest.mark.parametrize(
    "name, args",
    [
        ("summarize_period", {"start": "2019-01-01", "end": "2019-01-02"}),
        ("summarize_period", {"start": "2018-02-10", "end": "2018-02-01"}),
        ("summarize_period", {"start": "어제", "end": "오늘"}),
        ("get_timeseries", {"start": "2018-01-01", "end": "2018-12-31", "freq": "hour", "metric": "usage_kwh"}),
        ("simulate_peak_cap", {"start": "2018-01-01", "end": "2018-01-02", "reduction_pct": 0}),
        ("없는_도구", {}),
    ],
)
def test_bad_tool_input_returns_error_message(name, args):
    content, chart, is_error = run_tool(name, args)
    assert is_error and content and chart is None


def test_every_tool_runs_with_valid_input():
    samples = {
        "get_dataset_info": {},
        "summarize_period": {"start": "2018-01-01", "end": "2018-01-31"},
        "get_timeseries": {"start": "2018-01-01", "end": "2018-01-31", "freq": "day", "metric": "power_factor"},
        "get_profile": {"start": "2018-01-01", "end": "2018-01-31", "by": "load_type", "metric": "peak_kw"},
        "compare_periods": {"a_start": "2018-01-01", "a_end": "2018-01-31", "b_start": "2018-09-01", "b_end": "2018-09-30"},
        "detect_anomalies": {"start": "2018-01-01", "end": "2018-12-31", "top_n": 5, "min_score": 3.0},
        "analyze_power_factor": {"start": "2018-01-01", "end": "2018-01-31", "threshold": 90},
        "simulate_peak_cap": {"start": "2018-01-01", "end": "2018-01-31", "reduction_pct": 10},
        "get_daily_report": {"date": "2018-01-18"},
    }
    assert set(samples) == {tool["name"] for tool in TOOLS}
    for name, args in samples.items():
        content, _, is_error = run_tool(name, args)
        assert not is_error, f"{name}: {content}"
        assert "NaN" not in content
        json.loads(content)


def test_chart_comes_from_tool_rows():
    content, chart, _ = run_tool("get_timeseries", {"start": "2018-01-01", "end": "2018-01-31", "freq": "day", "metric": "usage_kwh"})
    assert chart["rows"] == json.loads(content)["rows"]
    assert chart["kind"] == "line"
