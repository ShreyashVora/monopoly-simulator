"""Monopoly rules engine with auctions and player-to-player trading.

Turn flow is a small state machine. Actions advance the game until a human
decision is required, then park at `phase == "await_*"` with `pending` set.
The same decision points are also driven by the built-in agent policies.
"""

import math
import random
import threading
from copy import deepcopy

import cards
from board import GROUP_MEMBERS, HOTEL_LIMIT, HOUSE_LIMIT, SQUARES
from state import (GO_TO_JAIL_POS, JAIL_FINE, JAIL_POS, MAX_PLAYERS,
                   MIN_PLAYERS, PASS_GO_BONUS, GameState)


class RuleError(Exception):
    pass


def validate_player_count(n_players):
    if (isinstance(n_players, bool) or not isinstance(n_players, int)
            or not MIN_PLAYERS <= n_players <= MAX_PLAYERS):
        raise RuleError(
            f"Player count must be between {MIN_PLAYERS} and {MAX_PLAYERS}.")


class Game:
    def __init__(self, seed=None, n_players=4):
        validate_player_count(n_players)
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self.forced_dice = None
        self.n_players = n_players
        self._reset()

    # ------------------------------------------------------------------ reset
    def _reset(self):
        self.s = GameState(self.n_players)
        self.s.chance_deck = [c["id"] for c in cards.CHANCE]
        self.s.chest_deck = [c["id"] for c in cards.CHEST]
        self._rng.shuffle(self.s.chance_deck)
        self._rng.shuffle(self.s.chest_deck)
        self._events = []
        self._stop = False
        self._then = "await_manage"
        self._payments = []
        self._payment_done = None
        self._bank_auction_queue = []
        self._bank_auction_resume = None
        self._log(f"New game — {self.n_players} players, $1500 each. "
                  "Player 1 to roll.")

    # -------------------------------------------------------------- utilities
    @property
    def current_player(self):
        return self.s.players[self.s.current]

    def decision_actor(self):
        pend = self.s.pending
        if pend:
            if self.s.phase == "await_debt" and pend.get("type") == "debt":
                return pend["player"]
            if self.s.phase == "await_auction" and pend.get("type") == "auction":
                return pend["player"]
            if self.s.phase == "await_trade" and pend.get("type") == "trade":
                return pend["recipient"]
        return self.s.current

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

    # ---------------------------------------------------------------- auctions
    def _active_order(self, start):
        n = len(self.s.players)
        return [(start + k) % n for k in range(n)
                if not self.s.players[(start + k) % n].bankrupt]

    def _auction_unit(self, idx):
        return max(1, (SQUARES[idx].get("price") or 0) // 10)

    def _auction_min_bid(self, pend):
        if pend["high_bid"] is None:
            return pend["unit"]
        return pend["high_bid"] + pend["unit"]

    def _auction_max_bid(self, pid, unit):
        return (self.s.players[pid].cash // unit) * unit

    def _next_auction_pid(self, pend, after):
        participants = pend["participants"]
        if after not in participants:
            return None
        start = participants.index(after)
        for k in range(1, len(participants) + 1):
            pid = participants[(start + k) % len(participants)]
            if pid not in pend["passed"]:
                return pid
        return None

    def _set_auction_turn(self, pend, pid):
        pend["player"] = pid
        pend["min_bid"] = self._auction_min_bid(pend)
        pend["max_bid"] = self._auction_max_bid(pid, pend["unit"])
        pend["active"] = [p for p in pend["participants"]
                          if p not in pend["passed"]]
        p = self.s.players[pid]
        name = SQUARES[pend["idx"]]["name"]
        if pend["high_bid"] is None:
            prompt = (f"{p.name} to bid on {name} — opening bid "
                      f"${pend['min_bid']} (max ${pend['max_bid']}).")
        else:
            high_name = self.s.players[pend["high_bidder"]].name
            prompt = (f"{p.name} to bid on {name} — high bid "
                      f"${pend['high_bid']} by {high_name}; minimum "
                      f"${pend['min_bid']} (max ${pend['max_bid']}).")
        pend["prompt"] = prompt
        pend["options"] = [
            {"action": "auction_bid",
             "label": f"Bid ${pend['min_bid']} or more", "payload": {}},
            {"action": "auction_pass", "label": "Pass", "payload": {}},
        ]

    def _start_auction(self, idx, then=None, bank=False):
        if self.s.winner is not None:
            return
        sq = SQUARES[idx]
        if self.s.owner[idx] is not None:
            return
        price = sq.get("price") or 0
        if price <= 0:
            return
        participants = self._active_order(self.s.current)
        if not participants:
            if bank:
                self._resume_bank_auctions()
            else:
                self._restore_phase(then or "await_manage")
            return
        unit = self._auction_unit(idx)
        self.s.pending = {
            "type": "auction",
            "idx": idx,
            "price": price,
            "unit": unit,
            "player": participants[0],
            "participants": participants,
            "passed": [],
            "active": list(participants),
            "high_bid": None,
            "high_bidder": None,
            "min_bid": unit,
            "max_bid": self._auction_max_bid(participants[0], unit),
            "then": then,
            "bank": bool(bank),
            "prompt": "",
            "options": [],
        }
        self.s.phase = "await_auction"
        self._log(f"{sq['name']} goes to auction — opening bid ${unit}.")
        self._auction_advance()

    def _auction_advance(self):
        while True:
            pend = self.s.pending
            if not pend or pend.get("type") != "auction":
                return
            active = [p for p in pend["participants"]
                      if p not in pend["passed"]]
            high = pend["high_bidder"]
            if high is not None:
                if not [p for p in active if p != high]:
                    self._finish_auction(high, pend["high_bid"])
                    return
            elif not active:
                self._finish_auction(None, 0)
                return

            pid = pend["player"]
            if pid in pend["passed"]:
                nxt = self._next_auction_pid(pend, pid)
                if nxt is None:
                    continue
                pid = nxt
                pend["player"] = pid

            p = self.s.players[pid]
            min_bid = self._auction_min_bid(pend)
            max_bid = self._auction_max_bid(pid, pend["unit"])
            if max_bid < min_bid:
                pend["passed"].append(pid)
                self._log(f"{p.name} cannot meet the ${min_bid} minimum "
                          "and is out of the auction.")
                pend["active"] = [x for x in pend["participants"]
                                  if x not in pend["passed"]]
                nxt = self._next_auction_pid(pend, pid)
                if nxt is None:
                    pend["player"] = pid
                    continue
                pend["player"] = nxt
                continue

            self._set_auction_turn(pend, pid)
            return

    def _finish_auction(self, winner, amount):
        pend = self.s.pending
        if not pend or pend.get("type") != "auction":
            return
        idx = pend["idx"]
        name = SQUARES[idx]["name"]
        bank = bool(pend.get("bank"))
        then = pend.get("then")
        if winner is None:
            self._log(f"No bids for {name} — it stays with the bank.")
        else:
            p = self.s.players[winner]
            p.cash -= amount
            self.s.owner[idx] = winner
            self._log(f"{p.name} wins {name} for ${amount}.")
        self.s.pending = None
        if bank:
            self._resume_bank_auctions()
        else:
            self._restore_phase(then or "await_manage")

    def _resume_bank_auctions(self):
        if self.s.winner is not None:
            self._bank_auction_queue = []
            self._bank_auction_resume = None
            return
        while self._bank_auction_queue:
            idx = self._bank_auction_queue.pop(0)
            if self.s.owner[idx] is None:
                self._start_auction(idx, bank=True)
                return
        phase = self._bank_auction_resume or "await_manage"
        self._bank_auction_resume = None
        self._restore_phase(phase)

    def _maybe_start_bank_auction(self):
        if (self.s.winner is not None or not self._bank_auction_queue
                or self.s.phase not in ("await_roll", "await_manage",
                                        "await_jail")):
            return
        pend = self.s.pending
        if pend is not None and pend.get("type") != "jail":
            return
        while self._bank_auction_queue:
            idx = self._bank_auction_queue.pop(0)
            if self.s.owner[idx] is not None:
                continue
            self._bank_auction_resume = self.s.phase
            self._start_auction(idx, bank=True)
            return

    def _restore_phase(self, phase):
        self.s.pending = None
        if phase == "await_jail":
            self._start_turn()
        else:
            self.s.phase = phase

    # ----------------------------------------------------------------- trading
    def _trade_item_desc(self, terms):
        parts = []
        if terms["cash"]:
            parts.append(f"${terms['cash']}")
        parts.extend(SQUARES[idx]["name"] for idx in terms["properties"])
        if terms["goojf"]:
            cards = terms["goojf"]
            parts.append(f"{cards} Get Out of Jail Free")
        return ", ".join(parts) if parts else "nothing"

    def _validate_trade_terms(self, pid, terms, label):
        if terms is None:
            terms = {}
        if not isinstance(terms, dict):
            raise RuleError(f"Trade {label} must be an object.")
        cash = terms.get("cash", 0)
        if isinstance(cash, bool) or not isinstance(cash, int) or cash < 0:
            raise RuleError(
                f"Trade {label} cash must be a non-negative whole dollar amount.")
        properties = terms.get("properties", [])
        if not isinstance(properties, list):
            raise RuleError(f"Trade {label} properties must be a list.")
        seen = set()
        for idx in properties:
            if isinstance(idx, bool) or not isinstance(idx, int):
                raise RuleError("Trade property indices must be integers.")
            if idx in seen:
                raise RuleError("A property cannot appear twice in a trade.")
            seen.add(idx)
            if not 0 <= idx < 40:
                raise RuleError("Bad trade property.")
            sq = SQUARES[idx]
            if sq["type"] not in ("street", "railroad", "utility"):
                raise RuleError(f"{sq['name']} cannot be traded.")
            if self.s.owner[idx] != pid:
                raise RuleError(
                    f"{self.s.players[pid].name} does not own {sq['name']}.")
            if self.s.mortgaged[idx]:
                raise RuleError(
                    f"Unmortgage {sq['name']} before trading it.")
            if any(self.s.houses[i] for i in self._group_indices(idx)):
                raise RuleError(
                    f"Sell all buildings in {sq['name']}'s color group "
                    "before trading it.")
        goojf = terms.get("goojf", 0)
        if isinstance(goojf, bool) or not isinstance(goojf, int) or goojf < 0:
            raise RuleError(
                f"Trade {label} GOOJF count must be a non-negative integer.")
        p = self.s.players[pid]
        if cash > p.cash:
            raise RuleError(
                f"{p.name} only has ${p.cash} for the trade.")
        if goojf > len(p.goojf):
            raise RuleError(
                f"{p.name} only has {len(p.goojf)} Get Out of Jail Free card(s).")
        return {"cash": cash, "properties": list(properties), "goojf": goojf}

    def _exchange_goojf(self, proposer, recipient, give_count, want_count):
        give_cards = (proposer.goojf[-give_count:]
                      if give_count else [])
        want_cards = (recipient.goojf[-want_count:]
                      if want_count else [])
        if give_count:
            del proposer.goojf[-give_count:]
        if want_count:
            del recipient.goojf[-want_count:]
        proposer.goojf.extend(want_cards)
        recipient.goojf.extend(give_cards)

    def _trade_is_empty(self, terms):
        return not (terms["cash"] or terms["properties"] or terms["goojf"])

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
        start = p.pos
        p.pos = JAIL_POS
        p.in_jail = True
        p.jail_rolls = 0
        self.s.doubles = 0
        path = [start, JAIL_POS] if start != JAIL_POS else [JAIL_POS]
        self.s.anim = {"mover": pid, "path": path}
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
                            {"action": "skip", "label": "Pass — auction it",
                             "payload": {}},
                        ],
                    }
                else:
                    self._log(f"{p.name} cannot afford {sq['name']} (${price}).")
                    self._start_auction(p.pos, then=self._then)
            elif owner == pid:
                self._log(f"{p.name} owns {sq['name']}.")
            else:
                rent = self._rent(p.pos, rent_mode)
                self._log(f"{p.name} pays ${rent} rent to "
                          f"{self.s.players[owner].name}.")
                self._pay(pid, rent, owner, reason=f"rent on {sq['name']}")
                return
        elif t == "tax":
            self._log(f"{p.name} pays ${sq['amount']} {sq['short']}.")
            self._pay(pid, sq["amount"], None, reason=sq["name"])
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
                        if sq2["type"] == "railroad" and self.s.owner[i] == owner)
            rent = sq["rents"][max(0, count - 1)]
            return rent * 2 if rent_mode == "rr_double" else rent
        if sq["type"] == "utility":
            if rent_mode == "utility_ten":
                return 10 * sum(self.s.last_dice or (7,))
            count = sum(1 for i, sq2 in enumerate(SQUARES)
                        if sq2["type"] == "utility" and self.s.owner[i] == owner)
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
                self._pay(pid, -amt, None, reason="card")
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
                self._pay(pid, owed, None, reason="repairs")
        elif eff == "pay_each":
            others = [o for o in self.s.players
                      if o.pid != pid and not o.bankrupt]
            amount = card["amount"] * len(others)
            creditors = [(o.pid, card["amount"]) for o in others]
            self._log(f"{p.name} owes each player ${card['amount']}.")
            if amount:
                self._queue_payments(
                    [(pid, amount, creditors, "card")])
        elif eff == "collect_each":
            payments = [
                (other.pid, card["amount"], [(pid, card["amount"])], "card")
                for other in self.s.players
                if other.pid != pid and not other.bankrupt
            ]
            self._log(f"{p.name} collects ${card['amount']} from each player.")
            self._queue_payments(payments)

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

    def _bank_count(self, kind):
        if kind == "house":
            return HOUSE_LIMIT - sum(min(h, 4) for h in self.s.houses)
        return HOTEL_LIMIT - sum(1 for h in self.s.houses if h == 5)

    def _creditor_label(self, creditors):
        if not creditors:
            return "the bank"
        names = [self.s.players[pid].name for pid, _ in creditors]
        return " and ".join(names)

    def _pay(self, pid, amount, creditor=None, reason="payment", done=None):
        if amount <= 0:
            if done is not None:
                done()
            return
        creditors = [] if creditor is None else [(creditor, amount)]
        self._queue_payments([(pid, amount, creditors, reason)], done)

    def _queue_payments(self, payments, done=None):
        if not payments:
            if done is not None:
                done()
            return
        self._payments = list(payments)
        self._payment_done = done
        self._process_payments()

    def _process_payments(self):
        while self._payments:
            payer, amount, creditors, reason = self._payments[0]
            p = self.s.players[payer]
            if p.bankrupt:
                self._payments.pop(0)
                continue
            if p.cash < amount:
                self._start_debt(payer, amount, creditors, reason)
                return
            p.cash -= amount
            for cid, share in creditors:
                if cid is not None and not self.s.players[cid].bankrupt:
                    self.s.players[cid].cash += share
            self._payments.pop(0)
            self._log(f"{p.name} pays ${amount} to "
                      f"{self._creditor_label(creditors)}.")
        self.s.pending = None
        if self._payment_done is not None:
            done = self._payment_done
            self._payment_done = None
            done()
        else:
            self.s.phase = self._then

    def _start_debt(self, pid, amount, creditors, reason):
        p = self.s.players[pid]
        self.s.phase = "await_debt"
        self.s.pending = {
            "type": "debt",
            "player": pid,
            "amount": amount,
            "creditor": creditors[0][0] if len(creditors) == 1 else None,
            "creditors": [{"player": cid, "amount": share}
                          for cid, share in creditors],
            "reason": reason,
            "prompt": (f"{p.name} owes ${amount} to "
                       f"{self._creditor_label(creditors)} ({reason}). "
                       "Sell buildings or mortgage property, then pay."),
            "options": [
                {"action": "pay_debt", "label": f"Pay ${amount}",
                 "payload": {}},
                {"action": "declare_bankruptcy",
                 "label": "Declare bankruptcy", "payload": {}},
            ],
        }
        self._log(f"{p.name} must raise ${amount} for {reason}.")

    def a_pay_debt(self, payload):
        pend = self.s.pending
        if self.s.phase != "await_debt" or not pend or pend["type"] != "debt":
            raise RuleError("No debt to pay.")
        pid = pend["player"]
        p = self.s.players[pid]
        amount = pend["amount"]
        if p.cash < amount:
            raise RuleError(
                f"Raise ${amount - p.cash} more before paying the debt.")
        p.cash -= amount
        for entry in pend["creditors"]:
            cid = entry["player"]
            if not self.s.players[cid].bankrupt:
                self.s.players[cid].cash += entry["amount"]
        self._log(f"{p.name} pays ${amount} to "
                  f"{self._creditor_label([(e['player'], e['amount']) for e in pend['creditors']])}.")
        self._payments.pop(0)
        self.s.pending = None
        self._process_payments()

    def a_declare_bankruptcy(self, payload):
        pend = self.s.pending
        if self.s.phase != "await_debt" or not pend or pend["type"] != "debt":
            raise RuleError("No debt to settle.")
        pid = pend["player"]
        was_current = self.s.current == pid
        creditors = [(e["player"], e["amount"]) for e in pend["creditors"]]
        self._payments.pop(0)
        self.s.pending = None
        self._bankrupt(pid, creditors)
        if self.s.winner is not None or was_current:
            self._payments = []
            self._payment_done = None
            return
        self._stop = False
        self._process_payments()

    def _bankrupt(self, pid, creditors=None):
        creditors = list(creditors or [])
        p = self.s.players[pid]
        banked = []
        self._log(f"{p.name} is bankrupt!")
        if len(creditors) == 1:
            cid = creditors[0][0]
            c = self.s.players[cid]
            c.cash += p.cash
            for idx in range(40):
                if self.s.owner[idx] == pid:
                    self.s.owner[idx] = cid
            c.goojf.extend(p.goojf)
        else:
            if creditors:
                owed = sum(amount for _, amount in creditors)
                remaining = p.cash
                for cid, amount in creditors:
                    share = int(p.cash * amount / owed)
                    self.s.players[cid].cash += share
                    remaining -= share
                if creditors and remaining:
                    self.s.players[creditors[0][0]].cash += remaining
                self.s.players[creditors[0][0]].goojf.extend(p.goojf)
            for idx in range(40):
                if self.s.owner[idx] == pid:
                    banked.append(idx)
                    self.s.owner[idx] = None
                    self.s.mortgaged[idx] = False
                    self.s.houses[idx] = 0
        p.cash = 0
        p.goojf = []
        p.bankrupt = True
        self._stop = True
        self._check_winner()
        if self.s.winner is not None:
            self._bank_auction_queue = []
            self._bank_auction_resume = None
        else:
            self._bank_auction_queue.extend(banked)
        if self.s.winner is None and self.s.current == pid:
            self._advance_turn()

    # ----------------------------------------------------------------- actions
    def _asset_actor(self):
        pend = self.s.pending
        if (self.s.phase == "await_debt" and pend
                and pend.get("type") == "debt"):
            return pend["player"]
        return self.s.current

    def _require_property_action(self, allow_spending=True):
        if self.s.winner is not None:
            raise RuleError("The game is over.")
        if self.s.phase not in ("await_roll", "await_manage",
                               "await_jail", "await_debt"):
            raise RuleError("No property action available right now.")
        if not allow_spending and self.s.phase == "await_debt":
            raise RuleError("You cannot spend cash while settling a debt.")

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

    def _release_from_jail(self, pid):
        p = self.s.players[pid]
        p.in_jail = False
        p.jail_rolls = 0
        self.s.pending = None
        self.s.phase = "await_roll"

    def _leave_jail_and_move(self, pid, steps):
        p = self.s.players[pid]
        p.in_jail = False
        p.jail_rolls = 0
        self.s.pending = None
        self._move_by(pid, steps)
        self._resolve_landing(pid)
        if self._stop or self.s.pending is not None:
            return
        if p.in_jail:
            self._advance_turn()
            return
        self.s.phase = self._then

    def a_jail_pay(self, payload):
        if self.s.phase != "await_jail":
            raise RuleError("Not in a jail decision.")
        pid = self.s.current
        p = self.s.players[pid]
        self._log(f"{p.name} pays ${JAIL_FINE} to get out of Jail.")
        self._then = "await_roll"
        self._pay(pid, JAIL_FINE, None, reason="Jail fine",
                  done=lambda: self._release_from_jail(pid))

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
        self._then = "await_manage"
        self._pay(pid, JAIL_FINE, None, reason="Jail fine",
                  done=lambda: self._leave_jail_and_move(pid, d1 + d2))

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
        self._log(f"{self.s.players[pend['player']].name} passes on "
                  f"{SQUARES[pend['idx']]['name']} — auctioning it.")
        self._start_auction(pend["idx"], then=pend["then"])

    def a_auction_bid(self, payload):
        pend = self.s.pending
        if (self.s.phase != "await_auction" or not pend
                or pend.get("type") != "auction"):
            raise RuleError("No auction is waiting for a bid.")
        pid = pend["player"]
        p = self.s.players[pid]
        amount = payload.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise RuleError("Bid amount must be a whole dollar amount.")
        unit = pend["unit"]
        min_bid = self._auction_min_bid(pend)
        if amount < min_bid:
            raise RuleError(f"The minimum bid is ${min_bid}.")
        if amount % unit:
            raise RuleError(f"Bids must be multiples of ${unit}.")
        if amount > p.cash:
            raise RuleError(f"{p.name} only has ${p.cash}.")
        pend["high_bid"] = amount
        pend["high_bidder"] = pid
        self._log(f"{p.name} bids ${amount} for "
                  f"{SQUARES[pend['idx']]['name']}.")
        nxt = self._next_auction_pid(pend, pid)
        if nxt is not None:
            pend["player"] = nxt
        self._auction_advance()

    def a_auction_pass(self, payload):
        pend = self.s.pending
        if (self.s.phase != "await_auction" or not pend
                or pend.get("type") != "auction"):
            raise RuleError("No auction is waiting for a pass.")
        pid = pend["player"]
        if pid not in pend["passed"]:
            pend["passed"].append(pid)
        self._log(f"{self.s.players[pid].name} passes in the auction for "
                  f"{SQUARES[pend['idx']]['name']}.")
        nxt = self._next_auction_pid(pend, pid)
        if nxt is not None:
            pend["player"] = nxt
        self._auction_advance()

    def a_trade_propose(self, payload):
        if self.s.winner is not None:
            raise RuleError("The game is over.")
        if self.s.phase not in ("await_roll", "await_manage", "await_jail"):
            raise RuleError("Trades are not available right now.")
        pend = self.s.pending
        if (pend is not None and not (self.s.phase == "await_jail"
                                      and pend.get("type") == "jail")):
            raise RuleError("Resolve the pending decision first.")
        pid = self.s.current
        rid = payload.get("recipient")
        if (isinstance(rid, bool) or not isinstance(rid, int)
                or not 0 <= rid < len(self.s.players)):
            raise RuleError("Choose a valid trade recipient.")
        if rid == pid:
            raise RuleError("You cannot trade with yourself.")
        if self.s.players[rid].bankrupt:
            raise RuleError("That player is bankrupt.")
        give = self._validate_trade_terms(pid, payload.get("give"), "offer")
        want = self._validate_trade_terms(rid, payload.get("want"), "request")
        if self._trade_is_empty(give) and self._trade_is_empty(want):
            raise RuleError("A trade must include at least one item.")
        p = self.s.players[pid]
        r = self.s.players[rid]
        resume_phase = self.s.phase
        self.s.phase = "await_trade"
        self.s.pending = {
            "type": "trade",
            "player": pid,
            "proposer": pid,
            "recipient": rid,
            "give": give,
            "want": want,
            "resume_phase": resume_phase,
            "prompt": f"{p.name} proposes a trade to {r.name}.",
            "options": [
                {"action": "trade_accept", "label": "Accept trade",
                 "payload": {}},
                {"action": "trade_reject", "label": "Reject trade",
                 "payload": {}},
            ],
        }
        self._log(f"{p.name} offers {r.name}: {self._trade_item_desc(give)} "
                  f"for {self._trade_item_desc(want)}.")

    def a_trade_accept(self, payload):
        pend = self.s.pending
        if (self.s.phase != "await_trade" or not pend
                or pend.get("type") != "trade"):
            raise RuleError("No trade offer to accept.")
        pid = pend["proposer"]
        rid = pend["recipient"]
        p = self.s.players[pid]
        r = self.s.players[rid]
        give = self._validate_trade_terms(pid, pend["give"], "offer")
        want = self._validate_trade_terms(rid, pend["want"], "request")
        p.cash -= give["cash"]
        r.cash += give["cash"]
        r.cash -= want["cash"]
        p.cash += want["cash"]
        for idx in give["properties"]:
            self.s.owner[idx] = rid
        for idx in want["properties"]:
            self.s.owner[idx] = pid
        self._exchange_goojf(p, r, give["goojf"], want["goojf"])
        resume_phase = pend["resume_phase"]
        self._log(f"{r.name} accepts the trade from {p.name}: "
                  f"{self._trade_item_desc(give)} for "
                  f"{self._trade_item_desc(want)}.")
        self.s.pending = None
        self._restore_phase(resume_phase)

    def a_trade_reject(self, payload):
        pend = self.s.pending
        if (self.s.phase != "await_trade" or not pend
                or pend.get("type") != "trade"):
            raise RuleError("No trade offer to reject.")
        pid = pend["proposer"]
        rid = pend["recipient"]
        p = self.s.players[pid]
        r = self.s.players[rid]
        resume_phase = pend["resume_phase"]
        self._log(f"{r.name} rejects the trade offer from {p.name}.")
        self.s.pending = None
        self._restore_phase(resume_phase)

    def a_build(self, payload):
        self._require_property_action(allow_spending=False)
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
        self._require_property_action()
        pid = self._asset_actor()
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
        if self.s.houses[idx] == 5 and self._bank_count("house") < 4:
            raise RuleError("Not enough houses in the bank to break the hotel.")

    def a_mortgage(self, payload):
        self._require_property_action()
        pid = self._asset_actor()
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
        self._require_property_action(allow_spending=False)
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
        n_players = payload.get("n_players", self.n_players)
        validate_player_count(n_players)
        self.n_players = n_players
        self._reset()

    # ------------------------------------------------------------------ public
    def public_state(self):
        with self._lock:
            d = self.s.to_dict(SQUARES)
            d["log"] = list(self.s.log)[-60:]
            d["bank_houses"] = self._bank_count("house")
            d["bank_hotels"] = self._bank_count("hotel")
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
                self._maybe_start_bank_auction()
            except RuleError as e:
                return {"ok": False, "error": str(e),
                        "state": self.public_state()}
            return {"ok": True, "state": self.public_state(),
                    "events": list(self._events), "anim": self.s.anim}
