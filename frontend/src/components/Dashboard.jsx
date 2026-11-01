import { getJson } from "../api.js";
import { number } from "../format.js";
import { useAsync } from "../useAsync.js";
import AsyncPanel from "./AsyncPanel.jsx";
import Chart from "./Chart.jsx";

function Kpis({ summary }) {
  const shares = summary["부하별_사용량_비중_pct"];
  const items = [
    ["연간 사용량", `${number(summary.usage_kwh / 1000, 1)} MWh`, `일평균 ${number(summary["일평균_kwh"])} kWh`],
    ["최대 수요전력", `${number(summary.peak_kw, 1)} kW`, summary.peak_at],
    ["지상 역률", `${summary.power_factor}%`, "사용량 가중 평균"],
    ["CO2 배출량", `${number(summary.co2_t, 1)} tCO2`, "연간 합계"],
    ["최대부하 비중", `${shares["최대부하"]}%`, "전체 사용량 대비"],
  ];
  return (
    <div className="kpis">
      {items.map(([label, value, note]) => (
        <div className="kpi" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small>{note}</small>
        </div>
      ))}
    </div>
  );
}

function ChartCard({ title, unit, wide, children }) {
  return (
    <figure className={`card${wide ? " wide" : ""}`}>
      <figcaption>
        <h2>{title}</h2>
        <span>{unit}</span>
      </figcaption>
      <div className="chart">{children}</div>
    </figure>
  );
}

export default function Dashboard() {
  const state = useAsync(() => getJson("/api/dashboard"), []);

  return (
    <section className="dashboard-panel" aria-label="대시보드">
      <AsyncPanel state={state} title="대시보드 데이터를 불러오지 못했습니다.">
        {(data) => (
          <>
            <Kpis summary={data.summary} />
            <div className="grid">
              <ChartCard title="월별 전력 사용량" unit="kWh">
                <Chart
                  kind="bar"
                  unit="kWh"
                  label="월별 전력 사용량 막대 차트"
                  rows={data.monthly.map((row) => ({ ...row, label: `${row.label.slice(5)}월` }))}
                />
              </ChartCard>
              <ChartCard title="시간대별 평균 사용량" unit="kWh/일">
                <Chart kind="bar" unit="kWh/일" label="시간대별 일평균 사용량 막대 차트" rows={data.hourly_profile} />
              </ChartCard>
              <ChartCard title="일별 전력 사용량" unit="kWh" wide>
                <Chart kind="line" unit="kWh" label="일별 전력 사용량 선 차트" rows={data.daily} />
              </ChartCard>
            </div>
          </>
        )}
      </AsyncPanel>
    </section>
  );
}
