"""FastAPI layer tests: manual play, player counts, runs, and analysis."""

import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture()
def client():
    with TestClient(api.create_app()) as test_client:
        yield test_client


def _state(client):
    res = client.get("/api/state")
    assert res.status_code == 200
    return res.json()


def _post(client, action, payload=None):
    return client.post(
        "/api/action", json={"type": action, "payload": payload or {}})


def test_root_serves_spa(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "monopoly" in res.text.lower()


def test_initial_state_is_a_four_player_game(client):
    state = _state(client)
    assert len(state["squares"]) == 40
    assert len(state["players"]) == 4
    assert state["phase"] == "await_roll"
    assert state["turn"] == 1
    assert state["bank_houses"] == 32
    assert state["bank_hotels"] == 12
    assert state["run_id"]


def test_unknown_action_is_rejected(client):
    res = _post(client, "not_an_action")
    assert res.status_code == 200
    body = res.json()
    assert not body["ok"]
    assert "Unknown action" in body["error"]


@pytest.mark.parametrize("n_players", [2, 3, 5, 6])
def test_new_game_accepts_supported_player_counts(client, n_players):
    res = _post(client, "new_game", {"n_players": n_players})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"]
    state = body["state"]
    assert len(state["players"]) == n_players
    assert len({p["glyph"] for p in state["players"]}) == n_players
    assert len({p["color"] for p in state["players"]}) == n_players
    assert state["phase"] == "await_roll"


@pytest.mark.parametrize("n_players", [1, 7, True])
def test_new_game_rejects_invalid_player_counts(client, n_players):
    res = _post(client, "new_game", {"n_players": n_players})
    assert res.status_code == 200
    body = res.json()
    assert not body["ok"]
    assert "between" in body["error"]


def test_games_endpoint_starts_seeded_game(client):
    res = client.post("/api/games", json={"n_players": 2, "seed": 7})
    assert res.status_code == 200
    state = res.json()
    assert len(state["players"]) == 2
    assert state["turn"] == 1


def test_games_endpoint_validates_count(client):
    res = client.post("/api/games", json={"n_players": 8})
    assert res.status_code == 400
    assert "between" in res.json()["detail"]


def test_scripted_play_through_api(client):
    state = _state(client)
    phases = set()
    for _ in range(60):
        phase = state["phase"]
        phases.add(phase)
        if phase == "await_roll":
            res = _post(client, "roll")
        elif phase == "await_buy":
            pending = state["pending"]
            affordable = (
                state["players"][pending["player"]]["cash"] >= pending["price"]
            )
            res = _post(client, "buy" if affordable else "skip")
        elif phase == "await_jail":
            player = state["players"][state["current"]]
            action = (
                "jail_pay"
                if player["cash"] >= 50
                else "jail_card"
                if player["goojf"]
                else "jail_roll"
            )
            res = _post(client, action)
        elif phase == "await_debt":
            pend = state["pending"]
            if state["players"][pend["player"]]["cash"] >= pend["amount"]:
                res = _post(client, "pay_debt")
            else:
                res = _post(client, "declare_bankruptcy")
        elif phase == "await_manage":
            owned = [
                i
                for i, owner in enumerate(state["owner"])
                if owner == state["current"]
            ]
            body = None
            for idx in owned:
                attempt = _post(client, "build", {"idx": idx})
                if attempt.json()["ok"]:
                    body = attempt.json()
                    break
            if body is None:
                body = _post(client, "end_turn").json()
            res = None
        elif phase == "game_over":
            break
        else:
            pytest.fail(f"unexpected phase {phase}")

        if res is not None:
            assert res.status_code == 200
            body = res.json()
        assert body["ok"], body.get("error")
        state = body["state"]
        for player in state["players"]:
            assert player["cash"] >= 0

    assert "await_roll" in phases
    assert state["turn"] > 5
    assert sum(owner is not None for owner in state["owner"]) >= 1


def test_manual_run_is_recorded(client):
    state = _state(client)
    run_id = state["run_id"]

    runs = client.get("/api/runs").json()
    manual = next(run for run in runs if run["id"] == run_id)
    assert manual["kind"] == "manual"
    assert manual["steps"] == 0

    _post(client, "roll")
    trace = client.get(f"/api/runs/{run_id}/trace").json()
    assert trace["steps"]
    assert trace["steps"][0]["action"] == "roll"
    assert trace["initial"]["turn"] == 1

    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/api/runs/missing/trace").status_code == 404


def test_active_manual_run_survives_history_cap(client):
    run_id = _state(client)["run_id"]
    for seed in range(35):
        res = client.post(
            "/api/runs",
            json={
                "n_players": 2,
                "seed": seed,
                "policy": "random",
                "max_steps": 20,
            },
        )
        assert res.status_code == 200

    runs = client.get("/api/runs").json()
    assert len(runs) == 30
    assert any(run["id"] == run_id for run in runs)
    assert client.get(f"/api/runs/{run_id}/trace").status_code == 200


def test_agent_run_and_event_stream(client):
    res = client.post(
        "/api/runs",
        json={
            "n_players": 2,
            "seed": 42,
            "policy": "greedy",
            "max_steps": 200,
        },
    )
    assert res.status_code == 200
    run = res.json()
    assert run["kind"] == "agent"
    assert run["n_players"] == 2
    assert run["status"] in {"done", "stopped"}
    assert run["steps"] <= 200

    trace = client.get(f"/api/runs/{run['id']}/trace").json()
    assert len(trace["steps"]) == run["steps"]
    assert trace["steps"][0]["meta"]["policy"] == "greedy"

    events = client.get(f"/api/runs/{run['id']}/events")
    assert events.status_code == 200
    assert "event: done" in events.text


def test_agent_run_rejects_invalid_player_count(client):
    res = client.post(
        "/api/runs",
        json={"n_players": 1, "policy": "random", "max_steps": 20},
    )
    assert res.status_code == 400
    assert "between" in res.json()["detail"]


def test_analysis_overview_is_consistent(client):
    res = client.get("/api/analysis/overview")
    assert res.status_code == 200
    data = res.json()
    assert len(data["labels"]) == 40
    assert len(set(data["labels"])) == 40
    assert len(data["matrix"]) == 40
    assert all(len(row) == 40 for row in data["matrix"])
    assert len(data["stationary"]) == 40
    assert sum(data["stationary"]) == pytest.approx(1.0)
    assert len(data["hittingTimes"]) == 40
    assert all(len(values) == 40 for values in data["hittingTimes"].values())
    assert data["note"]
