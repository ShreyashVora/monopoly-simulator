"""Emit JSON fixtures for the jsdom UI test (tests/ui.test.js)."""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import rules  # noqa: E402

game = rules.Game(seed=1)
initial = game.public_state()
game.forced_dice = (1, 2)  # GO -> Baltic Avenue (idx 3), unowned
roll = game.act("roll")
buy = game.act("buy")
print(json.dumps({"initial": initial, "roll": roll, "buy": buy}))
