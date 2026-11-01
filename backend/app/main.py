"""대시보드와 에이전트 API 서버. 빌드된 React 화면(frontend/dist)도 함께 제공한다."""
import json
import os
import uuid
from collections import OrderedDict

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analysis
from .agent import run_turn
from .db import ROOT, DataUnavailableError

DIST_DIR = ROOT / "frontend" / "dist"
MAX_SESSIONS = 100

app = FastAPI(title="Factory Energy Agent")
# 화면을 아직 빌드하지 않았어도 서버가 켜지도록 폴더 존재 확인은 요청이 올 때 한다.
app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets", check_dir=False), name="assets")
sessions: OrderedDict[str, list] = OrderedDict()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


@app.exception_handler(DataUnavailableError)
async def data_unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def has_credentials() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def get_history(session_id: str) -> list:
    history = sessions.setdefault(session_id, [])
    sessions.move_to_end(session_id)
    while len(sessions) > MAX_SESSIONS:
        sessions.popitem(last=False)
    return history


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _api_error_message(exc: anthropic.AnthropicError) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "API 키가 유효하지 않습니다. backend/.env 파일의 키를 확인해 주세요."
    if isinstance(exc, anthropic.RateLimitError):
        return "요청이 많아 제한되었습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Claude API에 연결하지 못했습니다. 네트워크를 확인해 주세요."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Claude API 오류가 발생했습니다 (HTTP {exc.status_code})."
    return "Claude API 호출 중 오류가 발생했습니다."


@app.get("/")
def index():
    page = DIST_DIR / "index.html"
    if page.is_file():
        return FileResponse(page)
    return HTMLResponse(
        "<p>화면이 아직 만들어지지 않았습니다. <code>frontend</code> 폴더에서 <code>npm run build</code>를 실행하세요.</p>",
        status_code=503,
    )


@app.get("/api/status")
def status() -> dict:
    return {"agent_ready": has_credentials()}


@app.get("/api/dashboard")
def dashboard() -> dict:
    return analysis.dashboard()


@app.get("/api/anomalies")
def anomalies() -> dict:
    return {"items": analysis.top_anomalies()}


@app.get("/api/report/{date}")
def report(date: str) -> dict:
    try:
        data = analysis.daily_report(date)
    except DataUnavailableError:
        raise
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**data, "markdown": analysis.report_markdown(data)}


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or uuid.uuid4().hex
    history = get_history(session_id)

    def events():
        yield _sse({"type": "session", "session_id": session_id})
        if not has_credentials():
            yield _sse({"type": "error", "message": "ANTHROPIC_API_KEY가 없습니다. backend/.env 파일에 키를 넣고 서버를 다시 시작해 주세요."})
            return
        try:
            for event in run_turn(anthropic.Anthropic(), history, request.message):
                yield _sse(event)
        except anthropic.AnthropicError as exc:
            yield _sse({"type": "error", "message": _api_error_message(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")
