"""Confidence intervals and paired tests (no scipy needed)."""
from __future__ import annotations

import math
import random


def wilson_ci(correct: int, n: int, z: float = 1.96):
    """95% Wilson interval for an accuracy. Better than mean +- 1.96*SE for small n."""
    if n == 0:
        return (0.0, 0.0)
    p = correct / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(a: list[bool], b: list[bool]):
    """Paired test: are methods A and B equally accurate on the SAME questions?
    Uses only the questions where they disagree. Returns (a_only, b_only, two-sided p)."""
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if y and not x)
    n = a_only + b_only
    if n == 0:
        return a_only, b_only, 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return a_only, b_only, min(1.0, 2 * tail)


def paired_bootstrap_diff(a: list[bool], b: list[bool], iters: int = 10000, seed: int = 0):
    """95% CI for accuracy(A) - accuracy(B), resampling questions."""
    n = len(a)
    if n == 0:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    d = [int(x) - int(y) for x, y in zip(a, b)]
    diffs = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return (sum(d) / n, diffs[int(0.025 * iters)], diffs[int(0.975 * iters) - 1])
