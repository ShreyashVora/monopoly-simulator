import type {
  ActionResult,
  AnalysisOverview,
  GameAnalysis,
  GameState,
  RunSummary,
  RunTrace,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      // keep status text
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  state: () => request<GameState>("/api/state"),
  action: (type: string, payload: Record<string, unknown> = {}) =>
    request<ActionResult>("/api/action", {
      method: "POST",
      body: JSON.stringify({ type, payload }),
    }),
  newGame: (n_players: number, seed?: number | null, agent_seats: number[] = []) =>
    request<GameState>("/api/games", {
      method: "POST",
      body: JSON.stringify({ n_players, seed: seed ?? null, agent_seats }),
    }),
  agentStep: () =>
    request<ActionResult>("/api/agent-step", {
      method: "POST",
    }),
  runs: () => request<RunSummary[]>("/api/runs"),
  run: (id: string) => request<RunSummary>(`/api/runs/${id}`),
  trace: (id: string) => request<RunTrace>(`/api/runs/${id}/trace`),
  promoteRun: (id: string) =>
    request<RunSummary>(`/api/runs/${id}/promote`, { method: "POST" }),
  promotedGames: () => request<RunSummary[]>("/api/analysis/games"),
  gameAnalysis: (id: string) =>
    request<GameAnalysis>(`/api/analysis/games/${id}`),
  startRun: (opts: {
    n_players: number;
    seed?: number | null;
    policy: "greedy" | "random";
    max_steps?: number;
  }) =>
    request<RunSummary>("/api/runs", {
      method: "POST",
      body: JSON.stringify(opts),
    }),
  analysis: () => request<AnalysisOverview>("/api/analysis/overview"),
};
