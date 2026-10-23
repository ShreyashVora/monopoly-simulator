"""Shared helpers for the pytest suite."""

import rules


def act_ok(game, action, payload=None):
    """Perform an action and assert the engine accepted it."""
    res = game.act(action, payload or {})
    assert res["ok"], f"{action} failed: {res.get('error')}"
    return res


def pass_auction(game):
    """Pass every remaining bidder until the current auction resolves."""
    while game.s.phase == "await_auction":
        game.act("auction_pass")


def random_policy_step(game):
    """Play one step using a simple buy-everything policy."""
    phase = game.s.phase
    if phase == "await_roll":
        game.act("roll")
    elif phase == "await_buy":
        pend = game.s.pending
        affordable = game.s.players[pend["player"]].cash >= pend["price"]
        game.act("buy" if affordable else "skip")
    elif phase == "await_auction":
        pend = game.s.pending
        p = game.s.players[pend["player"]]
        if pend["high_bid"] is None and p.cash >= pend["min_bid"]:
            game.act("auction_bid", {"amount": pend["min_bid"]})
        else:
            game.act("auction_pass")
    elif phase == "await_jail":
        p = game.current_player
        if p.cash >= 50:
            game.act("jail_pay")
        elif p.goojf:
            game.act("jail_card")
        else:
            game.act("jail_roll")
    elif phase == "await_debt":
        pend = game.s.pending
        pid = pend["player"]
        if game.s.players[pid].cash >= pend["amount"]:
            game.act("pay_debt")
        else:
            owned = [i for i in range(40) if game.s.owner[i] == pid]
            acted = False
            for idx in owned:
                if game.s.houses[idx] > 0:
                    if game.act("sell_house", {"idx": idx})["ok"]:
                        acted = True
                        break
            if not acted:
                for idx in owned:
                    if game.act("mortgage", {"idx": idx})["ok"]:
                        acted = True
                        break
            if not acted:
                game.act("declare_bankruptcy")
    elif phase == "await_manage":
        owned = [i for i in range(40) if game.s.owner[i] == game.s.current]
        acted = False
        for idx in owned:
            res = game.act("build", {"idx": idx})
            if res["ok"]:
                acted = True
                break
        if not acted:
            game.act("end_turn")
    return phase
