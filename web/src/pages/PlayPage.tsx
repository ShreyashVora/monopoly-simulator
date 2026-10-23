import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Board } from "../components/Board";
import {
  AgentTurnPanel,
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
import { isAgentDecision, isFreshGame, managingPid } from "../board";
import { useGame } from "../hooks";
import type { GameSetup } from "../types";

export function PlayPage() {
  const navigate = useNavigate();
  const {
    state, busy, loading, notice, act, stepAgent, startNewGame, anim,
  } = useGame();
  const [setupOpen, setSetupOpen] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promotionError, setPromotionError] = useState<string | null>(null);
  const [promotedRunId, setPromotedRunId] = useState<string | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [rolling, setRolling] = useState(false);
  const [agentPaused, setAgentPaused] = useState(false);
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

  useEffect(() => {
    if (!state) return;
    if (!isAgentDecision(state)) {
      setAgentPaused(false);
      return;
    }
    if (state.winner !== null || busy || rolling || agentPaused) return;

    const timer = window.setTimeout(() => {
      const rollsDice = state.phase === "await_roll";
      if (rollsDice) setRolling(true);
      const minimum = rollsDice
        ? new Promise((resolve) => window.setTimeout(resolve, 520))
        : Promise.resolve();
      void Promise.all([stepAgent(), minimum])
        .then(([result]) => {
          if (!result?.ok) setAgentPaused(true);
        })
        .finally(() => {
          if (rollsDice) setRolling(false);
        });
    }, 800);

    return () => window.clearTimeout(timer);
  }, [state, busy, rolling, agentPaused, stepAgent]);

  if (loading || !state) {
    return <div className="loading">Loading game…</div>;
  }

  const agentActing = isAgentDecision(state);
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
  const promoted = Boolean(
    state.promoted ||
      (state.run_id !== undefined && promotedRunId === state.run_id),
  );
  const promoteGame = async () => {
    if (!state.run_id || promoting) return;
    setPromoting(true);
    setPromotionError(null);
    try {
      await api.promoteRun(state.run_id);
      setPromotedRunId(state.run_id);
    } catch (e) {
      setPromotionError((e as Error).message);
    } finally {
      setPromoting(false);
    }
  };
  const onAction = (type: string, payload: Record<string, unknown> = {}) => {
    if (agentActing) return;
    void act(type, payload);
  };
  const onRoll = () => {
    if (busy || rolling || agentActing) return;
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
          onEndTurn={() => onAction("end_turn")}
          busy={busy || rolling || agentActing}
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
              disabled={busy}
              onClick={() => {
                setPromotionError(null);
                setAgentPaused(true);
                setAllowCancel(true);
                setSetupOpen(true);
              }}
            >
              New Game
            </button>
          </div>
          <PlayerCards state={state} />
        </div>
        {agentActing && (
          <AgentTurnPanel
            state={state}
            busy={busy}
            paused={agentPaused}
            onRetry={() => setAgentPaused(false)}
          />
        )}
        {!agentActing && (
          <JailPanel state={state} busy={busy} onAction={onAction} />
        )}
        {!agentActing && (
          <DebtPanel state={state} busy={busy} onAction={onAction} />
        )}
        <div className="panel">
          <div className="panel-head">
            <h2>
              Manage {"\u2014"} {manager.glyph} {manager.name}
            </h2>
          </div>
          <ManagePanel
            state={state}
            busy={busy || agentActing}
            onAction={onAction}
          />
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>Event Log</h2>
          </div>
          <EventLog state={state} />
        </div>
      </aside>

      {!agentActing && (
        <DecisionModal state={state} busy={busy} onAction={onAction} />
      )}
      <PropertyDeed
        state={state}
        idx={selectedIdx}
        onClose={() => setSelectedIdx(null)}
      />
      <WinnerOverlay
        state={state}
        open={winnerKey !== null && !winnerDismissed}
        onNewGame={() => {
          setPromotionError(null);
          setAgentPaused(true);
          setAllowCancel(true);
          setSetupOpen(true);
        }}
        onPromote={
          state.run_id ? () => void promoteGame() : undefined
        }
        onViewAnalysis={
          state.run_id
            ? () => navigate(`/analysis/${state.run_id}`)
            : undefined
        }
        promoting={promoting}
        promoted={promoted}
        promotionError={promotionError}
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
        onStart={async (setup: GameSetup) => {
          const ok = await startNewGame(setup);
          if (ok) {
            setSelectedIdx(null);
            setPromotionError(null);
            setAgentPaused(false);
            setSetupOpen(false);
          }
        }}
        onCancel={() => {
          setSetupOpen(false);
          setAgentPaused(false);
        }}
      />
      {notice && <div className="toast">{notice}</div>}
    </div>
  );
}
