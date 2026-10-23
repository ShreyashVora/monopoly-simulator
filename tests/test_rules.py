"""Rule-level tests for the Monopoly engine."""

import pytest

import rules
from board import SQUARES
from helpers import act_ok
from state import MAX_PLAYERS, MIN_PLAYERS, PLAYER_COLORS, TOKENS


# ------------------------------------------------------------------- players
def test_default_game_has_four_players():
    game = rules.Game(seed=1)
    assert len(game.s.players) == 4
    assert [p.name for p in game.s.players] == [
        "Player 1", "Player 2", "Player 3", "Player 4"]


@pytest.mark.parametrize("n_players", [MIN_PLAYERS, 3, 4, 5, MAX_PLAYERS])
def test_supported_player_counts(n_players):
    game = rules.Game(seed=1, n_players=n_players)
    assert len(game.s.players) == n_players
    assert len(game.s.owner) == 40
    assert [p.glyph for p in game.s.players] == [
        TOKENS[i][1] for i in range(n_players)]
    assert [p.color for p in game.s.players] == PLAYER_COLORS[:n_players]
    assert len(set(p.glyph for p in game.s.players)) == n_players
    assert len(set(p.color for p in game.s.players)) == n_players


@pytest.mark.parametrize("n_players", [0, 1, MAX_PLAYERS + 1, True, 2.5, "4"])
def test_invalid_player_counts_are_rejected(n_players):
    with pytest.raises(rules.RuleError):
        rules.Game(seed=1, n_players=n_players)


def test_new_game_action_changes_player_count():
    game = rules.Game(seed=1)
    act_ok(game, "new_game", {"n_players": MAX_PLAYERS})
    assert len(game.s.players) == MAX_PLAYERS
    assert game.s.turn == 1
    assert game.s.phase == "await_roll"
    res = game.act("new_game", {"n_players": 1})
    assert not res["ok"]
    assert "between" in res["error"]


def test_turn_order_wraps_across_all_players():
    game = rules.Game(seed=1, n_players=MAX_PLAYERS)
    seen = [game.s.current]
    for _ in range(MAX_PLAYERS - 1):
        game._advance_turn()
        seen.append(game.s.current)
    assert seen == list(range(MAX_PLAYERS))
    game._advance_turn()
    assert game.s.current == 0


# --------------------------------------------------------------------- buying
def test_roll_lands_on_unowned_property_and_prompts_buy(game):
    game.forced_dice = (1, 2)  # GO -> Baltic Avenue (idx 3)
    act_ok(game, "roll")
    assert game.s.phase == "await_buy"
    assert game.s.pending["type"] == "buy"
    assert game.s.pending["idx"] == 3
    assert game.s.pending["price"] == 60


def test_buy_transfers_ownership_and_cash(game):
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    act_ok(game, "buy")
    assert game.s.owner[3] == 0
    assert game.s.players[0].cash == 1440
    assert game.s.phase == "await_manage"
    assert game.s.pending is None


def test_skip_leaves_property_with_bank(game):
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    act_ok(game, "skip")
    assert game.s.owner[3] is None
    assert game.s.phase == "await_manage"


def test_buy_without_pending_is_rejected(game):
    res = game.act("buy")
    assert not res["ok"]
    assert "Nothing to buy" in res["error"]


def test_roll_twice_without_manage_is_rejected(game):
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    res = game.act("roll")  # still await_buy
    assert not res["ok"]


# ----------------------------------------------------------------------- rent
def test_monopoly_doubles_undeveloped_base_rent(game):
    game.s.owner[1] = 1
    game.s.owner[3] = 1  # full brown group
    game.forced_dice = (1, 2)  # lands Baltic, base rent 4 -> 8
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1492
    assert game.s.players[1].cash == 1508


def test_hotel_rent_can_force_bankruptcy(game):
    game.s.owner[39] = 1
    game.s.houses[39] = 5  # hotel on Boardwalk, rent $2000
    game.s.players[0].pos = 36
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    assert game.s.phase == "await_debt"
    assert game.s.pending["amount"] == 2000
    assert not game.s.players[0].bankrupt
    act_ok(game, "declare_bankruptcy")
    assert game.s.players[0].bankrupt


def test_utility_rent_10x_when_both_owned(game):
    game.s.players[0].pos = 10
    game.s.owner[12] = 1
    game.s.owner[28] = 1
    game.forced_dice = (1, 1)  # lands Electric, dice sum 2 -> $20
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1480


