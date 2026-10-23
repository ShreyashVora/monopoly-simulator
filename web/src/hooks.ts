import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { ActionResult, Anim, GameSetup, GameState } from "./types";

export function useGame() {
  const [state, setState] = useState<GameState | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [anim, setAnim] = useState<Anim | null>(null);
  const timer = useRef<number | null>(null);

  const notify = useCallback((msg: string) => {
    setNotice(msg);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setNotice(null), 2800);
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .state()
      .then((s) => {
        if (alive) setState(s);
      })
      .catch((e: Error) => {
        if (alive) notify(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [notify]);

  const perform = useCallback(
    async (
      request: Promise<ActionResult>,
      fallback: string,
    ): Promise<ActionResult | null> => {
      setBusy(true);
      try {
        const res = await request;
        setState(res.state);
        setAnim(res.anim ?? null);
        if (!res.ok) notify(res.error ?? fallback);
        return res;
      } catch (e) {
        notify((e as Error).message);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [notify],
  );

  const act = useCallback(
    (type: string, payload: Record<string, unknown> = {}) =>
      perform(api.action(type, payload), "Illegal action"),
    [perform],
  );

  const stepAgent = useCallback(
    () => perform(api.agentStep(), "Agent action failed"),
    [perform],
  );

  const startNewGame = useCallback(
    async (setup: GameSetup) => {
      const res = await perform(
        api.action("new_game", {
          n_players: setup.n_players,
          agent_seats: setup.agent_seats,
        }),
        "Could not start a new game",
      );
      return res?.ok ?? false;
    },
    [perform],
  );

  return {
    state, busy, loading, notice, notify, act, stepAgent, startNewGame, anim,
  };
}
