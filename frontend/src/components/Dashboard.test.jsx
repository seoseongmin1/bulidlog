import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { chartMock, failed, ok, stubFetch } from "../test/helpers.jsx";
import Dashboard from "./Dashboard.jsx";

vi.mock("./Chart.jsx", () => chartMock());

const months = Array.from({ length: 12 }, (_, i) => ({ label: `2018-${String(i + 1).padStart(2, "0")}`, value: 1000 + i }));
const DASHBOARD = {
  summary: {
    usage_kwh: 959636.71,
    일평균_kwh: 2629.14,
    co2_t: 403.81,
    peak_kw: 628.72,
    peak_at: "2018-11-22 09:30",
    power_factor: 90.29,
    부하별_사용량_비중_pct: { 경부하: 16.2, 최대부하: 44.9, 중부하: 38.8 },
  },
  monthly: months,
  daily: Array.from({ length: 365 }, (_, i) => ({ label: `d${i}`, value: i })),
  hourly_profile: Array.from({ length: 24 }, (_, i) => ({ label: `${i}시`, value: i })),
};

afterEach(() => vi.unstubAllGlobals());

test("숫자 카드와 그래프 3개가 보인다", async () => {
  stubFetch(() => Promise.resolve(ok(DASHBOARD)));
  render(<Dashboard />);

  expect(await screen.findByText("959.6 MWh")).toBeInTheDocument();
  expect(screen.getByText("628.7 kW")).toBeInTheDocument();
  expect(screen.getByText("90.29%")).toBeInTheDocument();
  expect(screen.getByText("44.9%")).toBeInTheDocument();

  const charts = screen.getAllByTestId("chart");
  expect(charts.map((chart) => chart.dataset.points)).toEqual(["12", "24", "365"]);
});

test("불러오지 못하면 안내문과 다시 시도 버튼이 보이고, 누르면 복구된다", async () => {
  const fetchMock = stubFetch(() => Promise.resolve(ok(DASHBOARD)));
  fetchMock.mockRejectedValueOnce(new TypeError("network"));
  render(<Dashboard />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("대시보드 데이터를 불러오지 못했습니다.");
  expect(alert).toHaveTextContent("서버에 연결하지 못했습니다.");

  await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(await screen.findByText("959.6 MWh")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("서버가 알려 준 데이터베이스 문제를 그대로 보여 준다", async () => {
  stubFetch(() => Promise.resolve(failed(503, "데이터베이스 파일이 없습니다.")));
  render(<Dashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("데이터베이스 파일이 없습니다.");
});
