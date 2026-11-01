export function ErrorNotice({ title, message, onRetry }) {
  return (
    <div className="error-notice" role="alert">
      <p>
        <strong>{title}</strong>
        {message ? ` ${message}` : ""}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          다시 시도
        </button>
      )}
    </div>
  );
}

/** 불러오는 중이면 안내, 실패하면 안내문과 다시 시도 버튼, 성공하면 내용을 보여 준다. 영역마다 따로 쓴다. */
export default function AsyncPanel({ state, title, children }) {
  if (state.status === "loading") {
    return (
      <p className="muted" role="status">
        불러오는 중…
      </p>
    );
  }
  if (state.status === "error") {
    return <ErrorNotice title={title} message={state.error.message} onRetry={state.retry} />;
  }
  return children(state.data);
}
