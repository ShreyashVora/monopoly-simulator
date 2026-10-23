import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  DICE,
  FILL,
  ICONS,
  idxAt,
  isCorner,
  N,
  orientOf,
  phaseText,
  tokenOffset,
} from "../board";
import type { Anim, GameState, Square } from "../types";

const posMap: Record<number, [number, number]> = {};
for (const [key, idx] of Object.entries(idxAt)) {
  const [r, c] = key.split(",").map(Number);
  posMap[idx] = [r, c];
}

function label(s: Square, withPrice: boolean) {
  return (
    <div className="label">
      {ICONS[s.type] && <div className="icon">{ICONS[s.type]}</div>}
      <div>{s.short}</div>
      {withPrice && s.price != null && <div className="price">${s.price}</div>}
    </div>
  );
}

const CORNERS: Record<string, [string, string]> = {
  go: ["GO", "\u2190 collect $200 salary as you pass"],
  jail: ["IN JAIL / JUST VISITING", "\u{1F527} bars stay shut"],
  free_parking: ["FREE PARKING", "rest stop \u2014 nothing happens"],
  go_to_jail: ["GO TO JAIL", "\u{1F46E} straight to jail"],
};

function cornerContent(s: Square) {
  const cfg = CORNERS[s.type];
  if (!cfg) return null;
  return (
    <div className="corner-inner">
      <div className="name" style={s.type === "go" ? { color: "#c00" } : undefined}>
        {cfg[0]}
      </div>
      <div className="sub">{cfg[1]}</div>
    </div>
  );
}

interface BoardProps {
  state: GameState;
  onRoll?: () => void;
  onEndTurn?: () => void;
  busy?: boolean;
  replay?: boolean;
  onSelect?: (idx: number) => void;
  selectedIdx?: number | null;
  anim?: Anim | null;
  rolling?: boolean;
}

export function Board({
  state,
  onRoll,
  onEndTurn,
  busy,
  replay,
  onSelect,
  selectedIdx,
  anim,
  rolling,
}: BoardProps) {
  const cur = state.players[state.current];
  const cells = [];
  for (let r = 1; r <= N; r++) {
    for (let c = 1; c <= N; c++) {
      const idx = idxAt[`${r},${c}`];
      if (idx === undefined) {
        cells.push(<div key={`${r}-${c}`} className="cell centerbg" />);
        continue;
      }
      const s = state.squares[idx];
      const o = state.owner[idx];
      const owned = o !== null && o !== undefined;
      const style = owned
        ? ({ "--owner-color": state.players[o].color } as CSSProperties)
        : undefined;
      const cell = isCorner(s) ? (
        <div
          key={idx}
          data-idx={idx}
          className={`cell corner ${orientOf(idx)} ${owned ? "owned" : ""} ${
            state.mortgaged[idx] ? "is-mortgaged" : ""
          }`}
          style={style}
        >
          {cornerContent(s)}
          <Markers state={state} idx={idx} />
        </div>
      ) : (
        <EdgeCell
          key={idx}
          state={state}
          idx={idx}
          style={style}
          onSelect={onSelect}
          selected={selectedIdx === idx}
        />
      );
      cells.push(cell);
    }
  }

  return (
    <div className="board">
      {cells}
      <div className="center-panel">
        <div className="logo">MONOPOLY</div>
        <div className="center-prompt">
          {state.winner !== null ? (
            `${state.players[state.winner].glyph} ${state.players[state.winner].name} wins`
          ) : (
            <>
              Turn {state.turn} {"\u2014"} {cur.glyph} {cur.name}
              <span className="center-sub">{phaseText(state)}</span>
            </>
          )}
        </div>
        <Dice dice={state.dice} rolling={!!rolling} />
        {state.doubles > 0 && state.winner === null && (
          <div className="roll-again">
            {state.phase === "await_roll"
              ? "Doubles \u2014 roll again"
              : "Doubles \u2014 extra roll after this decision"}
          </div>
        )}
        {onRoll && (
          <button
            className="roll-btn"
            onClick={onRoll}
            disabled={busy || state.phase !== "await_roll" || !!state.pending}
          >
            {replay ? "Replay" : "Roll Dice"}
          </button>
        )}
        {onEndTurn && (
          <button
            className="roll-btn end-turn-btn"
            onClick={onEndTurn}
            disabled={
              busy ||
              state.winner !== null ||
              state.phase !== "await_manage" ||
              !!state.pending
            }
          >
            End Turn
          </button>
        )}
      </div>
      <AnimatedTokens state={state} anim={anim ?? null} />
    </div>
  );
}

