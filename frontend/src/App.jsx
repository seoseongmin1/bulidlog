import { useRef, useState } from "react";
import Anomalies from "./components/Anomalies.jsx";
import Chat from "./components/Chat.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Report from "./components/Report.jsx";

export const DEFAULT_REPORT_DATE = "2018-12-16";

export default function App() {
  const [date, setDate] = useState(DEFAULT_REPORT_DATE);
  const reportSection = useRef(null);

  const openReport = (next) => {
    setDate(next);
    reportSection.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  };

  return (
    <>
      <header className="topbar">
        <h1>공장 에너지 에이전트</h1>
        <p>대우스틸 광양공장 2018년 전력 실측 데이터 · 15분 간격 35,040건</p>
      </header>

      <main className="layout">
        <div className="left">
          <Dashboard />
          <Anomalies onSelect={openReport} />
          <Report date={date} onDateChange={setDate} sectionRef={reportSection} />
        </div>
        <Chat />
      </main>

      <footer className="footer">
        데이터:{" "}
        <a href="https://archive.ics.uci.edu/dataset/851/steel+industry+energy+consumption" rel="noopener">
          UCI Steel Industry Energy Consumption
        </a>{" "}
        (CC BY 4.0)
      </footer>
    </>
  );
}
