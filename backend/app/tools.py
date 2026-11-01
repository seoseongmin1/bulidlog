"""Claude에게 공개하는 도구 정의와 실행기."""
import json

from . import analysis

DATE = {"type": "string", "description": "YYYY-MM-DD 형식의 날짜. 2018-01-01 ~ 2018-12-31"}
METRIC = {"type": "string", "enum": list(analysis.METRICS), "description": "분석할 지표"}


def _tool(name: str, description: str, properties: dict) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool("get_dataset_info", "데이터의 출처, 기간, 지표, 그리고 데이터에 없는 정보를 확인한다.", {}),
    _tool(
        "summarize_period",
        "기간의 총 사용량, 일평균, CO2, 최대 수요전력과 그 시각, 역률, 부하별 비중을 구한다.",
        {"start": DATE, "end": DATE},
    ),
    _tool(
        "get_timeseries",
        "기간의 지표를 시간, 일, 주, 월 단위로 집계한다. 결과는 화면에 차트로 표시된다. 최대 400행까지 가능하다.",
        {
            "start": DATE,
            "end": DATE,
            "freq": {"type": "string", "enum": ["hour", "day", "week", "month"], "description": "집계 단위"},
            "metric": METRIC,
        },
    ),
    _tool(
        "get_profile",
        "기간의 지표를 시간대, 요일, 부하 유형별로 묶어 패턴을 본다. 사용량과 CO2는 일평균이다. 결과는 차트로 표시된다.",
        {
            "start": DATE,
            "end": DATE,
            "by": {"type": "string", "enum": ["hour_of_day", "weekday", "load_type"], "description": "묶는 기준"},
            "metric": METRIC,
        },
    ),
    _tool(
        "compare_periods",
        "두 기간(A, B)의 일평균 사용량, 최대 수요전력, 역률을 비교한다.",
        {"a_start": DATE, "a_end": DATE, "b_start": DATE, "b_end": DATE},
    ),
    _tool(
        "detect_anomalies",
        "주변 같은 요일 유형과 비교해 사용량이 비정상인 날을 찾고, 공휴일 여부를 함께 알려준다.",
        {
            "start": DATE,
            "end": DATE,
            "top_n": {"type": "integer", "description": "반환할 최대 개수. 보통 10"},
            "min_score": {"type": "number", "description": "강건 Z-점수 기준. 보통 3.0"},
        },
    ),
    _tool(
        "analyze_power_factor",
        "기간의 지상 역률과 기준 미달 비율, 역률이 낮은 시간대를 분석한다. 결과는 차트로 표시된다.",
        {"start": DATE, "end": DATE, "threshold": {"type": "number", "description": "역률 기준(%). 보통 90"}},
    ),
    _tool(
        "simulate_peak_cap",
        "최대 수요전력을 일정 비율 낮출 때 옮겨야 할 사용량과 하루 안에 옮길 수 있는 일수를 계산한다.",
        {"start": DATE, "end": DATE, "reduction_pct": {"type": "number", "description": "낮출 비율(%)"}},
    ),
    _tool(
        "get_daily_report",
        "특정 날짜의 일일 보고서 수치를 만든다. 결과는 차트로 표시된다.",
        {"date": DATE},
    ),
]

_HANDLERS = {
    "get_dataset_info": analysis.dataset_info,
    "summarize_period": analysis.summarize,
    "get_timeseries": analysis.timeseries,
    "get_profile": analysis.profile,
    "compare_periods": analysis.compare_periods,
    "detect_anomalies": analysis.detect_anomalies,
    "analyze_power_factor": analysis.power_factor_report,
    "simulate_peak_cap": analysis.simulate_peak_cap,
    "get_daily_report": analysis.daily_report,
}


def _chart_for(name: str, args: dict, result: dict) -> dict | None:
    """차트는 도구 결과에서만 만든다. 모델이 쓴 숫자는 그리지 않는다."""
    rows = result.get("rows")
    if not rows or len(rows) < 2:
        return None
    metric = result.get("metric", "power_factor" if name == "analyze_power_factor" else "usage_kwh")
    label, unit = analysis.METRIC_LABELS[metric]
    scope = args.get("date") or f"{args['start']} ~ {args['end']}"
    continuous = name in ("get_timeseries", "get_daily_report", "analyze_power_factor") or args.get("by") == "hour_of_day"
    return {
        "title": f"{label} ({scope})",
        "unit": unit,
        "kind": "line" if continuous and len(rows) > 12 else "bar",
        "rows": rows,
    }


def run_tool(name: str, args: dict) -> tuple[str, dict | None, bool]:
    """결과 JSON, 차트, 오류 여부를 돌려준다. 오류는 모델이 고칠 수 있도록 메시지로 전달한다."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"알 수 없는 도구입니다: {name}", None, True
    try:
        result = handler(**args)
    except (ValueError, TypeError, KeyError) as exc:
        return str(exc), None, True
    return json.dumps(result, ensure_ascii=False), _chart_for(name, args, result), False
