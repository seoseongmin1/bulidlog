"""가짜 Messages API 서버로 실제 SDK를 통과시켜 에이전트 루프를 검증한다."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anthropic
import pytest

from app.agent import MAX_TOOL_ROUNDS, run_turn


def message(content, stop_reason):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


TOOL_CALL = message(
    [{"type": "tool_use", "id": "toolu_1", "name": "summarize_period", "input": {"start": "2018-01-01", "end": "2018-01-31"}}],
    "tool_use",
)
BAD_TOOL_CALL = message(
    [{"type": "tool_use", "id": "toolu_2", "name": "summarize_period", "input": {"start": "2019-01-01", "end": "2019-01-02"}}],
    "tool_use",
)
ANSWER = message([{"type": "text", "text": "1월 사용량은 많았습니다."}], "end_turn")


@pytest.fixture
def api():
    state = {"responses": [], "requests": [], "headers": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            state["requests"].append(body)
            state["headers"].append(dict(self.headers))
            reply = state["responses"].pop(0) if len(state["responses"]) > 1 else state["responses"][0]
            payload = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["client"] = anthropic.Anthropic(api_key="test", base_url=f"http://127.0.0.1:{server.server_port}")
    yield state
    server.shutdown()


def test_tool_result_goes_back_to_model_and_answer_is_returned(api):
    api["responses"] = [TOOL_CALL, ANSWER]
    history = []
    events = list(run_turn(api["client"], history, "1월 요약해줘"))

    assert [e["type"] for e in events] == ["tool_call", "tool_result", "answer"]
    assert events[-1]["text"] == "1월 사용량은 많았습니다."

    result = api["requests"][1]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "toolu_1"
    assert json.loads(result["content"])["usage_kwh"] == pytest.approx(126238, abs=1)
    assert len(history) == 4


def test_request_uses_expected_model_settings(api):
    api["responses"] = [ANSWER]
    list(run_turn(api["client"], [], "안녕"))
    body, headers = api["requests"][0], api["headers"][0]
    assert body["model"] == "claude-opus-5-5"
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    beta = next(v for k, v in headers.items() if k.lower() == "anthropic-beta")
    assert "server-side-fallback-2026-07-01" in beta


def test_system_prompt_carries_the_spec_promises(api):
    api["responses"] = [ANSWER]
    list(run_turn(api["client"], [], "안녕"))
    system = api["requests"][0]["system"]
    for promise in ("가능성", "원화 금액", "제어하지", "답할 수 없는 질문"):
        assert promise in system


def test_tool_error_is_reported_to_model_not_raised(api):
    api["responses"] = [BAD_TOOL_CALL, ANSWER]
    events = list(run_turn(api["client"], [], "2019년은?"))
    assert events[1] == {"type": "tool_result", "name": "summarize_period", "is_error": True}
    assert api["requests"][1]["messages"][-1]["content"][0]["is_error"] is True


def test_followup_question_keeps_history(api):
    api["responses"] = [TOOL_CALL, ANSWER, ANSWER]
    history = []
    list(run_turn(api["client"], history, "첫 질문"))
    list(run_turn(api["client"], history, "두 번째 질문"))
    assert api["requests"][-1]["messages"][0]["content"] == "첫 질문"
    assert api["requests"][-1]["messages"][-1]["content"] == "두 번째 질문"


def test_refusal_leaves_history_untouched(api):
    api["responses"] = [message([], "refusal")]
    history = []
    events = list(run_turn(api["client"], history, "질문"))
    assert events[-1]["type"] == "error"
    assert history == []


def test_endless_tool_calls_stop_at_limit(api):
    api["responses"] = [TOOL_CALL]
    history = []
    events = list(run_turn(api["client"], history, "질문"))
    assert events[-1]["type"] == "error"
    assert len(api["requests"]) == MAX_TOOL_ROUNDS
    assert history == []


def test_max_tokens_answer_is_marked_as_cut(api):
    api["responses"] = [message([{"type": "text", "text": "일부"}], "max_tokens")]
    events = list(run_turn(api["client"], [], "질문"))
    assert "잘렸습니다" in events[-1]["text"]
