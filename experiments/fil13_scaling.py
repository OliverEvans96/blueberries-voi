"""FIL-13 broader scaling + slow-turn L + effectiveness notes for Oliver.

Writes ``experiments/fil13_scaling.md`` and optionally
``figures/m1/fil13_scaling.png``. Prefer this over package changes.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from blueberries_voi.filter.backends import (
    SlidingWindowBackend,
    get_backend,
    run_microbench,
    tv_vs_exact,
)
from blueberries_voi.filter.types import (
    MAX_JOINT_FLOATS,
    P1Obs,
    joint_state_count,
)
from blueberries_voi.model import (
    Cohort,
    ModelParams,
    day_step,
)
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim import (
    DayLog,
    EpisodeLog,
    LotState,
    generate_arrival_age,
    open_loop_order,
    run_episode,
)

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures" / "m1"
EXP = ROOT / "experiments"

# Soft limits for the laptop microbench matrix.
MAX_FLOATS_SOFT = 2.0e8
TIMEOUT_S = 8.0
N_STEPS = 3

KS = (4, 6, 8, 10)
NS = (200, 500, 2000)
LS = (2, 3, 4, 6, 8, 10, 12, 15)

# Backends to time; sliding_window W=2/3 via memory formula + smoke time.
TIMED_BACKENDS: tuple[str, ...] = (
    "full_joint",
    "sliding_window",
    "mean_field",
    "bootstrap_pf",
    "bound_L",
)


@dataclass
class ScalingRow:
    backend: str
    K: int
    N: int
    L: int
    wall_s: float
    peak_mb: float
    bytes_proxy: float
    floats_proxy: float
    oom: bool
    timeout: bool
    skipped: bool
    skip_reason: str = ""
    tv: float | None = None


def bytes_proxy(backend: str, *, K: int, N: int, L: int, window: int = 3) -> float:
    """Documented float-count x 8 bytes (design memory, not stub allocation).

    Formulas (age posterior / particle state proxy):
    - full_joint: ``K**L * N``  (FIL-13 joint budget)
    - sliding_window W: ``(K**W + max(0, L-W)*K) * N``
    - mean_field: ``L * K * N``
    - bound_L (max_L=4): ``K**min(L,4) * N``
    - bootstrap_pf: ``N * L``  (one age index per cohort; no grid posterior)
    """
    name = backend
    w = window
    if name.startswith("sliding_window"):
        if "_W" in name:
            w = int(name.rsplit("_W", 1)[1])
        floats = (K**w + max(0, L - w) * K) * N
    elif name == "full_joint":
        floats = joint_state_count(K, L, N)
    elif name == "mean_field":
        floats = float(L * K * N)
    elif name == "bound_L":
        floats = joint_state_count(K, min(L, 4), N)
    elif name == "bootstrap_pf":
        floats = float(N * L)
    else:
        floats = float(L * K * N)
    return float(floats) * 8.0


def floats_proxy(backend: str, *, K: int, N: int, L: int) -> float:
    return bytes_proxy(backend, K=K, N=N, L=L) / 8.0


def would_skip(backend: str, *, K: int, N: int, L: int) -> str | None:
    f = floats_proxy(backend, K=K, N=N, L=L)
    if backend == "full_joint" and f > MAX_JOINT_FLOATS:
        return f"joint guard K^L*N={f:.2e} > {MAX_JOINT_FLOATS:.2e}"
    if f > MAX_FLOATS_SOFT:
        return f"soft skip floats_proxy={f:.2e} > {MAX_FLOATS_SOFT:.2e}"
    return None


def run_cell(backend: str, *, K: int, N: int, L: int) -> ScalingRow:
    reason = would_skip(backend, K=K, N=N, L=L)
    bp = bytes_proxy(backend, K=K, N=N, L=L)
    fp = bp / 8.0
    if reason is not None:
        return ScalingRow(
            backend=backend,
            K=K,
            N=N,
            L=L,
            wall_s=0.0,
            peak_mb=0.0,
            bytes_proxy=bp,
            floats_proxy=fp,
            oom=backend == "full_joint" and "joint guard" in reason,
            timeout=False,
            skipped=True,
            skip_reason=reason,
        )

    # Reuse package microbench (timeout soft-limit).
    row = run_microbench(backend, K=K, N=N, L=L, timeout_s=TIMEOUT_S)
    return ScalingRow(
        backend=backend,
        K=K,
        N=N,
        L=L,
        wall_s=row.wall_s,
        peak_mb=row.peak_rss_mb,
        bytes_proxy=bp,
        floats_proxy=fp,
        oom=row.oom,
        timeout=row.timeout,
        skipped=False,
        tv=row.tv,
    )


def empirical_L(
    params: ModelParams,
    *,
    S: int = 60,
    lead_time: int = 1,
    delivery_every: int = 1,
    root_seed: int = 11,
    run_id: str = "fil13scale",
    n_burn: int = 20,
    n_score: int = 90,
) -> dict[str, float]:
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    if delivery_every <= 1:
        ep = run_episode(
            params,
            root_seed=root_seed,
            run_id=run_id,
            n_burn=n_burn,
            n_score=n_score,
            S=S,
            lead_time=lead_time,
            shipments=ships,
        )
    else:
        ep = _run_episode_cadence(
            params,
            root_seed=root_seed,
            run_id=run_id,
            n_burn=n_burn,
            n_score=n_score,
            S=S,
            lead_time=lead_time,
            delivery_every=delivery_every,
            shipments=ships,
        )
    Ls = np.array([d.L for d in ep.scored], dtype=float)
    return {
        "p50": float(np.percentile(Ls, 50)),
        "p90": float(np.percentile(Ls, 90)),
        "max": float(np.max(Ls)),
        "mean": float(np.mean(Ls)),
    }


def _run_episode_cadence(
    params: ModelParams,
    *,
    root_seed: int,
    run_id: str | int,
    n_burn: int,
    n_score: int,
    S: int,
    lead_time: int,
    delivery_every: int,
    shipments: list[Any],
) -> EpisodeLog:
    """Open-loop variant: order only every ``delivery_every`` days."""
    p = params
    ships = shipments
    cohorts: list[Cohort] = []
    next_lot_id = 1
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score

    for day in range(horizon):
        on_hand = sum(c.n for c in cohorts)
        if day % delivery_every == 0:
            order_qty = open_loop_order(on_hand, S=S)
            cases = int(np.ceil(order_qty / p.case_size)) if order_qty > 0 else 0
            order_units = cases * p.case_size
            pending[day + lead_time] = pending.get(day + lead_time, 0) + order_units
        else:
            order_units = 0

        arrival_units = int(pending.pop(day, 0))
        delivery: Cohort | None = None
        if arrival_units > 0:
            rng_ship = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SHIP
            )
            rng_sensor = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SENSOR
            )
            tau_in = generate_arrival_age(rng_ship, rng_sensor, ships, p)
            delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
            next_lot_id += 1

        rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
        result = day_step(
            cohorts,
            params=p,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
        )
        cohorts = result.cohorts
        lots = [LotState(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts]
        log.days.append(
            DayLog(
                day=day,
                lots=lots,
                sales_total=result.sales_total,
                waste_total=result.waste_total,
                arrivals=arrival_units,
                order_qty=order_units,
                demand=result.demand,
                L=len(lots),
            )
        )
    return log


def posterior_tv_between(
    be_a: str,
    be_b: str,
    *,
    L: int,
    K: int,
    N: int = 500,
) -> float:
    """TV between mean age posteriors after one shared predict/update (same seed)."""
    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(7)
    a = get_backend(be_a)
    b = get_backend(be_b)
    sa = a.initialize(N=N, K=K, L=L, params=ModelParams(), rng=rng_a)
    sb = b.initialize(N=N, K=K, L=L, params=ModelParams(), rng=rng_b)
    sa.age_post[:] = 1.0 / K
    sb.age_post[:] = 1.0 / K
    sa.days_on_shelf[:] = 0.0
    sb.days_on_shelf[:] = 0.0
    obs = P1Obs(sales_total=15, waste_total=1, arrivals=0)
    sa = a.predict_update(sa, obs, ModelParams(), rng_a)
    sb = b.predict_update(sb, obs, ModelParams(), rng_b)
    # Compare particle-mean marginal on cohort 0.
    pa = sa.age_post[:, 0, :].mean(axis=0)
    pb = sb.age_post[:, 0, :].mean(axis=0)
    pa = pa / max(float(pa.sum()), 1e-300)
    pb = pb / max(float(pb.sum()), 1e-300)
    return float(0.5 * np.abs(pa - pb).sum())


def tv_vs_exact_extended(*, L: int, K: int, backend: str = "full_joint") -> float:
    """Same as package helper; exposed for L=4 / K=4 tractability checks."""
    return tv_vs_exact(backend, L=L, K=K)


def q10_calendar_eta_days(params: ModelParams) -> float:
    """Rough calendar days to reach eta_ref effective age at store temperature."""
    rate = params.q10 ** ((params.t_store_c - params.t_ref_c) / 10.0)
    return float(params.eta_ref / rate)


def grocery_interpretation_md(base_L: dict[str, float]) -> list[str]:
    p = ModelParams()
    cases_day = p.demand_mu / p.case_size
    shelf_cases = 60 / p.case_size
    eta_cal = q10_calendar_eta_days(p)
    rate = p.q10 ** ((p.t_store_c - p.t_ref_c) / 10.0)
    return [
        "## Part A - Grocery interpretation of M1 defaults",
        "",
        "Think of one store selling one blueberry SKU (punnets):",
        "",
        f"- **Demand:** about **{p.demand_mu:.0f} punnets/day** "
        f"(~**{cases_day:.1f} cases/day** at case size {p.case_size}). "
        f"Demand is a bit jumpy (V/M={p.demand_vm}).",
        f"- **Ordering:** age-blind base-stock **S=60** punnets "
        f"(~**{shelf_cases:.1f} cases** on the shelf target) with **daily delivery, "
        f"1-day lead time**. That is roughly two days of mean demand cover.",
        f"- **Picking:** sigma={p.sigma} is a **mild fresh bias** - shoppers prefer "
        f"fresher trays a bit, but not pure LIFO. Strong LIFO would be sigma<<1.",
        f"- **Spoilage:** Weibull beta={p.beta}, eta={p.eta_ref:.0f} days at 0 degC; "
        f"store fridge **{p.t_store_c:.0f} degC** with Q10={p.q10:.0f} "
        "=> effective age "
        f"runs ~**{rate:.2f}x** calendar, so characteristic life is ~**{eta_cal:.1f} "
        f"calendar days** on the shelf - still long vs a ~2-day turn.",
        "",
        "### Shelf dwell and why measured L is tiny",
        "",
        "With ~30 sold/day from ~60 on hand, inventory **turns in about two days**. "
        "Daily deliveries add a new lot when the store reorders, but older lots empty "
        "quickly through sales (and mild fresh-bias still lets older stock move). "
        "Extinct lots (count->0) drop out. So live lot count L stays small:",
        "",
        f"- baseline scored window: **p50={base_L['p50']:.2f}, "
        f"p90={base_L['p90']:.2f}, max={base_L['max']:.0f}, "
        f"mean={base_L['mean']:.2f}**",
        "",
        "That matches intuition: a fast-turning berry facing with daily truck "
        "arrivals rarely has more than a couple of overlapping delivery lots.",
        "",
        '### Is the "6 lots ceiling" about the store?',
        "",
        "**No - it is about filter memory, not store reality.** "
        "`full_joint` budgets `K^L*N` floats. At production K=8, N=2000 the guard "
        f"trips near L~6 (`8^6*2000 ~ 5.2e7` vs budget `{MAX_JOINT_FLOATS:.0e}`). "
        'The bakeoff "OOM at L>=6" is that **guard**, not a claim that the store '
        "keeps six lots. Under M1 defaults the store typically has **2-4** live lots.",
        "",
        "### What would push L toward 6-15?",
        "",
        "- **Slower sales** (lower mu) -> lots linger.",
        "- **Larger target stock / bigger orders** (higher S, larger cases) -> more "
        "overlapping deliveries before the first sells out.",
        "- **Stronger LIFO** (smaller sigma) -> old lots stay while new ones sell.",
        "- **Colder store** (slower spoilage) -> old lots die slower, so they remain "
        "as live cohorts longer.",
        "- **Less frequent delivery** (e.g. every 2 days with larger protection "
        "stock) -> each arrival is bigger and more cohorts can coexist if picking "
        "is LIFO-ish.",
        "",
    ]


def fmt_row(r: ScalingRow) -> str:
    tv = "" if r.tv is None else f"{r.tv:.4f}"
    flag = (
        "skip"
        if r.skipped
        else ("oom" if r.oom else ("timeout" if r.timeout else "ok"))
    )
    return (
        f"| {r.backend} | {r.K} | {r.N} | {r.L} | {r.wall_s:.4f} | "
        f"{r.peak_mb:.1f} | {r.floats_proxy:.2e} | {flag} | {tv} |"
    )


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()

    base_params = ModelParams()
    base_L = empirical_L(base_params, run_id="fil13L_base")
    print("Baseline L:", base_L)

    # --- Slow-turn regimes ---
    regimes: list[tuple[str, ModelParams, dict[str, Any]]] = [
        ("baseline mu=30 S=60 sigma=0.5 daily", base_params, {}),
        ("slow sales mu=15", ModelParams(demand_mu=15.0), {}),
        ("fat stock S=120", base_params, {"S": 120}),
        ("strong LIFO sigma=0.2", ModelParams(sigma=0.2), {}),
        ("delivery every 2d (S=90)", base_params, {"S": 90, "delivery_every": 2}),
        (
            "combo mu=15 sigma=0.2 S=120",
            ModelParams(demand_mu=15.0, sigma=0.2),
            {"S": 120},
        ),
    ]
    regime_rows: list[tuple[str, dict[str, float]]] = []
    for name, params, kw in regimes:
        stats = empirical_L(params, run_id=f"reg_{name[:12]}", **kw)
        regime_rows.append((name, stats))
        print(f"Regime {name}: {stats}")

    # Pick highest empirical max L for an optional bakeoff row.
    slow = max(regime_rows, key=lambda x: x[1]["max"])
    slow_L_forced = max(2, int(slow[1]["max"]))

    # --- Microbench matrix ---
    rows: list[ScalingRow] = []
    for be in TIMED_BACKENDS:
        for K in KS:
            for N in NS:
                for L in LS:
                    r = run_cell(be, K=K, N=N, L=L)
                    rows.append(r)
                    if not r.skipped:
                        print(
                            f"{be} K={K} N={N} L={L}: "
                            f"wall={r.wall_s:.4f}s peak={r.peak_mb:.1f}MB "
                            f"oom={r.oom} timeout={r.timeout}"
                        )

    # Sliding window W=2 / W=3: memory table + smoke time at one cell
    # (package SlidingWindowBackend.window is currently unused in the update stub;
    #  we still time the backend and document the *design* memory formula).
    window_note_rows: list[ScalingRow] = []
    for w, label in ((2, "sliding_window_W2"), (3, "sliding_window_W3")):
        for L in (3, 6, 12):
            K, N = 8, 200
            bp = bytes_proxy(label, K=K, N=N, L=L, window=w)
            # Smoke: time default sliding_window once per W label at L=3.
            if L == 3:
                sw_be = SlidingWindowBackend(window=w)
                rng = np.random.default_rng(0)
                tracemalloc.start()
                t0 = time.perf_counter()
                st = sw_be.initialize(N=N, K=K, L=L, params=base_params, rng=rng)
                obs = P1Obs(20, 2, 8)
                for _ in range(N_STEPS):
                    st = sw_be.predict_update(st, obs, base_params, rng)
                wall = time.perf_counter() - t0
                _c, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                window_note_rows.append(
                    ScalingRow(
                        backend=label,
                        K=K,
                        N=N,
                        L=L,
                        wall_s=wall,
                        peak_mb=peak / (1024 * 1024),
                        bytes_proxy=bp,
                        floats_proxy=bp / 8.0,
                        oom=False,
                        timeout=False,
                        skipped=False,
                    )
                )
            else:
                window_note_rows.append(
                    ScalingRow(
                        backend=label,
                        K=K,
                        N=N,
                        L=L,
                        wall_s=0.0,
                        peak_mb=0.0,
                        bytes_proxy=bp,
                        floats_proxy=bp / 8.0,
                        oom=False,
                        timeout=False,
                        skipped=True,
                        skip_reason="memory formula only (window unused in stub)",
                    )
                )

    # --- Effectiveness / TV ---
    tv_exact: list[tuple[str, int, int, float]] = []
    for L in (2, 3, 4):
        for be in ("full_joint", "sliding_window", "mean_field"):
            try:
                tv = tv_vs_exact_extended(L=L, K=4, backend=be)
                tv_exact.append((be, L, 4, tv))
            except MemoryError:
                tv_exact.append((be, L, 4, float("nan")))

    tv_pairs: list[tuple[str, str, int, float]] = []
    for L in (2, 3, 4):
        for a, b in (
            ("sliding_window", "full_joint"),
            ("mean_field", "full_joint"),
        ):
            try:
                tv_pairs.append((a, b, L, posterior_tv_between(a, b, L=L, K=4)))
            except MemoryError:
                tv_pairs.append((a, b, L, float("nan")))

    # Bootstrap note: compare TV-vs-exact is N/A the same way (bootstrap has no
    # age_post update). Instead measure ESS / weight collapse proxy at N in {200,2000}.
    boot_notes: list[str] = []
    for N in (200, 2000, 10000):
        boot_be = get_backend("bootstrap_pf")
        rng = np.random.default_rng(0)
        st = boot_be.initialize(N=N, K=8, L=3, params=base_params, rng=rng)
        obs = P1Obs(20, 2, 8)
        for _ in range(10):
            st = boot_be.predict_update(st, obs, base_params, rng)
        from blueberries_voi.filter.backends import ess

        boot_notes.append(
            f"N={N}: ESS after 10 steps ~ {ess(st.weights):.1f} "
            f"({100 * ess(st.weights) / N:.1f}% of N)"
        )

    # Optional bakeoff-style row at slow empirical L
    slow_bake: list[ScalingRow] = []
    for be in ("full_joint", "sliding_window", "mean_field", "bootstrap_pf"):
        slow_bake.append(run_cell(be, K=8, N=200, L=slow_L_forced))

    # --- Figure: wall vs L at K=8, N=200 ---
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for be in TIMED_BACKENDS:
        xs, ys = [], []
        for L in LS:
            match = [
                r
                for r in rows
                if r.backend == be and r.K == 8 and r.N == 200 and r.L == L
            ]
            if not match:
                continue
            r = match[0]
            xs.append(L)
            if r.skipped or r.oom:
                ys.append(np.nan)
            else:
                ys.append(r.wall_s)
        ax.plot(xs, ys, marker="o", label=be)
    ax.set_xlabel("L (live cohorts, forced)")
    ax.set_ylabel(f"Wall time (s) for {N_STEPS} predict/update steps")
    ax.set_title(
        "FIL-13 scaling runtime (K=8, N=200); "
        f"emp L p50={base_L['p50']:.1f} max={base_L['max']:.0f}"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig_path = FIG / "fil13_scaling.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)

    # --- Markdown write-up ---
    lines: list[str] = [
        "# FIL-13 scaling & effectiveness (Oliver deep-dive)",
        "",
        "Companion to [`fil13_bakeoff.md`](fil13_bakeoff.md) / ADR 0082. "
        "Broader microbench, slow-turn L, grocery interpretation, and "
        "when each backend is appropriate.",
        "",
        *grocery_interpretation_md(base_L),
        "## Part B - Scaling microbench",
        "",
        "### Memory proxies (design formulas x 8 bytes)",
        "",
        "| backend | floats proxy |",
        "| --- | --- |",
        f"| `full_joint` | `K^L * N` (guarded; budget `{MAX_JOINT_FLOATS:.0e}`) |",
        "| `sliding_window` W | `(K^W + max(0,L-W)*K) * N` |",
        "| `mean_field` | `L * K * N` |",
        "| `bound_L` (max_L=4) | `K^{min(L,4)} * N` |",
        "| `bootstrap_pf` | `N * L` (age indices; no grid posterior) |",
        "",
        "**Implementation note:** the current bakeoff stubs store "
        "`age_post` as shape `(N, L, K)` for RBPF-style backends and share "
        "the same per-cohort update. `full_joint`'s distinctive behavior in "
        "this repo is the **`K^L*N` memory guard** (true dense joint tensor "
        "is not materialized). Sliding-window `window` is accepted but not "
        "yet used to change the update. Treat runtime differences among "
        "`full_joint` / `sliding_window` / `mean_field` as small; treat "
        "**memory formulas** as the decision surface for FIL-13.",
        "",
        f"Soft skip if floats proxy > `{MAX_FLOATS_SOFT:.0e}`; "
        f"per-cell timeout ~ `{TIMEOUT_S:.0f}` s; `{N_STEPS}` predict/update steps.",
        "",
        "### Sample rows (K=8, N=200)",
        "",
        "| backend | K | N | L | wall_s | peak_MB | floats_proxy | flag | tv |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for be in TIMED_BACKENDS:
        for L in LS:
            match = [
                r
                for r in rows
                if r.backend == be and r.K == 8 and r.N == 200 and r.L == L
            ]
            if match:
                lines.append(fmt_row(match[0]))

    lines.extend(
        [
            "",
            "### Extra cells (K∈{4,6,8,10}, N∈{200,500,2000}) - condensed",
            "",
            "Full matrix is large; highlights:",
            "",
        ]
    )
    # Highlight OOM / skip / timeout boundaries for full_joint
    lines.append("**`full_joint` feasibility frontier** (first skip/oom per K,N):")
    lines.append("")
    lines.append("| K | N | max L ok | first fail L | reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for K in KS:
        for N in NS:
            ok_L = [
                r.L
                for r in rows
                if r.backend == "full_joint"
                and r.K == K
                and r.N == N
                and not r.skipped
                and not r.oom
                and not r.timeout
            ]
            fail = [
                r
                for r in rows
                if r.backend == "full_joint"
                and r.K == K
                and r.N == N
                and (r.skipped or r.oom or r.timeout)
            ]
            max_ok = max(ok_L) if ok_L else None
            if fail:
                f0 = sorted(fail, key=lambda r: r.L)[0]
                reason = f0.skip_reason or ("oom" if f0.oom else "timeout")
                lines.append(f"| {K} | {N} | {max_ok} | {f0.L} | {reason} |")
            else:
                lines.append(f"| {K} | {N} | {max_ok} | - | all ok |")

    lines.extend(
        [
            "",
            "### Sliding window W=2 vs W=3 (memory formula + smoke time)",
            "",
            "| backend | K | N | L | wall_s | floats_proxy | note |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for r in window_note_rows:
        note = r.skip_reason or "timed"
        lines.append(
            f"| {r.backend} | {r.K} | {r.N} | {r.L} | {r.wall_s:.4f} | "
            f"{r.floats_proxy:.2e} | {note} |"
        )

    lines.extend(
        [
            "",
            "## Slow-turn regimes (empirical L, 20 burn + 90 score)",
            "",
            "| regime | p50 | p90 | max | mean |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for name, stats in regime_rows:
        lines.append(
            f"| {name} | {stats['p50']:.2f} | {stats['p90']:.2f} | "
            f"{stats['max']:.0f} | {stats['mean']:.2f} |"
        )

    lines.extend(
        [
            "",
            f"Highest max L among regimes: **{slow[0]}** -> max={slow[1]['max']:.0f}. "
            f"Optional bakeoff cells at forced L={slow_L_forced}, K=8, N=200:",
            "",
            "| backend | wall_s | floats_proxy | flag |",
            "| --- | --- | --- | --- |",
        ]
    )
    for r in slow_bake:
        flag = (
            "skip"
            if r.skipped
            else ("oom" if r.oom else ("timeout" if r.timeout else "ok"))
        )
        lines.append(
            f"| {r.backend} | {r.wall_s:.4f} | {r.floats_proxy:.2e} | {flag} |"
        )

    lines.extend(
        [
            "",
            "## Effectiveness / appropriateness",
            "",
            "### Accuracy: TV vs exact one-step update (K=4)",
            "",
            "| backend | L | K | TV |",
            "| --- | --- | --- | --- |",
        ]
    )
    for be, L, K, tv in tv_exact:
        lines.append(f"| {be} | {L} | {K} | {tv:.6f} |")

    lines.extend(
        [
            "",
            "### Approximation error: posterior TV between backends (K=4)",
            "",
            "| A | B | L | TV(A,B) |",
            "| --- | --- | --- | --- |",
        ]
    )
    for a, b, L, tv in tv_pairs:
        lines.append(f"| {a} | {b} | {L} | {tv:.6f} |")

    lines.extend(
        [
            "",
            "Near-zero TV among `full_joint` / `sliding_window` / `mean_field` "
            "is expected with the current shared factorized update stub.",
            "",
            "### Bootstrap PF",
            "",
            "Theory: putting age in the particle (no Rao-Blackwell grid) needs "
            "**much larger N** to match marginal age accuracy of an RBPF - "
            "variance scales like sampling a discrete age per cohort without "
            "marginalising. Quick ESS smoke (same toy obs):",
            "",
        ]
    )
    for note in boot_notes:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "### Decision table - when is each OK?",
            "",
            "| Backend | Use when | Avoid when |",
            "| --- | --- | --- |",
            "| **full_joint (E)** | Empirical L small (<=3-4 at K=8, N~2e3); "
            "want exact joint budget semantics + production lock | "
            "`K^L*N` near/over `5e7` (guard); policy regimes that raise L |",
            "| **sliding_window (A)** | L grows; coupling strongest among "
            "youngest W lots; need fallback without full `K^L` | "
            "Need proven joint accuracy on long LIFO tails (implement W "
            "semantics first) |",
            "| **mean_field (B)** | Diagnostics / speed; dependence weak | "
            "Allocation coupling matters and you need joint fidelity |",
            "| **bound_L (C)** | Stress tests with capped state | "
            "Production sim (silently wrong if true L > cap) |",
            "| **bootstrap_pf (D)** | Ablation / bakeoff arm | "
            "Production age posterior at modest N |",
            "",
            "## Recommendation (Oliver)",
            "",
            "1. **Store reality under M1 defaults:** L~2-3. The "
            '"ceiling of 6" is **filter memory**, not how many lots the '
            "grocery shelf carries.",
            "2. **Keep `full_joint` for production** while measured L stays <=3-4 "
            "at K=8 / N=2000.",
            "3. **Switch to sliding_window (or reopen FIL-13)** if a controller / "
            "cadence / LIFO regime pushes empirical L so the joint guard trips.",
            "4. Slow-turn knobs (mu↓, S↑, sigma↓, less frequent delivery) can raise L; "
            "re-check empirical L before trusting the memory budget.",
            "",
            f"*Generated in {time.perf_counter() - t_all:.1f}s. "
            f"Figure: `{fig_path.relative_to(ROOT)}`.*",
            "",
        ]
    )

    out = EXP / "fil13_scaling.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", out)
    print("Wrote", fig_path)

    # Pointer from bakeoff md
    bake = EXP / "fil13_bakeoff.md"
    if bake.exists():
        text = bake.read_text(encoding="utf-8")
        pointer = (
            "\n## See also\n\n"
            "Broader K/N/L microbench, slow-turn L regimes, grocery "
            "interpretation, and backend effectiveness notes: "
            "[`fil13_scaling.md`](fil13_scaling.md) "
            "(`figures/m1/fil13_scaling.png`).\n"
        )
        if "fil13_scaling.md" not in text:
            bake.write_text(text.rstrip() + "\n" + pointer, encoding="utf-8")
            print("Updated", bake)


if __name__ == "__main__":
    main()
