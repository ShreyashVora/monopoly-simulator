"""Headless fuzz games: random policy, thousands of steps, invariant checks."""

import pytest

import rules
from board import SQUARES
from helpers import random_policy_step

PHASES = {
    "await_roll", "await_buy", "await_jail", "await_debt",
    "await_manage", "game_over",
}


def assert_invariants(game):
    n_players = len(game.s.players)
    for idx in range(40):
        owner = game.s.owner[idx]
        assert owner is None or 0 <= owner < n_players
        assert 0 <= game.s.houses[idx] <= 5
        if game.s.houses[idx]:
            assert SQUARES[idx]["type"] == "street"
            assert not game.s.mortgaged[idx]
    assert 0 <= game._bank_count("house") <= 32
    assert 0 <= game._bank_count("hotel") <= 12
    for p in game.s.players:
        assert p.cash >= 0
        assert p.pos in range(40)


@pytest.mark.parametrize(
    "seed,n_players", [(2, 2), (3, 3), (4, 4), (5, 5), (6, 6)])
def test_random_game_runs_without_rule_crashes(seed, n_players):
    game = rules.Game(seed=seed, n_players=n_players)
    steps = 0
    while game.s.winner is None and steps < 6000:
        phase = random_policy_step(game)
        steps += 1
        assert phase in PHASES
        if phase != "game_over":
            assert game.s.phase in PHASES
        assert_invariants(game)
    assert steps > 10, "game did not progress"


@pytest.mark.parametrize("seed,n_players", [(11, 2), (12, 4), (13, 6)])
def test_seeded_games_are_reproducible(seed, n_players):
    def play():
        game = rules.Game(seed=seed, n_players=n_players)
        for _ in range(80):
            if game.s.winner is not None:
                break
            random_policy_step(game)
        return (
            [p.cash for p in game.s.players],
            [p.pos for p in game.s.players],
            list(game.s.owner),
            list(game.s.houses),
        )

    assert play() == play()