def test_mortgaged_utility_still_counts_for_multiplier(game):
    game.s.players[0].pos = 10
    game.s.owner[12] = 1
    game.s.owner[28] = 1
    game.s.mortgaged[28] = True
    game.forced_dice = (1, 1)  # lands Electric, still both utilities -> $20
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1480


def test_railroad_rent_scales_with_count(game):
    for idx in (5, 15, 25, 35):
        game.s.owner[idx] = 1
    game.s.players[0].pos = 1
    game.forced_dice = (2, 2)  # lands Reading with all 4 -> $200
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1300


def test_mortgaged_railroads_still_count_for_multiplier(game):
    for idx in (5, 15, 25, 35):
        game.s.owner[idx] = 1
    game.s.mortgaged[15] = True
    game.s.players[0].pos = 2
    game.forced_dice = (1, 2)  # lands Reading, still four owned railroads
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1300


def test_mortgaged_property_pays_no_rent(game):
    game.s.owner[3] = 1
    game.s.mortgaged[3] = True
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    assert game.s.players[0].cash == 1500
    assert game.s.players[1].cash == 1500


# -------------------------------------------------------------------- housing
def test_build_requires_even_development(game):
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    act_ok(game, "build", {"idx": 1})
    assert game.s.houses[1] == 1
    res = game.act("build", {"idx": 1})
    assert not res["ok"]
    assert "evenly" in res["error"]
    act_ok(game, "build", {"idx": 3})


def test_build_requires_full_group(game):
    game.s.owner[1] = 0  # Mediterranean only, Baltic owned by nobody
    res = game.act("build", {"idx": 1})
    assert not res["ok"]


def test_hotel_sale_requires_four_bank_houses(game):
    game.s.owner[1] = 0
    game.s.houses[1] = 5
    for idx in (6, 8, 9, 11, 13, 14):
        game.s.houses[idx] = 4
    game.s.houses[16] = 4  # bank now has zero houses
    res = game.act("sell_house", {"idx": 1})
    assert not res["ok"]
    assert "houses in the bank" in res["error"]


def test_sell_house_is_even_and_pays_half(game):
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    for _ in range(2):
        for idx in (1, 3):
            act_ok(game, "build", {"idx": idx})
    cash = game.s.players[0].cash
    act_ok(game, "sell_house", {"idx": 3})
    assert game.s.houses[3] == 1
    assert game.s.players[0].cash == cash + 25
    res = game.act("sell_house", {"idx": 3})
    assert not res["ok"]  # would be 0 vs 2 in the group


def test_mortgage_blocked_while_group_has_buildings(game):
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    act_ok(game, "build", {"idx": 1})
    res = game.act("mortgage", {"idx": 3})
    assert not res["ok"]


def test_mortgage_and_unmortgage_cash_flow(game):
    game.s.owner[1] = 0
    cash = game.s.players[0].cash
    act_ok(game, "mortgage", {"idx": 1})
    assert game.s.players[0].cash == cash + 30
    assert game.s.mortgaged[1]
    cost = 33  # ceil(30 * 1.1)
    act_ok(game, "unmortgage", {"idx": 1})
    assert game.s.players[0].cash == cash + 30 - cost
    assert not game.s.mortgaged[1]


# ----------------------------------------------------------------------- jail
def test_third_double_sends_to_jail_and_ends_turn(game):
    for _ in range(2):
        game.forced_dice = (2, 2)
        act_ok(game, "roll")
        if game.s.pending:
            act_ok(game, "skip")
    game.forced_dice = (2, 2)
    act_ok(game, "roll")
    assert game.s.players[0].in_jail
    assert game.s.current == 1


def test_jail_pay_releases_and_charges_50(game):
    game.s.current = 0
    game.s.players[0].in_jail = True
    game.s.players[0].pos = 10
    game._start_turn()
    assert game.s.phase == "await_jail"
    cash = game.s.players[0].cash
    act_ok(game, "jail_pay")
    assert game.s.players[0].cash == cash - 50
    assert not game.s.players[0].in_jail
    assert game.s.phase == "await_roll"


def test_goojf_use_returns_card_to_deck(game):
    p = game.s.players[0]
    p.in_jail = True
    p.pos = 10
    p.goojf = ["chance"]
    game.s.current = 0
    game._start_turn()
    act_ok(game, "jail_card")
    assert not p.goojf and not p.in_jail
    assert game.s.chance_deck[-1] == "ch_goojf"


