# Monopoly Simulator

A 2–6 player hot-seat Monopoly game with a complete rules engine, a React board UI, replayable manual and agent runs, and Markov-chain analysis.

The Python engine is dependency-free apart from numpy in the analysis module. FastAPI exposes the engine, React 19 + TypeScript + Vite provides the UI, ECharts renders the analysis views, and Vitest covers the frontend.

## Quick start

```bash
python -m pip install -r requirements.txt
npm --prefix web install
npm --prefix web run build
python src/server.py
```

Open http://127.0.0.1:8000. Pick 2–6 players, then click **Roll Dice**, resolve the buy popup or the Jail/debt controls in the sidebar, manage properties, and **End Turn**.

### Development

Run the API and the Vite dev server in separate terminals:

```bash
python src/server.py
npm --prefix web run dev
```

Vite runs at http://localhost:5173 and proxies `/api` to `127.0.0.1:8000`. The production build is served by FastAPI from `web/dist`.

## Test

```bash
python -m pytest             # 79 tests: rules, player counts, fuzz, API, runs, analysis
npm --prefix web test        # 18 Vitest tests: board/deeds, management, debt/jail, setup, winner
npm --prefix web run build   # TypeScript project build + production bundle
```

Install dev dependencies first with `python -m pip install -r requirements-dev.txt`; frontend test dependencies come from `npm --prefix web install`.

## Features

- **2–6 players** with a count picker on a fresh game and on every New Game. Each player has a unique token and color.
- **Token ownership**: owned squares show the owner's token badge and an owner-color outline; houses, hotels, and mortgage markers are always visible.
- **Full manual play**: roll, doubles, jail, cards, purchase decisions, even building, mortgage/unmortgage, manual debt settlement, bankruptcy, winner.
- **Title deeds and clear management**: click any property for its rent schedule, see grouped holdings, bank house/hotel stock, and the reason a build, sale, or mortgage is disabled.
- **Dismissible result**: after a win, stay on the board or browse Runs/Analysis without starting a new game.
- **Replayable runs**: manual games are traced automatically; replay any run with a timeline and step-by-step decision/state inspector.
- **Built-in agents**: greedy and random policies play complete seeded games in the background.
- **Analysis**: dice-only 40-state Markov chain, stationary distribution, 40×40 transition heatmap, expected hitting times.

## Architecture

| Path | Role |
|------|------|
| `src/board.py` | 40-square standard US board: names, color groups, prices, rent tables, house costs, mortgages |
| `src/state.py` | `GameState` + `Player`, 6 tokens/colors, `MIN_PLAYERS`/`MAX_PLAYERS` |
| `src/cards.py` | 16 Chance + 16 Community Chest cards as declarative effects |
| `src/rules.py` | `Game` turn state machine, player-count validation, rent, cards, building, mortgage, manual debt, bankruptcy, winner |
| `src/trace.py` | Thread-safe `Run`/`RunStore`: initial state, per-action state snapshots, summaries, 30-run cap |
| `src/agents.py` | Greedy/random policies over the same decision interface; synchronous `simulate()` |
| `src/analysis.py` | Dice transition matrix, stationary distribution, hitting times via numpy linear solves |
| `src/api.py` | FastAPI app: game actions, runs, trace, SSE events, analysis, SPA + `web/dist` serving |
| `src/server.py` | Uvicorn entry point (`api:app`, 127.0.0.1:8000) |
| `web/src` | React 19 SPA: board, setup dialog, play/runs/replay/analysis pages, typed API client |
| `web/src/components/Board.tsx` | 11×11 CSS-grid board, path animations, dice animation, token layer, owner/house/mortgage markers, deed targets |
| `tests/` | `conftest.py`, `test_rules.py`, `test_fuzz.py`, `test_api.py` |
| `notebooks/` | Reserved for marimo deep-dives (install `marimo` separately) |

## Turn state machine

`rules.Game` advances automatically until a human decision is needed, then parks with `phase` + `pending`:

| Phase | Meaning | Exit actions |
|-------|---------|--------------|
| `await_roll` | current player must roll (manage actions also allowed) | `roll` |
| `await_jail` | player in jail must choose (manage actions also allowed) | `jail_pay`, `jail_card`, `jail_roll` |
| `await_buy` | landed on an unowned, affordable property | `buy`, `skip` |
| `await_debt` | player cannot cover a payment | `sell_house`, `mortgage`, `pay_debt`, `declare_bankruptcy` |
| `await_manage` | post-move development window | `build`, `sell_house`, `mortgage`, `unmortgage`, `end_turn` |
| `game_over` | one player left | `new_game` |

