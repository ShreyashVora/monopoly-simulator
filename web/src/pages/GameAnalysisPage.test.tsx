import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import type {
  AnalysisOverview,
  GameAnalysis,
  RunSummary,
} from "../types";
import { GameAnalysisPage } from "./GameAnalysisPage";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />,
}));

const run: RunSummary = {
  id: "abc123",
  kind: "agent",
  label: "Agent run",
  seed: 5,
  n_players: 2,
  policy: "greedy",
  agent_seats: [],
  promoted: true,
  created_at: "2026-10-23T12:00:00+00:00",
  status: "done",
  winner: 0,
  steps: 4,
  turns: 3,
  phase: "game_over",
  cash: [1500, 0],
  error: null,
};

const overview: AnalysisOverview = {
  labels: ["GO", "Jail"],
  matrix: [
    [0, 1],
    [1, 0],
  ],
  stationary: [0.5, 0.5],
  hittingTimes: {
    GO: [0, 1],
    Jail: [1, 0],
  },
  note: "Dice-only test chain.",
};

const report: GameAnalysis = {
  run,
  winner: 0,
  steps: 4,
  turns: 3,
  bankrupt_count: 1,
  players: [
    {
      pid: 0,
      name: "Player 1",
      glyph: "A",
      color: "#ed1b24",
      bankrupt: false,
      final_cash: 1500,
      final_net_worth: 2100,
      properties: 2,
      monopolies: 1,
      houses: 2,
      hotels: 0,
      mortgaged: 0,
      peak_cash: 1800,
      peak_net_worth: 2300,
    },
    {
      pid: 1,
      name: "Player 2",
      glyph: "B",
      color: "#16213e",
      bankrupt: true,
      final_cash: 0,
      final_net_worth: 0,
      properties: 0,
      monopolies: 0,
      houses: 0,
      hotels: 0,
      mortgaged: 0,
      peak_cash: 900,
      peak_net_worth: 1200,
    },
  ],
  timeline: {
    labels: ["Start", "Step 1", "Step 2", "Step 3", "Step 4"],
    turns: [1, 1, 2, 2, 3],
    cash: [[1500, 1500], [1500, 1200], [1800, 600], [1800, 0], [1500, 0]],
    net_worth: [[1500, 1500], [1600, 1300], [2000, 700], [2200, 0], [2100, 0]],
    properties: [[0, 0], [1, 0], [1, 1], [2, 1], [2, 0]],
  },
  actions: { roll: 3, end_turn: 1 },
  rolls: { 3: 2, 7: 1 },
  observed_transitions: {
    labels: ["GO", "Jail"],
    counts: [
      [0, 2],
      [1, 0],
    ],
    total: 3,
  },
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/analysis/abc123"]}>
      <Routes>
        <Route path="/analysis/:runId" element={<GameAnalysisPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("GameAnalysisPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "analysis").mockResolvedValue(overview);
  });

  it("renders the per-game dashboard", async () => {
    const games = vi.spyOn(api, "gameAnalysis").mockResolvedValue(report);
    renderPage();

    expect(await screen.findByText("Agent run")).toBeInTheDocument();
    expect(games).toHaveBeenCalledWith("abc123");
    expect(screen.getAllByText("$2,100").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Player 1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Player 2/).length).toBeGreaterThan(0);
    expect(screen.getByText("Bankruptcies")).toBeInTheDocument();
    expect(screen.getByText("Observed moves heatmap")).toBeInTheDocument();
    expect(screen.getByText("Expected rolls to target")).toBeInTheDocument();
    expect(screen.queryByText("Action sources")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("chart")).toHaveLength(6);
    expect(screen.getByText("roll")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All promoted games" }))
      .toHaveAttribute("href", "/analysis");
  });

  it("shows a not-found error with a way back", async () => {
    vi.spyOn(api, "gameAnalysis").mockRejectedValue(
      new Error("Promoted game not found"),
    );
    renderPage();

    expect(
      await screen.findByText("Promoted game not found"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to analysis" }))
      .toHaveAttribute("href", "/analysis");
  });
});
