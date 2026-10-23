"""FastAPI layer for the Monopoly engine, traces, agents, and analysis."""

import asyncio
import json
import pathlib
import threading
from typing import Literal

import rules
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import analysis
from agents import simulate
from trace import RunStore

WEB_DIST = pathlib.Path(__file__).resolve().parent.parent / "web" / "dist"


class ActionRequest(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class GameRequest(BaseModel):
    n_players: int = 4
    seed: int | None = None


class RunRequest(BaseModel):
    n_players: int = 4
    seed: int | None = None
    policy: Literal["greedy", "random"] = "greedy"
    max_steps: int = Field(default=4000, ge=10, le=20000)


class Session:
    """One active hot-seat game plus a history of manual and agent runs."""

    def __init__(self):
        self.lock = threading.RLock()
        self.runs = RunStore()
        self.game = rules.Game()
        self.run = None
        self._record_manual(self.game.public_state())

    def _record_manual(self, state, seed=None, n_players=None):
        if self.run is not None:
            self.run.finish("stopped")
            self.runs.unprotect(self.run.id)
        self.run = self.runs.create(
            "manual", state, seed=seed, n_players=n_players,
            label="Manual game", protected=True)

    def state(self):
        with self.lock:
            data = self.game.public_state()
            data["run_id"] = self.run.id
            return data

    def new_game(self, n_players=4, seed=None):
        with self.lock:
            rules.validate_player_count(n_players)
            if seed is None:
                self.game.n_players = n_players
                self.game._reset()
            else:
                self.game = rules.Game(seed=seed, n_players=n_players)
            self._record_manual(self.game.public_state(), seed=seed,
                                n_players=n_players)
            return self.state()

    def act(self, action_type, payload=None):
        payload = payload or {}
        with self.lock:
            before = self.game.public_state()
            actor = self.game.decision_actor()
            result = self.game.act(action_type, payload)
            if result["ok"]:
                if action_type == "new_game":
                    self._record_manual(
                        result["state"], n_players=self.game.n_players)
                else:
                    self.run.add_step(action_type, payload, actor, before,
                                      result)
                result["run_id"] = self.run.id
            else:
                result["run_id"] = self.run.id
            return result

    def start_agent(self, req):
        run = simulate(req.seed, req.n_players, req.policy, req.max_steps)
        self.runs.add(run)
        return run


def create_app(session=None):
    session = session or Session()
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
            return session.new_game(body.n_players, body.seed)
        except rules.RuleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
