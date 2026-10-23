import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type { RunSummary } from "../types";
import { AnalysisPage } from "./AnalysisPage";

const promoted: RunSummary = {
  id: "abc123",
  kind: "mixed",
  label: "Human + 1 random agent",
  seed: 5,
  n_players: 3,
  policy: "random",
  agent_seats: [2],
  promoted: true,
  created_at: "2026-10-23T12:00:00+00:00",
  status: "done",
  winner: 0,
  steps: 120,
  turns: 40,
  phase: "game_over",
  cash: [1200, 0, 0],
  error: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalysisPage />
    </MemoryRouter>,
  );
}

describe("AnalysisPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lists only promoted games with a link to each dashboard", async () => {
    vi.spyOn(api, "promotedGames").mockResolvedValue([promoted]);
    renderPage();

    expect(
      await screen.findByRole("link", { name: /Human \+ 1 random agent/ }),
    ).toHaveAttribute("href", "/analysis/abc123");
    expect(screen.getByText(/1 agent/)).toBeInTheDocument();
    expect(screen.getByText("promoted")).toBeInTheDocument();
  });

  it("shows a play link when nothing has been promoted", async () => {
    vi.spyOn(api, "promotedGames").mockResolvedValue([]);
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "No promoted games yet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Play a game" }))
      .toHaveAttribute("href", "/play");
  });

  it("surfaces a loading error", async () => {
    vi.spyOn(api, "promotedGames").mockRejectedValue(new Error("offline"));
    renderPage();

    expect(await screen.findByText("offline")).toBeInTheDocument();
  });
});
