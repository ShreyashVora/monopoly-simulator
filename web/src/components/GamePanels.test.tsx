import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import state2 from "../test/state2.json";
import type { GameState } from "../types";
import {
  DebtPanel,
  DecisionModal,
  JailPanel,
  ManagePanel,
  PropertyDeed,
  WinnerOverlay,
} from "./GamePanels";

const finished = {
  ...(state2 as unknown as GameState),
  winner: 0,
  phase: "game_over" as const,
  turn: 42,
};

describe("WinnerOverlay", () => {
  it("does not render when closed", () => {
    render(
      <WinnerOverlay
        state={finished}
        open={false}
        onNewGame={vi.fn()}
        onStay={vi.fn()}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers both new game and stay actions", async () => {
    const onNewGame = vi.fn();
    const onStay = vi.fn();
    const user = userEvent.setup();
    render(
      <WinnerOverlay
        state={finished}
        open
        onNewGame={onNewGame}
        onStay={onStay}
      />,
    );

    expect(screen.getByText(/Player 1 wins/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stay on this page" }));
    expect(onStay).toHaveBeenCalledOnce();
    expect(onNewGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "New Game" }));
    expect(onNewGame).toHaveBeenCalledOnce();
  });
});


const base = state2 as unknown as GameState;

function debtState(): GameState {
  const s = structuredClone(base);
  s.current = 0;
  s.phase = "await_debt";
  s.players[0].cash = 40;
  s.pending = {
    type: "debt",
    player: 0,
    amount: 100,
    creditor: 1,
    creditors: [{ player: 1, amount: 100 }],
    reason: "rent on Boardwalk",
    prompt: "Player 1 owes $100 to Player 2 (rent on Boardwalk).",
    options: [
      { action: "pay_debt", label: "Pay $100", payload: {} },
      { action: "declare_bankruptcy", label: "Declare bankruptcy", payload: {} },
    ],
  };
  return s;
}

describe("ManagePanel", () => {
  it("groups properties and shows bank stock and disabled reasons", () => {
    const s = structuredClone(base);
    s.owner[1] = 0;
    s.owner[5] = 0;
    render(
      <ManagePanel state={s} busy={false} onAction={vi.fn()} />,
    );
    expect(screen.getByText("Brown")).toBeInTheDocument();
    expect(screen.getByText("Railroads")).toBeInTheDocument();
    expect(screen.getByText(/32 houses/)).toBeInTheDocument();
    expect(screen.getByText(/12 hotels/)).toBeInTheDocument();
    expect(screen.getByText("Own all Brown streets to build.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /Build \$50 on Mediterranean Avenue/,
      }),
    ).toBeDisabled();
  });

  it("stays usable while a debt is being settled", () => {
    const s = debtState();
    s.owner[1] = 0;
    render(
      <ManagePanel state={s} busy={false} onAction={vi.fn()} />,
    );
    expect(screen.getByText(/Raise cash by selling/)).toBeInTheDocument();
    expect(screen.getByText("Settle the debt first.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /Mortgage Mediterranean Avenue/,
      }),
    ).not.toBeDisabled();
  });
});

describe("decision panels", () => {
  it("uses a non-blocking jail panel", async () => {
    const onAction = vi.fn();
    const user = userEvent.setup();
    const s = structuredClone(base);
    s.phase = "await_jail";
    s.current = 0;
    s.players[0].in_jail = true;
    s.pending = {
      type: "jail",
      player: 0,
      prompt: "Player 1 is in Jail.",
      options: [
        { action: "jail_pay", label: "Pay $50", payload: {} },
        { action: "jail_roll", label: "Roll for doubles", payload: {} },
      ],
    };
    render(<JailPanel state={s} busy={false} onAction={onAction} />);
    expect(screen.getByText(/manage properties below/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pay $50" }));
    expect(onAction).toHaveBeenCalledWith("jail_pay", {});
  });

  it("shows the debt balance and disables payment until covered", async () => {
    const onAction = vi.fn();
    const user = userEvent.setup();
    const s = debtState();
    render(<DebtPanel state={s} busy={false} onAction={onAction} />);
    expect(screen.getByText(/owes Player 2/)).toBeInTheDocument();
    expect(screen.getByText(/need \$60 more/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Pay $100" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Declare Bankruptcy" }),
    );
    expect(onAction).toHaveBeenCalledWith("declare_bankruptcy", {});
  });

  it("does not use the blocking modal for debt or jail decisions", () => {
    const s = debtState();
    render(<DecisionModal state={s} busy={false} onAction={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("PropertyDeed", () => {
  it("shows the full rent schedule and closes", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PropertyDeed state={base} idx={39} onClose={onClose} />);
    expect(
      screen.getByRole("dialog", { name: "Boardwalk title deed" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Hotel")).toBeInTheDocument();
    expect(screen.getByText("$2000")).toBeInTheDocument();
    expect(screen.getByText("Price")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Close title deed" }),
    );
    expect(onClose).toHaveBeenCalledOnce();
  });
});
