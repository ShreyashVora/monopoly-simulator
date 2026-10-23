"""FastAPI layer for the Monopoly engine, traces, agents, and analysis."""

import asyncio
import json
import pathlib
import random
import threading
from typing import Literal

import rules
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import analysis
from agents import random_agent_action, simulate
from trace import RunStore

WEB_DIST = pathlib.Path(__file__).resolve().parent.parent / "web" / "dist"
PROMOTED_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "promoted"


class ActionRequest(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class GameRequest(BaseModel):
    n_players: int = 4
    seed: int | None = None
    agent_seats: list[int] = Field(default_factory=list)


class RunRequest(BaseModel):
    n_players: int = 4
    seed: int | None = None
    policy: Literal["greedy", "random"] = "greedy"
    max_steps: int = Field(default=4000, ge=10, le=20000)


class Session:
    """One active game plus a history of manual, mixed, and agent runs."""

    def __init__(self, promoted_dir=None):
        self.lock = threading.RLock()
        self.runs = RunStore(promoted_dir=promoted_dir)
        self.game = rules.Game()
        self.run = None
        self.agent_seats = []
        self.policy = None
        self._agent_rng = random.Random()
        self._record_game(self.game.public_state())

    @staticmethod
    def _validate_agent_seats(seats, n_players):
        if seats is None:
            return []
        if not isinstance(seats, (list, tuple)):
            raise rules.RuleError(
                "agent_seats must be a list of player indices.")
        normalized = []
        for seat in seats:
            if isinstance(seat, bool) or not isinstance(seat, int):
                raise rules.RuleError(
                    "Agent seats must be integer player indices.")
            if not 0 <= seat < n_players:
                raise rules.RuleError(
                    f"Agent seat {seat} is outside this game.")
            if seat in normalized:
                raise rules.RuleError("Agent seats must be unique.")
            normalized.append(seat)
        if normalized and len(normalized) >= n_players:
            raise rules.RuleError(
                "A mixed game needs at least one human player.")
        return sorted(normalized)

    def _mixed_label(self):
        n = len(self.agent_seats)
        return f"Human + {n} random agent" + ("" if n == 1 else "s")

    def _record_game(self, state, seed=None, n_players=None):
        if self.run is not None:
            self.run.finish("stopped")
            self.runs.unprotect(self.run.id)
        mixed = bool(self.agent_seats)
        self.run = self.runs.create(
            "mixed" if mixed else "manual", state, seed=seed,
            n_players=n_players,
            policy=self.policy if mixed else None,
            label=self._mixed_label() if mixed else "Manual game",
            agent_seats=self.agent_seats,
            protected=True)

    def _configure_agents(self, agent_seats, seed=None):
        self.agent_seats = list(agent_seats)
        self.policy = "random" if self.agent_seats else None
        self._agent_rng = (random.Random(seed) if seed is not None
                           else random.Random())

    def _decorate(self, state):
        state["run_id"] = self.run.id if self.run is not None else None
        state["agent_seats"] = list(self.agent_seats)
        state["mode"] = "mixed" if self.agent_seats else "manual"
        state["policy"] = self.policy
        state["promoted"] = bool(self.run.promoted) if self.run else False
        return state

    def _error(self, message):
        return {"ok": False, "error": message, "state": self.state(),
                "run_id": self.run.id if self.run is not None else None}

    def state(self):
        with self.lock:
            return self._decorate(self.game.public_state())

    def new_game(self, n_players=4, seed=None, agent_seats=None):
        with self.lock:
            rules.validate_player_count(n_players)
            seats = self._validate_agent_seats(agent_seats, n_players)
            if seed is None:
                self.game.n_players = n_players
                self.game._reset()
            else:
                self.game = rules.Game(seed=seed, n_players=n_players)
            self._configure_agents(seats, seed)
            self._record_game(self.game.public_state(), seed=seed,
                              n_players=n_players)
            return self.state()

    def act(self, action_type, payload=None):
        payload = payload or {}
        with self.lock:
            if action_type == "new_game":
                n_players = payload.get("n_players", self.game.n_players)
                try:
                    rules.validate_player_count(n_players)
                    seats = self._validate_agent_seats(
                        payload.get("agent_seats", []), n_players)
                except rules.RuleError as exc:
                    return self._error(str(exc))
                result = self.game.act(action_type, payload)
                if result["ok"]:
                    self._configure_agents(seats)
                    self._record_game(self.game.public_state(),
                                      n_players=self.game.n_players)
                result["state"] = self.state()
                result["run_id"] = self.run.id
                return result

            if (self.agent_seats and self.game.s.winner is None
                    and self.game.decision_actor() in self.agent_seats):
                return self._error("Waiting for the random agent to move.")

            before = self.game.public_state()
            actor = self.game.decision_actor()
            result = self.game.act(action_type, payload)
            result["state"] = self._decorate(result["state"])
            result["run_id"] = self.run.id
            if result["ok"]:
                meta = {"source": "human"} if self.agent_seats else None
                self.run.add_step(action_type, payload, actor, before, result,
                                  meta=meta)
            return result

    def agent_step(self):
        with self.lock:
            if not self.agent_seats:
                return self._error("No agents are configured in this game.")
            if self.game.s.winner is not None:
                return self._error("The game is over.")
            actor = self.game.decision_actor()
            if actor not in self.agent_seats:
                return self._error("It is a human player's decision.")
            before = self.game.public_state()
            outcome = random_agent_action(self.game, self._agent_rng)
            if outcome is None:
                return self._error(
                    "The agent could not find a legal action.")
            action, payload, result = outcome
            result["state"] = self._decorate(result["state"])
            result["run_id"] = self.run.id
            result["action"] = action
            self.run.add_step(action, payload, actor, before, result,
                              meta={"source": "agent", "policy": "random"})
            return result

    def start_agent(self, req):
        run = simulate(req.seed, req.n_players, req.policy, req.max_steps)
        self.runs.add(run)
        return run

    def promote_run(self, run_id):
        with self.lock:
            return self.runs.promote(run_id)


def create_app(session=None):
    session = session or Session(promoted_dir=PROMOTED_DIR)
    app = FastAPI(title="Monopoly Simulator API", version="2.0.0")
    app.state.session = session
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/state")
    def get_state():
        return session.state()

    @app.post("/api/action")
    def action(body: ActionRequest):
        return session.act(body.type, body.payload)

    @app.post("/api/games")
    def new_game(body: GameRequest):
        try:
            return session.new_game(body.n_players, body.seed,
                                    body.agent_seats)
        except rules.RuleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/agent-step")
    def agent_step():
        return session.agent_step()

    @app.get("/api/runs")
    def list_runs():
        return session.runs.list()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        run = session.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.to_dict(include_steps=False)

    @app.get("/api/runs/{run_id}/trace")
    def get_trace(run_id: str):
        run = session.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.to_dict(include_steps=True)

    @app.post("/api/runs/{run_id}/promote")
    def promote_run(run_id: str):
        try:
            return session.promote_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail="Could not persist promoted game."
            ) from exc

    @app.post("/api/runs")
    def create_run(body: RunRequest):
        try:
            run = session.start_agent(body)
        except rules.RuleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return run.to_dict(include_steps=False)

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str):
        run = session.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        async def stream():
            sent = 0
            while True:
                with run.lock:
                    steps = run.steps[sent:]
                    status = run.status
                    sent += len(steps)
                for step in steps:
                    yield f"data: {json.dumps(step)}\n\n"
                if status != "running":
                    yield "event: done\ndata: {}\n\n"
                    break
                await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/analysis/games")
    def promoted_games():
        return session.runs.promoted()

    @app.get("/api/analysis/games/{run_id}")
    def game_analysis(run_id: str):
        run = session.runs.get(run_id)
        if run is None or not run.promoted:
            raise HTTPException(status_code=404, detail="Promoted game not found")
        return analysis.game_report(run.to_dict(include_steps=True))

    @app.get("/api/analysis/overview")
    def analysis_overview():
        return analysis.overview()

    if WEB_DIST.exists():
        assets = WEB_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        index = WEB_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse(
            "<h1>MONOPOLY</h1><p>UI build not found. Run "
            "<code>npm --prefix web install &amp;&amp; npm --prefix web run build"
            "</code> or use the Vite dev server.</p>")

    return app


app = create_app()
