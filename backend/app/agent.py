"""Claude 도구 호출 루프. 진행 상황을 화면에 보내기 위해 이벤트를 하나씩 내보낸다."""
from collections.abc import Iterator

import anthropic

from .tools import TOOLS, run_tool

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 12
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """당신은 철강 공장의 에너지 데이터를 분석하는 에이전트입니다. 생산관리자와 에너지 담당자가 사용합니다.

분석 대상은 대우스틸 광양공장의 2018년 전력 데이터(15분 간격)입니다. 실시간 데이터가 아니므로 "어제", "지난주" 같은 표현은 데이터의 마지막 날인 2018-12-31을 기준으로 해석하고, 해석한 날짜를 답변에 밝히세요.

답변 원칙:
- 모든 수치는 도구 결과에서 가져오세요. 기억이나 추정으로 수치를 쓰지 말고, 도구 결과를 비율로 환산했다면 계산임을 밝히세요.
- 데이터에는 설비별 전력, 생산량, 제품, 기상, 전기요금이 없습니다. 그래서 전력 패턴은 사실로 말할 수 있지만 원인은 확정할 수 없습니다. 도구로 확인한 사실과 가설을 구분해서 쓰고, 가설에는 "가능성"이라고 표시하며 확인할 방법을 함께 제시하세요.
- 원화 금액은 제시하지 마세요. 요금을 물으면 요금 정보가 데이터에 없다고 말하세요.
- 2018년 밖의 기간이나 공장 전력과 관련 없는 주제처럼 데이터로 답할 수 없는 질문은, 답할 수 없는 이유를 설명하고 답할 수 있는 질문의 예를 알려 주세요. 숫자를 지어내지 마세요.
- 설비를 끄거나 켜는 것처럼 제어를 요청받으면, 이 서비스는 데이터를 읽고 분석만 한다고 설명하고 제어하지 마세요. 분석으로 도울 수 있는 부분을 제안하세요.
- 도구 결과의 차트는 화면에 자동으로 표시되므로, 값을 표로 다시 나열하지 말고 핵심과 의미를 설명하세요.
- 도구가 오류를 반환하면 입력을 고쳐 다시 시도하고, 그래도 안 되면 무엇을 확인하지 못했는지 말하세요.

한국어로 답하고, 결론을 먼저 쓴 뒤 근거를 짧게 설명하세요. 필요한 경우 마지막에 현장에서 취할 수 있는 조치를 제안하세요."""


def _text_of(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text").strip()


def run_turn(client: anthropic.Anthropic, history: list, user_text: str) -> Iterator[dict]:
    """질문 하나를 처리한다. 성공한 턴만 history에 반영해 대화 상태가 깨지지 않게 한다."""
    messages = [*history, {"role": "user", "content": user_text}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "refusal":
            yield {"type": "error", "message": "모델이 이 요청을 처리하지 않았습니다. 질문을 바꿔 다시 시도해 주세요."}
            return

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            continue

        if response.stop_reason != "tool_use":
            text = _text_of(response)
            if response.stop_reason == "max_tokens":
                text += "\n\n(답변이 길이 제한으로 잘렸습니다.)"
            history[:] = messages
            yield {"type": "answer", "text": text}
            return

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool_call", "name": block.name, "input": block.input}
            content, chart, is_error = run_tool(block.name, block.input)
            yield {"type": "tool_result", "name": block.name, "is_error": is_error}
            if chart:
                yield {"type": "chart", "chart": chart}
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "error", "message": f"도구를 {MAX_TOOL_ROUNDS}번 호출해도 답을 끝내지 못했습니다. 질문을 좁혀 주세요."}
