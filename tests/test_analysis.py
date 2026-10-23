"""Tests for per-game analysis metrics."""

from copy import deepcopy

from agents import simulate
from analysis import _property_stats, game_report, observed_transitions


def base_state():
    return deepcopy(simulate(5, 2, max_steps=4000).initial)


def test_property_stats_counts_monopolies_houses_and_mortgages():
    state = base_state()
    state["owner"] = [None] * 40
    state["houses"] = [0] * 40
    state["mortgaged"] = [False] * 40
    state["players"][0]["cash"] = 100

    state["owner"][1] = 0
    assert _property_stats(state, 0)["monopolies"] == 0

    state["owner"][3] = 0
    state["houses"][3] = 2
    state["mortgaged"][1] = True

    stats = _property_stats(state, 0)
    assert stats["properties"] == 2
    assert stats["monopolies"] == 1
    assert stats["houses"] == 1
    assert stats["hotels"] == 0
    assert stats["mortgaged"] == 1
    assert stats["net_worth"] == 290


def test_observed_transitions_counts_actual_actor_moves():
    initial = base_state()
    moved = deepcopy(initial)
    moved["players"][0]["pos"] = 5
    unchanged = deepcopy(moved)
    other_actor = deepcopy(unchanged)
    other_actor["players"][1]["pos"] = 10
    run = {
        "initial": initial,
        "steps": [
            {"actor": 0, "action": "roll", "state": moved},
            {"actor": 0, "action": "buy", "state": unchanged},
            {"actor": 1, "action": "roll", "state": other_actor},
        ],
    }

    result = observed_transitions(run)

    assert result["labels"][0] == "GO"
    assert result["counts"][0][5] == 1
    assert result["counts"][0][10] == 1
    assert result["total"] == 2


def test_game_report_includes_observed_moves_and_no_action_sources():
    run = simulate(5, 2, max_steps=4000)
    report = game_report(run.to_dict(include_steps=True))

    observed = report["observed_transitions"]
    assert "sources" not in report
    assert observed["total"] > 0
    assert sum(sum(row) for row in observed["counts"]) == observed["total"]
