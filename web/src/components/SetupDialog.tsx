import { useEffect, useState } from "react";
import type { GameSetup } from "../types";

interface SetupDialogProps {
  open: boolean;
  allowCancel: boolean;
  busy?: boolean;
  onStart: (setup: GameSetup) => void;
  onCancel: () => void;
}

const COUNTS = [2, 3, 4, 5, 6];

export function SetupDialog({
  open,
  allowCancel,
  busy,
  onStart,
  onCancel,
}: SetupDialogProps) {
  const [mode, setMode] = useState<"manual" | "mixed">("manual");
  const [nPlayers, setNPlayers] = useState(4);
  const [humans, setHumans] = useState(3);

  useEffect(() => {
    if (!open) return;
    setMode("manual");
    setNPlayers(4);
    setHumans(3);
  }, [open]);

  if (!open) return null;

  const chooseCount = (n: number) => {
    setNPlayers(n);
    setHumans((h) => Math.min(h, n - 1));
  };
  const agentCount = nPlayers - humans;
  const start = () => {
    const agentSeats =
      mode === "mixed"
        ? Array.from({ length: agentCount }, (_, i) => humans + i)
        : [];
    onStart({ n_players: nPlayers, agent_seats: agentSeats });
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card setup-card">
        <h2 className="setup-title">New Game</h2>
        <p className="setup-sub">Choose who controls each seat.</p>

        <div className="setup-modes">
          <button
            className={`mode-btn${mode === "manual" ? " active" : ""}`}
            aria-pressed={mode === "manual"}
            disabled={busy}
            onClick={() => setMode("manual")}
          >
            Hot-seat
            <span>All players are human</span>
          </button>
          <button
            className={`mode-btn${mode === "mixed" ? " active" : ""}`}
            aria-pressed={mode === "mixed"}
            disabled={busy}
            onClick={() => setMode("mixed")}
          >
            Humans + agents
            <span>Random legal moves</span>
          </button>
        </div>

        <div className="setup-label">Players</div>
        <div className="setup-counts">
          {COUNTS.map((n) => (
            <button
              key={n}
              className={`optbtn${n === nPlayers ? " selected" : ""}`}
              aria-pressed={n === nPlayers}
              disabled={busy}
              onClick={() => chooseCount(n)}
            >
              {n}
            </button>
          ))}
        </div>

        {mode === "mixed" && (
          <>
            <label className="field setup-humans">
              Human players
              <select
                value={humans}
                disabled={busy}
                onChange={(e) => setHumans(Number(e.target.value))}
              >
                {Array.from({ length: nPlayers - 1 }, (_, i) => i + 1).map(
                  (n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ),
                )}
              </select>
            </label>
            <p className="setup-note">
              {agentCount === 1
                ? `Player ${humans + 1} will be a random agent.`
                : `Players ${humans + 1}\u2013${nPlayers} will be random agents.`}
            </p>
          </>
        )}

        <button className="optbtn setup-start" disabled={busy} onClick={start}>
          Start Game
        </button>
        {allowCancel && (
          <button className="optbtn subtle" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