function EdgeCell({
  state,
  idx,
  style,
  onSelect,
  selected,
}: {
  state: GameState;
  idx: number;
  style?: CSSProperties;
  onSelect?: (idx: number) => void;
  selected: boolean;
}) {
  const s = state.squares[idx];
  const o = orientOf(idx);
  const owned = state.owner[idx] !== null;
  const selectable =
    !!onSelect && ["street", "railroad", "utility"].includes(s.type);
  return (
    <div
      data-idx={idx}
      style={style}
      className={`cell edge ${o} ${owned ? "owned" : ""} ${
        state.mortgaged[idx] ? "is-mortgaged" : ""
      } ${selectable ? "selectable" : ""} ${selected ? "selected" : ""}`}
      role={selectable ? "button" : undefined}
      tabIndex={selectable ? 0 : undefined}
      aria-label={selectable ? `Open title deed for ${s.name}` : undefined}
      onClick={selectable ? () => onSelect?.(idx) : undefined}
      onKeyDown={
        selectable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect?.(idx);
              }
            }
          : undefined
      }
    >
      {edgeInner(s)}
      <Markers state={state} idx={idx} />
    </div>
  );
}

function edgeInner(s: Square) {
  const o = orientOf(s.idx);
  if (["street", "railroad", "utility"].includes(s.type)) {
    const bar = (
      <div className="bar" style={{ background: FILL[s.group ?? ""] }}>
        {s.type === "railroad" ? "\u{1F682}" : s.type === "utility" ? "\u{1F4A1}\u26A1" : ""}
      </div>
    );
    const body = label(s, true);
    if (o === "bottom") return <>{bar}{body}</>;
    if (o === "top") return <>{body}{bar}</>;
    if (o === "left") return <>{body}{bar}</>;
    return <>{bar}{body}</>;
  }
  return label(s, true);
}

function Dice({
  dice,
  rolling,
}: {
  dice: [number, number] | null;
  rolling: boolean;
}) {
  const [faces, setFaces] = useState<[number, number] | null>(dice);
  useEffect(() => {
    if (!rolling) {
      setFaces(dice);
      return;
    }
    const roll = () =>
      setFaces([
        Math.floor(Math.random() * 6) + 1,
        Math.floor(Math.random() * 6) + 1,
      ]);
    roll();
    const timer = window.setInterval(roll, 85);
    return () => window.clearInterval(timer);
  }, [dice, rolling]);
  const shown = rolling ? faces : dice;
  return (
    <div
      className={`dice${rolling ? " rolling" : ""}`}
      aria-label={shown ? `Dice ${shown[0]} and ${shown[1]}` : "Dice"}
    >
      {shown ? DICE[shown[0] - 1] + DICE[shown[1] - 1] : ""}
    </div>
  );
}

function AnimatedTokens({
  state,
  anim,
}: {
  state: GameState;
  anim: Anim | null;
}) {
  const [positions, setPositions] = useState<number[]>(() =>
    state.players.map((p) => p.pos),
  );
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
    const target = state.players.map((p) => p.pos);
    if (!anim || anim.path.length === 0) {
      setPositions(target);
      return;
    }
    const next = target.slice();
    next[anim.mover] = anim.path[0];
    setPositions(next);
    let step = 0;
    if (anim.path.length === 1) {
      setPositions(target);
      return;
    }
    timer.current = window.setInterval(() => {
      step += 1;
      if (step >= anim.path.length) {
        setPositions(target);
        if (timer.current !== null) {
          window.clearInterval(timer.current);
          timer.current = null;
        }
        return;
      }
      setPositions((prev) => {
        const moved = prev.slice();
        moved[anim.mover] = anim.path[step];
        return moved;
      });
    }, 130);
    return () => {
      if (timer.current !== null) {
        window.clearInterval(timer.current);
        timer.current = null;
      }
    };
  }, [anim, state.players]);
  return (
    <div className={`tokens ${state.players.length > 4 ? "many" : ""}`}>
      {state.players.map((p, i) => {
        const pos = posMap[positions[i] ?? p.pos] ?? [6, 6];
        const [ox, oy] = tokenOffset(state.players.length, i);
        const left = `calc((${pos[1]} - 0.5) * var(--cell) + ${ox} * var(--cell))`;
        const top = `calc((${pos[0]} - 0.5) * var(--cell) + ${oy} * var(--cell))`;
        return (
          <div
            key={p.pid}
            className="token"
            title={`${p.name}${p.bankrupt ? " (bankrupt)" : ""}`}
            style={{ left, top, opacity: p.bankrupt ? 0.35 : 1 }}
          >
            {p.glyph}
          </div>
        );
      })}
    </div>
  );
}

function Markers({ state, idx }: { state: GameState; idx: number }) {
  const o = state.owner[idx];
  return (
    <div className="markers">
      {o !== null && o !== undefined && (
        <div
          className="owner-badge"
          title={`Owned by ${state.players[o].name} (${state.players[o].glyph})`}
          style={{ borderColor: state.players[o].color }}
        >
          {state.players[o].glyph}
        </div>
      )}
      {state.houses[idx] > 0 && (
        <div className="buildings">
          {state.houses[idx] === 5 ? "\u{1F3E8}" : "\u{1F3E0}".repeat(state.houses[idx])}
        </div>
      )}
      {state.mortgaged[idx] && <div className="mort-tag">M</div>}
    </div>
  );
}
