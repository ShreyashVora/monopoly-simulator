"""Per-game analysis reports plus dice-only Markov-chain helpers.

Promoted runs are summarized into standings, timelines, observed move
counts, action mixes, and dice totals. The legacy overview builds the 40x40
transition matrix for two fair dice, redirects Go To Jail to the jail square,
and derives the stationary distribution and hitting times.
"""

from collections import Counter
from functools import lru_cache

import numpy as np

from board import SQUARES
from state import GO_TO_JAIL_POS, JAIL_POS

N = 40


def dice_sums():
    return Counter(a + b for a in range(1, 7) for b in range(1, 7))


def transition_matrix():
    sums = dice_sums()
    matrix = np.zeros((N, N), dtype=float)
    for start in range(N):
        for total, count in sums.items():
            target = (start + total) % N
            if target == GO_TO_JAIL_POS:
                target = JAIL_POS
            matrix[start, target] += count / 36.0
    return matrix


def stationary_distribution(matrix, iters=10000, tol=1e-13):
    pi = np.full(len(matrix), 1.0 / len(matrix))
    for _ in range(iters):
        nxt = pi @ matrix
        if np.abs(nxt - pi).sum() < tol:
            pi = nxt
            break
        pi = nxt
    total = pi.sum()
    if total:
        pi = pi / total
    return pi


def hitting_times(matrix, target):
    """Expected rolls to reach `target`, for every starting square."""
    n = len(matrix)
    keep = [i for i in range(n) if i != target]
    q = matrix[np.ix_(keep, keep)]
    try:
        h = np.linalg.solve(np.eye(len(keep)) - q, np.ones(len(keep)))
    except np.linalg.LinAlgError:
        h = np.linalg.pinv(np.eye(len(keep)) - q) @ np.ones(len(keep))
    result = np.zeros(n)
    result[keep] = h
    return result


def labels():
    """Unique square labels; repeated names carry their board index."""
    counts = Counter(s["short"] for s in SQUARES)
    return [s["short"] if counts[s["short"]] == 1
            else f'{s["short"]} #{s["idx"]}' for s in SQUARES]


@lru_cache(maxsize=1)
def overview():
    matrix = transition_matrix()
    pi = stationary_distribution(matrix)
    names = labels()
    hits = {name: hitting_times(matrix, s["idx"]).tolist()
            for name, s in zip(names, SQUARES)}
    return {
        "labels": names,
        "matrix": matrix.tolist(),
        "stationary": pi.tolist(),
        "hittingTimes": hits,
        "note": "Dice-only 40-square chain; Go To Jail redirects to Jail.",
    }


PROPERTY_TYPES = {"street", "railroad", "utility"}
STREET_GROUPS = {}
for _idx, _square in enumerate(SQUARES):
    _group = _square.get("group")
    if _square["type"] == "street" and _group:
        STREET_GROUPS.setdefault(_group, []).append(_idx)


def _property_stats(state, pid):
    owned = [i for i, owner in enumerate(state["owner"]) if owner == pid]
    properties = [i for i in owned if SQUARES[i]["type"] in PROPERTY_TYPES]
    monopolies = sum(
        1 for idxs in STREET_GROUPS.values()
        if all(state["owner"][i] == pid for i in idxs)
    )
    houses = sum(1 for i in properties if 0 < state["houses"][i] < 5)
    hotels = sum(1 for i in properties if state["houses"][i] >= 5)
    mortgaged = sum(1 for i in properties if state["mortgaged"][i])
    equity = 0
    for idx in properties:
        sq = SQUARES[idx]
        price = sq.get("price") or 0
        if state["mortgaged"][idx]:
            price -= sq.get("mortgage") or 0
        equity += price
        if state["houses"][idx]:
            equity += state["houses"][idx] * (sq.get("house_cost") or 0)
    cash = state["players"][pid]["cash"]
    return {
        "cash": cash,
        "net_worth": cash + equity,
        "properties": len(properties),
        "monopolies": monopolies,
        "houses": houses,
        "hotels": hotels,
        "mortgaged": mortgaged,
    }


def observed_transitions(run):
    """Count actual square-to-square moves in a recorded game trace."""
    counts = [[0] * N for _ in range(N)]
    previous = run["initial"]
    total = 0
    for step in run.get("steps") or []:
        actor = step["actor"]
        before = previous["players"][actor]["pos"]
        after = step["state"]["players"][actor]["pos"]
        if before != after:
            counts[before][after] += 1
            total += 1
        previous = step["state"]
    return {"labels": labels(), "counts": counts, "total": total}


def game_report(run):
    """Build a per-game dashboard report from a complete run trace."""
    initial = run["initial"]
    steps = run.get("steps") or []
    states = [initial] + [step["state"] for step in steps]
    final = states[-1]
    players = final.get("players", [])
    stats_by_player = [
        [_property_stats(state, pid) for state in states]
        for pid in range(len(players))
    ]
    timeline_players = [
        {
            "pid": pid,
            "cash": [value["cash"] for value in values],
            "net_worth": [value["net_worth"] for value in values],
            "properties": [value["properties"] for value in values],
        }
        for pid, values in enumerate(stats_by_player)
    ]

    standings = []
    for pid, player in enumerate(players):
        values = stats_by_player[pid]
        final_stats = values[-1]
        standings.append({
            "pid": pid,
            "name": player["name"],
            "glyph": player["glyph"],
            "color": player["color"],
            "bankrupt": player["bankrupt"],
            "final_cash": final_stats["cash"],
            "final_net_worth": final_stats["net_worth"],
            "properties": final_stats["properties"],
            "monopolies": final_stats["monopolies"],
            "houses": final_stats["houses"],
            "hotels": final_stats["hotels"],
            "mortgaged": final_stats["mortgaged"],
            "peak_cash": max(value["cash"] for value in values),
            "peak_net_worth": max(value["net_worth"] for value in values),
        })
    standings.sort(key=lambda row: (-row["final_net_worth"], row["pid"]))

    actions = Counter(step["action"] for step in steps)
    rolls = Counter()
    for step in steps:
        if step["action"] not in ("roll", "jail_roll"):
            continue
        dice = step["state"].get("dice")
        if dice:
            rolls[str(sum(dice))] += 1

    run_summary = {key: value for key, value in run.items()
                   if key not in ("initial", "steps")}
    return {
        "run": run_summary,
        "winner": run.get("winner"),
        "steps": len(steps),
        "turns": final.get("turn", 1),
        "bankrupt_count": sum(1 for player in players if player["bankrupt"]),
        "players": standings,
        "timeline": {
            "labels": ["Start"] + [f"Step {step['seq']}" for step in steps],
            "turns": [state.get("turn", 1) for state in states],
            "cash": [player["cash"] for player in timeline_players],
            "net_worth": [player["net_worth"] for player in timeline_players],
            "properties": [player["properties"] for player in timeline_players],
        },
        "actions": dict(sorted(actions.items())),
        "rolls": {str(total): rolls.get(str(total), 0)
                  for total in range(2, 13)},
        "observed_transitions": observed_transitions(run),
    }
