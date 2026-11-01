import { useCallback, useEffect, useState } from "react";

/**
 * 데이터를 불러오는 상태(loading, ready, error)와 다시 시도 함수를 돌려준다.
 * 결과에는 어느 요청의 것인지(key)를 함께 기억해, 날짜처럼 입력이 바뀐 직후에는
 * 이전 요청의 결과를 보여 주지 않고 곧바로 loading으로 본다.
 */
export function useAsync(load, deps) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([...deps, attempt]);
  const [state, setState] = useState({ key, status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ key, status: "loading", data: null, error: null });
    load().then(
      (data) => {
        if (!cancelled) setState({ key, status: "ready", data, error: null });
      },
      (error) => {
        if (!cancelled) setState({ key, status: "error", data: null, error });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const current = state.key === key ? state : { status: "loading", data: null, error: null };
  return { status: current.status, data: current.data, error: current.error, retry };
}
