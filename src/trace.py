"""Replayable run traces shared by manual and agent play."""

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


class Run:
    """A sequence of engine actions plus the state after every action."""

    def __init__(self, kind, initial_state, seed=None, n_players=None,
                 policy=None, label=None):
        self.lock = threading.RLock()
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.initial = deepcopy(initial_state)
        self.seed = seed
        self.n_players = n_players if n_players is not None else len(
            initial_state["players"])
        self.policy = policy
        self.label = label or f"{kind.title()} run"
        self.created_at = _now()
        self.status = "running"
        self.winner = None
        self.steps = []
        self.error = None

    def add_step(self, action, payload, actor, before, result, meta=None):
        with self.lock:
            self.steps.append({
                "seq": len(self.steps) + 1,
                "action": action,
                "payload": deepcopy(payload or {}),
                "actor": actor,
                "phase_before": before["phase"],
                "pending_before": deepcopy(before["pending"]),
                "state": deepcopy(result["state"]),
                "events": list(result.get("events") or []),
                "anim": deepcopy(result.get("anim")),
                "meta": deepcopy(meta or {}),
                "created_at": _now(),
            })
            self.winner = result["state"].get("winner")
            if self.winner is not None:
                self.status = "done"

    def finish(self, status="done", error=None):
        with self.lock:
            self.status = status
            self.error = error
            if self.winner is not None:
                self.status = "done"

    def summary(self):
        with self.lock:
            return self._summary()

    def _summary(self):
        last_state = self.steps[-1]["state"] if self.steps else self.initial
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "seed": self.seed,
            "n_players": self.n_players,
            "policy": self.policy,
            "created_at": self.created_at,
            "status": self.status,
            "winner": self.winner,
            "steps": len(self.steps),
            "turns": last_state.get("turn", 1),
            "phase": last_state.get("phase"),
            "cash": [p["cash"] for p in last_state.get("players", [])],
            "error": self.error,
        }

    def to_dict(self, include_steps=True):
        with self.lock:
            data = self._summary()
            data["initial"] = deepcopy(self.initial)
            if include_steps:
                data["steps"] = deepcopy(self.steps)
            return data


class RunStore:
    """Thread-safe in-memory run history."""

    def __init__(self, limit=30):
        self._lock = threading.RLock()
        self._runs = {}
        self._order = []
        self._limit = limit
        self._protected = set()

    def create(self, kind, initial_state, protected=False, **kwargs):
        return self.add(Run(kind, initial_state, **kwargs),
                        protected=protected)

    def add(self, run, protected=False):
        with self._lock:
            self._runs[run.id] = run
            self._order.append(run.id)
            if protected:
                self._protected.add(run.id)
            while len(self._order) > self._limit:
                old = next((rid for rid in self._order
                            if rid not in self._protected), None)
                if old is None:
                    break
                self._order.remove(old)
                self._runs.pop(old, None)
        return run

    def protect(self, run_id):
        with self._lock:
            self._protected.add(run_id)

    def unprotect(self, run_id):
        with self._lock:
            self._protected.discard(run_id)

    def get(self, run_id):
        with self._lock:
            return self._runs.get(run_id)

    def require(self, run_id):
        run = self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def list(self):
        with self._lock:
            return [self._runs[i].summary() for i in reversed(self._order)
                    if i in self._runs]

    def all_runs(self):
        with self._lock:
            return [self._runs[i] for i in reversed(self._order)
                    if i in self._runs]