def test_jail_roll_failure_stays_in_jail(game):
    p = game.s.players[0]
    p.in_jail = True
    p.pos = 10
    game.s.current = 0
    game._start_turn()
    game.forced_dice = (1, 2)
    act_ok(game, "jail_roll")
    assert p.in_jail
    assert p.jail_rolls == 1
    assert game.s.current == 1


def test_property_management_is_allowed_in_jail(game):
    p = game.s.players[0]
    p.in_jail = True
    p.pos = 10
    game.s.current = 0
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    game.s.owner[5] = 0
    game._start_turn()
    assert game.s.phase == "await_jail"
    act_ok(game, "build", {"idx": 1})
    act_ok(game, "mortgage", {"idx": 5})
    assert game.s.houses[1] == 1
    assert game.s.mortgaged[5]


def test_jail_roll_doubles_releases_without_extra_roll(game):
    p = game.s.players[0]
    p.in_jail = True
    p.pos = 10
    game.s.current = 0
    game._start_turn()
    game.forced_dice = (2, 2)  # out of jail, moves 4 -> 14 (Virginia)
    act_ok(game, "jail_roll")
    if game.s.pending:
        act_ok(game, "skip")
    assert not p.in_jail
    assert p.pos == 14
    assert game.s.phase == "await_manage"


# ---------------------------------------------------------------------- cards
def test_advance_to_reading_moves_and_returns_card_to_bottom(game):
    p = game.s.players[0]
    p.pos = 7
    game.s.chance_deck = ["ch_reading"] + [
        c for c in game.s.chance_deck if c != "ch_reading"]
    game._draw_card(0, "chance")
    assert p.pos == 5
    assert game.s.chance_deck[-1] == "ch_reading"


def test_advance_to_go_collects_bonus(game):
    p = game.s.players[0]
    p.pos = 7
    game.s.chance_deck = ["ch_go"] + [
        c for c in game.s.chance_deck if c != "ch_go"]
    game._draw_card(0, "chance")
    assert p.pos == 0
    assert p.cash == 1700


def test_goojf_card_is_kept_not_returned(game):
    p = game.s.players[0]
    p.pos = 7
    game.s.chance_deck = ["ch_goojf"] + [
        c for c in game.s.chance_deck if c != "ch_goojf"]
    game._draw_card(0, "chance")
    assert p.goojf == ["chance"]


def test_pay_each_creates_one_debt_with_all_creditors(game):
    game.s.players[0].cash = 30
    game.s.chance_deck = ["ch_chairman"] + [
        c for c in game.s.chance_deck if c != "ch_chairman"]
    game._then = "await_manage"
    game._draw_card(0, "chance")
    assert game.s.phase == "await_debt"
    assert game.s.pending["amount"] == 150
    assert game.s.pending["creditors"] == [
        {"player": 1, "amount": 50},
        {"player": 2, "amount": 50},
        {"player": 3, "amount": 50},
    ]
    act_ok(game, "declare_bankruptcy")
    assert game.s.players[0].bankrupt
    assert [p.cash for p in game.s.players[1:]] == [1510, 1510, 1510]


def test_collect_each_queues_bankrupt_debtors(game):
    game.s.players[0].pos = 2
    game.s.players[1].cash = 0
    game.s.players[2].cash = 0
    game.s.chest_deck = ["cc_birthday"] + [
        c for c in game.s.chest_deck if c != "cc_birthday"]
    game._then = "await_manage"
    game._draw_card(0, "chest")
    assert game.s.phase == "await_debt"
    assert game.s.pending["player"] == 1
    assert game.s.pending["amount"] == 10
    act_ok(game, "declare_bankruptcy")
    assert game.s.phase == "await_debt"
    assert game.s.pending["player"] == 2
    assert game.s.pending["amount"] == 10
    act_ok(game, "declare_bankruptcy")
    assert game.s.phase == "await_manage"
    assert game.s.players[0].cash == 1510
    assert game.s.players[1].bankrupt
    assert game.s.players[2].bankrupt
    assert game._payments == []


# --------------------------------------------------------------- bankruptcy
def test_bankruptcy_transfers_cash_and_advances_turn(game):
    game.s.players[0].pos = 36
    game.s.owner[39] = 1
    game.s.houses[39] = 5
    game.s.players[0].cash = 10
    game.forced_dice = (1, 2)
    act_ok(game, "roll")
    assert game.s.phase == "await_debt"
    act_ok(game, "declare_bankruptcy")
    assert game.s.players[0].bankrupt
    assert game.s.players[1].cash == 1510
    assert game.s.current == 1


