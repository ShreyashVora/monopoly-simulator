import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type {
  AnalysisOverview,
  GameAnalysis,
  ObservedTransitions,
} from "../types";

function money(value: number) {
  return `$${value.toLocaleString()}`;
}

function timelineOption(
  data: GameAnalysis,
  metric: "net_worth" | "cash" | "properties",
  title: string,
) {
  const values = data.timeline[metric];
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) =>
        metric === "properties" ? `${value}` : money(value),
    },
    legend: { top: 0, type: "scroll" },
    grid: { left: 64, right: 22, top: 42, bottom: 34 },
    xAxis: {
      type: "category",
      data: data.timeline.labels,
      axisLabel: {
        interval: Math.max(0, Math.floor(data.timeline.labels.length / 8)),
      },
    },
    yAxis: {
      type: "value",
      name: title,
      axisLabel: {
        formatter: (value: number) =>
          metric === "properties" ? `${value}` : `$${value}`,
      },
    },
    series: data.players.map((player) => ({
      name: player.name,
      type: "line",
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2.5, color: player.color },
      itemStyle: { color: player.color },
      data: values[player.pid] ?? [],
    })),
  };
}

function observedHeatmapOption(transitions: ObservedTransitions) {
  const { labels, counts } = transitions;
  const rowTotals = counts.map((row) => row.reduce((sum, n) => sum + n, 0));
  const points: Array<[number, number, number]> = [];
  counts.forEach((row, source) =>
    row.forEach((count, target) => {
      if (count > 0) points.push([target, source, count]);
    }),
  );
  const max = Math.max(1, ...points.map((point) => point[2]));
  return {
    tooltip: {
      formatter: (point: { value: [number, number, number] }) => {
        const [target, source, count] = point.value;
        const share = rowTotals[source]
          ? Math.round((count / rowTotals[source]) * 100)
          : 0;
        return `${labels[source]} → ${labels[target]}<br/>${count} observed move${
          count === 1 ? "" : "s"
        }<br/>${share}% of moves from ${labels[source]}`;
      },
    },
    grid: { left: 85, right: 60, top: 55, bottom: 90 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: 60, fontSize: 7, interval: 0 },
      splitArea: { show: true },
    },
    yAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 7, interval: 0 },
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max,
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
}

function hittingOption(overview: AnalysisOverview, target: string) {
  const values = overview.hittingTimes[target] ?? [];
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) => `${value.toFixed(1)} rolls`,
    },
    grid: { left: 55, right: 18, top: 24, bottom: 100 },
    xAxis: {
      type: "category",
      data: overview.labels,
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
}

