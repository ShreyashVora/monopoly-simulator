# Monopoly Simulator

Four-player Monopoly with a full rules engine, a browser board UI, and a decision-point architecture designed to later host automated agents.

## Run

```
python src/server.py
```

Open http://127.0.0.1:8000 and play hot-seat: click **Roll Dice**, resolve the popup decision (buy/jail), manage properties in the sidebar, then **End Turn**.

## Test

```
python -m pytest              # 38 tests: rules, fuzz, API
npm install && npm run test:ui   # optional jsdom UI smoke test (Node required)
```

## Architecture

| Path | Role |
|------|------|
| `src/board.py` | 40-square standard US board: names, color groups, prices, full rent tables (6 levels), house costs, mortgage values |
| `src/state.py` | `GameState` + `Player`: cash, positions, ownership, houses, mortgages, decks, turn marker, phase, pending decision |
| `src/cards.py` | 16 Chance + 16 Community Chest cards as declarative effect records |
| `src/rules.py` | `Game` — turn state machine, validated actions, rent, cards, building, mortgage, liquidation, bankruptcy, winner |
| `src/server.py` | stdlib `ThreadingHTTPServer`: serves `ui/board.html`, JSON API; `make_server(port=0)` used by tests |
| `ui/board.html` | Single-file UI: CSS-grid board, animated tokens, owner/house/mortgage markers, decision modal, manage panel, log |
| `tests/` | `conftest.py` (seed fixture), `test_rules.py`, `test_fuzz.py`, `test_api.py`, `ui.test.js` + fixture |
| `pytest.ini` | `testpaths = tests` |

`src/` has no third-party dependencies; UI test optionally uses jsdom.

## Turn state machine

`rules.Game` advances automatically until a human decision is needed, then parks with `phase` + `pending`:

| Phase | Meaning | Exit actions |
|-------|---------|--------------|
| `await_roll` | current player must roll (manage actions also allowed) | `roll` |
| `await_jail` | player in jail must choose | `jail_pay`, `jail_card`, `jail_roll` |
| `await_buy` | landed on an unowned, affordable property | `buy`, `skip` |
| `await_manage` | post-move development window | `build`, `sell_house`, `mortgage`, `unmortgage`, `end_turn` |
| `game_over` | one player left | `new_game` |

Doubles grant another roll (`phase` returns to `await_roll` after resolution); three consecutive doubles send the player to jail. `pending` carries `type`, `player`, `prompt`, and legal `options`, so a UI or an agent can resolve the same decision points.

## HTTP API

`GET /api/state` → full serialized state (board, players, ownership, buildings, mortages, phase, pending, log).

`POST /api/action` with `{"type": <action>, "payload": {...}}` → `{ok, state, events, anim}` (or `{ok:false, error}`).

| Action | Payload | Effect |
|--------|---------|--------|
| `roll` | — | roll two dice (jail attempts use `jail_roll`) |
| `buy` / `skip` | — | resolve a `buy` decision |
| `jail_pay` / `jail_card` / `jail_roll` | — | resolve a jail decision |
| `build` / `sell_house` | `{idx}` | build/sell one level (even-build enforced) |
| `mortgage` / `unmortgage` | `{idx}` | toggle mortgage (±10% on unmortgage) |
| `end_turn` | — | finish turn (only in `await_manage`) |
| `new_game` | — | reset state |

State is a plain dict (`Game.public_state()`), deep-copied under the engine lock. `anim` reports the moving player's path for token animation.

## Rules coverage

- Dice movement, pass-GO bonus, doubles (extra roll, three-strike jail), Go-To-Jail square
- Jail: pay $50, use a Get Out of Jail Free card, or roll doubles; 3 failed attempts force the fine + move
- Property purchase (decline leaves it with the bank), full rent tables: streets (base / 4 house levels / hotel), monopoly doubles, railroads 25/50/100/200, utilities 4×/10× of the landing roll
- Income Tax $200, Luxury Tax $75, Free Parking (no payout)
- All 32 cards: advances, nearest utility/railroad, back-3, money, pay/collect each player, repairs, GOOJF (held, returned to deck on use)
- Even build/sell across color groups, 32-house/12-hotel bank limits, group full + unmortgaged requirement
- Mortgage rules (no buildings in group; cost + 10% to lift)
- Automatic liquidation (sell buildings at half, then mortgage) before bankruptcy; asset transfer to creditor or bank; turn skip; last player standing wins
- Server-side validation of every action; illegal actions leave state untouched

## Deliberate omissions

Auctions, trading, house-shortage rule, Free Parking pot, Income Tax 10% option, and bank-auction of bankrupt properties are not implemented.

## Use the engine without the UI

```python
import sys
sys.path.insert(0, "src")
from rules import Game

game = Game(seed=42)
state = game.act("roll")["state"]
while game.s.pending:                 # resolve decision points programmatically
    action = game.s.pending["options"][0]["action"]
    state = game.act(action)["state"]
```

`Game.forced_dice = (1, 2)` is a deterministic test hook used by the test suite.
