import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api } from "./api";
import state2 from "./test/state2.json";
import state4 from "./test/state4.json";
import type { GameState } from "./types";

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

    expect(await screen.findByText("How many players?")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
    for (const n of [2, 3, 4, 5, 6]) {
      expect(screen.getByRole("button", { name: String(n) })).toBeInTheDocument();
    }
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

    await screen.findByText("How many players?");
    await user.click(screen.getByRole("button", { name: "2" }));

    await waitFor(() =>
      expect(action).toHaveBeenCalledWith("new_game", { n_players: 2 }),
    );
    await waitFor(() =>
      expect(screen.queryByText("How many players?")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/Player 2/)).toBeInTheDocument();
    expect(document.querySelectorAll(".pcard").length).toBe(2);
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
    expect(screen.queryByText("How many players?")).not.toBeInTheDocument();
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
    expect(screen.queryByText("How many players?")).not.toBeInTheDocument();
  });
});