export function GameAnalysisPage() {
  const { runId = "" } = useParams();
  const [data, setData] = useState<GameAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<AnalysisOverview | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [target, setTarget] = useState("Jail");

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api
      .gameAnalysis(runId)
      .then((report) => {
        if (alive) setData(report);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [runId]);

  useEffect(() => {
    let alive = true;
    setOverview(null);
    setOverviewError(null);
    api
      .analysis()
      .then((model) => {
        if (!alive) return;
        setOverview(model);
        setTarget((current) =>
          model.labels.includes(current) ? current : (model.labels[0] ?? ""),
        );
      })
      .catch((e: Error) => {
        if (alive) setOverviewError(e.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <div className="card">
        <div className="error-box">{error}</div>
        <p>
          <Link to="/analysis">Back to analysis</Link>
        </p>
      </div>
    );
  }
  if (!data) return <div className="loading">Loading game analysis…</div>;

  const winner =
    data.winner !== null
      ? data.players.find((player) => player.pid === data.winner)
      : null;
  const actionRows = Object.entries(data.actions);

  return (
    <>
      <h1 className="page-title">
        {data.run.label}
        <small>
          {data.run.n_players} players {"\u00b7"} {data.steps} steps{" "}
          {"\u00b7"} {data.turns} turns
          {winner ? ` \u00b7 ${winner.name} wins` : ""}
        </small>
      </h1>
      <div className="analysis-toolbar">
        <Link className="mbtn" to="/analysis">
          All promoted games
        </Link>
        <span className="pill promoted">promoted</span>
      </div>

      <div className="kpi-grid">
        <div className="card kpi">
          <span>Winner</span>
          <strong>
            {winner ? `${winner.glyph} ${winner.name}` : "No winner"}
          </strong>
        </div>
        <div className="card kpi">
          <span>Final net worth</span>
          <strong>{winner ? money(winner.final_net_worth) : "—"}</strong>
        </div>
        <div className="card kpi">
          <span>Steps</span>
          <strong>{data.steps}</strong>
        </div>
        <div className="card kpi">
          <span>Bankruptcies</span>
          <strong>{data.bankrupt_count}</strong>
        </div>
      </div>

      <div className="analysis-grid">
        <div className="card span-2">
          <div className="panel-head">
            <h2>Final standings</h2>
            <span className="pill">ranked by net worth</span>
          </div>
          <div className="table-scroll">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Player</th>
                  <th>Net worth</th>
                  <th>Cash</th>
                  <th>Properties</th>
                  <th>Monopolies</th>
                  <th>Houses</th>
                  <th>Hotels</th>
                  <th>Mortgaged</th>
                  <th>Peak net worth</th>
                </tr>
              </thead>
              <tbody>
                {data.players.map((player, index) => (
                  <tr
                    key={player.pid}
                    className={player.pid === data.winner ? "winner-row" : ""}
                  >
                    <td>{index + 1}</td>
                    <td>
                      <span
                        className="player-dot"
                        style={{ background: player.color }}
                      />
                      {player.glyph} {player.name}
                      {player.bankrupt ? " · bankrupt" : ""}
                    </td>
                    <td>{money(player.final_net_worth)}</td>
                    <td>{money(player.final_cash)}</td>
                    <td>{player.properties}</td>
                    <td>{player.monopolies}</td>
                    <td>{player.houses}</td>
                    <td>{player.hotels}</td>
                    <td>{player.mortgaged}</td>
                    <td>{money(player.peak_net_worth)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card span-2">
          <div className="panel-head">
            <h2>Net worth over time</h2>
            <span className="pill">cash + property equity</span>
          </div>
          <ReactECharts
            option={timelineOption(data, "net_worth", "net worth")}
            style={{ height: 320 }}
            notMerge
          />
        </div>

        <div className="card">
          <div className="panel-head">
            <h2>Cash over time</h2>
          </div>
          <ReactECharts
            option={timelineOption(data, "cash", "cash")}
            style={{ height: 280 }}
            notMerge
          />
        </div>

        <div className="card">
          <div className="panel-head">
            <h2>Property count over time</h2>
          </div>
          <ReactECharts
            option={timelineOption(data, "properties", "properties")}
            style={{ height: 280 }}
            notMerge
          />
        </div>

        <div className="card span-2">
          <div className="panel-head">
            <h2>Observed moves heatmap</h2>
            <span className="pill">
              {data.observed_transitions.total} recorded moves
            </span>
          </div>
          <p className="analysis-note">
            Actual square-to-square moves in this game, including card and jail
            relocations. Tooltips show move counts and each source's share.
          </p>
          {data.observed_transitions.total === 0 ? (
            <div className="empty">No recorded moves.</div>
          ) : (
            <ReactECharts
              option={observedHeatmapOption(data.observed_transitions)}
              style={{ height: 500 }}
              notMerge
            />
          )}
        </div>

        <div className="card">
          <div className="panel-head">
            <h2>Expected rolls to target</h2>
            <select
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              aria-label="target square"
              disabled={!overview}
            >
              {(overview?.labels ?? []).map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <p className="analysis-note">
            Dice-only board baseline, independent of this game's players and
            policy. It includes the Go To Jail redirect.
          </p>
          {overviewError ? (
            <div className="error-box">{overviewError}</div>
          ) : overview ? (
            <ReactECharts
              option={hittingOption(overview, target)}
              style={{ height: 280 }}
              notMerge
            />
          ) : (
            <div className="empty">Loading dice baseline…</div>
          )}
        </div>

        <div className="card">
          <div className="panel-head">
            <h2>Dice totals</h2>
            <span className="pill">{actionRows.length} action types</span>
          </div>
          <ReactECharts
            option={{
              tooltip: { trigger: "axis" },
              grid: { left: 44, right: 18, top: 20, bottom: 34 },
              xAxis: {
                type: "category",
                data: Object.keys(data.rolls),
              },
              yAxis: { type: "value", name: "rolls" },
              series: [
                {
                  type: "bar",
                  data: Object.values(data.rolls),
                  itemStyle: { color: "#ed1b24" },
                  barMaxWidth: 24,
                },
              ],
            }}
            style={{ height: 280 }}
            notMerge
          />
        </div>

        <div className="card span-2">
          <div className="panel-head">
            <h2>Action mix</h2>
          </div>
          {actionRows.length === 0 ? (
            <div className="empty">No steps recorded.</div>
          ) : (
            <div className="action-bars">
              {actionRows.map(([action, count]) => (
                <div className="action-row" key={action}>
                  <span>{action.replaceAll("_", " ")}</span>
                  <div className="action-track">
                    <div
                      className="action-fill"
                      style={{
                        width: `${(count / data.steps) * 100}%`,
                      }}
                    />
                  </div>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
