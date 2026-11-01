import { useEffect, useRef, useState } from "react";
import Chart from "./Chart.jsx";
import MarkdownView from "./MarkdownView.jsx";

export const SUGGESTIONS = [
  "12월 16일 일요일에 왜 전력을 많이 썼을까?",
  "역률이 낮은 시간대와 개선 방향을 알려줘",
  "1월과 9월을 비교해줘",
  "최대 수요전력을 10% 낮추면 어떻게 돼?",
];
export const MAX_LENGTH = 2000;

const TOOL_LABELS = {
  get_dataset_info: "데이터 정보 확인",
  summarize_period: "기간 요약 계산",
  get_timeseries: "추이 집계",
  get_profile: "패턴 분석",
  compare_periods: "기간 비교",
  detect_anomalies: "이상 사용일 탐지",
  analyze_power_factor: "역률 분석",
  simulate_peak_cap: "최대 수요 시뮬레이션",
  get_daily_report: "일일 보고서 생성",
};

function Item({ item }) {
  switch (item.type) {
    case "user":
      return <div className="msg-user">{item.text}</div>;
    case "step": {
      const label = TOOL_LABELS[item.name] || item.name;
      return (
        <div className={`step${item.status === "failed" ? " failed" : ""}`}>
          {item.status === "running" ? `${label} 중…` : `✓ ${label}`}
        </div>
      );
    }
    case "chart":
      return (
        <div className="inline-chart">
          <h3>
            {item.chart.title} · {item.chart.unit}
          </h3>
          <div className="chart">
            <Chart kind={item.chart.kind} rows={item.chart.rows} unit={item.chart.unit} label={item.chart.title} />
          </div>
        </div>
      );
    case "answer":
      return <MarkdownView text={item.text} />;
    case "error":
      return (
        <div className="msg-error" role="alert">
          {item.text}
        </div>
      );
    default:
      return null;
  }
}

export default function Chat() {
  const [items, setItems] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [agentReady, setAgentReady] = useState(true);
  const busyRef = useRef(false);
  const sessionId = useRef(null);
  const nextId = useRef(0);
  const list = useRef(null);

  useEffect(() => {
    fetch("/api/status")
      .then((response) => response.json())
      .then((status) => setAgentReady(Boolean(status.agent_ready)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [items, busy]);

  const add = (item) => setItems((current) => [...current, { id: nextId.current++, ...item }]);

  function handleEvent(event) {
    if (event.type === "session") {
      sessionId.current = event.session_id;
    } else if (event.type === "tool_call") {
      add({ type: "step", name: event.name, status: "running" });
    } else if (event.type === "tool_result") {
      setItems((current) => {
        const index = current.findLastIndex(
          (item) => item.type === "step" && item.name === event.name && item.status === "running",
        );
        if (index < 0) return current;
        const next = [...current];
        next[index] = { ...next[index], status: event.is_error ? "failed" : "done" };
        return next;
      });
    } else if (event.type === "chart") {
      add({ type: "chart", chart: event.chart });
    } else if (event.type === "answer") {
      add({ type: "answer", text: event.text });
    } else if (event.type === "error") {
      add({ type: "error", text: event.message });
    }
  }

  async function ask(raw) {
    const text = raw.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setInput("");
    add({ type: "user", text });

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId.current }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          if (chunk.startsWith("data: ")) handleEvent(JSON.parse(chunk.slice(6)));
        }
      }
    } catch (error) {
      add({ type: "error", text: `서버와 통신하지 못했습니다 (${error.message}).` });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <aside className="agent" aria-label="에너지 에이전트">
      <div className="agent-head">
        <h2>에이전트에게 묻기</h2>
        <p>모든 수치는 분석 도구가 계산합니다.</p>
      </div>

      {!agentReady && (
        <div className="notice" role="status">
          대화를 사용하려면 <code>backend/.env</code> 파일에 <code>ANTHROPIC_API_KEY</code>를 넣고 서버를 다시 시작하세요.
          대시보드와 보고서는 키 없이 작동합니다.
        </div>
      )}

      <div className="messages" ref={list} aria-live="polite">
        {items.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((question) => (
              <button key={question} type="button" onClick={() => ask(question)}>
                {question}
              </button>
            ))}
          </div>
        )}
        {items.map((item) => (
          <Item key={item.id} item={item} />
        ))}
        {busy && (
          <div className="step" role="status">
            분석하는 중…
          </div>
        )}
      </div>

      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          ask(input);
        }}
      >
        <textarea
          rows={2}
          value={input}
          maxLength={MAX_LENGTH}
          placeholder="공장 에너지에 대해 물어보세요"
          aria-label="질문 입력"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              ask(input);
            }
          }}
        />
        <button type="submit" disabled={busy}>
          보내기
        </button>
      </form>
    </aside>
  );
}
