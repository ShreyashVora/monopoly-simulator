import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { api } from "../api";
import type { AnalysisOverview } from "../types";

export function AnalysisPage() {
  const [data, setData] = useState<AnalysisOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState("Jail");

  useEffect(() => {
    let alive = true;
    api
      .analysis()
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  const stationaryOption = useMemo(() => {
    if (!data) return null;
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: number) => `${(v * 100).toFixed(2)}%`,
      },
      grid: { left: 50, right: 18, top: 24, bottom: 110 },
      xAxis: {
        type: "category",
        data: data.labels,
        axisLabel: { rotate: 55, fontSize: 9, interval: 0 },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      },
      series: [
        {
          type: "bar",
          data: data.stationary,
          itemStyle: { color: "#ed1b24" },
          barMaxWidth: 16,
        },
      ],
    };
  }, [data]);

  const matrixOption = useMemo(() => {
    if (!data) return null;
    const points: Array<[number, number, number]> = [];
    data.matrix.forEach((row, i) =>
      row.forEach((v, j) => {
        if (v > 0) points.push([j, i, v]);
      }),
    );
    return {
      tooltip: {
        formatter: (p: { value: [number, number, number] }) =>
          `${data.labels[p.value[1]]} → ${data.labels[p.value[0]]}<br/>${(
            p.value[2] * 100
          ).toFixed(2)}%`,
      },
      grid: { left: 85, right: 60, top: 55, bottom: 90 },
      xAxis: {
        type: "category",
        data: data.labels,
        axisLabel: { rotate: 60, fontSize: 7, interval: 0 },
        splitArea: { show: true },
      },
      yAxis: {
        type: "category",
        data: data.labels,
        axisLabel: { fontSize: 7, interval: 0 },
        splitArea: { show: true },
      },
      visualMap: {
        min: 0,
        max: Math.max(...data.matrix.flat()),
        calculable: true,
        orient: "vertical",
        right: 0,
        top: "middle",
        inRange: { color: ["#f7f4e9", "#ffd23f", "#ed1b24", "#5a0008"] },
      },
      series: [
        {
          type: "heatmap",
          data: points,
          progressive: 2000,
          emphasis: {
            itemStyle: { borderColor: "#111", borderWidth: 1 },
          },
        },
      ],
    };
  }, [data]);

  const hittingOption = useMemo(() => {
    if (!data) return null;
    const values = data.hittingTimes[target] ?? [];
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: number) => `${v.toFixed(1)} rolls`,
      },
      grid: { left: 55, right: 18, top: 24, bottom: 100 },
      xAxis: {
        type: "category",
        data: data.labels,
        axisLabel: { rotate: 55, fontSize: 9, interval: 0 },
      },
      yAxis: { type: "value", name: "rolls" },
      series: [
        {
          type: "bar",
          data: values,
          itemStyle: { color: "#16213e" },
          barMaxWidth: 14,
        },
      ],
    };
  }, [data, target]);

  if (error) {
    return <div className="error-box">{error}</div>;
  }
  if (!data) return <div className="loading">Building Markov chain…</div>;

  const top = data.labels
    .map((label, i) => ({ label, p: data.stationary[i] }))
    .sort((a, b) => b.p - a.p)
    .slice(0, 8);

  return (
    <>
      <h1 className="page-title">
        Analysis
        <small>{data.note}</small>
      </h1>
      <div className="analysis-grid">
        <div className="card span-2">
          <div className="panel-head">
            <h2>Stationary distribution</h2>
            <span className="pill">long-run occupancy</span>
          </div>
          <p className="analysis-note">
            Fraction of turns spent on each square if the dice were the only
            thing moving players. Jail is the strongest attractor.
          </p>
          <ReactECharts
            option={stationaryOption!}
            style={{ height: 320 }}
            notMerge
          />
        </div>
        <div className="card span-2">
          <div className="panel-head">
            <h2>Transition matrix</h2>
            <span className="pill">one row = one roll</span>
          </div>
          <p className="analysis-note">
            Every row sums to 1. Only the 11 dice totals have mass; the Go To
            Jail square redirects its incoming mass to Jail.
          </p>
          <ReactECharts
            option={matrixOption!}
            style={{ height: 520 }}
            notMerge
          />
        </div>
        <div className="card">
          <div className="panel-head">
            <h2>Expected hitting time</h2>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              aria-label="target square"
            >
              {data.labels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <p className="analysis-note">
            Expected number of rolls to land on {target} from every start
            square.
          </p>
          <ReactECharts
            option={hittingOption!}
            style={{ height: 320 }}
            notMerge
          />
        </div>
        <div className="card">
          <div className="panel-head">
            <h2>Most visited</h2>
          </div>
          <table className="hits-table">
            <thead>
              <tr>
                <th>Square</th>
                <th>Share</th>
                <th>Hitting time</th>
              </tr>
            </thead>
            <tbody>
              {top.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{(row.p * 100).toFixed(2)}%</td>
                  <td>
                    {(data.hittingTimes[row.label]?.[0] ?? 0).toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
