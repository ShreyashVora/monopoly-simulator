import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import state4 from "../test/state4.json";
import state6 from "../test/state6.json";
import type { GameState } from "../types";
import { Board } from "./Board";

const base = state4 as unknown as GameState;

describe("Board", () => {
  it("renders 40 squares and one token per player", () => {
    render(<Board state={base} />);
    expect(document.querySelectorAll(".cell").length).toBe(121);
    expect(document.querySelectorAll(".token").length).toBe(4);
    expect(screen.getAllByTitle(/Player \d/).length).toBeGreaterThanOrEqual(4);
  });

  it("marks owner, buildings, and mortgage", () => {
    const s = structuredClone(base);
    s.owner[1] = 0;
    s.houses[1] = 2;
    s.mortgaged[3] = true;
    s.owner[3] = 1;
    render(<Board state={s} />);
    expect(document.querySelectorAll(".owner-badge").length).toBe(2);
    expect(screen.getByTitle(/Owned by Player 1/)).toHaveTextContent(
      s.players[0].glyph,
    );
    expect(document.querySelector(".buildings")).toHaveTextContent("\u{1F3E0}\u{1F3E0}");
    expect(document.querySelector(".mort-tag")).toHaveTextContent("M");
  });

  it("supports six players", () => {
    render(<Board state={state6 as unknown as GameState} />);
    expect(document.querySelectorAll(".token").length).toBe(6);
  });

  it("opens a title deed when a property square is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <Board state={base} onSelect={onSelect} selectedIdx={1} />,
    );
    const cell = screen.getByRole("button", {
      name: "Open title deed for Mediterranean Avenue",
    });
    expect(cell).toHaveClass("selected");
    await user.click(cell);
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("shows an extra-roll reminder after doubles", () => {
    const s = { ...structuredClone(base), doubles: 1 };
    render(<Board state={s} />);
    expect(screen.getByText(/Doubles — roll again/i)).toBeInTheDocument();
  });
});
