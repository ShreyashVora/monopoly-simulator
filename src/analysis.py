"""Analytical helpers for the roadmap's Markov-chain phases.

The first version is deliberately dice-only: it builds the 40x40 transition
matrix for two fair dice, redirects Go To Jail to the jail square, and derives
the stationary distribution and hitting times. Augmented state spaces (doubles
count, jail status) can be layered on later without changing the API shape.
"""

from collections import Counter

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
