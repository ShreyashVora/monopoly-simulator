import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { RunSummary } from "../types";

export function RunsPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nPlayers, setNPlayers] = useState(4);
  const [policy, setPolicy] = useState<"greedy" | "random">("greedy");
  const [seed, setSeed] = useState("");
  const [maxSteps, setMaxSteps] = useState(4000);

  const refresh = useCallback(async () => {
    try {
      setRuns(await api.runs());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await api.startRun({
        n_players: nPlayers,
        policy,
        seed: seed.trim() === "" ? null : Number(seed),
        max_steps: maxSteps,
      });
      navigate(`/runs/${run.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="page-title">
        Runs
        <small>Replay manual games or launch a policy-driven agent game.</small>
      </h1>
      <div className="runs-layout">
        <div className="card">
          <div className="panel-head">
            <h2>Start Agent Run</h2>
          </div>
          <label className="field">
            Players
            <select
              value={nPlayers}
              onChange={(e) => setNPlayers(Number(e.target.value))}
            >
              {[2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>
                  {n} players
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Policy
            <select
              value={policy}
              onChange={(e) =>
                setPolicy(e.target.value as "greedy" | "random")
              }
            >
              <option value="greedy">Greedy buyer / builder</option>
              <option value="random">Random legal actions</option>
            </select>
          </label>
          <label className="field">
            Seed (optional)
            <input
              value={seed}
              inputMode="numeric"
              placeholder="random"
              onChange={(e) => setSeed(e.target.value)}
            />
          </label>
          <label className="field">
            Max steps
            <input
              value={maxSteps}
              type="number"
              min={10}
              max={20000}
              onChange={(e) => setMaxSteps(Number(e.target.value))}
            />
          </label>
          <button className="wide-btn" disabled={busy} onClick={start}>
            {busy ? "Running…" : "Run Agent"}
          </button>
          {error && <div className="error-box">{error}</div>}
        </div>

        <div className="card">
          <div className="panel-head">
            <h2>History</h2>
            <button className="mbtn" onClick={refresh} disabled={loading}>
              Refresh
            </button>
          </div>
          {loading ? (
            <div className="empty">Loading runs…</div>
          ) : runs.length === 0 ? (
            <div className="empty">No runs yet.</div>
          ) : (
            <div className="run-list">
              {runs.map((r) => (
                <Link className="run-row" to={`/runs/${r.id}`} key={r.id}>
                  <div className="run-main">
                    <div className="run-name">
                      {r.label} {"\u00b7"} {r.n_players}p
                    </div>
                    <div className="run-meta">
                      {r.steps} steps {"\u00b7"} {r.turns} turns {"\u00b7"}{" "}
                      {r.policy ?? "manual"}
                      {r.winner !== null ? ` \u00b7 winner P${r.winner + 1}` : ""}
                    </div>
                  </div>
                  <span className={`pill ${r.status}`}>{r.status}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
