"""Small built-in policies and a synchronous simulation runner."""

import random

import rules
from board import SQUARES
from trace import Run


def _greedy_manage(game):
    pid = game.s.current
    owned = [i for i in range(40) if game.s.owner[i] == pid]
    candidates = [("build", {"idx": idx}) for idx in owned
                  if SQUARES[idx]["type"] == "street"]
    candidates.append(("end_turn", {}))
    return candidates


def _random_manage(game, rng):
    pid = game.s.current
    owned = [i for i in range(40) if game.s.owner[i] == pid]
    candidates = []
    if owned and rng.random() < 0.4:
        idx = rng.choice(owned)
        candidates.append(("build", {"idx": idx}))
    if owned and rng.random() < 0.15:
        idx = rng.choice(owned)
        candidates.append(("mortgage", {"idx": idx}))
    candidates.append(("end_turn", {}))
    return candidates


def _auction_choices(game, policy, rng):
    pend = game.s.pending
    pid = pend["player"]
    p = game.s.players[pid]
    unit = pend["unit"]
    min_bid = pend["min_bid"]
    cap = min(p.cash, pend["price"])
    cap = (cap // unit) * unit
    if cap < min_bid:
        return [("auction_pass", {})]
    if policy == "greedy":
        if pend["high_bid"] is not None and pend["high_bid"] >= pend["price"]:
            return [("auction_pass", {})]
        return [("auction_bid", {"amount": min_bid}), ("auction_pass", {})]
    choices = [("auction_pass", {})]
    if rng.random() < 0.5:
        amount = rng.choice(list(range(min_bid, cap + 1, unit)))
        choices.insert(0, ("auction_bid", {"amount": amount}))
    return choices


def next_actions(game, policy="greedy", rng=None):
    """Return candidate actions for the current decision, best first."""
    rng = rng or random.Random()
    phase = game.s.phase
    if game.s.winner is not None or phase == "game_over":
        return []
    if phase == "await_roll":
        return [("roll", {})]
    if phase == "await_auction":
        return _auction_choices(game, policy, rng)
    if phase == "await_trade":
        return [("trade_accept", {}), ("trade_reject", {})]
    if phase == "await_jail":
        p = game.current_player
        if policy == "greedy":
            if p.cash >= 50:
                return [("jail_pay", {})]
            if p.goojf:
                return [("jail_card", {})]
            return [("jail_roll", {})]
        return [(o["action"], {}) for o in game.s.pending["options"]]
    if phase == "await_buy":
        pend = game.s.pending
        if policy == "greedy":
            p = game.s.players[pend["player"]]
            return [("buy" if p.cash >= pend["price"] else "skip", {})]
        return [("buy", {}), ("skip", {})]
    if phase == "await_debt":
        pend = game.s.pending
        pid = pend["player"]
        p = game.s.players[pid]
        if p.cash >= pend["amount"]:
            return [("pay_debt", {})]
        owned = [i for i in range(40) if game.s.owner[i] == pid]
        sells = sorted(
            (i for i in owned if game.s.houses[i] > 0),
            key=lambda i: SQUARES[i]["house_cost"] or 0, reverse=True)
        mortgages = sorted(
            (i for i in owned
             if not game.s.mortgaged[i]
             and SQUARES[i]["type"] in ("street", "railroad", "utility")
             and not any(game.s.houses[j]
                         for j in game._group_indices(i))),
            key=lambda i: SQUARES[i]["mortgage"] or 0, reverse=True)
        if policy == "greedy":
            return ([("sell_house", {"idx": i}) for i in sells]
                    + [("mortgage", {"idx": i}) for i in mortgages]
                    + [("declare_bankruptcy", {})])
        choices = ([("sell_house", {"idx": i}) for i in sells]
                   + [("mortgage", {"idx": i}) for i in mortgages])
        rng.shuffle(choices)
        return choices + [("declare_bankruptcy", {})]
    if phase == "await_manage":
        if policy == "greedy":
            return _greedy_manage(game)
        return _random_manage(game, rng)
    return []


def _apply_first(game, candidates):
    """Apply the first accepted candidate, returning action details."""
    for action, payload in candidates:
        result = game.act(action, payload)
        if result["ok"]:
            return action, payload, result
    return None


def random_agent_action(game, rng=None):
    """Apply one uniformly chosen legal action for the current decision actor.

    Pending purchase/jail decisions use the engine's declared options. Manage
    and debt phases enumerate candidate property actions, shuffle them, and
    apply the first action the engine accepts. Debt resolution pays when
    possible, otherwise raises cash before declaring bankruptcy.
    """
    rng = rng or random.Random()
    if game.s.winner is not None or game.s.phase == "game_over":
        return None

    phase = game.s.phase
    if phase in ("await_buy", "await_jail", "await_trade"):
        pend = game.s.pending
        if not pend:
            return None
        candidates = [(o["action"], o.get("payload") or {})
                      for o in pend["options"]]
        rng.shuffle(candidates)
        return _apply_first(game, candidates)

    if phase == "await_roll":
        return _apply_first(game, [("roll", {})])

    if phase == "await_auction":
        return _apply_first(game, _auction_choices(game, "random", rng))

    pid = game.decision_actor()
    owned = [i for i in range(40) if game.s.owner[i] == pid]

    if phase == "await_manage":
        candidates = []
        for idx in owned:
            sq = SQUARES[idx]
            if sq["type"] == "street":
                candidates.append(("build", {"idx": idx}))
                candidates.append(("sell_house", {"idx": idx}))
            if sq["type"] in ("street", "railroad", "utility"):
                candidates.append(("mortgage", {"idx": idx}))
                candidates.append(("unmortgage", {"idx": idx}))
        candidates.append(("end_turn", {}))
        rng.shuffle(candidates)
        return _apply_first(game, candidates)

    if phase == "await_debt":
        pend = game.s.pending
        if not pend:
            return None
        p = game.s.players[pid]
        if p.cash >= pend["amount"]:
            return _apply_first(game, [("pay_debt", {})])
        candidates = []
        for idx in owned:
            sq = SQUARES[idx]
            if sq["type"] == "street" and game.s.houses[idx] > 0:
                candidates.append(("sell_house", {"idx": idx}))
            if (sq["type"] in ("street", "railroad", "utility")
                    and not game.s.mortgaged[idx]):
                candidates.append(("mortgage", {"idx": idx}))
        rng.shuffle(candidates)
        result = _apply_first(game, candidates)
        if result:
            return result
        return _apply_first(game, [("declare_bankruptcy", {})])

    return None


def simulate(seed, n_players, policy="greedy", max_steps=4000, run_id=None):
    """Play a complete game with a built-in policy and return a Run trace."""
    rng = random.Random(seed)
    game = rules.Game(seed=seed, n_players=n_players)
    run = Run("agent", game.public_state(), seed=seed, n_players=n_players,
              policy=policy, label=f"{policy.title()} agent")
    if run_id:
        run.id = run_id
    steps = 0
    while game.s.winner is None and steps < max_steps:
        before = game.public_state()
        actor = game.decision_actor()
        acted = False
        for action, payload in next_actions(game, policy, rng):
            result = game.act(action, payload)
            if result["ok"]:
                run.add_step(action, payload, actor, before, result,
                             meta={"policy": policy})
                steps += 1
                acted = True
                break
        if not acted:
            run.finish("error", "policy could not find a legal action")
            return run
    if game.s.winner is None:
        run.finish("stopped", f"max steps reached ({max_steps})")
    else:
        run.finish("done")
    return run
