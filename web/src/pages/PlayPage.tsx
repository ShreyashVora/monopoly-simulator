import { useEffect, useRef, useState } from "react";
import { Board } from "../components/Board";
import {
  DebtPanel,
  DecisionModal,
  EventLog,
  JailPanel,
  ManagePanel,
  PlayerCards,
  PropertyDeed,
  WinnerOverlay,
} from "../components/GamePanels";
import { SetupDialog } from "../components/SetupDialog";
import { isFreshGame, managingPid } from "../board";
import { useGame } from "../hooks";

export function PlayPage() {
  const { state, busy, loading, notice, act, startNewGame, anim } = useGame();
  const [setupOpen, setSetupOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [rolling, setRolling] = useState(false);
  const [allowCancel, setAllowCancel] = useState(false);
  const [dismissedWinner, setDismissedWinner] = useState<string | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (!state || initialized.current) return;
    initialized.current = true;
    if (!isFreshGame(state)) return;
    setAllowCancel(false);
    setSetupOpen(true);
  }, [state]);

  if (loading || !state) {
    return <div className="loading">Loading game…</div>;
  }

  const winnerKey =
    state.winner !== null
      ? (state.run_id ?? `turn-${state.turn}`)
      : null;
  const winnerDismissed =
    winnerKey !== null &&
    (dismissedWinner === winnerKey ||
      sessionStorage.getItem(`monopoly:winner-dismissed:${winnerKey}`) ===
        "1");
  const manager = state.players[managingPid(state)];
  const onAction = (type: string, payload: Record<string, unknown> = {}) => {
    void act(type, payload);
  };
  const onRoll = () => {
    if (busy || rolling) return;
    setRolling(true);
    const minimum = new Promise((resolve) => window.setTimeout(resolve, 520));
    void Promise.all([act("roll"), minimum]).finally(() => setRolling(false));
  };

  return (
    <div className="play-layout">
      <div className="board-wrap">
        <Board
          state={state}
          onRoll={onRoll}
          busy={busy || rolling}
          onSelect={setSelectedIdx}
          selectedIdx={selectedIdx}
          anim={anim}
          rolling={rolling}
        />
      </div>
      <aside className="side">
        <div className="panel">
          <div className="panel-head">
            <h2>Players</h2>
            <button
              className="mbtn"
              onClick={() => {
                setAllowCancel(true);
                setSetupOpen(true);
              }}
            >
              New Game
            </button>
          </div>
          <PlayerCards state={state} />
        </div>
        <JailPanel state={state} busy={busy} onAction={onAction} />
        <DebtPanel state={state} busy={busy} onAction={onAction} />
        <div className="panel">
          <div className="panel-head">
            <h2>
              Manage {"\u2014"} {manager.glyph} {manager.name}
            </h2>
          </div>
          <ManagePanel state={state} busy={busy} onAction={onAction} />
          <button
            className="wide-btn"
            disabled={
              busy || state.phase !== "await_manage" || !!state.pending
            }
            onClick={() => onAction("end_turn")}
          >
            End Turn
          </button>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>Event Log</h2>
          </div>
          <EventLog state={state} />
        </div>
      </aside>

      <DecisionModal state={state} busy={busy} onAction={onAction} />
      <PropertyDeed
        state={state}
        idx={selectedIdx}
        onClose={() => setSelectedIdx(null)}
      />
      <WinnerOverlay
        state={state}
        open={winnerKey !== null && !winnerDismissed}
        onNewGame={() => {
          setAllowCancel(true);
          setSetupOpen(true);
        }}
        onStay={() => {
          if (!winnerKey) return;
          sessionStorage.setItem(
            `monopoly:winner-dismissed:${winnerKey}`,
            "1",
          );
          setDismissedWinner(winnerKey);
        }}
      />
      <SetupDialog
        open={setupOpen}
        allowCancel={allowCancel}
        busy={busy}
        onStart={async (n) => {
          const ok = await startNewGame(n);
          if (ok) {
            setSelectedIdx(null);
            setSetupOpen(false);
          }
        }}
        onCancel={() => setSetupOpen(false)}
      />
      {notice && <div className="toast">{notice}</div>}
    </div>
  );
}
