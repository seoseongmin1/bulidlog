import { getJson } from "../api.js";
import { number } from "../format.js";
import { useAsync } from "../useAsync.js";
import AsyncPanel from "./AsyncPanel.jsx";

/** 평소와 가장 크게 다른 날 목록. 날짜를 누르면 onSelect(날짜)로 그날의 보고서를 연다. */
export default function Anomalies({ onSelect }) {
  const state = useAsync(() => getJson("/api/anomalies"), []);

  return (
    <section className="card" aria-label="이상한 날">
      <div className="card-head">
        <h2>이상한 날</h2>
        <span>주변 같은 요일 유형 대비</span>
      </div>
      <AsyncPanel state={state} title="이상한 날 목록을 불러오지 못했습니다.">
        {({ items }) => (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>방향</th>
                  <th className="num">사용량 (kWh)</th>
                  <th className="num">기준선 (kWh)</th>
                  <th className="num">편차</th>
                  <th>휴일</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.date}>
                    <td>
                      <button type="button" className="date-button" onClick={() => onSelect(item.date)}>
                        {item.date} ({item["요일"]})
                      </button>
                    </td>
                    <td>{item["방향"] === "높음" ? "▲ 높음" : "▼ 낮음"}</td>
                    <td className="num">{number(item.usage_kwh)}</td>
                    <td className="num">{number(item["기준선_kwh"])}</td>
                    <td className="num">
                      {item["편차_pct"] > 0 ? "+" : ""}
                      {item["편차_pct"]}%
                    </td>
                    <td>{item["휴일"] || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AsyncPanel>
    </section>
  );
}
