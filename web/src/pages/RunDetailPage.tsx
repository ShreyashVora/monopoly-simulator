import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Board } from "../components/Board";
import { PropertyDeed } from "../components/GamePanels";
import type { GameState, RunTrace, TraceStep } from "../types";

function stateAt(trace: RunTrace, index: number): GameState {
  return index === 0 ? trace.initial : trace.steps[index - 1].state;
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [promoted, setPromoted] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setTrace(null);
    setError(null);
    setPromoted(false);
    setPromoteError(null);
    api
      .trace(runId)
      .then((t) => {
        if (!alive) return;
        setTrace(t);
        setPromoted(t.promoted);
        setIndex(t.steps.length);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [runId]);

  useEffect(() => {
    if (!playing || !trace) return;
    if (index >= trace.steps.length) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(
      () => setIndex((i) => Math.min(i + 1, trace.steps.length)),
      320,
    );
    return () => window.clearTimeout(timer);
  }, [playing, index, trace]);

  const current: TraceStep | null = useMemo(() => {
    if (!trace || index === 0) return null;
    return trace.steps[index - 1];
  }, [trace, index]);

  if (error) {
    return (
      <div className="card">
        <div className="error-box">{error}</div>
        <p>
          <Link to="/runs">Back to runs</Link>
        </p>
      </div>
    );
  }
  if (!trace) return <div className="loading">Loading trace…</div>;

  const state = stateAt(trace, index);
  const max = trace.steps.length;
  const winner =
    trace.winner !== null ? state.players[trace.winner]?.name : null;
  const promote = async () => {
    if (trace.winner === null || promoting) return;
    setPromoting(true);
    setPromoteError(null);
    try {
      await api.promoteRun(trace.id);
      setPromoted(true);
    } catch (e) {
      setPromoteError((e as Error).message);
    } finally {
      setPromoting(false);
    }
  };

  return (
    <>
      <h1 className="page-title">
        {trace.label}
        <small>
          {trace.n_players} players {"\u00b7"} {trace.policy ?? "manual"}{" "}
          {"\u00b7"} {max} steps {winner ? ` \u00b7 ${winner} wins` : ""}
          {promoted ? " \u00b7 promoted" : ""}
        </small>
      </h1>
      <div className="replay-layout">
        <Board
          state={state}
          replay
          onSelect={setSelectedIdx}
          selectedIdx={selectedIdx}
          anim={current?.anim ?? null}
        />
        <aside className="replay-side">
          <div className="panel">
            <div className="panel-head">
              <h2>Timeline</h2>
              <Link className="mbtn" to="/runs">
                All runs
              </Link>
            </div>
            <div className="timeline-label">
              Step {index} of {max}
              {current ? ` \u00b7 ${current.action}` : " \u00b7 start"}
            </div>
            <div className="timeline-controls">
              <button
                onClick={() => {
                  setPlaying(false);
                  setIndex(0);
                }}
                disabled={index === 0}
              >
                {"\u23EE"}
              </button>
              <button
                onClick={() => {
                  setPlaying(false);
                  setIndex((i) => Math.max(0, i - 1));
                }}
                disabled={index === 0}
              >
                {"\u25C0"}
              </button>
              <button
                onClick={() => setPlaying((p) => !p)}
                disabled={max === 0 || index >= max}
              >
                {playing ? "\u23F8" : "\u25B6"}
              </button>
              <button
                onClick={() => {
                  setPlaying(false);
                  setIndex((i) => Math.min(max, i + 1));
                }}
                disabled={index >= max}
              >
                {"\u25B6|"}
              </button>
              <button
                onClick={() => {
                  setPlaying(false);
                  setIndex(max);
                }}
                disabled={index >= max}
              >
                {"\u23ED"}
              </button>
            </div>
            <input
              type="range"
              min={0}
              max={max}
              value={index}
              style={{ width: "100%", accentColor: "#ed1b24" }}
              onChange={(e) => {
                setPlaying(false);
                setIndex(Number(e.target.value));
              }}
            />
          </div>

          {trace.winner !== null && (
            <div className="panel">
              <div className="panel-head">
                <h2>Game Analysis</h2>
              </div>
              {promoted ? (
                <button
                  className="wide-btn"
                  onClick={() => navigate(`/analysis/${trace.id}`)}
                >
                  View Analysis
                </button>
              ) : (
                <button
                  className="wide-btn"
                  disabled={promoting}
                  onClick={() => void promote()}
                >
                  {promoting ? "Promoting…" : "Promote for Analysis"}
                </button>
              )}
              {promoteError && <div className="error-box">{promoteError}</div>}
            </div>
          )}

          <div className="panel inspector">
            <div className="panel-head">
              <h2>Decision</h2>
            </div>
            {!current ? (
              <div className="empty">Start of run.</div>
            ) : (
              <>
                <dl className="kv">
                  <dt>Actor</dt>
                  <dd>
                    {state.players[current.actor]?.glyph}{" "}
                    {state.players[current.actor]?.name}
                  </dd>
                  <dt>Action</dt>
                  <dd>{current.action}</dd>
                  {Object.keys(current.payload).length > 0 && (
                    <>
                      <dt>Payload</dt>
                      <dd className="trace-payload">
                        {JSON.stringify(current.payload)}
                      </dd>
                    </>
                  )}
                  <dt>Phase before</dt>
                  <dd>{current.phase_before}</dd>
                  <dt>Policy</dt>
                  <dd>
                    {current.meta.source === "agent"
                      ? "random agent"
                      : trace.kind === "mixed"
                        ? "human"
                        : String(current.meta.policy ?? trace.policy ?? "manual")}
                  </dd>
                </dl>
                {current.pending_before && (
                  <>
                    <div className="timeline-label" style={{ marginTop: 8 }}>
                      {current.pending_before.prompt}
                    </div>
                    <ul className="events">
                      {current.pending_before.options.map((o) => (
                        <li key={o.action}>
                          {o.label}
                          {o.action === current.action ? " \u2190 chosen" : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {current.events.length > 0 && (
                  <>
                    <div className="timeline-label" style={{ marginTop: 8 }}>
                      Events
                    </div>
                    <ul className="events">
                      {current.events.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>

          <div className="panel inspector">
            <div className="panel-head">
              <h2>State</h2>
            </div>
            <pre>
              {JSON.stringify(
                {
                  turn: state.turn,
                  phase: state.phase,
                  current: state.players[state.current]?.name,
                  dice: state.dice,
                  pending: state.pending,
                  players: state.players.map((p) => ({
                    name: p.name,
                    cash: p.cash,
                    pos: state.squares[p.pos].short,
                    jail: p.in_jail,
                  })),
                  owner: state.owner
                    .map((o, i) => (o === null ? null : [i, o]))
                    .filter(Boolean),
                  houses: state.houses
                    .map((h, i) => (h ? [i, h] : null))
                    .filter(Boolean),
                  mortgaged: state.mortgaged
                    .map((m, i) => (m ? i : null))
                    .filter((i) => i !== null),
                },
                null,
                2,
              )}
            </pre>
          </div>
        </aside>
      </div>
      <PropertyDeed
        state={state}
        idx={selectedIdx}
        onClose={() => setSelectedIdx(null)}
      />
    </>
  );
}
