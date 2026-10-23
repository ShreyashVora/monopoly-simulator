"""Full Monopoly rules engine (auctions and trading intentionally absent).

Turn flow is a small state machine. Actions advance the game until a human
decision is required, then park at `phase == "await_*"` with `pending` set.
The same decision points will later be driven by agent policies instead of
the UI.
"""

import math
import random
import threading
from copy import deepcopy

import cards
from board import GROUP_MEMBERS, HOTEL_LIMIT, HOUSE_LIMIT, SQUARES
from state import (GO_TO_JAIL_POS, JAIL_FINE, JAIL_POS, PASS_GO_BONUS,
                   GameState)


class RuleError(Exception):
    pass


class Game:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self.forced_dice = None
        self._reset()

    # ------------------------------------------------------------------ reset
    def _reset(self):
        self.s = GameState()
        self.s.chance_deck = [c["id"] for c in cards.CHANCE]
        self.s.chest_deck = [c["id"] for c in cards.CHEST]
        self._rng.shuffle(self.s.chance_deck)
        self._rng.shuffle(self.s.chest_deck)
        self._events = []
        self._stop = False
        self._then = "await_manage"
        self._log("New game — 4 players, $1500 each. Player 1 to roll.")

    # -------------------------------------------------------------- utilities
    @property
    def current_player(self):
        return self.s.players[self.s.current]

    def _log(self, msg):
        self._events.append(msg)
        self.s.log.append(msg)
        if len(self.s.log) > 200:
            del self.s.log[:100]

    def _dice(self):
        if self.forced_dice is not None:
            d = self.forced_dice
            self.forced_dice = None
            return d
        return (self._rng.randint(1, 6), self._rng.randint(1, 6))

    def _group_indices(self, idx):
        sq = SQUARES[idx]
        return GROUP_MEMBERS.get(sq["group"], [])

    def _owns_group(self, pid, idx):
        members = self._group_indices(idx)
        return bool(members) and all(self.s.owner[i] == pid for i in members)

    def _group_has_mortgage(self, idx):
        return any(self.s.mortgaged[i] for i in self._group_indices(idx))

    # ------------------------------------------------------------- turn logic
    def _start_turn(self):
        p = self.current_player
        self.s.pending = None
        if p.in_jail:
            self.s.phase = "await_jail"
            opts = []
            opts.append({"action": "jail_pay", "label": f"Pay ${JAIL_FINE}",
                         "payload": {}})
            if p.goojf:
                opts.append({"action": "jail_card",
                             "label": "Use Get Out of Jail Free", "payload": {}})
            opts.append({"action": "jail_roll",
                         "label": "Roll for doubles", "payload": {}})
            self.s.pending = {
                "type": "jail", "player": p.pid,
                "prompt": f"{p.name} is in Jail — leave before rolling.",
                "options": opts,
            }
        else:
            self.s.phase = "await_roll"
            self.s.pending = None

    def _advance_turn(self):
        if self.s.winner is not None:
            return
        n = len(self.s.players)
        for k in range(1, n + 1):
            j = (self.s.current + k) % n
            if not self.s.players[j].bankrupt:
                self.s.current = j
                break
        self.s.doubles = 0
        self.s.turn += 1
        self._start_turn()

    def _check_winner(self):
        alive = [p for p in self.s.players if not p.bankrupt]
        if len(alive) == 1:
            self.s.winner = alive[0].pid
            self.s.phase = "game_over"
            self.s.pending = None
            self._log(f"{alive[0].name} wins the game!")

    # --------------------------------------------------------------- movement
    def _move_by(self, pid, steps):
        p = self.s.players[pid]
        path = [(p.pos + i) % 40 for i in range(1, steps + 1)]
        if 0 in path:
            p.cash += PASS_GO_BONUS
            self._log(f"{p.name} passes GO (+${PASS_GO_BONUS}).")
        p.pos = path[-1]
        self.s.anim = {"mover": pid, "path": path}
        return path

    def _advance_to(self, pid, target):
        p = self.s.players[pid]
        steps = (target - p.pos) % 40
        if steps == 0:
            steps = 40
        return self._move_by(pid, steps)

    def _send_to_jail(self, pid):
        p = self.s.players[pid]
        p.pos = JAIL_POS
        p.in_jail = True
        p.jail_rolls = 0
        self.s.doubles = 0
        self.s.anim = {"mover": pid, "path": [GO_TO_JAIL_POS, JAIL_POS]}
        self._log(f"{p.name} goes to Jail.")

    # ------------------------------------------------------------- resolution
    def _resolve_landing(self, pid, rent_mode=None):
        if self._stop or self.s.phase == "game_over":
            return
        p = self.s.players[pid]
        sq = SQUARES[p.pos]
        self._log(f"{p.name} lands on {sq['name']}.")
        t = sq["type"]

        if t in ("street", "railroad", "utility"):
            owner = self.s.owner[p.pos]
            if self.s.mortgaged[p.pos]:
                if owner is not None:
                    self._log(f"{sq['name']} is mortgaged — no rent.")
                return
            if owner is None:
                price = sq["price"]
                if p.cash >= price:
                    self.s.phase = "await_buy"
                    self.s.pending = {
                        "type": "buy", "player": pid, "idx": p.pos,
                        "price": price, "then": self._then,
                        "prompt": f"{sq['name']} is unowned — buy for ${price}?",
                        "options": [
                            {"action": "buy", "label": f"Buy for ${price}",
                             "payload": {}},
                            {"action": "skip", "label": "Skip (no auction)",
                             "payload": {}},
                        ],
                    }
                else:
                    self._log(f"{p.name} cannot afford {sq['name']} (${price}).")
            elif owner == pid:
                self._log(f"{p.name} owns {sq['name']}.")
            else:
                rent = self._rent(p.pos, rent_mode)
                self._log(f"{p.name} pays ${rent} rent to "
                          f"{self.s.players[owner].name}.")
                self._pay(pid, rent, owner)
                return
        elif t == "tax":
            self._log(f"{p.name} pays ${sq['amount']} {sq['short']}.")
            self._pay(pid, sq["amount"], None)
        elif t == "go_to_jail":
            self._send_to_jail(pid)
        elif t == "chance":
            self._draw_card(pid, "chance")
        elif t == "chest":
            self._draw_card(pid, "chest")

    def _rent(self, idx, rent_mode):
        sq = SQUARES[idx]
        owner = self.s.owner[idx]
        if sq["type"] == "street":
            h = self.s.houses[idx]
            if h > 0:
                return sq["rents"][h]
            base = sq["rents"][0]
            if self._owns_group(owner, idx):
                return base * 2
            return base
        if sq["type"] == "railroad":
            count = sum(1 for i, sq2 in enumerate(SQUARES)
                        if sq2["type"] == "railroad" and self.s.owner[i] == owner
                        and not self.s.mortgaged[i])
            rent = sq["rents"][max(0, count - 1)]
            return rent * 2 if rent_mode == "rr_double" else rent
        if sq["type"] == "utility":
            if rent_mode == "utility_ten":
                return 10 * sum(self.s.last_dice or (7,))
            count = sum(1 for i, sq2 in enumerate(SQUARES)
                        if sq2["type"] == "utility" and self.s.owner[i] == owner
                        and not self.s.mortgaged[i])
            mult = 10 if count >= 2 else 4
            return mult * sum(self.s.last_dice or (7,))
        return 0

    # ------------------------------------------------------------------- cards
    def _draw_card(self, pid, deck_name):
        p = self.s.players[pid]
        deck = self.s.chance_deck if deck_name == "chance" else self.s.chest_deck
        if not deck:  # safety net; should never trigger
            self._log("Deck empty — reshuffling.")
            deck.extend(c["id"] for c in
                        (cards.CHANCE if deck_name == "chance" else cards.CHEST))
            self._rng.shuffle(deck)
        cid = deck.pop(0)
        card = cards.BY_ID[cid]
        self._log(f"{deck_name.title()} card: {card['text']}")
        eff = card["effect"]
        if eff == "goojf":
            p.goojf.append(deck_name)
        else:
            deck.append(cid)  # to bottom
        if eff == "money":
            amt = card["amount"]
            if amt >= 0:
                p.cash += amt
            else:
                self._pay(pid, -amt, None)
        elif eff == "move_to":
            self._advance_to(pid, card["pos"])
            self._resolve_landing(pid)
        elif eff == "nearest":
            target = self._nearest(pid, card["what"])
            self._advance_to(pid, target)
            mode = "utility_ten" if card["what"] == "utility" else "rr_double"
            self._resolve_landing(pid, rent_mode=mode)
        elif eff == "back3":
            p.pos = (p.pos - 3) % 40
            self._log(f"{p.name} moves back 3 to {SQUARES[p.pos]['name']}.")
            self.s.anim = None
            self._resolve_landing(pid)
        elif eff == "jail":
            self._send_to_jail(pid)
        elif eff == "repairs":
            houses = sum(h for h in self.s.houses if h < 5)
            hotels = sum(1 for h in self.s.houses if h == 5)
            owed = houses * card["house"] + hotels * card["hotel"]
            self._log(f"Repairs: {houses} houses, {hotels} hotels — ${owed}.")
            if owed:
                self._pay(pid, owed, None)
        elif eff == "pay_each":
            for other in list(self.s.players):
                if other.pid != pid and not other.bankrupt:
                    self._pay(pid, card["amount"], other.pid)
            self._log(f"{p.name} pays each player ${card['amount']}.")
        elif eff == "collect_each":
            for other in list(self.s.players):
                if other.pid != pid and not other.bankrupt:
                    self._pay(other.pid, card["amount"], pid)
            self._log(f"{p.name} collects ${card['amount']} from each player.")

    def _nearest(self, pid, what):
        pos = self.s.players[pid].pos
        for i in range(1, 41):
            idx = (pos + i) % 40
            if SQUARES[idx]["type"] == what:
                return idx
        return pos

    # ------------------------------------------------------------ money flows
    def _sell_house_value(self, idx):
        return SQUARES[idx]["house_cost"] // 2

    def _liquidate(self, pid, need):
        p = self.s.players[pid]
        for idx in range(40):
            if self.s.owner[idx] != pid:
                continue
            while self.s.houses[idx] > 0 and p.cash < need:
                self.s.houses[idx] -= 1
                p.cash += self._sell_house_value(idx)
                self._log(f"Liquidated: sold a building on {SQUARES[idx]['name']}.")
        for idx in range(40):
            if p.cash >= need:
                break
            if (self.s.owner[idx] == pid and not self.s.mortgaged[idx]
                    and SQUARES[idx]["type"] in ("street", "railroad", "utility")):
                self.s.mortgaged[idx] = True
                p.cash += SQUARES[idx]["mortgage"]
                self._log(f"Liquidated: mortgaged {SQUARES[idx]['name']}.")

    def _pay(self, pid, amount, creditor=None):
        if amount <= 0 or self._stop:
            return
        p = self.s.players[pid]
        if p.cash < amount:
            self._liquidate(pid, amount)
        if p.cash >= amount:
            p.cash -= amount
            if creditor is not None:
                self.s.players[creditor].cash += amount
            return
        self._bankrupt(pid, creditor)

    def _bankrupt(self, pid, creditor):
        p = self.s.players[pid]
        self._log(f"{p.name} is bankrupt!")
        if creditor is not None:
            c = self.s.players[creditor]
            c.cash += p.cash
            for idx in range(40):
                if self.s.owner[idx] == pid:
                    self.s.owner[idx] = creditor
            c.goojf.extend(p.goojf)
        else:
            for idx in range(40):
                if self.s.owner[idx] == pid:
                    self.s.owner[idx] = None
                    self.s.mortgaged[idx] = False
        p.cash = 0
        p.goojf = []
        p.bankrupt = True
        self._stop = True
        self._check_winner()
        if self.s.winner is None and self.s.current == pid:
            self._advance_turn()

    # ----------------------------------------------------------------- actions
    def _require_turn(self):
        if self.s.winner is not None:
            raise RuleError("The game is over.")
        if self.s.phase == "await_buy":
            raise RuleError("Resolve the property purchase first.")
        if self.s.phase == "await_jail":
            raise RuleError("Resolve the jail decision first.")
        if self.s.phase not in ("await_roll", "await_manage"):
            raise RuleError("No action available right now.")

    def a_roll(self, payload):
        if self.s.phase != "await_roll":
            raise RuleError("You cannot roll right now.")
        pid = self.s.current
        d1, d2 = self._dice()
        self.s.last_dice = [d1, d2]
        p = self.s.players[pid]
        self._log(f"{p.name} rolls {d1} + {d2} = {d1 + d2}.")

        self._then = "await_manage"
        if d1 == d2:
            self.s.doubles += 1
            if self.s.doubles == 3:
                self._log("Third double in a row — straight to Jail!")
                self._send_to_jail(pid)
                self._advance_turn()
                return
            self._then = "await_roll"
            self._log("Doubles — roll again after resolving this move.")

        self._move_by(pid, d1 + d2)
        self._resolve_landing(pid)
        if self._stop:
            return
        if self.s.pending is not None:
            return
        if self.s.players[pid].in_jail:
            self._advance_turn()
            return
        self.s.phase = self._then

    def a_jail_pay(self, payload):
        if self.s.phase != "await_jail":
            raise RuleError("Not in a jail decision.")
        pid = self.s.current
        p = self.s.players[pid]
        self._log(f"{p.name} pays ${JAIL_FINE} to get out of Jail.")
        self._pay(pid, JAIL_FINE, None)
        if self._stop:
            return
        p.in_jail = False
        p.jail_rolls = 0
        self.s.phase = "await_roll"
        self.s.pending = None

    def a_jail_card(self, payload):
        if self.s.phase != "await_jail":
            raise RuleError("Not in a jail decision.")
        p = self.current_player
        if not p.goojf:
            raise RuleError("No Get Out of Jail Free card.")
        deck_name = p.goojf.pop()
        deck = self.s.chance_deck if deck_name == "chance" else self.s.chest_deck
        deck.append("ch_goojf" if deck_name == "chance" else "cc_goojf")
        p.in_jail = False
        p.jail_rolls = 0
        self._log(f"{p.name} uses a Get Out of Jail Free card.")
        self.s.phase = "await_roll"
        self.s.pending = None

    def a_jail_roll(self, payload):
        if self.s.phase != "await_jail":
            raise RuleError("Not in a jail decision.")
        pid = self.s.current
        p = self.s.players[pid]
        d1, d2 = self._dice()
        self.s.last_dice = [d1, d2]
        p.jail_rolls += 1
        self._log(f"{p.name} rolls {d1} + {d2} for doubles (attempt {p.jail_rolls}).")
        self.s.pending = None
        if d1 == d2:
            p.in_jail = False
            p.jail_rolls = 0
            self._log("Doubles — out of Jail, move the roll (no extra roll).")
            self._then = "await_manage"
            self._move_by(pid, d1 + d2)
            self._resolve_landing(pid)
            if self._stop or self.s.pending is not None:
                return
            if p.in_jail:
                self._advance_turn()
                return
            self.s.phase = "await_manage"
            return
        if p.jail_rolls < 3:
            self._log(f"No doubles — {p.name} stays in Jail.")
            self._advance_turn()
            return
        self._log("Third failed attempt — must pay the $50 fine and move.")
        self._pay(pid, JAIL_FINE, None)
        if self._stop:
            return
        p.in_jail = False
        p.jail_rolls = 0
        self._then = "await_manage"
        self._move_by(pid, d1 + d2)
        self._resolve_landing(pid)
        if self._stop or self.s.pending is not None:
            return
        if p.in_jail:
            self._advance_turn()
            return
        self.s.phase = "await_manage"

    def a_buy(self, payload):
        pend = self.s.pending
        if not pend or pend["type"] != "buy":
            raise RuleError("Nothing to buy.")
        pid = pend["player"]
        p = self.s.players[pid]
        price = pend["price"]
        if p.cash < price:
            raise RuleError("Not enough cash.")
        p.cash -= price
        self.s.owner[pend["idx"]] = pid
        self._log(f"{p.name} buys {SQUARES[pend['idx']]['name']} for ${price}.")
        self.s.phase = pend["then"]
        self.s.pending = None

    def a_skip(self, payload):
        pend = self.s.pending
        if not pend or pend["type"] != "buy":
            raise RuleError("Nothing to skip.")
        self._log(f"{self.s.players[pend['player']].name} skips "
                  f"{SQUARES[pend['idx']]['name']} (no auction).")
        self.s.phase = pend["then"]
        self.s.pending = None

    def _require_manage(self):
        self._require_turn()
        if self.s.phase not in ("await_roll", "await_manage"):
            raise RuleError("No action available right now.")

    def a_build(self, payload):
        self._require_manage()
        pid = self.s.current
        idx = payload.get("idx")
        self._validate_build(pid, idx)
        cost = SQUARES[idx]["house_cost"]
        self.s.players[pid].cash -= cost
        self.s.houses[idx] += 1
        what = "hotel" if self.s.houses[idx] == 5 else f"house {self.s.houses[idx]}"
        self._log(f"{self.s.players[pid].name} builds a {what} on "
                  f"{SQUARES[idx]['name']} for ${cost}.")

    def _validate_build(self, pid, idx):
        if idx is None or not (0 <= idx < 40):
            raise RuleError("Bad square.")
        sq = SQUARES[idx]
        if sq["type"] != "street":
            raise RuleError("You can only build on streets.")
        if self.s.owner[idx] != pid:
            raise RuleError("You do not own that property.")
        if not self._owns_group(pid, idx):
            raise RuleError("You must own the whole color group.")
        if self._group_has_mortgage(idx):
            raise RuleError("Cannot build while a property in the group is mortgaged.")
        h = self.s.houses[idx]
        if h >= 5:
            raise RuleError("Already a hotel.")
        group = self._group_indices(idx)
        min_h = min(self.s.houses[i] for i in group)
        if h != min_h:
            raise RuleError("Build evenly across the color group.")
        total_houses = sum(min(x, 4) for x in self.s.houses)
        hotels = sum(1 for x in self.s.houses if x == 5)
        if h < 4 and total_houses >= HOUSE_LIMIT:
            raise RuleError("No houses left in the bank.")
        if h == 4 and hotels >= HOTEL_LIMIT:
            raise RuleError("No hotels left in the bank.")
        if self.s.players[pid].cash < sq["house_cost"]:
            raise RuleError("Not enough cash.")

    def a_sell_house(self, payload):
        self._require_manage()
        pid = self.s.current
        idx = payload.get("idx")
        self._validate_sell(pid, idx)
        self.s.houses[idx] -= 1
        self.s.players[pid].cash += self._sell_house_value(idx)
        self._log(f"{self.s.players[pid].name} sells a building on "
                  f"{SQUARES[idx]['name']} for "
                  f"${self._sell_house_value(idx)}.")

    def _validate_sell(self, pid, idx):
        if idx is None or not (0 <= idx < 40):
            raise RuleError("Bad square.")
        sq = SQUARES[idx]
        if sq["type"] != "street":
            raise RuleError("Only streets hold buildings.")
        if self.s.owner[idx] != pid:
            raise RuleError("You do not own that property.")
        if self.s.houses[idx] <= 0:
            raise RuleError("No buildings to sell.")
        group = self._group_indices(idx)
        max_h = max(self.s.houses[i] for i in group)
        if self.s.houses[idx] != max_h:
            raise RuleError("Sell evenly across the color group.")

    def a_mortgage(self, payload):
        self._require_manage()
        pid = self.s.current
        idx = payload.get("idx")
        if idx is None or not (0 <= idx < 40):
            raise RuleError("Bad square.")
        sq = SQUARES[idx]
        if sq["type"] not in ("street", "railroad", "utility"):
            raise RuleError("That cannot be mortgaged.")
        if self.s.owner[idx] != pid:
            raise RuleError("You do not own that property.")
        if self.s.mortgaged[idx]:
            raise RuleError("Already mortgaged.")
        if any(self.s.houses[i] for i in self._group_indices(idx)):
            raise RuleError("Sell all buildings in the group first.")
        self.s.mortgaged[idx] = True
        self.s.players[pid].cash += sq["mortgage"]
        self._log(f"{self.s.players[pid].name} mortgages "
                  f"{sq['name']} (+${sq['mortgage']}).")

    def a_unmortgage(self, payload):
        self._require_manage()
        pid = self.s.current
        idx = payload.get("idx")
        if idx is None or not (0 <= idx < 40):
            raise RuleError("Bad square.")
        sq = SQUARES[idx]
        if self.s.owner[idx] != pid:
            raise RuleError("You do not own that property.")
        if not self.s.mortgaged[idx]:
            raise RuleError("That property is not mortgaged.")
        cost = math.ceil(sq["mortgage"] * 1.1)
        if self.s.players[pid].cash < cost:
            raise RuleError(f"You need ${cost} to unmortgage.")
        self.s.players[pid].cash -= cost
        self.s.mortgaged[idx] = False
        self._log(f"{self.s.players[pid].name} unmortgages {sq['name']} "
                  f"(-${cost}).")

    def a_end_turn(self, payload):
        if self.s.phase != "await_manage":
            raise RuleError("Finish resolving the move first.")
        if self.s.pending is not None:
            raise RuleError("Resolve the pending decision first.")
        self._log(f"{self.current_player.name} ends their turn.")
        self._advance_turn()

    def a_new_game(self, payload):
        self._reset()

    # ------------------------------------------------------------------ public
    def public_state(self):
        with self._lock:
            d = self.s.to_dict(SQUARES)
            d["log"] = list(self.s.log)[-60:]
            return deepcopy(d)

    def act(self, action_type, payload=None):
        with self._lock:
            self._events = []
            self.s.anim = None
            self._stop = False
            try:
                handler = getattr(self, f"a_{action_type}", None)
                if handler is None:
                    raise RuleError(f"Unknown action: {action_type}")
                handler(payload or {})
            except RuleError as e:
                return {"ok": False, "error": str(e),
                        "state": self.public_state()}
            return {"ok": True, "state": self.public_state(),
                    "events": list(self._events), "anim": self.s.anim}