Doubles grant another roll; three consecutive doubles send the player to jail. `pending` carries `type`, `player`, `prompt`, and legal `options`, so the UI and agents resolve the same decision points.

## HTTP API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/state` | Current game state plus active `run_id` |
| `POST /api/action` | `{"type": <action>, "payload": {...}}` → `{ok, state, events, anim}` |
| `POST /api/games` | New seeded/unseeded game: `{n_players, seed?}` |
| `GET /api/runs` | Run history summaries, newest first |
| `POST /api/runs` | Run an agent: `{n_players, policy, seed?, max_steps?}` |
| `GET /api/runs/{id}` | Run summary |
| `GET /api/runs/{id}/trace` | Initial state + every recorded step |
| `GET /api/runs/{id}/events` | SSE stream of steps, terminated by `event: done` |
| `GET /api/analysis/overview` | labels, 40×40 matrix, stationary π, hitting times |

Manual actions include `roll`, `buy`/`skip`, `jail_pay`/`jail_card`/`jail_roll`, `build`/`sell_house`, `mortgage`/`unmortgage`, `pay_debt`/`declare_bankruptcy`, `end_turn`, and `new_game` (payload `{"n_players": 2..6}`).

State is a plain dict (`Game.public_state()`), deep-copied under the engine lock. `anim` reports the moving player's path.

## Runs and agents

Every manual action after the active run is created appends a trace step containing the actor, phase before the action, pending decision, resulting state, events, and animation payload. Starting a new game starts a new manual run while keeping the previous one in history.

`POST /api/runs` executes a synchronous policy game and stores it in the same history. The frontend's **Runs** page launches runs and links to a replay view with an action timeline, decision inspector, and compact state inspector. The SSE endpoint is available for live consumers even though agent runs currently finish before the response returns.

## Analysis

`src/analysis.py` builds the dice-only 40×40 transition matrix for two fair dice, redirecting Go To Jail to Jail. It then computes the stationary distribution by power iteration and expected hitting times by solving `(I − Q)h = 1` for each target. Repeated square short names (Chance, Community Chest, taxes) receive an index suffix so API labels remain unique.

The UI exposes the stationary distribution, the transition heatmap, per-origin hitting times for any target, and a table of the most visited squares. This is the first cut of the roadmap's Markov phases; augmented state spaces (doubles count, jail status) can be layered on without changing the endpoint shape.

## Rules coverage

- Dice movement, pass-GO bonus, doubles (extra roll, three-strike jail), Go-To-Jail square
- Jail: pay $50, use a Get Out of Jail Free card, or roll doubles; 3 failed attempts force the fine + move; property management stays available in Jail
- Property purchase (decline leaves it with the bank), full rent tables: streets (base / 4 house levels / hotel), monopoly doubles, railroads 25/50/100/200, utilities 4×/10× of the landing roll; mortgaged railroads/utilities still count toward the multiplier
- Income Tax $200, Luxury Tax $75, Free Parking (no payout)
- All 32 cards: advances, nearest utility/railroad, back-3, money, pay/collect each player, repairs, GOOJF (held, returned to deck on use)
- Even build/sell across color groups, 32-house/12-hotel bank limits and live bank inventory, group full + unmortgaged requirement, four bank houses required to break a hotel
- Mortgage rules (no buildings in group; cost + 10% to lift)
- Manual debt settlement: sell buildings or mortgage assets in any order, then pay the full amount; spending is blocked while in debt; declare bankruptcy if assets cannot cover it; asset transfer to creditor or bank; turn skip; last player standing wins
- Server-side validation of every action; illegal actions leave state untouched

## Deliberate omissions

Auctions, trading, house-shortage auctions, Free Parking pot, Income Tax 10% option, and bank-auction of bankrupt properties are not implemented.

## Use the engine without the UI

```python
import sys
sys.path.insert(0, "src")
from rules import Game

game = Game(seed=42, n_players=6)
state = game.act("roll")["state"]
while game.s.pending:                 # resolve decision points programmatically
    action = game.s.pending["options"][0]["action"]
    state = game.act(action)["state"]
```

`Game.forced_dice = (1, 2)` is a deterministic test hook used by the test suite. `rules.validate_player_count()` enforces 2–6 players.
