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


def next_actions(game, policy="greedy", rng=None):
    """Return candidate actions for the current decision, best first."""
    rng = rng or random.Random()
    phase = game.s.phase
    if game.s.winner is not None or phase == "game_over":
        return []
    if phase == "await_roll":
        return [("roll", {})]
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
