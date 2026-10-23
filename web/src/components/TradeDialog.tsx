import { useEffect, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import {
  FILL,
  propertyGroups,
  tradePropertyReason,
} from "../board";
import type { GameState, TradeTerms } from "../types";

interface Draft {
  cash: string;
  properties: number[];
  goojf: number;
}

function blankDraft(): Draft {
  return { cash: "0", properties: [], goojf: 0 };
}

function cashValue(value: string): number | null {
  if (value.trim() === "") return 0;
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

function draftTerms(draft: Draft): TradeTerms | null {
  const cash = cashValue(draft.cash);
  if (cash === null) return null;
  return { cash, properties: draft.properties, goojf: draft.goojf };
}

function TermList({ state, terms }: { state: GameState; terms: TradeTerms }) {
  const items: ReactNode[] = [];
  if (terms.cash) items.push(<li key="cash">${terms.cash}</li>);
  terms.properties.forEach((idx) => {
    const sq = state.squares[idx];
    items.push(
      <li key={`p-${idx}`}>
        <span
          className="trade-color"
          style={{ background: FILL[sq.group ?? ""] ?? "#999" }}
        />
        {sq.name}
      </li>,
    );
  });
  if (terms.goojf) {
    items.push(
      <li key="goojf">
        {"\u{1F39F}"} {terms.goojf} Get Out of Jail Free
      </li>,
    );
  }
  if (!items.length) return <div className="trade-empty">Nothing</div>;
  return <ul className="trade-term-list">{items}</ul>;
}

function TradeColumn({
  title,
  state,
  pid,
  draft,
  setDraft,
  busy,
}: {
  title: string;
  state: GameState;
  pid: number;
  draft: Draft;
  setDraft: Dispatch<SetStateAction<Draft>>;
  busy: boolean;
}) {
  const p = state.players[pid];
  const groups = propertyGroups(state, pid);
  const toggleProperty = (idx: number, checked: boolean) => {
    setDraft((d) => ({
      ...d,
      properties: checked
        ? [...d.properties, idx]
        : d.properties.filter((x) => x !== idx),
    }));
  };
  return (
    <section className="trade-column">
      <h3>
        {title}
        <span>
          {p.glyph} {p.name}
        </span>
      </h3>
      <label className="trade-field">
        Cash
        <input
          type="number"
          min={0}
          max={p.cash}
          step={1}
          value={draft.cash}
          disabled={busy}
          aria-label={`${title} cash`}
          onChange={(e) => setDraft((d) => ({ ...d, cash: e.target.value }))}
        />
      </label>
      <div className="trade-cash-note">Available ${p.cash}</div>
      {p.goojf > 0 && (
        <label className="trade-field">
          Get Out of Jail Free
          <input
            type="number"
            min={0}
            max={p.goojf}
            step={1}
            value={draft.goojf}
            disabled={busy}
            aria-label={`${title} Get Out of Jail Free`}
            onChange={(e) =>
              setDraft((d) => ({
                ...d,
                goojf: Math.max(
                  0,
                  Math.min(p.goojf, Number(e.target.value) || 0),
                ),
              }))
            }
          />
        </label>
      )}
      <div className="trade-props">
        {!groups.length ? (
          <div className="trade-empty">No properties.</div>
        ) : (
          groups.map((group) => (
            <div className="trade-group" key={group.group}>
              <div
                className="trade-group-head"
                style={{ borderLeftColor: FILL[group.group] ?? "#999" }}
              >
                {group.label}
              </div>
              {group.idxs.map((idx) => {
                const sq = state.squares[idx];
                const reason = tradePropertyReason(state, idx, pid);
                const checked = draft.properties.includes(idx);
                return (
                  <label
                    className={`trade-prop${reason ? " disabled" : ""}`}
                    key={idx}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={busy || reason !== null}
                      aria-label={`${checked ? "Remove" : "Include"} ${sq.name}`}
                      onChange={(e) =>
                        toggleProperty(idx, e.target.checked)
                      }
                    />
                    <span
                      className="trade-color"
                      style={{ background: FILL[sq.group ?? ""] ?? "#999" }}
                    />
                    <span className="trade-prop-name">{sq.name}</span>
                    {reason && (
                      <span className="trade-prop-reason">{reason}</span>
                    )}
                  </label>
                );
              })}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export function TradeDialog({
  state,
  busy,
  open,
  onClose,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  open: boolean;
  onClose: () => void;
  onAction: (type: string, payload: Record<string, unknown>) => void;
}) {
  const pending = state.pending;
  const isOffer =
    state.phase === "await_trade" &&
    pending?.type === "trade" &&
    state.winner === null;
  const others = state.players.filter(
    (p) => !p.bankrupt && p.pid !== state.current,
  );
  const [recipient, setRecipient] = useState<number>(others[0]?.pid ?? -1);
  const [give, setGive] = useState<Draft>(blankDraft);
  const [want, setWant] = useState<Draft>(blankDraft);
  const recipientPid = others.some((p) => p.pid === recipient)
    ? recipient
    : (others[0]?.pid ?? -1);

  useEffect(() => {
    if (!open || isOffer) return;
    setGive(blankDraft());
    setWant(blankDraft());
    setRecipient(others[0]?.pid ?? -1);
    // Reset only when the composer opens or a new run starts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isOffer, state.run_id]);

  useEffect(() => {
    setWant(blankDraft());
  }, [recipientPid]);

  if (isOffer && pending) {
    const proposer = state.players[pending.proposer ?? pending.player];
    const recipientPlayer =
      state.players[pending.recipient ?? state.current];
    const giveTerms = pending.give ?? { cash: 0, properties: [], goojf: 0 };
    const wantTerms = pending.want ?? { cash: 0, properties: [], goojf: 0 };
    return (
      <div
        className="modal-backdrop trade-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="Trade offer"
      >
        <div className="modal-card trade-card">
          <div className="trade-head">
            <h2>Trade offer</h2>
            <span className="trade-offer-from">
              {proposer.glyph} {proposer.name}
            </span>
          </div>
          <div className="trade-offer-sub">
            {proposer.name} proposes a trade to {recipientPlayer.name}.
          </div>
          <div className="trade-columns">
            <section className="trade-column">
              <h3>You receive</h3>
              <TermList state={state} terms={giveTerms} />
            </section>
            <section className="trade-column">
              <h3>You give</h3>
              <TermList state={state} terms={wantTerms} />
            </section>
          </div>
          <div className="trade-preview">
            <span>
              Your cash after: $
              {recipientPlayer.cash + giveTerms.cash - wantTerms.cash}
            </span>
            <span>
              Their cash after: $
              {proposer.cash - giveTerms.cash + wantTerms.cash}
            </span>
          </div>
          <div className="trade-actions">
            <button
              className="trade-send"
              disabled={busy}
              onClick={() => onAction("trade_accept", {})}
            >
              Accept trade
            </button>
            <button
              className="trade-cancel"
              disabled={busy}
              onClick={() => onAction("trade_reject", {})}
            >
              Reject trade
            </button>
          </div>
          <div className="action-note">
            No counteroffers. Accept or reject this offer.
          </div>
        </div>
      </div>
    );
  }

  if (!open || state.winner !== null || recipientPid < 0) return null;

  const proposer = state.players[state.current];
  const recipientPlayer = state.players[recipientPid];
  const giveTerms = draftTerms(give);
  const wantTerms = draftTerms(want);
  let invalidReason: string | null = null;
  if (!giveTerms || !wantTerms) {
    invalidReason = "Cash must be a non-negative whole dollar amount.";
  } else if (giveTerms.cash > proposer.cash) {
    invalidReason = `You only have $${proposer.cash} in cash.`;
  } else if (wantTerms.cash > recipientPlayer.cash) {
    invalidReason = `${recipientPlayer.name} only has $${recipientPlayer.cash}.`;
  } else if (giveTerms.goojf > proposer.goojf) {
    invalidReason = "You do not have that many Get Out of Jail Free cards.";
  } else if (wantTerms.goojf > recipientPlayer.goojf) {
    invalidReason = `${recipientPlayer.name} does not have that many cards.`;
  } else if (
    giveTerms.properties.some(
      (idx) => tradePropertyReason(state, idx, state.current) !== null,
    )
  ) {
    invalidReason = "One of your selected properties cannot be traded.";
  } else if (
    wantTerms.properties.some(
      (idx) => tradePropertyReason(state, idx, recipientPid) !== null,
    )
  ) {
    invalidReason = "One of their selected properties cannot be traded.";
  } else if (
    !giveTerms.cash &&
    !giveTerms.properties.length &&
    !giveTerms.goojf &&
    !wantTerms.cash &&
    !wantTerms.properties.length &&
    !wantTerms.goojf
  ) {
    invalidReason = "Add at least one item to the trade.";
  }

  const send = () => {
    if (invalidReason || !giveTerms || !wantTerms) return;
    onAction("trade_propose", {
      recipient: recipientPid,
      give: giveTerms,
      want: wantTerms,
    });
    onClose();
  };

  return (
    <div
      className="modal-backdrop trade-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Propose a trade"
    >
      <div className="modal-card trade-card">
        <div className="trade-head">
          <h2>Trade</h2>
          <button
            className="trade-close"
            disabled={busy}
            aria-label="Close trade"
            onClick={onClose}
          >
            {"\u00d7"}
          </button>
        </div>
        <div className="trade-recipient">
          <label>
            Trade with
            <select
              value={recipientPid}
              disabled={busy}
              onChange={(e) => setRecipient(Number(e.target.value))}
            >
              {others.map((p) => (
                <option value={p.pid} key={p.pid}>
                  {p.glyph} {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="trade-columns">
          <TradeColumn
            title="You give"
            state={state}
            pid={state.current}
            draft={give}
            setDraft={setGive}
            busy={busy}
          />
          <TradeColumn
            title="You receive"
            state={state}
            pid={recipientPid}
            draft={want}
            setDraft={setWant}
            busy={busy}
          />
        </div>
        <div className="trade-preview">
          <span>
            Your cash after: $
            {(giveTerms?.cash ?? 0) > proposer.cash
              ? "—"
              : proposer.cash - (giveTerms?.cash ?? 0) + (wantTerms?.cash ?? 0)}
          </span>
          <span>
            Their cash after: $
            {recipientPlayer.cash -
              (wantTerms?.cash ?? 0) +
              (giveTerms?.cash ?? 0)}
          </span>
        </div>
        {invalidReason && (
          <div className="trade-error">{invalidReason}</div>
        )}
        <div className="trade-actions">
          <button
            className="trade-send"
            disabled={busy || invalidReason !== null}
            onClick={send}
          >
            Send offer
          </button>
          <button
            className="trade-cancel"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
