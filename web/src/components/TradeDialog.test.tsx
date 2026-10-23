import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import state2 from "../test/state2.json";
import type { GameState } from "../types";
import { TradeDialog } from "./TradeDialog";

function tradeState(): GameState {
  const state = {
    ...(state2 as unknown as GameState),
    owner: [...(state2 as unknown as GameState).owner],
    mortgaged: [...(state2 as unknown as GameState).mortgaged],
    houses: [...(state2 as unknown as GameState).houses],
    players: (state2 as unknown as GameState).players.map((p) => ({ ...p })),
  };
  state.owner[1] = 0;
  state.owner[3] = 1;
  return state;
}

describe("TradeDialog", () => {
  it("sends cash and property terms", async () => {
    const onAction = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TradeDialog
        state={tradeState()}
        busy={false}
        open
        onClose={onClose}
        onAction={onAction}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Propose a trade" }),
    ).toBeInTheDocument();
    const cash = screen.getByLabelText("You give cash");
    await user.clear(cash);
    await user.type(cash, "100");
    await user.click(
      screen.getByRole("checkbox", {
        name: "Include Mediterranean Avenue",
      }),
    );
    await user.click(
      screen.getByRole("checkbox", { name: "Include Baltic Avenue" }),
    );
    await user.click(screen.getByRole("button", { name: "Send offer" }));

    expect(onAction).toHaveBeenCalledWith("trade_propose", {
      recipient: 1,
      give: { cash: 100, properties: [1], goojf: 0 },
      want: { cash: 0, properties: [3], goojf: 0 },
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("explains why mortgaged and improved deeds are unavailable", () => {
    const state = tradeState();
    state.mortgaged[1] = true;
    state.houses[3] = 1;
    render(
      <TradeDialog
        state={state}
        busy={false}
        open
        onClose={vi.fn()}
        onAction={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("checkbox", {
        name: "Include Mediterranean Avenue",
      }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "Include Baltic Avenue" }),
    ).toBeDisabled();
    expect(screen.getByText("Unmortgage this deed first.")).toBeInTheDocument();
    expect(
      screen.getByText("Sell all Brown buildings first."),
    ).toBeInTheDocument();
  });

  it("shows a pending offer from the recipient's view and accepts it", async () => {
    const state = tradeState();
    state.phase = "await_trade";
    state.pending = {
      type: "trade",
      player: 1,
      proposer: 0,
      recipient: 1,
      give: { cash: 100, properties: [1], goojf: 0 },
      want: { cash: 0, properties: [3], goojf: 0 },
      prompt: "Trade offer",
      options: [],
    };
    const onAction = vi.fn();
    const user = userEvent.setup();
    render(
      <TradeDialog
        state={state}
        busy={false}
        open={false}
        onClose={vi.fn()}
        onAction={onAction}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Trade offer" }),
    ).toBeInTheDocument();
    expect(screen.getByText("You receive")).toBeInTheDocument();
    expect(screen.getByText("You give")).toBeInTheDocument();
    expect(screen.getByText("Your cash after: $1600")).toBeInTheDocument();
    expect(screen.getByText("Their cash after: $1400")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Accept trade" }));
    expect(onAction).toHaveBeenCalledWith("trade_accept", {});
  });

  it("rejects a pending offer", async () => {
    const state = tradeState();
    state.phase = "await_trade";
    state.pending = {
      type: "trade",
      player: 1,
      proposer: 0,
      recipient: 1,
      give: { cash: 10, properties: [], goojf: 0 },
      want: { cash: 0, properties: [], goojf: 0 },
      prompt: "Trade offer",
      options: [],
    };
    const onAction = vi.fn();
    const user = userEvent.setup();
    render(
      <TradeDialog
        state={state}
        busy={false}
        open={false}
        onClose={vi.fn()}
        onAction={onAction}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reject trade" }));
    expect(onAction).toHaveBeenCalledWith("trade_reject", {});
  });

  it("requires at least one item", () => {
    render(
      <TradeDialog
        state={tradeState()}
        busy={false}
        open
        onClose={vi.fn()}
        onAction={vi.fn()}
      />,
    );

    expect(screen.getByText("Add at least one item to the trade.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send offer" })).toBeDisabled();
  });
});
