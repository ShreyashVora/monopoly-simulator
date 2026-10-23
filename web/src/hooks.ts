import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { ActionResult, Anim, GameState } from "./types";

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

  const act = useCallback(
    async (
      type: string,
      payload: Record<string, unknown> = {},
    ): Promise<ActionResult | null> => {
      setBusy(true);
      try {
        const res = await api.action(type, payload);
        setState(res.state);
        setAnim(res.anim ?? null);
        if (!res.ok) notify(res.error ?? "Illegal action");
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

  const startNewGame = useCallback(
    async (n: number) => {
      setBusy(true);
      try {
        const res = await api.action("new_game", { n_players: n });
        setState(res.state);
        setAnim(null);
        if (!res.ok) {
          notify(res.error ?? "Could not start a new game");
          return false;
        }
        return true;
      } catch (e) {
        notify((e as Error).message);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [notify],
  );

  return { state, busy, loading, notice, notify, act, startNewGame, anim };
}
