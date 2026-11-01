import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { chartMock, ok, stubFetch } from "../test/helpers.jsx";
import Chat, { MAX_LENGTH, SUGGESTIONS } from "./Chat.jsx";

vi.mock("./Chart.jsx", () => chartMock());

function sse(events) {
  const encoder = new TextEncoder();
  const chunks = events.map((event) => encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
  let index = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () => (index < chunks.length ? { value: chunks[index++], done: false } : { value: undefined, done: true }),
      }),
    },
  };
}

const ANSWER_EVENTS = [
  { type: "session", session_id: "s1" },
  { type: "tool_call", name: "get_timeseries", input: {} },
  { type: "tool_result", name: "get_timeseries", is_error: false },
  { type: "chart", chart: { title: "전력 사용량 (2018-12-16)", unit: "kWh", kind: "line", rows: [{ label: "a", value: 1 }, { label: "b", value: 2 }] } },
  { type: "tool_call", name: "detect_anomalies", input: {} },
  { type: "tool_result", name: "detect_anomalies", is_error: true },
  { type: "answer", text: "## 결론\n\n**12월 16일**은 평소의 5.5배입니다.\n\n<img src=x onerror=\"window.__xss=1\">" },
];

function stubServer({ ready = true, chat }) {
  return stubFetch((url, options) => {
    if (url === "/api/status") return Promise.resolve(ok({ agent_ready: ready }));
    return chat(url, options);
  });
}

const chatCalls = (fetchMock) => fetchMock.mock.calls.filter(([url]) => url === "/api/chat");
const box = () => screen.getByLabelText("질문 입력");
const sendButton = () => screen.getByRole("button", { name: "보내기" });

afterEach(() => vi.unstubAllGlobals());

test("추천 질문 4개가 보인다", () => {
  stubServer({ chat: () => Promise.resolve(sse([])) });
  render(<Chat />);
  expect(SUGGESTIONS).toHaveLength(4);
  for (const question of SUGGESTIONS) {
    expect(screen.getByRole("button", { name: question })).toBeInTheDocument();
  }
});

test("빈 질문이나 공백만 있는 질문은 보내지지 않고 화면도 바뀌지 않는다", async () => {
  const fetchMock = stubServer({ chat: () => Promise.resolve(sse([])) });
  render(<Chat />);

  await userEvent.click(sendButton());
  await userEvent.type(box(), "   ");
  await userEvent.click(sendButton());
  await userEvent.type(box(), "{Enter}");

  expect(chatCalls(fetchMock)).toHaveLength(0);
  expect(screen.getAllByRole("button", { name: /\?|줘|돼/ })).toHaveLength(4);
});

test("질문 입력 칸은 2,000자까지만 받는다", () => {
  stubServer({ chat: () => Promise.resolve(sse([])) });
  render(<Chat />);
  expect(MAX_LENGTH).toBe(2000);
  expect(box()).toHaveAttribute("maxlength", "2000");
});

test("추천 질문을 누르면 진행 단계, 그래프, 답변이 차례로 보인다", async () => {
  const fetchMock = stubServer({ chat: () => Promise.resolve(sse(ANSWER_EVENTS)) });
  render(<Chat />);

  await userEvent.click(screen.getByRole("button", { name: SUGGESTIONS[0] }));

  expect(await screen.findByRole("heading", { name: "결론" })).toBeInTheDocument();
  expect(screen.getByText("12월 16일")).toBeInTheDocument();
  expect(screen.getByText("✓ 추이 집계")).toBeInTheDocument();
  expect(screen.getByText("✓ 이상 사용일 탐지")).toHaveClass("failed");
  expect(screen.getByTestId("chart").dataset.points).toBe("2");
  expect(screen.getByText(SUGGESTIONS[0], { selector: ".msg-user" })).toBeInTheDocument();

  // 추천 질문은 대화가 시작되면 사라지고, AI 답변 속 HTML은 실행되지 않는다.
  expect(screen.queryByRole("button", { name: SUGGESTIONS[1] })).not.toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
  expect(window.__xss).toBeUndefined();

  const body = JSON.parse(chatCalls(fetchMock)[0][1].body);
  expect(body).toEqual({ message: SUGGESTIONS[0], session_id: null });
});

test("이어서 물으면 앞의 대화 번호를 함께 보낸다", async () => {
  const fetchMock = stubServer({ chat: () => Promise.resolve(sse(ANSWER_EVENTS)) });
  render(<Chat />);

  await userEvent.type(box(), "첫 질문{Enter}");
  await screen.findByRole("heading", { name: "결론" });
  await userEvent.type(box(), "그것도 자세히 알려줘{Enter}");
  await vi.waitFor(() => expect(chatCalls(fetchMock)).toHaveLength(2));

  const second = JSON.parse(chatCalls(fetchMock)[1][1].body);
  expect(second).toEqual({ message: "그것도 자세히 알려줘", session_id: "s1" });
});

test("서버가 보낸 오류(API 키 없음 등)를 대화 영역에 보여 주고 다시 보낼 수 있다", async () => {
  const fetchMock = stubServer({
    chat: () =>
      Promise.resolve(sse([{ type: "session", session_id: "s1" }, { type: "error", message: "ANTHROPIC_API_KEY가 없습니다." }])),
  });
  render(<Chat />);

  await userEvent.type(box(), "안녕{Enter}");
  expect(await screen.findByRole("alert")).toHaveTextContent("ANTHROPIC_API_KEY가 없습니다.");

  await userEvent.type(box(), "다시 질문{Enter}");
  await vi.waitFor(() => expect(chatCalls(fetchMock)).toHaveLength(2));
  expect(await screen.findAllByRole("alert")).toHaveLength(2);
});

test("서버에 연결하지 못하면 안내가 보이고 입력은 계속 쓸 수 있다", async () => {
  stubServer({ chat: () => Promise.reject(new TypeError("Failed to fetch")) });
  render(<Chat />);

  await userEvent.type(box(), "안녕{Enter}");
  expect(await screen.findByRole("alert")).toHaveTextContent("서버와 통신하지 못했습니다");
  expect(box()).toBeEnabled();
  expect(sendButton()).toBeEnabled();
});

test("API 키가 없으면 미리 안내한다", async () => {
  stubServer({ ready: false, chat: () => Promise.resolve(sse([])) });
  render(<Chat />);
  expect(await screen.findByRole("status")).toHaveTextContent("ANTHROPIC_API_KEY");
});
