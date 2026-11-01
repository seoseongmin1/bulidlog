import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { failed, ok, stubFetch } from "../test/helpers.jsx";
import Report from "./Report.jsx";

const reportFor = (date) => ({
  markdown: `# 일일 에너지 보고서: ${date}\n\n| 항목 | 값 |\n|---|---|\n| 전력 사용량 | 2,014.66 kWh |`,
});
const answerReports = (url) => Promise.resolve(ok(reportFor(url.split("/").pop())));

function Harness({ initial = "2018-12-16" }) {
  const [date, setDate] = useState(initial);
  return <Report date={date} onDateChange={setDate} />;
}

const readBlob = (blob) =>
  new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsText(blob);
  });

let downloads;
let blobs;

beforeEach(() => {
  downloads = [];
  blobs = [];
  URL.createObjectURL = vi.fn((blob) => {
    blobs.push(blob);
    return "blob:test";
  });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function click() {
    downloads.push(this.download);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("처음에는 날짜 범위가 정해진 상태로 12월 16일 보고서가 보인다", async () => {
  const fetchMock = stubFetch(answerReports);
  render(<Harness />);

  expect(await screen.findByText("2,014.66 kWh")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/report/2018-12-16");
  const input = screen.getByLabelText("보고서 날짜");
  expect(input).toHaveValue("2018-12-16");
  expect(input).toHaveAttribute("min", "2018-01-01");
  expect(input).toHaveAttribute("max", "2018-12-31");
});

test("다른 날짜로 바꾸면 그 날짜의 보고서가 보인다", async () => {
  const fetchMock = stubFetch(answerReports);
  render(<Harness />);
  await screen.findByRole("heading", { name: /2018-12-16/ });

  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "2018-05-26" } });
  expect(await screen.findByRole("heading", { name: /2018-05-26/ })).toBeInTheDocument();
  expect(fetchMock).toHaveBeenLastCalledWith("/api/report/2018-05-26");
});

test("범위 밖 날짜를 입력하면 고를 수 있는 기간을 안내하고 서버에 묻지 않는다", async () => {
  const fetchMock = stubFetch(answerReports);
  render(<Harness />);
  await screen.findByText("2,014.66 kWh");

  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "2019-01-01" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("고를 수 있는 기간은 2018년 1월 1일부터 12월 31일까지입니다.");
  expect(fetchMock).not.toHaveBeenCalledWith("/api/report/2019-01-01");
  expect(screen.queryByRole("button", { name: /저장/ })).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "2018-03-01" } });
  expect(await screen.findByRole("heading", { name: /2018-03-01/ })).toBeInTheDocument();
});

test("날짜를 바꾼 직후에는 이전 날짜의 보고서와 저장 버튼을 보여 주지 않는다", async () => {
  let release;
  const fetchMock = stubFetch(answerReports);
  render(<Harness />);
  await screen.findByRole("heading", { name: /2018-12-16/ });

  fetchMock.mockImplementationOnce(
    () => new Promise((resolve) => (release = () => resolve(ok(reportFor("2018-05-26"))))),
  );
  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "2018-05-26" } });

  expect(screen.queryByRole("heading", { name: /2018-12-16/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /저장/ })).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("불러오는 중");

  release();
  expect(await screen.findByRole("heading", { name: /2018-05-26/ })).toBeInTheDocument();
});

test("저장 버튼은 날짜가 들어간 .md 파일을 화면과 같은 내용으로 저장한다", async () => {
  stubFetch(answerReports);
  render(<Harness />);
  await screen.findByText("2,014.66 kWh");

  await userEvent.click(screen.getByRole("button", { name: "보고서 .md 파일로 저장" }));

  expect(downloads).toEqual(["energy-report-2018-12-16.md"]);
  expect(await readBlob(blobs[0])).toBe(`${reportFor("2018-12-16").markdown}\n`);
});

test("다른 날짜의 보고서는 그 날짜 이름으로 저장된다", async () => {
  stubFetch(answerReports);
  render(<Harness />);
  await screen.findByText("2,014.66 kWh");

  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "2018-01-01" } });
  await screen.findByRole("heading", { name: /2018-01-01/ });
  await userEvent.click(screen.getByRole("button", { name: "보고서 .md 파일로 저장" }));

  expect(downloads).toEqual(["energy-report-2018-01-01.md"]);
});

test("저장에 실패하면 안내문과 다시 시도 버튼이 보이고, 다시 누르면 저장된다", async () => {
  stubFetch(answerReports);
  render(<Harness />);
  await screen.findByText("2,014.66 kWh");

  URL.createObjectURL = vi.fn(() => {
    throw new Error("저장 공간이 없습니다.");
  });
  await userEvent.click(screen.getByRole("button", { name: "보고서 .md 파일로 저장" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("보고서 파일을 저장하지 못했습니다.");
  expect(alert).toHaveTextContent("저장 공간이 없습니다.");
  expect(downloads).toEqual([]);

  URL.createObjectURL = vi.fn((blob) => {
    blobs.push(blob);
    return "blob:test";
  });
  await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(downloads).toEqual(["energy-report-2018-12-16.md"]);
});

test("보고서를 불러오지 못하면 보고서 영역에 안내문과 다시 시도 버튼이 보인다", async () => {
  const fetchMock = stubFetch(answerReports);
  fetchMock.mockResolvedValueOnce(failed(503, "데이터베이스 파일이 없습니다."));
  render(<Harness />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("보고서를 불러오지 못했습니다.");
  expect(alert).toHaveTextContent("데이터베이스 파일이 없습니다.");
  expect(screen.queryByRole("button", { name: /저장/ })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(await screen.findByText("2,014.66 kWh")).toBeInTheDocument();
});

test("날짜 칸을 비우면 날짜를 고르라고 안내한다", async () => {
  stubFetch(answerReports);
  render(<Harness />);
  await screen.findByText("2,014.66 kWh");

  fireEvent.change(screen.getByLabelText("보고서 날짜"), { target: { value: "" } });
  expect(await screen.findByRole("status")).toHaveTextContent("날짜를 골라 주세요.");
});