def test_debt_does_not_auto_sell_assets(game):
    game.s.owner[1] = 0     # payer owns Mediterranean with one house
    game.s.owner[39] = 1    # creditor owns Boardwalk
    game.s.houses[1] = 1
    game.s.players[0].cash = 0
    game._pay(0, 60, 1)
    assert game.s.phase == "await_debt"
    assert game.s.houses[1] == 1
    assert not game.s.mortgaged[1]
    assert not game.s.players[0].bankrupt


def test_debt_can_be_paid_after_selling_and_mortgaging(game):
    game.s.owner[1] = 0
    game.s.owner[39] = 1
    game.s.houses[1] = 1
    game.s.players[0].cash = 10
    game._pay(0, 60, 1)
    assert game.s.phase == "await_debt"
    res = game.act("pay_debt")
    assert not res["ok"]
    act_ok(game, "sell_house", {"idx": 1})
    act_ok(game, "mortgage", {"idx": 1})
    assert game.s.players[0].cash == 65
    act_ok(game, "pay_debt")
    assert game.s.players[0].cash == 5
    assert game.s.players[1].cash == 1560
    assert game.s.phase == "await_manage"
    assert game.s.pending is None


def test_decision_actor_tracks_non_current_debtor(game):
    game.s.current = 0
    game.s.players[1].cash = 0
    game._pay(1, 60, 0)
    assert game.decision_actor() == 1
    game.act("declare_bankruptcy")
    assert game.decision_actor() == 0


def test_non_current_debtor_can_sell_and_mortgage_own_assets(game):
    game.s.current = 0
    game.s.owner[1] = 1
    game.s.houses[1] = 1
    game.s.players[1].cash = 10
    game._pay(1, 60, 0)
    assert game.s.pending["player"] == 1
    res = game.act("unmortgage", {"idx": 1})
    assert not res["ok"]
    assert "debt" in res["error"]
    act_ok(game, "sell_house", {"idx": 1})
    act_ok(game, "mortgage", {"idx": 1})
    act_ok(game, "pay_debt")
    assert game.s.players[1].cash == 5
    assert game.s.players[0].cash == 1560
    assert game.s.current == 0
    assert game.s.phase == "await_manage"


def test_spending_is_blocked_while_settling_debt(game):
    game.s.owner[1] = 0
    game.s.owner[3] = 0
    game.s.mortgaged[3] = True
    game.s.players[0].cash = 10
    game._pay(0, 60, 1)
    res = game.act("build", {"idx": 1})
    assert not res["ok"]
    assert "debt" in res["error"]
    res = game.act("unmortgage", {"idx": 3})
    assert not res["ok"]
    assert "debt" in res["error"]


def test_insolvent_manual_debt_can_be_settled_by_bankruptcy(game):
    game.s.owner[1] = 0
    game.s.owner[39] = 1
    game.s.houses[1] = 1
    game.s.players[0].cash = 0
    game._pay(0, 60, 1)
    act_ok(game, "sell_house", {"idx": 1})
    act_ok(game, "mortgage", {"idx": 1})
    assert game.s.players[0].cash == 55
    act_ok(game, "declare_bankruptcy")
    assert game.s.players[0].bankrupt
    assert game.s.players[1].cash == 1555
    assert game.s.owner[1] == 1


def test_last_standing_player_wins(game):
    for i in (1, 2, 3):
        game.s.players[i].bankrupt = True
    game._check_winner()
    assert game.s.winner == 0
    assert game.s.phase == "game_over"


# ------------------------------------------------------------------- squares
def test_board_has_40_squares_with_valid_metadata():
    assert len(SQUARES) == 40
    assert SQUARES[0]["type"] == "go"
    assert SQUARES[39]["name"] == "Boardwalk"
    for idx, sq in enumerate(SQUARES):
        assert sq["idx"] == idx
        if sq["type"] == "street":
            assert len(sq["rents"]) == 6
            assert sq["mortgage"] == sq["price"] // 2
        if sq["type"] == "tax":
            assert sq["amount"] in (75, 200)


def test_group_membership_is_complete():
    members = {c for sq in SQUARES if sq["type"] == "street"
               for c in [sq["group"]]}
    assert len(members) == 8
    counts = {}
    for sq in SQUARES:
        if sq["type"] == "street":
            counts[sq["group"]] = counts.get(sq["group"], 0) + 1
    assert sum(counts.values()) == 22
