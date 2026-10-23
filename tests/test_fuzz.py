"""Headless fuzz games: random policy, thousands of steps, invariant checks."""

import pytest

import rules
from board import SQUARES
from helpers import random_policy_step

PHASES = {"await_roll", "await_buy", "await_jail", "await_manage", "game_over"}


def assert_invariants(game):
    for idx in range(40):
        assert game.s.owner[idx] in (None, 0, 1, 2, 3)
        assert 0 <= game.s.houses[idx] <= 5
        if game.s.houses[idx]:
            assert SQUARES[idx]["type"] == "street"
            assert not game.s.mortgaged[idx]
    for p in game.s.players:
        assert p.cash >= 0
        assert p.pos in range(40)


@pytest.mark.parametrize("seed", [2, 3, 4])
def test_random_game_runs_without_rule_crashes(seed):
    game = rules.Game(seed=seed)
    steps = 0
    while game.s.winner is None and steps < 6000:
        phase = random_policy_step(game)
        steps += 1
        assert phase in PHASES
        if phase != "game_over":
            assert game.s.phase in PHASES
        assert_invariants(game)
    assert steps > 10, "game did not progress"


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_seeded_games_are_reproducible(seed):
    def play():
        game = rules.Game(seed=seed)
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
