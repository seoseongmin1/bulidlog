import { useEffect, useState } from "react";
import { getJson } from "../api.js";
import { useAsync } from "../useAsync.js";
import AsyncPanel, { ErrorNotice } from "./AsyncPanel.jsx";
import MarkdownView from "./MarkdownView.jsx";

export const MIN_DATE = "2018-01-01";
export const MAX_DATE = "2018-12-31";

/** 보고서를 브라우저의 다운로드 폴더에 energy-report-날짜.md 파일로 저장한다. */
function downloadMarkdown(markdown, date) {
  const url = URL.createObjectURL(new Blob([`${markdown}\n`], { type: "text/markdown;charset=utf-8" }));
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = `energy-report-${date}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export default function Report({ date, onDateChange, sectionRef }) {
  const inRange = Boolean(date) && date >= MIN_DATE && date <= MAX_DATE;
  const state = useAsync(() => (inRange ? getJson(`/api/report/${date}`) : Promise.resolve(null)), [date, inRange]);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => setSaveError(null), [date]);

  const save = (markdown) => {
    try {
      downloadMarkdown(markdown, date);
      setSaveError(null);
    } catch (error) {
      setSaveError(error instanceof Error && error.message ? error.message : "알 수 없는 오류입니다.");
    }
  };

  return (
    <section className="card" ref={sectionRef} aria-label="일일 보고서">
      <div className="card-head">
        <h2>일일 보고서</h2>
        <input
          type="date"
          aria-label="보고서 날짜"
          min={MIN_DATE}
          max={MAX_DATE}
          value={date}
          onChange={(event) => onDateChange(event.target.value)}
        />
      </div>

      {!date && (
        <p className="range-notice" role="status">
          날짜를 골라 주세요.
        </p>
      )}
      {date && !inRange && (
        <p className="range-notice" role="alert">
          고를 수 있는 기간은 2018년 1월 1일부터 12월 31일까지입니다.
        </p>
      )}

      {inRange && (
        <AsyncPanel state={state} title="보고서를 불러오지 못했습니다.">
          {(data) => (
            <>
              <MarkdownView text={data.markdown} />
              <div className="report-actions">
                <button type="button" className="save-button" onClick={() => save(data.markdown)}>
                  보고서 .md 파일로 저장
                </button>
              </div>
              {saveError && (
                <ErrorNotice
                  title="보고서 파일을 저장하지 못했습니다."
                  message={saveError}
                  onRetry={() => save(data.markdown)}
                />
              )}
            </>
          )}
        </AsyncPanel>
      )}
    </section>
  );
}
