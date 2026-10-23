"""Replayable run traces shared by manual and agent play."""

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


class Run:
    """A sequence of engine actions plus the state after every action."""

    def __init__(self, kind, initial_state, seed=None, n_players=None,
                 policy=None, label=None, agent_seats=None, promoted=False):
        self.lock = threading.RLock()
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.initial = deepcopy(initial_state)
        self.seed = seed
        self.n_players = n_players if n_players is not None else len(
            initial_state["players"])
        self.policy = policy
        self.agent_seats = list(agent_seats or [])
        self.label = label or f"{kind.title()} run"
        self.created_at = _now()
        self.status = "running"
        self.winner = None
        self.steps = []
        self.error = None
        self.promoted = bool(promoted)

    @classmethod
    def from_dict(cls, data):
        """Rebuild a run from its persisted trace JSON."""
        run = cls(
            data["kind"],
            data["initial"],
            seed=data.get("seed"),
            n_players=data.get("n_players"),
            policy=data.get("policy"),
            label=data.get("label"),
            agent_seats=data.get("agent_seats"),
            promoted=bool(data.get("promoted")),
        )
        run.id = data.get("id") or run.id
        run.created_at = data.get("created_at") or run.created_at
        run.status = data.get("status", "running")
        run.winner = data.get("winner")
        run.error = data.get("error")
        run.steps = deepcopy(data.get("steps") or [])
        return run

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
            "agent_seats": list(self.agent_seats),
            "promoted": self.promoted,
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
    """Thread-safe run history with optional persistent promoted games."""

    def __init__(self, limit=30, promoted_dir=None):
        self._lock = threading.RLock()
        self._runs = {}
        self._order = []
        self._limit = limit
        self._protected = set()
        self._promoted_dir = (Path(promoted_dir).expanduser()
                              if promoted_dir is not None else None)
        self._load_promoted()

    def _load_promoted(self):
        if self._promoted_dir is None:
            return
        self._promoted_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self._promoted_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                run = Run.from_dict(data)
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if not run.promoted:
                continue
            with self._lock:
                self._runs[run.id] = run
                self._order.append(run.id)
                self._protected.add(run.id)

    def _save_promoted(self, run):
        if self._promoted_dir is None:
            return
        self._promoted_dir.mkdir(parents=True, exist_ok=True)
        path = self._promoted_dir / f"{run.id}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(run.to_dict(include_steps=True), indent=2),
                        encoding="utf-8")
        os.replace(temp, path)

    def create(self, kind, initial_state, protected=False, **kwargs):
        return self.add(Run(kind, initial_state, **kwargs),
                        protected=protected)

    def add(self, run, protected=False):
        with self._lock:
            self._runs[run.id] = run
            self._order.append(run.id)
            if protected or run.promoted:
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
            run = self._runs.get(run_id)
            if run is not None and run.promoted:
                return
            self._protected.discard(run_id)

    def promote(self, run_id):
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            if run.winner is None:
                raise ValueError("Only completed games can be promoted.")
            was_promoted = run.promoted
            run.promoted = True
            try:
                self._save_promoted(run)
            except OSError:
                run.promoted = was_promoted
                if not was_promoted:
                    self._protected.discard(run_id)
                raise
            self._protected.add(run_id)
            return run.summary()

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

    def promoted(self):
        with self._lock:
            rows = [self._runs[i].summary() for i in self._order
                    if i in self._runs and self._runs[i].promoted]
        return sorted(rows, key=lambda run: run["created_at"], reverse=True)

    def all_runs(self):
        with self._lock:
            return [self._runs[i] for i in reversed(self._order)
                    if i in self._runs]
