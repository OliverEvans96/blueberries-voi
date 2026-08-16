#!/usr/bin/env python3
"""C2 freshness inference accuracy study (unit truth vs filter approximations).

Outputs JSON consumed by ``generate_c2_accuracy_report.py``.

Study blocks:
  1. K sensitivity (histogram B): K ∈ {8, 16, 32} at L=4
  2. L sweep including L=20: A + B (+ MF at L≤4 only)
  3. Particle count: N ∈ {200, 2000}
  4. Observation channel: totals-only vs sales_by
  5. L=20 tractability / accuracy notes

Run:
  uv run python experiments/c2_accuracy_study.py --probe   # 1 rep/cell timing check
  uv run python experiments/c2_accuracy_study.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy import stats

from blueberries_voi.filter.age_likelihood import mean_field_update
from blueberries_voi.filter.types import P1Obs
from blueberries_voi.model import ModelParams, allocate_sales, picking_weights

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "c2_accuracy_study.json"

# Truth / filter knobs
DAYS = 14
UNITS_PER_LOT = 15
GAMMA_SHAPE = 2.0
GAMMA_SCALE = 0.05
FRESH_GRID = (0.0, 1.0)  # bin k covers [k/K, (k+1)/K); 0 = spoiled
LL_MAX_L = 4  # exact log_p_sales_waste_given_ages cap
LL_COUNT = 4  # per-lot count in tractable LL


@dataclass
class Metrics:
    mean_f_mae: float
    hist_tv_mean: float
    ess_final: float
    ess_min: float
    coverage90_mean_f: float


@dataclass
class CellResult:
    block: str
    algorithm: str
    label: str
    n_particles: int
    n_lots: int
    k_bins: int
    obs_mode: str
    n_reps: int
    metrics: Metrics
  # optional stderr over reps
    mean_f_mae_se: float
    hist_tv_se: float
    ess_final_se: float


def ess(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    w = w / max(w.sum(), 1e-300)
    return float(1.0 / np.sum(w**2))


def tv(p: np.ndarray, q: np.ndarray) -> float:
    return float(0.5 * np.abs(p - q).sum())


def freshness_bins(k: int) -> np.ndarray:
    return np.linspace(FRESH_GRID[0], FRESH_GRID[1], k + 1)


def f_to_bin(f: float, edges: np.ndarray) -> int:
    if f <= edges[0]:
        return 0
    if f >= edges[-1]:
        return len(edges) - 2
    return int(np.searchsorted(edges, f, side="right") - 1)


def lot_mean_f(units_f: np.ndarray, offsets: list[int]) -> np.ndarray:
    return np.array(
        [float(units_f[offsets[i] : offsets[i + 1]].mean()) for i in range(len(offsets) - 1)]
    )


def truth_hist_per_lot(units_f: np.ndarray, offsets: list[int], edges: np.ndarray) -> np.ndarray:
    l = len(offsets) - 1
    k = len(edges) - 1
    h = np.zeros((l, k), dtype=float)
    for ell in range(l):
        sl = units_f[offsets[ell] : offsets[ell + 1]]
        for f in sl:
            h[ell, f_to_bin(float(f), edges)] += 1.0
        s = h[ell].sum()
        if s > 0:
            h[ell] /= s
    return h


def gamma_decrement(rng: np.random.Generator) -> float:
    return float(rng.gamma(GAMMA_SHAPE, GAMMA_SCALE))


def unit_tau(f: float, eta: float) -> float:
    return max(0.0, 1.0 - f) * eta


def simulate_pick_units(
    units_f: np.ndarray,
    offsets: list[int],
    demand: int,
    params: ModelParams,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Kernel-weighted sequential unit picks; returns (sold_mask, sales_by_lot)."""
    alive = units_f > 0.0
    n_units = len(units_f)
    sold = np.zeros(n_units, dtype=bool)
    l = len(offsets) - 1
    sales_by = np.zeros(l, dtype=int)
    to_sell = min(demand, int(alive.sum()))
    for _ in range(to_sell):
        idx_alive = np.where(alive & ~sold)[0]
        if idx_alive.size == 0:
            break
        taus = np.array([unit_tau(units_f[i], params.eta_ref) for i in idx_alive])
        w = picking_weights(
            taus,
            sigma=params.sigma,
            beta=params.beta,
            eta=params.eta_ref,
            uniform=params.uniform_picking,
        )
        w = np.asarray(w, dtype=float)
        tot = w.sum()
        if tot <= 0:
            j = int(rng.choice(idx_alive))
        else:
            j = int(idx_alive[int(rng.choice(len(idx_alive), p=w / tot))])
        sold[j] = True
        # lot id
        for ell in range(l):
            if offsets[ell] <= j < offsets[ell + 1]:
                sales_by[ell] += 1
                break
    return sold, sales_by


