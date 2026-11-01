import { vi } from "vitest";

export const ok = (body) => ({ ok: true, status: 200, json: async () => body });
export const failed = (status, detail) => ({ ok: false, status, json: async () => ({ detail }) });

/** 그래프 그리기는 브라우저 캔버스가 필요하므로 테스트에서는 자리표시만 만든다. */
export const chartMock = () => ({
  default: ({ label, rows }) => <div data-testid="chart" aria-label={label} data-points={rows.length} />,
});

export const stubFetch = (handler) => {
  const fetchMock = vi.fn(handler);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};
