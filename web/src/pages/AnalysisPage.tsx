import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { RunSummary } from "../types";

function modeLabel(run: RunSummary) {
  if (run.kind === "mixed") {
    return `${run.agent_seats?.length ?? 0} agent${
      (run.agent_seats?.length ?? 0) === 1 ? "" : "s"
    }`;
  }
  return run.policy ?? "manual";
}

export function AnalysisPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .promotedGames()
      .then((data) => {
        if (alive) setRuns(data);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return <div className="error-box">{error}</div>;
  }
  if (!runs) return <div className="loading">Loading promoted games…</div>;

  return (
    <>
      <h1 className="page-title">
        Analysis
        <small>Only promoted completed games appear here.</small>
      </h1>

      {runs.length === 0 ? (
        <div className="card empty-analysis">
          <h2>No promoted games yet</h2>
          <p>
            Finish a game, then choose <strong>Promote for Analysis</strong> in
            the winner dialog or on the run replay page. Promoted games are
            stored on disk.
          </p>
          <Link className="mbtn" to="/play">
            Play a game
          </Link>
        </div>
      ) : (
        <>
          <div className="kpi-grid">
            <div className="card kpi">
              <span>Promoted games</span>
              <strong>{runs.length}</strong>
            </div>
            <div className="card kpi">
              <span>Table sizes</span>
              <strong>
                {new Set(runs.map((run) => run.n_players)).size}
              </strong>
            </div>
            <div className="card kpi">
              <span>Latest game</span>
              <strong>{runs[0]?.label ?? "—"}</strong>
            </div>
          </div>

          <div className="card">
            <div className="panel-head">
              <h2>Promoted games</h2>
              <span className="pill promoted">{runs.length} saved</span>
            </div>
            <div className="promoted-list">
              {runs.map((run) => (
                <Link
                  className="promoted-row"
                  to={`/analysis/${run.id}`}
                  key={run.id}
                >
                  <div className="promoted-main">
                    <div className="promoted-name">{run.label}</div>
                    <div className="run-meta">
                      {run.n_players} players {"\u00b7"} {modeLabel(run)}{" "}
                      {"\u00b7"} {run.steps} steps {"\u00b7"} {run.turns} turns
                      {run.winner !== null
                        ? ` \u00b7 winner P${run.winner + 1}`
                        : ""}
                    </div>
                  </div>
                  <div className="promoted-side">
                    <span className="pill promoted">promoted</span>
                    <span className="muted">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
