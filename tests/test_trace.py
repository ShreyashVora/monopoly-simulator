"""Tests for persistent promoted-game storage."""

import pytest

from agents import simulate
from trace import Run, RunStore


def test_promoted_run_persists_all_steps(tmp_path):
    directory = tmp_path / "promoted"
    store = RunStore(promoted_dir=directory)
    run = simulate(5, 2, max_steps=4000)
    assert run.winner is not None
    store.add(run)

    summary = store.promote(run.id)
    assert summary["promoted"] is True
    assert store.promoted()[0]["id"] == run.id
    assert (directory / f"{run.id}.json").exists()

    reloaded = RunStore(promoted_dir=directory)
    saved = reloaded.get(run.id)
    assert saved is not None
    assert saved.promoted is True
    assert saved.winner == run.winner
    assert len(saved.steps) == len(run.steps)
    assert saved.summary() == run.summary()


def test_promoted_run_survives_eviction(tmp_path):
    store = RunStore(limit=1, promoted_dir=tmp_path / "promoted")
    run = simulate(5, 2, max_steps=4000)
    store.add(run)
    store.promote(run.id)

    for _ in range(3):
        store.add(Run("agent", run.initial))

    assert store.get(run.id) is not None
    assert [item["id"] for item in store.list()] == [run.id]


def test_active_game_cannot_be_promoted(tmp_path):
    run = simulate(5, 2, max_steps=4000)
    active = Run("manual", run.initial)
    store = RunStore(promoted_dir=tmp_path / "promoted")
    store.add(active)

    with pytest.raises(ValueError, match="completed"):
        store.promote(active.id)
    assert not active.promoted
    assert active.id not in store._protected