def simulate_truth_day(
    units_f: np.ndarray,
    offsets: list[int],
    params: ModelParams,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int, int, np.ndarray]:
    before = units_f.copy()
    units = units_f.copy()
    for i in range(len(units)):
        if units[i] > 0:
            units[i] = max(0.0, units[i] - gamma_decrement(rng))
    on_hand = int((units > 0).sum())
    demand = int(rng.integers(max(1, on_hand // 5), max(2, on_hand // 3 + 1)))
    demand = min(demand, on_hand)
    sold_mask, sales_by = simulate_pick_units(units, offsets, demand, params, rng)
    spoiled_before_pick = int(((before > 0) & (units <= 0)).sum())
    units[sold_mask] = 0.0
    spoiled_after = int(((units <= 0) & ~sold_mask & (before > 0)).sum())
    waste = max(spoiled_before_pick, spoiled_after)
    return units, int(sold_mask.sum()), waste, sales_by


def hist_predict(h: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Shift mass toward bin 0 (spoilage) via random gamma decrement (per-lot)."""
    l, kb = h.shape
    assert kb == k
    out = np.zeros_like(h)
    edges = freshness_bins(k)
    for ell in range(l):
        for b in range(k):
            mass = h[ell, b]
            if mass <= 0:
                continue
            d = gamma_decrement(rng)
            # center of bin
            center = 0.5 * (edges[b] + edges[b + 1])
            new_f = max(0.0, center - d)
            nb = f_to_bin(new_f, edges)
            out[ell, nb] += mass
        s = out[ell].sum()
        if s > 0:
            out[ell] /= s
    return out


def tau_from_hist(h_row: np.ndarray, edges: np.ndarray, eta: float) -> float:
  # E[tau] from histogram over freshness
    centers = 0.5 * (edges[:-1] + edges[1:])
    mean_f = float((h_row * centers).sum())
    return unit_tau(mean_f, eta)


def loglik_totals(
    lot_counts: np.ndarray,
    taus: np.ndarray,
    sales: int,
    waste: int,
    params: ModelParams,
) -> float:
    from blueberries_voi.filter.age_likelihood import log_p_sales_waste_given_ages

    n = [int(x) for x in lot_counts]
    if len(n) > LL_MAX_L:
        return 0.0  # defer to factorized below
    return float(log_p_sales_waste_given_ages(n, list(taus), int(sales), int(waste), params))


def loglik_sales_by(
    lot_counts: np.ndarray,
    taus: np.ndarray,
    sales_by: np.ndarray,
    params: ModelParams,
) -> float:
    """Factorized per-lot sequential-WOR (tractable at L=20)."""
    from blueberries_voi.filter.age_likelihood.sequential_wor import (
        sequential_wor_composition_prob,
    )

    ll = 0.0
    for ell in range(len(lot_counts)):
        n = int(lot_counts[ell])
        s = int(sales_by[ell])
        if s < 0 or s > n:
            return float(-np.inf)
        w = picking_weights(
            [float(taus[ell])],
            sigma=params.sigma,
            beta=params.beta,
            eta=params.eta_ref,
            uniform=params.uniform_picking,
        )
        p = sequential_wor_composition_prob([n], [s], w)
        if p <= 0.0:
            return float(-np.inf)
        ll += math.log(p)
    return ll


def loglik_for_obs(
    lot_counts: np.ndarray,
    taus: np.ndarray,
    sales: int,
    waste: int,
    sales_by: np.ndarray | None,
    obs_mode: str,
    params: ModelParams,
) -> float:
    if obs_mode == "sales_by" and sales_by is not None:
        return loglik_sales_by(lot_counts, taus, sales_by, params)
    if len(lot_counts) <= LL_MAX_L:
        return loglik_totals(lot_counts, taus, sales, waste, params)
    # L>4 totals: match aggregate sales/waste only (weak but O(L))
    on_hand = int(lot_counts.sum())
    if sales < 0 or sales > on_hand:
        return float(-np.inf)
    return 0.0 if waste >= 0 else float(-np.inf)


def effective_obs_mode(n_lots: int, obs_mode: str) -> str:
    """L>4 must use factorized sales_by (exact joint totals LL is exponential)."""
    if n_lots > LL_MAX_L:
        return "sales_by"
    return obs_mode


def run_histogram_pf(
    *,
    n_particles: int,
    n_lots: int,
    k: int,
    obs_mode: str,
    seed: int,
    params: ModelParams,
) -> Metrics:
    obs_mode = effective_obs_mode(n_lots, obs_mode)
    rng = np.random.default_rng(seed)
    upl = UNITS_PER_LOT
    total = n_lots * upl
    offsets = [i * upl for i in range(n_lots + 1)]
    edges = freshness_bins(k)

    # truth units
    units_f = rng.uniform(0.45, 0.95, size=total)
    lot_counts = np.full(n_lots, upl, dtype=int)

    # particles: L x K histograms
    hists = np.zeros((n_particles, n_lots, k), dtype=float)
    for p in range(n_particles):
        for ell in range(n_lots):
            hists[p, ell, k // 2] = 1.0

    log_w = np.zeros(n_particles, dtype=float)
    ess_trace: list[float] = []

    for _day in range(DAYS):
        units_f, sales, waste, sales_by = simulate_truth_day(units_f, offsets, params, rng)
        obs_by = sales_by if obs_mode == "sales_by" else None

        for p in range(n_particles):
            hists[p] = hist_predict(hists[p], k, rng)
            taus = np.array(
                [tau_from_hist(hists[p, ell], edges, params.eta_ref) for ell in range(n_lots)]
            )
            ll = loglik_for_obs(
                lot_counts, taus, sales, waste, obs_by, obs_mode, params
            )
            log_w[p] = ll if math.isfinite(ll) else -1e9

        mx = log_w.max()
        w = np.exp(log_w - mx)
        w /= w.sum()
        ess_trace.append(ess(w))
        # resample
        idx = rng.choice(n_particles, size=n_particles, p=w)
        hists = hists[idx]
        log_w = np.zeros(n_particles)

    truth_mf = lot_mean_f(units_f, offsets)
    truth_h = truth_hist_per_lot(units_f, offsets, edges)

    w = np.ones(n_particles) / n_particles
    pred_mf = np.zeros(n_lots)
    pred_h = np.zeros((n_lots, k))
    for p in range(n_particles):
        centers = 0.5 * (edges[:-1] + edges[1:])
        for ell in range(n_lots):
            pred_mf[ell] += w[p] * float((hists[p, ell] * centers).sum())
            pred_h[ell] += w[p] * hists[p, ell]

    mae = float(np.abs(pred_mf - truth_mf).mean())
    tv_mean = float(np.mean([tv(pred_h[ell], truth_h[ell]) for ell in range(n_lots)]))

    # 90% CI coverage on lot mean f
    centers = 0.5 * (edges[:-1] + edges[1:])
    particle_mf = np.array(
        [[(hists[p, ell] * centers).sum() for ell in range(n_lots)] for p in range(n_particles)]
    )
    lo = np.percentile(particle_mf, 5, axis=0)
    hi = np.percentile(particle_mf, 95, axis=0)
    cov = float(np.mean((truth_mf >= lo) & (truth_mf <= hi)))

    return Metrics(
        mean_f_mae=mae,
        hist_tv_mean=tv_mean,
        ess_final=ess_trace[-1],
        ess_min=float(min(ess_trace)),
        coverage90_mean_f=cov,
    )


def run_unit_pf(
    *,
    n_particles: int,
    n_lots: int,
    obs_mode: str,
    seed: int,
    params: ModelParams,
) -> Metrics:
    rng = np.random.default_rng(seed)
    upl = UNITS_PER_LOT
    total = n_lots * upl
    offsets = [i * upl for i in range(n_lots + 1)]
    k = 32
    edges = freshness_bins(k)

    units_f = rng.uniform(0.45, 0.95, size=total)
    freshness = rng.uniform(0.45, 0.95, size=(n_particles, total))

    log_w = np.zeros(n_particles, dtype=float)
    ess_trace: list[float] = []

    for _day in range(DAYS):
        units_f, sales, waste, sales_by = simulate_truth_day(units_f, offsets, params, rng)

        for p in range(n_particles):
            for i in range(total):
                if freshness[p, i] > 0:
                    freshness[p, i] = max(0.0, freshness[p, i] - gamma_decrement(rng))
            # kernel path loglik proxy
            taus = np.array([unit_tau(freshness[p, i], params.eta_ref) for i in range(total)])
            w_pick = picking_weights(
                taus,
                sigma=params.sigma,
                beta=params.beta,
                eta=params.eta_ref,
                uniform=params.uniform_picking,
            )
            ll = 0.0
            alive = freshness[p] > 0
            if int(alive.sum()) >= sales and obs_mode == "totals":
                # sequential weighted picks along fixed rng substream
                sub = np.random.default_rng(seed + p + _day)
                rem = alive.copy()
                for _ in range(sales):
                    idx = np.where(rem)[0]
                    ww = np.array([w_pick[i] for i in idx], dtype=float)
                    tot = ww.sum()
                    if tot <= 0:
                        break
                    j = idx[int(sub.choice(len(idx), p=ww / tot))]
                    ll += math.log(max(ww[list(idx).index(j)] / tot, 1e-300))
                    rem[j] = False
            elif obs_mode == "sales_by" and sales_by is not None:
                # per-lot factorized score
                for ell in range(n_lots):
                    sl = slice(offsets[ell], offsets[ell + 1])
                    mean_f = float(freshness[p, sl][freshness[p, sl] > 0].mean() if (freshness[p, sl] > 0).any() else 0)
                    ll += -abs(mean_f - sales_by[ell] / upl)
            log_w[p] = ll

        mx = log_w.max()
        w = np.exp(log_w - mx)
        w /= w.sum()
        ess_trace.append(ess(w))
        idx = rng.choice(n_particles, size=n_particles, p=w)
        freshness = freshness[idx]
        log_w = np.zeros(n_particles)

    truth_mf = lot_mean_f(units_f, offsets)
    truth_h = truth_hist_per_lot(units_f, offsets, edges)
    w = np.ones(n_particles) / n_particles
    pred_mf = np.zeros(n_lots)
    pred_h = np.zeros((n_lots, k))
    for p in range(n_particles):
        for ell in range(n_lots):
            sl = freshness[p, offsets[ell] : offsets[ell + 1]]
            pred_mf[ell] += w[p] * float(sl[sl > 0].mean() if (sl > 0).any() else 0)
            for f in sl:
                if f > 0:
                    pred_h[ell, f_to_bin(float(f), edges)] += w[p]
    for ell in range(n_lots):
        s = pred_h[ell].sum()
        if s > 0:
            pred_h[ell] /= s

    mae = float(np.abs(pred_mf - truth_mf).mean())
    tv_mean = float(np.mean([tv(pred_h[ell], truth_h[ell]) for ell in range(n_lots)]))
    particle_mf = np.array(
        [
            [
                float(
                    freshness[p, offsets[ell] : offsets[ell + 1]][
                        freshness[p, offsets[ell] : offsets[ell + 1]] > 0
                    ].mean()
                    if (freshness[p, offsets[ell] : offsets[ell + 1]] > 0).any()
                    else 0.0
                )
                for ell in range(n_lots)
            ]
            for p in range(n_particles)
        ]
    )
    lo = np.percentile(particle_mf, 5, axis=0)
    hi = np.percentile(particle_mf, 95, axis=0)
    cov = float(np.mean((truth_mf >= lo) & (truth_mf <= hi)))

    return Metrics(
        mean_f_mae=mae,
        hist_tv_mean=tv_mean,
        ess_final=ess_trace[-1],
        ess_min=float(min(ess_trace)),
        coverage90_mean_f=cov,
    )


def run_mf(
    *,
    n_lots: int,
    k: int,
    seed: int,
    params: ModelParams,
) -> Metrics:
    """MF on age grid (L≤4); maps freshness truth to τ marginals for scoring."""
    if n_lots > LL_MAX_L:
        raise ValueError("MF exact LL requires L<=4")
    rng = np.random.default_rng(seed)
    upl = UNITS_PER_LOT
    total = n_lots * upl
    offsets = [i * upl for i in range(n_lots + 1)]
    edges = freshness_bins(k)
    from blueberries_voi.filter.types import age_grid

    tau_grid = age_grid(k)
    units_f = rng.uniform(0.45, 0.95, size=total)
    q = np.ones((n_lots, k), dtype=float) / k

    for _day in range(DAYS):
        units_f, sales, waste, _ = simulate_truth_day(units_f, offsets, params, rng)
        q = mean_field_update(
            [LL_COUNT] * n_lots,
            q,
            P1Obs(sales_total=sales, waste_total=waste, arrivals=0),
            params,
            tau_grid=tau_grid,
        )

    truth_mf = lot_mean_f(units_f, offsets)
    centers = np.linspace(0, 1, k)
    pred_mf = (q * centers).sum(axis=1)
    mae = float(np.abs(pred_mf - truth_mf).mean())
    truth_h = truth_hist_per_lot(units_f, offsets, edges)
    # map q to coarse hist for TV
    tv_mean = float(np.mean([tv(q[ell], truth_h[ell]) for ell in range(n_lots)]))
    return Metrics(
        mean_f_mae=mae,
        hist_tv_mean=tv_mean,
        ess_final=float("nan"),
        ess_min=float("nan"),
        coverage90_mean_f=float("nan"),
    )


def aggregate(block: str, algo: str, label: str, rows: list[Metrics], **meta) -> CellResult:
    mae = np.array([r.mean_f_mae for r in rows])
    tvv = np.array([r.hist_tv_mean for r in rows])
    ef = np.array([r.ess_final for r in rows if math.isfinite(r.ess_final)])
    return CellResult(
        block=block,
        algorithm=algo,
        label=label,
        n_reps=len(rows),
        metrics=Metrics(
            mean_f_mae=float(mae.mean()),
            hist_tv_mean=float(tvv.mean()),
            ess_final=float(ef.mean()) if ef.size else float("nan"),
            ess_min=float(np.nanmean([r.ess_min for r in rows])),
            coverage90_mean_f=float(np.mean([r.coverage90_mean_f for r in rows])),
        ),
        mean_f_mae_se=float(mae.std(ddof=1) / math.sqrt(len(rows))) if len(rows) > 1 else 0.0,
        hist_tv_se=float(tvv.std(ddof=1) / math.sqrt(len(rows))) if len(rows) > 1 else 0.0,
        ess_final_se=float(ef.std(ddof=1) / math.sqrt(len(ef))) if ef.size > 1 else 0.0,
        **meta,
    )


def try_voi_beta_null(n_reps: int = 12) -> dict[str, float | int | str]:
    if os.environ.get("BLUEBERRIES_VOI_BACKEND", "").lower() != "rust":
        return {"status": "skipped", "reason": "BLUEBERRIES_VOI_BACKEND!=rust"}
    try:
        from blueberries_voi.voi import run_voi_crn_cell
    except ImportError:
        return {"status": "skipped", "reason": "voi import failed"}

    deltas: list[float] = []
    for i in range(n_reps):
        rows = run_voi_crn_cell(
            scenario="P1",
            beta=1.0,
            n_reps=1,
            seed=1000 + i,
            n_particles=64,
            horizon=7,
        )
        if not rows:
            continue
        p0 = next(r for r in rows if r.scenario == "P0")
        p1 = next(r for r in rows if r.scenario == "P1")
        deltas.append(float(p1.profit_mean - p0.profit_mean))
    if not deltas:
        return {"status": "skipped", "reason": "no rows"}
    arr = np.array(deltas)
    t_stat, p_val = stats.ttest_1samp(arr, 0.0) if len(arr) > 1 else (0.0, 1.0)
    return {
        "status": "ok",
        "n_reps": len(arr),
        "mean_delta": float(arr.mean()),
        "std_delta": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        "t_stat": float(t_stat),
        "p_value": float(p_val),
    }


def wor_state_count(l: int, count_per_lot: int = 4) -> int:
    return int((count_per_lot + 1) ** l)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="1 rep/cell runtime probe")
    args = parser.parse_args()
    probe = args.probe

    reps_k = 1 if probe else 20
    reps_l = 1 if probe else 15
    reps_l_big = 1 if probe else 8  # L>=8 unit PF
    reps_n = 1 if probe else 15
    reps_n2k = 1 if probe else 10
    reps_obs = 1 if probe else 15

    t0 = time.time()
    params = ModelParams()
    results: list[CellResult] = []
    timings: list[tuple[str, float]] = []

    def timed(label: str, fn):
        t_cell = time.time()
        out = fn()
        timings.append((label, time.time() - t_cell))
        if probe:
            print(f"  {label}: {timings[-1][1]:.2f}s")
        return out

    print("block 1: K sensitivity …")
    for k in (8, 16, 32):
        rows = [
            timed(
                f"B K={k} rep={i}",
                lambda k=k, i=i: run_histogram_pf(
                    n_particles=200,
                    n_lots=4,
                    k=k,
                    obs_mode="totals",
                    seed=10_000 + k * 100 + i,
                    params=params,
                ),
            )
            for i in range(reps_k)
        ]
        results.append(
            aggregate(
                "k_sensitivity",
                "c2_b",
                f"K={k}",
                rows,
                n_particles=200,
                n_lots=4,
                k_bins=k,
                obs_mode="totals",
            )
        )

    print("block 2: L sweep …")
    for l in (2, 4, 8, 20):
        obs_l = "sales_by" if l > LL_MAX_L else "totals"
        n_rep_a = reps_l_big if l >= 8 else reps_l
        rows_b = [
            timed(
                f"B L={l} rep={i}",
                lambda l=l, i=i, obs_l=obs_l: run_histogram_pf(
                    n_particles=200,
                    n_lots=l,
                    k=16,
                    obs_mode=obs_l,
                    seed=20_000 + l * 100 + i,
                    params=params,
                ),
            )
            for i in range(reps_l)
        ]
        results.append(
            aggregate(
                "l_sweep",
                "c2_b",
                f"L={l}",
                rows_b,
                n_particles=200,
                n_lots=l,
                k_bins=16,
                obs_mode=obs_l,
            )
        )
        rows_a = [
            timed(
                f"A L={l} rep={i}",
                lambda l=l, i=i: run_unit_pf(
                    n_particles=200,
                    n_lots=l,
                    obs_mode="totals",
                    seed=30_000 + l * 100 + i,
                    params=params,
                ),
            )
            for i in range(n_rep_a)
        ]
        results.append(
            aggregate(
                "l_sweep",
                "c2_a",
                f"L={l}",
                rows_a,
                n_particles=200,
                n_lots=l,
                k_bins=0,
                obs_mode="totals",
            )
        )
        if l <= LL_MAX_L:
            rows_c = [
                timed(
                    f"C L={l} rep={i}",
                    lambda l=l, i=i: run_mf(
                        n_lots=l, k=16, seed=40_000 + l * 100 + i, params=params
                    ),
                )
                for i in range(reps_l)
            ]
            results.append(
                aggregate(
                    "l_sweep",
                    "c2_c",
                    f"L={l}",
                    rows_c,
                    n_particles=1,
                    n_lots=l,
                    k_bins=16,
                    obs_mode="totals",
                )
            )

    print("block 3: N sweep …")
    for n in (200, 2000):
        n_rep = reps_n2k if n == 2000 else reps_n
        rows = [
            timed(
                f"B N={n} rep={i}",
                lambda n=n, i=i: run_histogram_pf(
                    n_particles=n,
                    n_lots=4,
                    k=16,
                    obs_mode="totals",
                    seed=50_000 + n + i,
                    params=params,
                ),
            )
            for i in range(n_rep)
        ]
        results.append(
            aggregate(
                "n_sweep",
                "c2_b",
                f"N={n}",
                rows,
                n_particles=n,
                n_lots=4,
                k_bins=16,
                obs_mode="totals",
            )
        )

    print("block 4: obs channel …")
    for mode in ("totals", "sales_by"):
        rows = [
            timed(
                f"B obs={mode} rep={i}",
                lambda mode=mode, i=i: run_histogram_pf(
                    n_particles=200,
                    n_lots=4,
                    k=16,
                    obs_mode=mode,
                    seed=60_000 + i + (0 if mode == "totals" else 1000),
                    params=params,
                ),
            )
            for i in range(reps_obs)
        ]
        results.append(
            aggregate(
                "obs_channel",
                "c2_b",
                mode,
                rows,
                n_particles=200,
                n_lots=4,
                k_bins=16,
                obs_mode=mode,
            )
        )
        rows_a = [
            timed(
                f"A obs={mode} rep={i}",
                lambda mode=mode, i=i: run_unit_pf(
                    n_particles=200,
                    n_lots=4,
                    obs_mode=mode,
                    seed=70_000 + i + (0 if mode == "totals" else 1000),
                    params=params,
                ),
            )
            for i in range(reps_obs)
        ]
        results.append(
            aggregate(
                "obs_channel",
                "c2_a",
                mode,
                rows_a,
                n_particles=200,
                n_lots=4,
                k_bins=0,
                obs_mode=mode,
            )
        )

    voi = try_voi_beta_null() if not probe else {"status": "skipped", "reason": "probe mode"}

    if probe and timings:
        worst = max(timings, key=lambda x: x[1])
        print(f"slowest cell: {worst[0]} = {worst[1]:.2f}s")
        est_full = sum(t for _, t in timings) * max(reps_k, reps_l, reps_n)
        print(f"rough full-study estimate: {est_full:.0f}s ({est_full/60:.1f} min)")

    payload = {
        "probe": probe,
        "wall_seconds": time.time() - t0,
        "probe_timings": timings if probe else [],
        "days_per_rep": DAYS,
        "units_per_lot": UNITS_PER_LOT,
        "ll_max_l": LL_MAX_L,
        "wor_states_l20_n4": wor_state_count(20, 4),
        "wor_states_l4_n4": wor_state_count(4, 4),
        "voi_beta_null": voi,
        "results": [asdict(r) for r in results],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"wrote {OUT_JSON} in {payload['wall_seconds']:.1f}s")


if __name__ == "__main__":
    main()
