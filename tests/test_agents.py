"""Tests for mixed human/agent play and random legal action selection."""

import random

import api
import rules
from agents import random_agent_action


def test_random_agent_uses_pending_purchase_options(game):
    rng = random.Random(1)
    game.forced_dice = (1, 2)
    result = random_agent_action(game, rng)
    assert result is not None
    action, _, response = result
    assert action == "roll"
    assert response["ok"]

    action, _, response = random_agent_action(game, rng)
    assert action in ("buy", "skip")
    assert response["ok"]
    assert game.s.phase == "await_manage"


def test_random_agent_sells_or_mortgages_for_non_current_debt(game):
    game.s.current = 0
    game.s.players[1].cash = 0
    game.s.owner[39] = 1
    game._pay(1, 60, 0)

    action, _, response = random_agent_action(game, random.Random(2))
    assert action == "mortgage"
    assert response["ok"]
    assert game.s.players[1].cash == 200
    assert game.s.phase == "await_debt"

    action, _, response = random_agent_action(game, random.Random(3))
    assert action == "pay_debt"
    assert response["ok"]
    assert game.s.phase == "await_manage"
    assert game.s.current == 0


def test_random_agent_declares_when_it_cannot_raise_cash(game):
    game.s.players[0].cash = 0
    game._pay(0, 60, 1)
    action, _, response = random_agent_action(game, random.Random(4))
    assert action == "declare_bankruptcy"
    assert response["ok"]
    assert game.s.players[0].bankrupt


def test_mixed_new_game_exposes_agents_and_run_metadata():
    session = api.Session()
    state = session.new_game(3, seed=9, agent_seats=[2])
    assert state["mode"] == "mixed"
    assert state["policy"] == "random"
    assert state["agent_seats"] == [2]
    assert session.run.kind == "mixed"
    assert session.run.policy == "random"
    assert session.run.agent_seats == [2]
    assert session.run.label == "Human + 1 random agent"


def test_agent_step_advances_agent_turn_and_records_source():
    session = api.Session()
    session.new_game(2, seed=5, agent_seats=[0])
    result = session.agent_step()
    assert result["ok"]
    assert result["action"] == "roll"
    step = session.run.steps[-1]
    assert step["actor"] == 0
    assert step["meta"] == {"source": "agent", "policy": "random"}
    assert result["state"]["run_id"] == session.run.id


def test_human_action_is_blocked_during_agent_decision():
    session = api.Session()
    session.new_game(2, seed=5, agent_seats=[0])
    result = session.act("roll")
    assert not result["ok"]
    assert "Waiting for the random agent" in result["error"]


def test_agent_step_rejects_human_decision():
    session = api.Session()
    session.new_game(2, seed=5, agent_seats=[1])
    result = session.agent_step()
    assert not result["ok"]
    assert "human player's decision" in result["error"]


def test_agent_step_handles_non_current_debt():
    session = api.Session()
    session.new_game(2, seed=5, agent_seats=[1])
    session.game.s.players[1].cash = 0
    session.game.s.owner[39] = 1
    session.game._pay(1, 60, 0)
    assert session.game.decision_actor() == 1
    result = session.agent_step()
    assert result["ok"]
    assert result["action"] in ("mortgage", "sell_house", "declare_bankruptcy")
    assert session.run.steps[-1]["actor"] == 1


def test_mixed_game_requires_a_human_seat():
    session = api.Session()
    try:
        session.new_game(2, agent_seats=[0, 1])
    except rules.RuleError as exc:
        assert "at least one human" in str(exc)
    else:
        raise AssertionError("all-agent game should be rejected")
