import { useEffect, useState } from "react";
import {
  bankHotels,
  bankHouses,
  buildReason,
  decisionActor,
  FILL,
  groupLabel,
  managingPid,
  mortgageReason,
  propertyGroups,
  sellReason,
  unmortgageCost,
  unmortgageReason,
} from "../board";
import type { GameState, Square } from "../types";

export function PlayerCards({ state }: { state: GameState }) {
  return (
    <div className="players-grid">
      {state.players.map((p, i) => {
        const agent = (state.agent_seats ?? []).includes(p.pid);
        return (
          <div
            key={p.pid}
            className={`pcard${i === state.current && state.winner === null ? " current" : ""}${
              p.bankrupt ? " bankrupt" : ""
            }`}
            style={{ borderColor: p.color }}
          >
            <div className="pname">
              <span>
                {p.glyph} {p.name}
              </span>
              {agent && <span className="agent-badge">BOT</span>}
            </div>
            <div className="cash">${p.cash}</div>
            <div className="pos">
              {state.squares[p.pos].short}
              {p.in_jail ? " \u{1F527}" : ""}
            </div>
            {p.goojf > 0 && (
              <div className="badge">{"\u{1F39F}"}×{p.goojf}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function BankStock({ state }: { state: GameState }) {
  return (
    <div className="bank-stock">
      <span className="bank-label">Bank</span>
      <span>
        {"\u{1F3E0}"} {bankHouses(state)} houses
      </span>
      <span>
        {"\u{1F3E8}"} {bankHotels(state)} hotels
      </span>
    </div>
  );
}

function rowHint(
  state: GameState,
  idx: number,
  buildIssue: string | null,
  sellIssue: string | null,
  mortgageIssue: string | null,
  unmortgageIssue: string | null,
): string | null {
  if (buildIssue && buildIssue !== "Hotel already built.") return buildIssue;
  if (sellIssue && state.houses[idx] > 0) return sellIssue;
  if (mortgageIssue && !state.mortgaged[idx]) return mortgageIssue;
  if (unmortgageIssue && state.mortgaged[idx]) return unmortgageIssue;
  return null;
}

export function ManagePanel({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  if (state.winner !== null) {
    return <div className="empty">Game over.</div>;
  }
  const pid = managingPid(state);
  const groups = propertyGroups(state, pid);
  return (
    <>
      <BankStock state={state} />
      {state.phase === "await_jail" && (
        <div className="manage-note">
          You may still build, sell, and mortgage while in Jail.
        </div>
      )}
      {state.phase === "await_debt" && (
        <div className="manage-note debt-note">
          Raise cash by selling buildings or mortgaging property, then pay the
          debt above.
        </div>
      )}
      {!groups.length ? (
        <div className="empty">No properties yet.</div>
      ) : (
        <div className="manage-list">
          {groups.map((group) => (
            <div className="mgroup" key={group.group}>
              <div
                className="mgroup-head"
                style={{ borderLeftColor: FILL[group.group] ?? "#999" }}
              >
                {group.label}
              </div>
              {group.idxs.map((idx) => (
                <ManageRow
                  key={idx}
                  state={state}
                  idx={idx}
                  pid={pid}
                  busy={busy}
                  onAction={onAction}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function ManageRow({
  state,
  idx,
  pid,
  busy,
  onAction,
}: {
  state: GameState;
  idx: number;
  pid: number;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  const sq = state.squares[idx];
  const h = state.houses[idx];
  const stat = state.mortgaged[idx]
    ? "MORTGAGED"
    : h === 5
      ? "\u{1F3E8} hotel"
      : h > 0
        ? `${"\u{1F3E0}".repeat(h)} (${h})`
        : "unimproved";
  const mortar = unmortgageCost(state, idx);
  const buildIssue =
    sq.type === "street" ? buildReason(state, idx, pid) : null;
  const sellIssue = sq.type === "street" ? sellReason(state, idx, pid) : null;
  const mortgageIssue = mortgageReason(state, idx, pid);
  const unmortgageIssue = unmortgageReason(state, idx, pid);
  const hint = rowHint(
    state,
    idx,
    buildIssue,
    sellIssue,
    mortgageIssue,
    unmortgageIssue,
  );
  const buildLabel =
    h === 4 ? `Hotel $${sq.house_cost}` : `Build $${sq.house_cost}`;
  return (
    <div className="mrow">
      <div className="mtitle">
        <span>{sq.short}</span>
        <span className="mstat">{stat}</span>
      </div>
      <div className="mbtns">
        {sq.type === "street" && (
          <>
            <button
              className="mbtn build"
              disabled={busy || buildIssue !== null}
              title={buildIssue ?? buildLabel}
              aria-label={`${buildLabel} on ${sq.name}${buildIssue ? `: ${buildIssue}` : ""}`}
              onClick={() => onAction("build", { idx })}
            >
              {buildLabel}
            </button>
            <button
              className="mbtn sell"
              disabled={busy || sellIssue !== null}
              title={sellIssue ?? `Sell a building on ${sq.name}`}
              aria-label={`Sell a building on ${sq.name}${sellIssue ? `: ${sellIssue}` : ""}`}
              onClick={() => onAction("sell_house", { idx })}
            >
              Sell
            </button>
          </>
        )}
        <button
          className="mbtn mort"
          disabled={busy || mortgageIssue !== null}
          title={mortgageIssue ?? `Mortgage ${sq.name} for $${sq.mortgage}`}
          aria-label={`Mortgage ${sq.name}${mortgageIssue ? `: ${mortgageIssue}` : ""}`}
          onClick={() => onAction("mortgage", { idx })}
        >
          Mortgage ${sq.mortgage}
        </button>
        <button
          className="mbtn mort"
          disabled={busy || unmortgageIssue !== null}
          title={unmortgageIssue ?? `Unmortgage ${sq.name} for $${mortar}`}
          aria-label={`Unmortgage ${sq.name}${unmortgageIssue ? `: ${unmortgageIssue}` : ""}`}
          onClick={() => onAction("unmortgage", { idx })}
        >
          Unmortgage ${mortar}
        </button>
      </div>
      {hint && <div className="mreason">{hint}</div>}
    </div>
  );
}

export function DecisionModal({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  if (
    !state.pending ||
    state.pending.type !== "buy" ||
    state.winner !== null
  )
    return null;
  const p = state.players[state.pending.player];
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-player">
          {p.glyph} {p.name} {"\u2014"} ${p.cash}
        </div>
        <div className="modal-prompt">{state.pending.prompt}</div>
        {state.pending.options.map((o) => (
          <button
            key={o.action}
            className="optbtn"
            disabled={busy}
            onClick={() => onAction(o.action, o.payload ?? {})}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function AuctionPanel({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  const pending = state.pending;
  const isAuction =
    state.phase === "await_auction" &&
    pending?.type === "auction" &&
    state.winner === null;
  const unit = pending?.unit ?? 10;
  const minBid = pending?.min_bid ?? unit;
  const [amount, setAmount] = useState<number | "">(minBid);

  useEffect(() => {
    if (isAuction) setAmount(minBid);
  }, [isAuction, minBid, pending?.idx, pending?.player]);

  if (!isAuction || !pending) return null;

  const idx = pending.idx ?? 0;
  const sq = state.squares[idx];
  const p = state.players[pending.player];
  const maxBid = pending.max_bid ?? Math.floor(p.cash / unit) * unit;
  const numeric = typeof amount === "number" ? amount : Number.NaN;
  const valid =
    Number.isInteger(numeric) &&
    numeric >= minBid &&
    numeric <= p.cash &&
    numeric % unit === 0;
  const highBidder =
    pending.high_bidder == null ? null : state.players[pending.high_bidder];
  const active = pending.active ?? pending.participants ?? [];
  const passed = pending.passed ?? [];

  return (
    <div className="panel action-panel auction-panel">
      <div className="panel-head">
        <h2>Auction</h2>
        {pending.bank && <span className="auction-badge">BANK</span>}
      </div>
      <div
        className="auction-deed"
        style={{ borderLeftColor: FILL[sq.group ?? ""] ?? "#999" }}
      >
        <div className="auction-name">{sq.name}</div>
        <div className="auction-meta">
          List ${pending.price ?? sq.price ?? 0} · bids in ${unit} units
        </div>
      </div>
      <div className="auction-high">
        {pending.high_bid == null
          ? "No bids yet"
          : `High bid $${pending.high_bid} — ${highBidder?.name ?? "unknown"}`}
      </div>
      <div className="action-prompt">
        {p.glyph} {p.name} — cash ${p.cash}
      </div>
      <label className="auction-bid-label">
        Your bid
        <input
          className="auction-bid-input"
          type="number"
          min={minBid}
          max={maxBid}
          step={unit}
          value={amount}
          disabled={busy || maxBid < minBid}
          aria-label={`Bid on ${sq.name}`}
          onChange={(e) =>
            setAmount(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
      </label>
      <div className="auction-range">
        Minimum ${minBid} · Maximum ${maxBid}
      </div>
      {amount !== "" && !valid && (
        <div className="auction-error">
          Enter a whole multiple of ${unit} within your cash.
        </div>
      )}
      <button
        className="wide-btn auction-bid-btn"
        disabled={busy || !valid}
        onClick={() => onAction("auction_bid", { amount: numeric })}
      >
        Bid ${Number.isFinite(numeric) ? numeric : minBid}
      </button>
      <button
        className="wide-btn auction-pass-btn"
        disabled={busy}
        onClick={() => onAction("auction_pass", {})}
      >
        Pass
      </button>
      <div className="auction-players">
        <span>
          <b>In:</b>{" "}
          {active.map((pid) => state.players[pid].name).join(", ") || "—"}
        </span>
        {passed.length > 0 && (
          <span>
            <b>Out:</b>{" "}
            {passed.map((pid) => state.players[pid].name).join(", ")}
          </span>
        )}
      </div>
      <div className="action-note">
        Bids are total prices. Passing is permanent for this auction.
      </div>
    </div>
  );
}

export function JailPanel({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  if (
    state.phase !== "await_jail" ||
    !state.pending ||
    state.pending.type !== "jail"
  )
    return null;
  return (
    <div className="panel action-panel jail-panel">
      <div className="panel-head">
        <h2>In Jail</h2>
      </div>
      <div className="action-prompt">{state.pending.prompt}</div>
      {state.pending.options.map((o) => (
        <button
          key={o.action}
          className="optbtn action-opt"
          disabled={busy}
          onClick={() => onAction(o.action, o.payload ?? {})}
        >
          {o.label}
        </button>
      ))}
      <div className="action-note">
        You can still manage properties below before choosing.
      </div>
    </div>
  );
}

export function AgentTurnPanel({
  state,
  busy,
  paused,
  onRetry,
}: {
  state: GameState;
  busy: boolean;
  paused: boolean;
  onRetry: () => void;
}) {
  const p = state.players[decisionActor(state)];
  const pend = state.pending;
  let detail = "Choosing a move.";
  if (pend?.type === "debt") detail = `Settling a $${pend.amount ?? 0} debt.`;
  else if (pend?.type === "buy") detail = "Deciding whether to buy property.";
  else if (pend?.type === "auction") {
    detail = `Bidding on ${state.squares[pend.idx ?? 0].name}.`;
  } else if (pend?.type === "trade") {
    detail = "Reviewing a trade offer.";
  } else if (pend?.type === "jail") detail = "Choosing a Jail action.";
  else if (state.phase === "await_roll") detail = "Rolling the dice.";
  else if (state.phase === "await_manage") {
    detail = "Managing property or ending the turn.";
  }
  return (
    <div className="panel action-panel agent-panel">
      <div className="panel-head">
        <h2>Random Agent</h2>
        <span className="agent-badge">BOT</span>
      </div>
      <div className="action-prompt">
        {p.glyph} {p.name} {detail}
      </div>
      <div className={`agent-status${paused ? " paused" : ""}`}>
        {paused
          ? "Paused after an error."
          : busy
            ? "Applying a legal move…"
            : "Choosing a legal move…"}
      </div>
      {paused && (
        <button className="wide-btn" disabled={busy} onClick={onRetry}>
          Retry Agent
        </button>
      )}
    </div>
  );
}

export function DebtPanel({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  if (
    state.phase !== "await_debt" ||
    !state.pending ||
    state.pending.type !== "debt"
  )
    return null;
  const pend = state.pending;
  const p = state.players[pend.player];
  const amount = pend.amount ?? 0;
  const cash = p.cash;
  const shortfall = Math.max(0, amount - cash);
  const creditors = pend.creditors ?? [];
  const target =
    creditors.length > 1
      ? creditors.map((c) => state.players[c.player]?.name ?? "bank").join(" + ")
      : pend.creditor != null
        ? (state.players[pend.creditor]?.name ?? "bank")
        : "the bank";
  return (
    <div className="panel action-panel debt-panel">
      <div className="panel-head">
        <h2>Debt Due</h2>
        <span className="debt-amount">${amount}</span>
      </div>
      <div className="action-prompt">
        {p.glyph} {p.name} owes {target}
        {pend.reason ? ` for ${pend.reason}` : ""}.
      </div>
      <div className="debt-cash">
        Cash ${cash}
        {shortfall > 0 ? ` \u00b7 need $${shortfall} more` : " \u00b7 ready to pay"}
      </div>
      <button
        className="wide-btn pay-debt"
        disabled={busy || cash < amount}
        title={cash < amount ? `Raise $${shortfall} more first` : "Pay the debt"}
        onClick={() => onAction("pay_debt", {})}
      >
        Pay ${amount}
      </button>
      <button
        className="wide-btn bankrupt-btn"
        disabled={busy}
        onClick={() => onAction("declare_bankruptcy", {})}
      >
        Declare Bankruptcy
      </button>
      <div className="action-note">
        Sell buildings or mortgage property in Manage below to raise cash.
      </div>
    </div>
  );
}

const RENT_LABELS = ["Rent", "1 House", "2 Houses", "3 Houses", "4 Houses"];

function deedRents(state: GameState, idx: number) {
  const sq = state.squares[idx];
  const h = state.houses[idx];
  if (sq.type === "street" && sq.rents) {
    return [
      { label: "Rent", value: `$${sq.rents[0]}`, active: h === 0 },
      ...sq.rents.slice(1, 5).map((rent, i) => ({
        label: RENT_LABELS[i + 1],
        value: `$${rent}`,
        active: h === i + 1,
      })),
      { label: "Hotel", value: `$${sq.rents[5]}`, active: h === 5 },
    ];
  }
  if (sq.type === "railroad" && sq.rents) {
    return sq.rents.map((rent, i) => ({
      label: `${i + 1} Railroad${i ? "s" : ""}`,
      value: `$${rent}`,
      active: false,
    }));
  }
  if (sq.type === "utility") {
    const owned =
      state.owner[idx] === null
        ? 0
        : state.owner.filter(
            (owner, i) =>
              owner === state.owner[idx] && state.squares[i].type === "utility",
          ).length;
    return [
      { label: "One utility", value: "4 \u00d7 dice", active: owned < 2 },
      { label: "Both utilities", value: "10 \u00d7 dice", active: owned >= 2 },
    ];
  }
  return [];
}

export function PropertyDeed({
  state,
  idx,
  onClose,
}: {
  state: GameState;
  idx: number | null;
  onClose: () => void;
}) {
  if (idx === null) return null;
  const sq: Square = state.squares[idx];
  const owner = state.owner[idx];
  const h = state.houses[idx];
  const rents = deedRents(state, idx);
  const status =
    owner === null
      ? "Unowned"
      : state.mortgaged[idx]
        ? `Mortgaged \u00b7 ${state.players[owner].name}`
        : h === 5
          ? `Hotel \u00b7 ${state.players[owner].name}`
          : h > 0
            ? `${h} house${h > 1 ? "s" : ""} \u00b7 ${state.players[owner].name}`
            : `Undeveloped \u00b7 ${state.players[owner].name}`;
  return (
    <div
      className="modal-backdrop deed-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={`${sq.name} title deed`}
      onMouseDown={onClose}
    >
      <div className="deed-card" onMouseDown={(e) => e.stopPropagation()}>
        <button
          className="deed-close"
          aria-label="Close title deed"
          onClick={onClose}
        >
          {"\u00d7"}
        </button>
        <div
          className="deed-bar"
          style={{ background: FILL[sq.group ?? ""] ?? "#cfcfcf" }}
        />
        <div className="deed-title">{sq.type === "railroad" ? "\u{1F686}" : sq.type === "utility" ? "\u{1F4A1}" : ""}</div>
        <h2>{sq.name}</h2>
        <div className="deed-group">{groupLabel(sq.group)}</div>
        {rents.length > 0 && (
          <div className="deed-rents">
            {rents.map((rent) => (
              <div
                className={`deed-rent${rent.active ? " active" : ""}`}
                key={rent.label}
              >
                <span>{rent.label}</span>
                <strong>{rent.value}</strong>
              </div>
            ))}
          </div>
        )}
        {sq.type === "street" && sq.rents && (
          <div className="deed-note">
            Owning the full color group doubles the base rent before houses.
          </div>
        )}
        <div className="deed-facts">
          <div>
            <span>Price</span>
            <strong>${sq.price}</strong>
          </div>
          <div>
            <span>Mortgage</span>
            <strong>${sq.mortgage}</strong>
          </div>
          {sq.house_cost != null && (
            <div>
              <span>House / Hotel</span>
              <strong>${sq.house_cost}</strong>
            </div>
          )}
        </div>
        <div className={`deed-status${state.mortgaged[idx] ? " mortgaged" : ""}`}>
          {status}
        </div>
      </div>
    </div>
  );
}

export function WinnerOverlay({
  state,
  open,
  onNewGame,
  onStay,
  onPromote,
  onViewAnalysis,
  promoting = false,
  promoted = false,
  promotionError = null,
}: {
  state: GameState;
  open: boolean;
  onNewGame: () => void;
  onStay: () => void;
  onPromote?: () => void;
  onViewAnalysis?: () => void;
  promoting?: boolean;
  promoted?: boolean;
  promotionError?: string | null;
}) {
  if (!open || state.winner === null) return null;
  const p = state.players[state.winner];
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card winner-card">
        <h2>
          {p.glyph} {p.name} wins!
        </h2>
        <p>
          Final cash: ${p.cash} after {state.turn} turns.
        </p>
        {promoted && onViewAnalysis ? (
          <button className="optbtn" onClick={onViewAnalysis}>
            View Analysis
          </button>
        ) : (
          onPromote && (
            <button
              className="optbtn"
              disabled={promoting}
              onClick={onPromote}
            >
              {promoting ? "Promoting…" : "Promote for Analysis"}
            </button>
          )
        )}
        {promotionError && <div className="error-box">{promotionError}</div>}
        <button className="optbtn" onClick={onNewGame}>
          New Game
        </button>
        <button className="optbtn subtle" onClick={onStay}>
          Stay on this page
        </button>
      </div>
    </div>
  );
}

export function EventLog({ state }: { state: GameState }) {
  return (
    <div className="log">
      {[...state.log].reverse().map((line, i) => (
        <div key={`${i}-${line}`}>{line}</div>
      ))}
    </div>
  );
}
