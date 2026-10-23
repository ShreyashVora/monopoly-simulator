"""API smoke tests — server runs in-process on an ephemeral port."""

import json
import threading
import urllib.request

import pytest

import server


@pytest.fixture()
def api():
    srv = server.make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def _state(base):
    status, body = _get(base + "/api/state")
    assert status == 200
    return json.loads(body)


def _post(base, action, payload=None):
    req = urllib.request.Request(
        base + "/api/action",
        data=json.dumps({"type": action, "payload": payload or {}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def test_board_page_is_served(api):
    status, body = _get(api + "/")
    assert status == 200
    assert b"MONOPOLY" in body


def test_initial_state_has_full_board(api):
    s = _state(api)
    assert len(s["squares"]) == 40
    assert len(s["players"]) == 4
    assert s["phase"] == "await_roll"
    assert s["turn"] == 1


def test_unknown_action_is_rejected(api):
    res = _post(api, "not_an_action")
    assert not res["ok"]
    assert "Unknown action" in res["error"]


def test_scripted_play_through_api(api):
    s = _state(api)
    phases = set()
    for _ in range(60):
        phase = s["phase"]
        phases.add(phase)
        if phase == "await_roll":
            res = _post(api, "roll")
        elif phase == "await_buy":
            pend = s["pending"]
            affordable = s["players"][pend["player"]]["cash"] >= pend["price"]
            res = _post(api, "buy" if affordable else "skip")
        elif phase == "await_jail":
            p = s["players"][s["current"]]
            action = ("jail_pay" if p["cash"] >= 50
                      else "jail_card" if p["goojf"] else "jail_roll")
            res = _post(api, action)
        elif phase == "await_manage":
            owned = [i for i, o in enumerate(s["owner"]) if o == s["current"]]
            res = None
            for idx in owned:
                attempt = _post(api, "build", {"idx": idx})
                if attempt["ok"]:
                    res = attempt
                    break
            if res is None:
                res = _post(api, "end_turn")
        elif phase == "game_over":
            break
        else:
            pytest.fail(f"unexpected phase {phase}")
        assert res["ok"], res.get("error")
        s = res["state"]
        for p in s["players"]:
            assert p["cash"] >= 0

    assert "await_roll" in phases
    assert s["turn"] > 5
    assert sum(1 for o in s["owner"] if o is not None) >= 1
