import json

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_dashboard_has_everything_the_screen_needs():
    data = client.get("/api/dashboard").json()
    assert data["summary"]["usage_kwh"] == pytest.approx(959636.71, abs=0.01)
    assert len(data["monthly"]) == 12
    assert len(data["daily"]) == 365
    assert len(data["hourly_profile"]) == 24


def test_anomalies_are_eight_days_with_december_16_first():
    items = client.get("/api/anomalies").json()["items"]
    assert len(items) == 8
    assert items[0]["date"] == "2018-12-16"
    assert any(item["휴일"] == "신정" for item in items)


def test_report_for_valid_and_invalid_date():
    good = client.get("/api/report/2018-12-16")
    assert good.status_code == 200
    assert "2018-12-16" in good.json()["markdown"]
    assert "2,014.66" in good.json()["markdown"]
    bad_range = client.get("/api/report/2019-01-01")
    assert bad_range.status_code == 400
    assert "2018-01-01 ~ 2018-12-31" in bad_range.json()["detail"]
    assert client.get("/api/report/not-a-date").status_code == 400


def test_chat_without_key_explains_setup(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    response = client.post("/api/chat", json={"message": "안녕"})
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "session"
    assert events[-1]["type"] == "error"
    assert "ANTHROPIC_API_KEY" in events[-1]["message"]


def test_chat_rejects_empty_and_too_long_message(monkeypatch):
    # 실제 키가 있어도 진짜 AI를 호출하지 않도록 키를 비운다.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "가" * 2001}).status_code == 422
    assert client.post("/api/chat", json={"message": "가" * 2000}).status_code == 200


def test_index_serves_built_screen_or_explains(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DIST_DIR", tmp_path)
    missing = client.get("/")
    assert missing.status_code == 503
    assert "npm run build" in missing.text

    (tmp_path / "index.html").write_text("<p>화면</p>", encoding="utf-8")
    assert client.get("/").status_code == 200
