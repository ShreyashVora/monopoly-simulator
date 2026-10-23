"""Auctions, including bankruptcy-to-bank property queues."""

from helpers import act_ok, pass_auction


def start_baltic_auction(game):
    game.forced_dice = (1, 2)  # GO -> Baltic Avenue (idx 3)
    act_ok(game, "roll")
    act_ok(game, "skip")
    assert game.s.phase == "await_auction"
    assert game.s.pending["idx"] == 3


def test_declining_purchase_starts_auction_at_ten_percent(game):
    start_baltic_auction(game)
    pend = game.s.pending
    assert pend["type"] == "auction"
    assert pend["price"] == 60
    assert pend["unit"] == 6
    assert pend["min_bid"] == 6
    assert pend["player"] == 0
    assert pend["high_bid"] is None


def test_unaffordable_purchase_starts_auction_and_auto_passes(game):
    game.s.players[0].cash = 5
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    assert game.s.phase == "await_auction"
    assert game.s.pending["player"] == 1
    assert 0 in game.s.pending["passed"]
    assert game.s.owner[3] is None


def test_bid_must_be_unit_multiple_and_cash_capped(game):
    start_baltic_auction(game)
    game.s.players[0].cash = 10

    res = game.act("auction_bid", {"amount": 7})
    assert not res["ok"]
    assert "multiples of $6" in res["error"]

    res = game.act("auction_bid", {"amount": 5})
    assert not res["ok"]
    assert "minimum bid is $6" in res["error"]

    res = game.act("auction_bid", {"amount": 12})
    assert not res["ok"]
    assert "only has $10" in res["error"]

    act_ok(game, "auction_bid", {"amount": 6})
    assert game.s.pending["high_bid"] == 6
    assert game.s.pending["high_bidder"] == 0


def test_bid_can_exceed_list_price_and_winner_pays(game):
    start_baltic_auction(game)
    act_ok(game, "auction_bid", {"amount": 60})
    for _ in range(3):
        act_ok(game, "auction_pass")
    assert game.s.owner[3] == 0
    assert game.s.players[0].cash == 1440
    assert game.s.phase == "await_manage"
    assert game.s.pending is None


def test_highest_bidder_wins_when_others_pass(game):
    start_baltic_auction(game)
    act_ok(game, "auction_bid", {"amount": 12})
    act_ok(game, "auction_bid", {"amount": 18})
    act_ok(game, "auction_pass")  # player 2
    act_ok(game, "auction_pass")  # player 3
    act_ok(game, "auction_pass")  # player 0
    assert game.s.owner[3] == 1
    assert game.s.players[1].cash == 1482
    assert game.s.phase == "await_manage"


def test_no_bids_leaves_property_with_bank(game):
    start_baltic_auction(game)
    pass_auction(game)
    assert game.s.owner[3] is None
    assert game.s.phase == "await_manage"
    assert game.s.pending is None


def test_auction_on_doubles_resumes_extra_roll(game):
    game.s.players[0].pos = 1
    game.forced_dice = (1, 1)  # Mediterranean -> Baltic
    act_ok(game, "roll")
    act_ok(game, "skip")
    act_ok(game, "auction_bid", {"amount": 6})
    for _ in range(3):
        act_ok(game, "auction_pass")
    assert game.s.phase == "await_roll"
    assert game.s.doubles == 1


def test_bankruptcy_to_bank_queues_properties_one_at_a_time(game):
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    game.s.players[0].cash = 0
    game._pay(0, 100, None)
    assert game.s.phase == "await_debt"

    act_ok(game, "declare_bankruptcy")
    assert game.s.phase == "await_auction"
    assert game.s.pending["idx"] == 1
    assert game.s.pending["bank"] is True
    assert game.s.current == 1

    act_ok(game, "auction_pass")
    act_ok(game, "auction_pass")
    act_ok(game, "auction_pass")
    assert game.s.phase == "await_auction"
    assert game.s.pending["idx"] == 3

    pass_auction(game)
    assert game.s.phase == "await_roll"
    assert game.s.current == 1
    assert game.s.owner[1] is None
    assert game.s.owner[3] is None


def test_single_creditor_bankruptcy_transfers_without_auction(game):
    game.s.owner[3] = 0
    game.s.players[0].cash = 0
    game._pay(0, 100, 1)
    act_ok(game, "declare_bankruptcy")
    assert game.s.owner[3] == 1
    assert game.s.phase == "await_roll"
    assert game.s.pending is None
    assert game.s.current == 1


def test_bank_auctions_resume_jail_decision(game):
    game.s.owner[3] = 0
    game.s.players[0].cash = 0
    game.s.players[1].in_jail = True
    game.s.players[1].pos = 10
    game._pay(0, 100, None)
    act_ok(game, "declare_bankruptcy")

    assert game.s.phase == "await_auction"
    pass_auction(game)
    assert game.s.phase == "await_jail"
    assert game.s.pending["type"] == "jail"
    assert game.s.current == 1
