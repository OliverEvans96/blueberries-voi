"""Sequential without-replacement sales composition PMF (DP)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray


def sequential_wor_composition_probs(
    counts: Sequence[int],
    sales_tot: int,
    weights: NDArray[np.floating],
) -> dict[tuple[int, ...], float]:
    """PMF over sales compositions under the ``allocate_sales`` pick loop (DP).

    Among nonempty cohorts, pick proportional to fixed ``weights`` (not
    ``remaining * weights``) - matching ``model.allocate_sales``.

    NumPy-vectorized active-state DP (ADR 0103 / T-065); same recurrence as the
    prior pure-Python enumerate/unpack loop.
    """
    counts_arr = np.asarray([int(c) for c in counts], dtype=np.int64)
    L = int(counts_arr.size)
    if L == 0:
        return {(): 1.0} if sales_tot == 0 else {}
    if sales_tot < 0 or sales_tot > int(counts_arr.sum()):
        return {}
    if sales_tot == 0:
        return {tuple(0 for _ in range(L)): 1.0}

    # Flat index for composition c: mix-radix with digit bounds (n_i+1).
    dims = counts_arr + np.int64(1)
    strides = np.ones(L, dtype=np.int64)
    for i in range(L - 2, -1, -1):
        strides[i] = strides[i + 1] * dims[i + 1]
    size = int(np.prod(dims))

    cur = np.zeros(size, dtype=np.float64)
    cur[0] = 1.0  # zero composition
    w = np.asarray(weights, dtype=np.float64)

    for _ in range(sales_tot):
        active = np.flatnonzero(cur > 0.0)
        if active.size == 0:
            break
        p = cur[active]
        rem = active.copy()
        comps = np.empty((active.size, L), dtype=np.int64)
        for i in range(L):
            comps[:, i] = rem // strides[i]
            rem %= strides[i]
        room = comps < counts_arr[None, :]
        avail = np.where(room, w[None, :], 0.0)
        tot = avail.sum(axis=1)
        valid = tot > 0.0
        if not np.any(valid):
            cur = np.zeros(size, dtype=np.float64)
            break
        active = active[valid]
        p = p[valid]
        avail = avail[valid]
        tot = tot[valid]
        probs = avail / tot[:, None]

        nxt = np.zeros(size, dtype=np.float64)
        for j in range(L):
            mask_j = avail[:, j] > 0.0
            if not np.any(mask_j):
                continue
            dest = active[mask_j] + int(strides[j])
            np.add.at(nxt, dest, p[mask_j] * probs[mask_j, j])
        cur = nxt

    out: dict[tuple[int, ...], float] = {}
    active = np.flatnonzero(cur > 0.0)
    if active.size == 0:
        return out
    rem = active.copy()
    comps = np.empty((active.size, L), dtype=np.int64)
    for i in range(L):
        comps[:, i] = rem // strides[i]
        rem %= strides[i]
    for k in range(active.size):
        out[tuple(int(x) for x in comps[k])] = float(cur[active[k]])
    return out


def sequential_wor_composition_prob(
    counts: Sequence[int],
    sales: Sequence[int],
    weights: NDArray[np.floating],
) -> float:
    """PMF of one sales composition under ``allocate_sales`` (via DP table)."""
    sales_l = [int(s) for s in sales]
    demand = int(sum(sales_l))
    table = sequential_wor_composition_probs(counts, demand, weights)
    return float(table.get(tuple(sales_l), 0.0))
