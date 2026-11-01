import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { failed, ok, stubFetch } from "../test/helpers.jsx";
import Anomalies from "./Anomalies.jsx";

const dates = ["2018-12-16", "2018-05-26", "2018-12-08", "2018-05-20", "2018-05-19", "2018-09-01", "2018-11-17", "2018-01-01"];
const ITEMS = dates.map((date, index) => ({
  date,
  요일: "일",
  방향: date === "2018-01-01" ? "낮음" : "높음",
  usage_kwh: 2000 - index * 100,
  기준선_kwh: 366.3,
  편차_pct: date === "2018-01-01" ? -92.9 : 450 - index,
  휴일: date === "2018-01-01" ? "신정" : null,
}));

afterEach(() => vi.unstubAllGlobals());

test("정확히 8일이 보이고 신정은 사용량이 적은 날로 표시된다", async () => {
  stubFetch(() => Promise.resolve(ok({ items: ITEMS })));
  render(<Anomalies onSelect={() => {}} />);

  const rows = await screen.findAllByRole("row");
  expect(rows).toHaveLength(9); // 제목 줄 1 + 8일
  expect(within(rows[1]).getByRole("button")).toHaveTextContent("2018-12-16");

  const newYear = rows[8];
  expect(newYear).toHaveTextContent("▼ 낮음");
  expect(newYear).toHaveTextContent("신정");
  expect(newYear).toHaveTextContent("-92.9%");
  expect(rows[1]).toHaveTextContent("▲ 높음");
  expect(rows[1]).toHaveTextContent("+450%");
});

test("날짜를 누르면 그 날짜가 전달된다", async () => {
  stubFetch(() => Promise.resolve(ok({ items: ITEMS })));
  const onSelect = vi.fn();
  render(<Anomalies onSelect={onSelect} />);

  await userEvent.click(await screen.findByRole("button", { name: /2018-05-26/ }));
  expect(onSelect).toHaveBeenCalledWith("2018-05-26");
});

test("불러오지 못하면 이 영역에만 안내문과 다시 시도 버튼이 보인다", async () => {
  const fetchMock = stubFetch(() => Promise.resolve(ok({ items: ITEMS })));
  fetchMock.mockResolvedValueOnce(failed(503, "데이터베이스에서 전력 데이터를 읽지 못했습니다."));
  render(<Anomalies onSelect={() => {}} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("이상한 날 목록을 불러오지 못했습니다.");
  await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(await screen.findAllByRole("row")).toHaveLength(9);
});
