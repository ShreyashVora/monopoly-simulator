"""Pytest bootstrap: make `src/` importable for all tests."""

import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import rules  # noqa: E402


@pytest.fixture()
def game():
    """A fresh seeded game for rule tests."""
    return rules.Game(seed=1)
