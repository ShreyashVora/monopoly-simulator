import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api } from "./api";
import state2 from "./test/state2.json";
import state4 from "./test/state4.json";
import type { GameState, RunSummary } from "./types";

const four = state4 as unknown as GameState;
const two = state2 as unknown as GameState;

describe("setup flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "state").mockResolvedValue(structuredClone(four));
  });

  it("requires a player count before the first game", async () => {
    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "New Game" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
    for (const n of [2, 3, 4, 5, 6]) {
      expect(screen.getByRole("button", { name: String(n) })).toBeInTheDocument();
    }
    expect(
      screen.getByRole("button", { name: /Hot-seat/ }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("starts a two-player game from the picker", async () => {
    const action = vi
      .spyOn(api, "action")
      .mockResolvedValue({ ok: true, state: structuredClone(two) });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "New Game" });
    await user.click(screen.getByRole("button", { name: "2" }));
    await user.click(screen.getByRole("button", { name: "Start Game" }));

    await waitFor(() =>
      expect(action).toHaveBeenCalledWith("new_game", {
        n_players: 2,
        agent_seats: [],
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "New Game" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/Player 2/)).toBeInTheDocument();
    expect(document.querySelectorAll(".pcard").length).toBe(2);
  });

  it("starts a mixed game with the remaining seats as agents", async () => {
    const action = vi
      .spyOn(api, "action")
      .mockResolvedValue({ ok: true, state: structuredClone(four) });
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "New Game" });
    await user.click(
      screen.getByRole("button", { name: /Humans \+ agents/ }),
    );
    expect(screen.getByText(/Player 4 will be a random agent/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Start Game" }));

    await waitFor(() =>
      expect(action).toHaveBeenCalledWith("new_game", {
        n_players: 4,
        agent_seats: [3],
      }),
    );
  });

  it("auto-steps an agent decision and stops on a human turn", async () => {
    const agentTurn = {
      ...structuredClone(four),
      turn: 2,
      current: 0,
      agent_seats: [0],
      mode: "mixed" as const,
      policy: "random",
      log: ["New game", "Player 4 ends their turn"],
    };
    const humanTurn = {
      ...structuredClone(agentTurn),
      current: 1,
      log: [...agentTurn.log, "Player 1 rolls"],
    };
    vi.mocked(api.state).mockResolvedValue(agentTurn);
    const step = vi
      .spyOn(api, "agentStep")
      .mockResolvedValue({ ok: true, state: humanTurn });

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Random Agent")).toBeInTheDocument();
    await waitFor(() => expect(step).toHaveBeenCalledTimes(1), {
      timeout: 2000,
    });
    expect(screen.queryByText("Random Agent")).not.toBeInTheDocument();
  });

  it("resumes an in-progress game without reopening setup", async () => {
    const inProgress = {
      ...structuredClone(four),
      turn: 5,
      log: ["New game", "Player 1 rolls"],
    };
    vi.mocked(api.state).mockResolvedValue(inProgress);

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Player 4/)).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "New Game" }),
    ).not.toBeInTheDocument();
  });
});

describe("finished game", () => {
  const finished = {
    ...(state2 as unknown as GameState),
    winner: 0,
    phase: "game_over" as const,
    turn: 42,
  };

  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(api, "state").mockResolvedValue(structuredClone(finished));
  });

  it("lets the player dismiss the result and navigate away", async () => {
    vi.spyOn(api, "runs").mockResolvedValue([]);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: /Player 1 wins/ });
    await user.click(screen.getByRole("button", { name: "Stay on this page" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.querySelector(".board")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Runs" }));
    expect(await screen.findByText("No runs yet.")).toBeInTheDocument();
  });

  it("promotes the finished game and exposes the analysis link", async () => {
    const withRun = {
      ...structuredClone(finished),
      run_id: "run123",
    };
    vi.mocked(api.state).mockResolvedValue(withRun);
    const summary: RunSummary = {
      id: "run123",
      kind: "manual",
      label: "Manual game",
      seed: null,
      n_players: 2,
      policy: null,
      promoted: true,
      created_at: "2026-10-23T12:00:00+00:00",
      status: "done",
      winner: 0,
      steps: 10,
      turns: 42,
      phase: "game_over",
      cash: [1500, 0],
      error: null,
    };
    const promote = vi.spyOn(api, "promoteRun").mockResolvedValue(summary);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Promote for Analysis" }),
    );
    await waitFor(() => expect(promote).toHaveBeenCalledWith("run123"));
    expect(
      await screen.findByRole("button", { name: "View Analysis" }),
    ).toBeInTheDocument();
  });

  it("keeps the result dismissed when Play is remounted", async () => {
    const user = userEvent.setup();
    const first = render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: /Player 1 wins/ });
    await user.click(screen.getByRole("button", { name: "Stay on this page" }));
    first.unmount();

    render(
      <MemoryRouter initialEntries={["/play"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Player 2/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "New Game" }),
    ).not.toBeInTheDocument();
  });
});
