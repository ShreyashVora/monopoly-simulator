"""Player-to-player trade proposals, validation, and resolution."""

import rules
from helpers import act_ok


def trade_game():
    game = rules.Game(seed=1)
    game.s.owner[1] = 0
    game.s.owner[3] = 1
    game.s.players[0].cash = 1000
    game.s.players[1].cash = 1200
    return game


def test_proposal_targets_recipient_as_decision_actor():
    game = trade_game()
    act_ok(game, "trade_propose", {
        "recipient": 1,
        "give": {"cash": 100, "properties": [1]},
        "want": {"properties": [3]},
    })
    assert game.s.phase == "await_trade"
    assert game.s.pending["proposer"] == 0
    assert game.s.pending["recipient"] == 1
    assert game.decision_actor() == 1
    assert game.s.pending["resume_phase"] == "await_roll"


def test_accept_swaps_cash_properties_and_goojf():
    game = trade_game()
    game.s.players[0].goojf = ["chance"]
    game.s.players[1].goojf = ["chest"]
    act_ok(game, "trade_propose", {
        "recipient": 1,
        "give": {"cash": 100, "properties": [1], "goojf": 1},
        "want": {"cash": 50, "properties": [3], "goojf": 1},
    })
    act_ok(game, "trade_accept")

    assert game.s.owner[1] == 1
    assert game.s.owner[3] == 0
    assert game.s.players[0].cash == 950
    assert game.s.players[1].cash == 1250
    assert game.s.players[0].goojf == ["chest"]
    assert game.s.players[1].goojf == ["chance"]
    assert game.s.phase == "await_roll"
    assert game.s.pending is None


def test_reject_restores_phase_without_changes():
    game = trade_game()
    act_ok(game, "trade_propose", {
        "recipient": 1,
        "give": {"cash": 100},
        "want": {"properties": [3]},
    })
    act_ok(game, "trade_reject")
    assert game.s.phase == "await_roll"
    assert game.s.pending is None
    assert game.s.owner[1] == 0
    assert game.s.owner[3] == 1
    assert game.s.players[0].cash == 1000
    assert game.s.players[1].cash == 1200


def test_reject_mortgaged_deed():
    game = trade_game()
    game.s.mortgaged[1] = True
    res = game.act("trade_propose", {
        "recipient": 1,
        "give": {"properties": [1]},
        "want": {"cash": 10},
    })
    assert not res["ok"]
    assert "Unmortgage Mediterranean Avenue" in res["error"]
    assert game.s.phase == "await_roll"


def test_reject_property_from_group_with_buildings():
    game = trade_game()
    game.s.owner[3] = 0
    game.s.houses[1] = 1
    res = game.act("trade_propose", {
        "recipient": 1,
        "give": {"properties": [3]},
        "want": {"cash": 10},
    })
    assert not res["ok"]
    assert "Sell all buildings" in res["error"]


def test_reject_empty_self_bankrupt_and_duplicate_trades():
    game = trade_game()

    res = game.act("trade_propose", {"recipient": 1, "give": {}, "want": {}})
    assert not res["ok"]
    assert "at least one item" in res["error"]

    res = game.act("trade_propose", {
        "recipient": 0, "give": {"cash": 1}, "want": {}})
    assert not res["ok"]
    assert "yourself" in res["error"]

    game.s.players[1].bankrupt = True
    res = game.act("trade_propose", {
        "recipient": 1, "give": {"cash": 1}, "want": {}})
    assert not res["ok"]
    assert "bankrupt" in res["error"]

    game.s.players[1].bankrupt = False
    res = game.act("trade_propose", {
        "recipient": 1,
        "give": {"properties": [1, 1]},
        "want": {"cash": 1},
    })
    assert not res["ok"]
    assert "cannot appear twice" in res["error"]


def test_reject_unaffordable_or_unowned_terms():
    game = trade_game()
    game.s.players[0].cash = 50

    res = game.act("trade_propose", {
        "recipient": 1, "give": {"cash": 100}, "want": {}})
    assert not res["ok"]
    assert "only has $50" in res["error"]

    game.s.players[0].cash = 1000
    res = game.act("trade_propose", {
        "recipient": 1,
        "give": {"properties": [3]},
        "want": {"cash": 1},
    })
    assert not res["ok"]
    assert "does not own Baltic Avenue" in res["error"]


def test_trade_is_unavailable_during_buy_or_auction(game):
    game.s.phase = "await_buy"
    res = game.act("trade_propose", {
        "recipient": 1, "give": {"cash": 1}, "want": {}})
    assert not res["ok"]
    assert "not available" in res["error"]

    game.s.phase = "await_auction"
    res = game.act("trade_propose", {
        "recipient": 1, "give": {"cash": 1}, "want": {}})
    assert not res["ok"]
    assert "not available" in res["error"]


def test_accept_revalidates_terms():
    game = trade_game()
    act_ok(game, "trade_propose", {
        "recipient": 1,
        "give": {"properties": [1]},
        "want": {"cash": 10},
    })
    game.s.mortgaged[1] = True
    res = game.act("trade_accept")
    assert not res["ok"]
    assert "Unmortgage Mediterranean Avenue" in res["error"]
    assert game.s.phase == "await_trade"
    assert game.s.pending["type"] == "trade"


def test_trade_during_jail_rebuilds_goojf_options():
    game = trade_game()
    p0 = game.s.players[0]
    p0.in_jail = True
    p0.pos = 10
    game.s.players[1].goojf = ["chance"]
    game._start_turn()
    assert game.s.pending["type"] == "jail"

    act_ok(game, "trade_propose", {
        "recipient": 1,
        "give": {"properties": [1]},
        "want": {"goojf": 1},
    })
    act_ok(game, "trade_accept")

    assert game.s.phase == "await_jail"
    assert game.s.pending["type"] == "jail"
    assert p0.goojf == ["chance"]
    assert any(o["action"] == "jail_card" for o in game.s.pending["options"])


def test_reject_during_jail_keeps_jail_decision():
    game = trade_game()
    game.s.players[0].in_jail = True
    game.s.players[0].pos = 10
    game._start_turn()
    act_ok(game, "trade_propose", {
        "recipient": 1, "give": {"cash": 1}, "want": {}})
    act_ok(game, "trade_reject")
    assert game.s.phase == "await_jail"
    assert game.s.pending["type"] == "jail"
