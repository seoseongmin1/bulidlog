import { useEffect, useRef } from "react";
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { number } from "../format.js";

ChartJS.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
);

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** kind는 "bar" 또는 "line", rows는 [{label, value}] 목록이다. */
export default function Chart({ kind, rows, unit, label }) {
  const canvas = useRef(null);
  const rowsKey = JSON.stringify(rows);

  useEffect(() => {
    const series = cssVar("--series");
    const muted = cssVar("--muted");
    const chart = new ChartJS(canvas.current, {
      type: kind,
      data: {
        labels: rows.map((row) => row.label),
        datasets: [
          {
            data: rows.map((row) => row.value),
            backgroundColor: series,
            borderColor: series,
            borderWidth: 2,
            borderRadius: { topLeft: 4, topRight: 4 },
            borderSkipped: "bottom",
            maxBarThickness: 18,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            displayColors: false,
            callbacks: { label: (item) => `${number(item.parsed.y, 2)} ${unit}` },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: muted, autoSkipPadding: 14, maxRotation: 0 } },
          y: { grid: { color: cssVar("--grid") }, border: { display: false }, ticks: { color: muted, maxTicksLimit: 5 } },
        },
      },
    });
    return () => chart.destroy();
  }, [kind, unit, rowsKey]);

  return <canvas ref={canvas} role="img" aria-label={label} />;
}
