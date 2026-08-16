//! C2 filter-algorithm timing study (A–E) vs current baseline.
//!
//! Complexity guards (avoid exponential paths):
//!   - exact LL / MF: L ≤ 4, per-lot count ≤ 4  → WOR states ≤ 5^4 = 625
//!   - C2-A truth: O(N × units × sales) picking-kernel path (no unit-WOR enum)
//!   - C2-B histogram: O(N × L × K²) convolution
//!   - C2-D: production filter at L=2; unit truth swept separately
//!
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_algorithms -- --calibrate
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_algorithms -- \
//!     --output outputs/c2_algorithm_timing.json

use std::collections::HashMap;
use std::env;
use std::fs;
use std::time::Instant;

use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma};
use rand_pcg::Pcg64;
use serde::Serialize;
use voi_core::exact_ll::log_p_sales_waste_given_ages;
use voi_core::{
    day_step, filter_step, mask_for, picking_weights, DayStepIn, EngineSession, ModelParams,
    ParticleBank, RichDay, ShipmentTrace,
};

const SEED: u64 = 42;
const ORDER_QTY: u32 = 16;
const WARM_DAYS: usize = 7;
const MF_MAX_SWEEPS: usize = 5;
const MF_TV_STOP: f64 = 1e-4;
const DEFAULT_H: u32 = 7;
const DEFAULT_PATHS: u32 = 2;
const DEFAULT_RADIUS: i32 = 1;
const FILTER_L: usize = 2;
const FILTER_K: usize = 4;
const LL_COUNT_PER_LOT: u32 = 4;
const MAX_WOR_STATES: usize = 10_000;

const FULL_OUTER_RUNS: usize = 3;
const FULL_INNER_REPS: usize = 20;
const FULL_INNER_WARMUP: usize = 5;

const FULL_N: [usize; 4] = [64, 100, 200, 400];
const FULL_K: [usize; 4] = [4, 8, 16, 32];
/// Polynomial unit physics — safe to sweep to 8.
const FULL_L_UNITS: [usize; 3] = [2, 4, 8];
const FULL_UNITS_PER_LOT: [usize; 3] = [10, 20, 30];
/// Exact-LL / MF paths — keep L small (WOR is ∏(n_l+1)).
const FULL_L_LL: [usize; 2] = [2, 4];

const CAL_OUTER_RUNS: usize = 1;
const CAL_INNER_REPS: usize = 5;
const CAL_INNER_WARMUP: usize = 2;

#[derive(Clone, Copy)]
struct BenchCfg {
    outer_runs: usize,
    inner_reps: usize,
    inner_warmup: usize,
}

#[derive(Clone, Debug, Serialize)]
struct TimingRow {
    algorithm: &'static str,
    n_particles: usize,
    k_dim: usize,
    n_lots: usize,
    units_per_lot: usize,
    units_total: usize,
    mean_ms: f64,
    run_ms: Vec<f64>,
    outer_runs: usize,
    inner_reps: usize,
}

#[derive(Clone, Debug, Serialize)]
struct CalProbe {
    algorithm: &'static str,
    label: String,
    mean_ms: f64,
    n_particles: usize,
    k_dim: usize,
    n_lots: usize,
    units_per_lot: usize,
}

#[derive(Clone, Debug, Serialize)]
struct StudyReport {
    mode: &'static str,
    meta: StudyMeta,
    rows: Vec<TimingRow>,
    calibration: Vec<CalProbe>,
    wall_seconds: f64,
}

#[derive(Clone, Debug, Serialize)]
struct StudyMeta {
    target_ms: f64,
    outer_runs: usize,
    inner_reps: usize,
    inner_warmup: usize,
    mf_max_sweeps: usize,
    cell_count: usize,
    estimated_full_wall_s: Option<f64>,
    algorithms: Vec<&'static str>,
    disclaimer: &'static str,
    omp_threads: String,
    complexity_notes: Vec<&'static str>,
}

fn time_cell<F: FnMut()>(cfg: BenchCfg, mut f: F) -> (f64, Vec<f64>) {
    let mut run_ms = Vec::with_capacity(cfg.outer_runs);
    for _ in 0..cfg.outer_runs {
        for _ in 0..cfg.inner_warmup {
            f();
        }
        let mut acc = 0.0;
        for _ in 0..cfg.inner_reps {
            let t0 = Instant::now();
            f();
            acc += t0.elapsed().as_secs_f64() * 1000.0;
        }
        run_ms.push(acc / cfg.inner_reps as f64);
    }
    let mean = run_ms.iter().sum::<f64>() / cfg.outer_runs as f64;
    (mean, run_ms)
}

fn smoke_shipment() -> ShipmentTrace {
    ShipmentTrace {
        times_d: vec![0.0, 1.0, 2.0],
        temps_c: vec![1.0, 1.0, 1.0],
    }
}

fn configured_session(n_particles: usize, k_dim: usize, l: usize) -> EngineSession {
    let mut s = EngineSession::new(SEED);
    s.init(SEED);
    s.set_belief_dims(l, k_dim);
    s.configure(
        1,
        true,
        DEFAULT_H,
        DEFAULT_PATHS,
        DEFAULT_RADIUS,
        vec![smoke_shipment()],
        n_particles,
        None,
        None,
    );
    let _ = s.set_obs_scenario("P1");
    s
}

fn warm_session(s: &mut EngineSession) {
    for _ in 0..WARM_DAYS {
        s.step(ORDER_QTY);
    }
}

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

fn tau_grid(k: usize) -> Vec<f64> {
    (0..k).map(|i| 0.5 + i as f64 * 0.75).collect()
}

fn lot_counts(l: usize, units_per_lot: usize) -> Vec<u32> {
    vec![units_per_lot as u32; l]
}

fn ll_lot_counts(l: usize) -> Vec<u32> {
    assert!(l <= 4, "exact LL capped at L=4");
    vec![LL_COUNT_PER_LOT; l]
}

fn wor_state_product(counts: &[u32]) -> usize {
    counts
        .iter()
        .fold(1usize, |acc, &c| acc.saturating_mul((c as usize) + 1))
}

fn assert_ll_tractable(counts: &[u32]) {
    let states = wor_state_product(counts);
    assert!(
        states <= MAX_WOR_STATES,
        "WOR state space {states} exceeds cap {MAX_WOR_STATES}"
    );
}

fn bench_obs_units(l: usize, units_per_lot: usize) -> (voi_core::FilterObs, ModelParams) {
    let params = ModelParams::default();
    let n_lots = lot_counts(l, units_per_lot);
    let on_hand: i32 = n_lots.iter().map(|&x| x as i32).sum();
    let sales = (on_hand / 4).max(1);
    let waste = 1;
    let state = DayStepIn {
        counts: n_lots.clone(),
        taus: vec![1.5; l],
        lot_ids: (1..=l as i64).collect(),
        demand: Some((on_hand as u32).saturating_sub(sales as u32 + waste as u32)),
        spoil_by: None,
        delivery_n: 0,
        delivery_tau: 0.0,
        delivery_lot_id: 0,
    };
    let mut rng_a = stream_rng(SEED, 7, 2);
    let mut rng_s = stream_rng(SEED, 7, 3);
    let out = day_step(&state, &params, Some(&mut rng_a), Some(&mut rng_s));
    let rich = RichDay {
        sales_total: out.sales_total,
        waste_total: out.waste_total,
        arrivals: 0,
        sales_by: out.sales_by,
        waste_by: out.waste_by,
        lot_ids: out.lot_ids,
        age_at_receipt: None,
        pack_date_days: None,
    };
    (mask_for("P1").unwrap().apply(&rich), params)
}

fn bench_obs_ll(l: usize) -> (voi_core::FilterObs, ModelParams) {
    bench_obs_units(l, LL_COUNT_PER_LOT as usize)
}

fn warm_bank(n_particles: usize) -> (ParticleBank, voi_core::FilterObs, ModelParams, u32) {
    let mut hold = configured_session(n_particles, FILTER_K, FILTER_L);
    warm_session(&mut hold);
    let day = hold.episode_day();
    let bank = ParticleBank {
        weights: hold.bank_weights(),
        counts: vec![vec![LL_COUNT_PER_LOT; FILTER_L]; n_particles],
        taus: vec![vec![1.2f64; FILTER_L]; n_particles],
    };
    let (obs, params) = bench_obs_ll(FILTER_L);
    (bank, obs, params, day)
}

fn push_row(
    rows: &mut Vec<TimingRow>,
    algorithm: &'static str,
    n: usize,
    k: usize,
    l: usize,
    upl: usize,
    mean_ms: f64,
    run_ms: Vec<f64>,
    cfg: BenchCfg,
) {
    rows.push(TimingRow {
        algorithm,
        n_particles: n,
        k_dim: k,
        n_lots: l,
        units_per_lot: upl,
        units_total: if upl > 0 { l * upl } else { 0 },
        mean_ms,
        run_ms,
        outer_runs: cfg.outer_runs,
        inner_reps: cfg.inner_reps,
    });
}

fn bench_baseline(cfg: BenchCfg, n: usize, k: usize) -> (f64, Vec<f64>) {
    time_cell(cfg, || {
        let mut s = configured_session(n, k, FILTER_L);
        warm_session(&mut s);
        s.step(ORDER_QTY);
    })
}

fn unit_f_to_tau(f: f64, eta: f64) -> f64 {
    (1.0 - f).max(0.0) * eta
}

/// Kernel-weighted sequential picking along one path — O(sales × units).
fn sequential_kernel_path_logprob(
    freshness: &[f64],
    sales: usize,
    params: &ModelParams,
    rng: &mut Pcg64,
) -> f64 {
    let taus: Vec<f64> = freshness
        .iter()
        .map(|&f| unit_f_to_tau(f, params.eta_ref))
        .collect();
    let base_w = picking_weights(
        &taus,
        params.sigma,
        params.beta,
        params.eta_ref,
        params.uniform_picking,
    );
    let mut alive = vec![true; freshness.len()];
    let mut log_p = 0.0;
    for _ in 0..sales {
        let mut tot = 0.0;
        for i in 0..freshness.len() {
            if alive[i] {
                tot += base_w[i];
            }
        }
        if tot <= 0.0 {
            return f64::NEG_INFINITY;
        }
        let draw = rng.random::<f64>() * tot;
        let mut acc = 0.0;
        let mut picked = 0usize;
        for i in 0..freshness.len() {
            if !alive[i] {
                continue;
            }
            acc += base_w[i];
            if draw < acc {
                picked = i;
                break;
            }
        }
        log_p += (base_w[picked] / tot).ln();
        alive[picked] = false;
    }
    log_p
}

fn binom_pmf(k: i32, n: i32, p: f64) -> f64 {
    if k < 0 || k > n || n < 0 {
        return 0.0;
    }
    let mut coef = 1.0;
    for i in 0..k {
        coef *= (n - i) as f64 / (i + 1) as f64;
    }
    coef * p.powi(k) * (1.0 - p).powi(n - k)
}

fn bench_c2_a(cfg: BenchCfg, n: usize, l: usize, upl: usize) -> (f64, Vec<f64>) {
    let units = l * upl;
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    let (obs, params) = bench_obs_units(l, upl);
    let sales = obs.sales_tot.unwrap_or(2).max(0) as usize;
    let waste = obs.waste_tot.unwrap_or(1);
    time_cell(cfg, || {
        let mut rng = Pcg64::seed_from_u64(SEED);
        let mut freshness: Vec<Vec<f64>> = (0..n)
            .map(|_| {
                (0..units)
                    .map(|_| 0.4 + rng.random::<f64>() * 0.55)
                    .collect()
            })
            .collect();
        let mut log_w = vec![0.0f64; n];
        for p in 0..n {
            for f in &mut freshness[p] {
                *f -= gamma.sample(&mut rng);
                if *f <= 0.0 {
                    *f = 0.0;
                }
            }
            let alive = freshness[p].iter().filter(|&&f| f > 0.0).count();
            if alive < sales {
                log_w[p] = -1e300;
                continue;
            }
            let ll_sales =
                sequential_kernel_path_logprob(&freshness[p], sales, &params, &mut rng);
            let dead = freshness[p].iter().filter(|&&f| f <= 0.0).count() as i32;
            let rem = alive as i32 - sales as i32;
            let p_die = (dead as f64 / units as f64).clamp(0.0, 1.0);
            let pw = binom_pmf(waste, rem, p_die);
            log_w[p] = if pw > 0.0 && ll_sales.is_finite() {
                ll_sales + pw.ln()
            } else {
                -1e300
            };
        }
        let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - mx).exp()).collect();
        let z: f64 = w.iter().sum();
        if z > 0.0 {
            for x in &mut w {
                *x /= z;
            }
        }
        let mut cdf = 0.0;
        for i in 0..n {
            cdf += w[i];
            if cdf >= 0.5 {
                freshness[0] = freshness[i].clone();
                break;
            }
        }
    })
}

fn bench_c2_b(cfg: BenchCfg, n: usize, l: usize, k: usize) -> (f64, Vec<f64>) {
    let grid = tau_grid(k);
    let (obs, params) = bench_obs_ll(l);
    let sales = obs.sales_tot.unwrap_or(2);
    let waste = obs.waste_tot.unwrap_or(1);
    let n_lots = ll_lot_counts(l);
    assert_ll_tractable(&n_lots);
    time_cell(cfg, || {
        let mut hists: Vec<Vec<Vec<f64>>> = (0..n)
            .map(|_| (0..l).map(|_| vec![0.0; k]).collect())
            .collect();
        for p in 0..n {
            for ell in 0..l {
                hists[p][ell][k / 2] = 1.0;
            }
        }
        let kernel = vec![1.0f64 / k as f64; k];
        let mut log_w = vec![0.0f64; n];
        for p in 0..n {
            for ell in 0..l {
                let mut next = vec![0.0f64; k];
                for i in 0..k {
                    for j in 0..k {
                        let dst = i + j;
                        if dst < k {
                            next[dst] += hists[p][ell][i] * kernel[j];
                        }
                    }
                }
                let s: f64 = next.iter().sum();
                if s > 0.0 {
                    for x in &mut next {
                        *x /= s;
                    }
                }
                hists[p][ell] = next;
            }
            let taus: Vec<f64> = hists[p]
                .iter()
                .map(|h| h.iter().zip(grid.iter()).map(|(p, &t)| p * t).sum())
                .collect();
            let ll = log_p_sales_waste_given_ages(&n_lots, &taus, sales, waste, &params);
            log_w[p] = if ll.is_finite() { ll } else { -1e300 };
        }
        let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let _: f64 = log_w.iter().map(|lw| (lw - mx).exp()).sum::<f64>();
    })
}

fn marginal_tv(a: &[f64], b: &[f64]) -> f64 {
    0.5 * a.iter().zip(b).map(|(x, y)| (x - y).abs()).sum::<f64>()
}

fn mean_field_step(
    n_lots: &[u32],
    q: &mut [Vec<f64>],
    tau_grid: &[f64],
    sales: i32,
    waste: i32,
    params: &ModelParams,
) {
    let l = n_lots.len();
    let k = tau_grid.len();
    for _ in 0..MF_MAX_SWEEPS {
        let q_old: Vec<Vec<f64>> = q.to_vec();
        for ell in 0..l {
            let mut mean_tau = vec![0.0f64; l];
            for j in 0..l {
                if j != ell {
                    mean_tau[j] = q[j]
                        .iter()
                        .zip(tau_grid.iter())
                        .map(|(&p, &t)| p * t)
                        .sum();
                }
            }
            let mut log_unnorm = vec![f64::NEG_INFINITY; k];
            for ki in 0..k {
                let p0 = q[ell][ki];
                if p0 <= 0.0 {
                    continue;
                }
                let mut tau = mean_tau.clone();
                tau[ell] = tau_grid[ki];
                let ll = log_p_sales_waste_given_ages(n_lots, &tau, sales, waste, params);
                if ll.is_finite() {
                    log_unnorm[ki] = p0.ln() + ll;
                }
            }
            let m = log_unnorm.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            if !m.is_finite() {
                q[ell].fill(1.0 / k as f64);
            } else {
                let mut w: Vec<f64> = log_unnorm.iter().map(|&x| (x - m).exp()).collect();
                let s: f64 = w.iter().sum();
                for x in &mut w {
                    *x /= s.max(1e-300);
                }
                q[ell] = w;
            }
        }
        let max_change = (0..l)
            .map(|ell| marginal_tv(&q[ell], &q_old[ell]))
            .fold(0.0f64, f64::max);
        if max_change < MF_TV_STOP {
            break;
        }
    }
}

fn bench_c2_c(cfg: BenchCfg, l: usize, k: usize) -> (f64, Vec<f64>) {
    let grid = tau_grid(k);
    let (obs, params) = bench_obs_ll(l);
    let sales = obs.sales_tot.unwrap_or(2);
    let waste = obs.waste_tot.unwrap_or(1);
    let n_lots = ll_lot_counts(l);
    assert_ll_tractable(&n_lots);
    time_cell(cfg, || {
        let mut q: Vec<Vec<f64>> = (0..l)
            .map(|_| vec![1.0 / k as f64; k])
            .collect();
        mean_field_step(&n_lots, &mut q, &grid, sales, waste, &params);
    })
}

/// C2-D: production filter (L=2) + unit-level truth sim — filter L fixed, sweep units.
fn bench_c2_d(cfg: BenchCfg, n: usize, upl: usize) -> (f64, Vec<f64>) {
    let units = FILTER_L * upl;
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    let (bank, obs, params, day) = warm_bank(n);
    time_cell(cfg, || {
        let mut fr = stream_rng(SEED, day, 6);
        let _ = filter_step(&bank, &obs, &params, &mut fr);
        let mut rng = Pcg64::seed_from_u64(SEED);
        let mut f: Vec<f64> = (0..units)
            .map(|_| 0.4 + rng.random::<f64>() * 0.55)
            .collect();
        for x in &mut f {
            *x -= gamma.sample(&mut rng);
            if *x <= 0.0 {
                *x = 0.0;
            }
        }
        let _ = f.iter().filter(|&&x| x > 0.0).count();
    })
}

fn bench_c2_e(cfg: BenchCfg, n: usize, l: usize) -> (f64, Vec<f64>) {
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    let (obs, params) = bench_obs_ll(l);
    let sales = obs.sales_tot.unwrap_or(2);
    let waste = obs.waste_tot.unwrap_or(1);
    let n_lots = ll_lot_counts(l);
    assert_ll_tractable(&n_lots);
    time_cell(cfg, || {
        let mut rng = Pcg64::seed_from_u64(SEED);
        let mut f_l = vec![0.0f64; l];
        let mut theta = vec![0.0f64; l];
        let mut log_w = vec![0.0f64; n];
        for p in 0..n {
            for ell in 0..l {
                f_l[ell] = 0.5 + rng.random::<f64>() * 0.45;
                theta[ell] = 0.8 + rng.random::<f64>() * 0.4;
                f_l[ell] -= gamma.sample(&mut rng);
                if f_l[ell] <= 0.0 {
                    f_l[ell] = 0.0;
                }
            }
            let taus: Vec<f64> = f_l
                .iter()
                .zip(theta.iter())
                .map(|(&f, &th)| (1.0 - f) * 5.0 * th)
                .collect();
            let ll = log_p_sales_waste_given_ages(&n_lots, &taus, sales, waste, &params);
            log_w[p] = if ll.is_finite() { ll } else { -1e300 };
            let _ = p;
        }
        let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let _: f64 = log_w.iter().map(|lw| (lw - mx).exp()).sum::<f64>();
    })
}

fn meta_notes() -> Vec<&'static str> {
    vec![
        "Exact LL / MF: L≤4, n_l≤4 → WOR states ≤5^4=625",
        "C2-A: picking_weights kernel path O(N×units×sales); no unit-WOR enum",
        "C2-B: histogram conv O(N×L×K²) + tractable lot-level LL",
        "C2-D: filter fixed L=2; truth units swept via units/lot",
        "C2-C: single MF state (N-independent); sweeps×L×K×LL",
    ]
}

fn full_cell_count() -> usize {
    FULL_N.len() * FULL_K.len()
        + FULL_N.len() * FULL_L_UNITS.len() * FULL_UNITS_PER_LOT.len()
        + FULL_N.len() * FULL_L_LL.len() * FULL_K.len()
        + FULL_L_LL.len() * FULL_K.len()
        + FULL_N.len() * FULL_UNITS_PER_LOT.len()
        + FULL_N.len() * FULL_L_LL.len()
}

fn run_calibration() -> StudyReport {
    let t0 = Instant::now();
    let cfg = BenchCfg {
        outer_runs: CAL_OUTER_RUNS,
        inner_reps: CAL_INNER_REPS,
        inner_warmup: CAL_INNER_WARMUP,
    };
    let probes: Vec<(&str, String, usize, usize, usize, usize)> = vec![
        ("baseline", "N=64,K=4".into(), 64, 4, FILTER_L, 0),
        ("baseline", "N=400,K=32".into(), 400, 32, FILTER_L, 0),
        ("c2_a", "N=64,L=2,u=10".into(), 64, 0, 2, 10),
        ("c2_a", "N=400,L=8,u=30".into(), 400, 0, 8, 30),
        ("c2_b", "N=64,L=2,K=4".into(), 64, 4, 2, 0),
        ("c2_b", "N=400,L=4,K=32".into(), 400, 32, 4, 0),
        ("c2_c", "L=2,K=4".into(), 0, 4, 2, 0),
        ("c2_c", "L=4,K=32".into(), 0, 32, 4, 0),
        ("c2_d", "N=64,u=10".into(), 64, 0, FILTER_L, 10),
        ("c2_d", "N=400,u=30".into(), 400, 0, FILTER_L, 30),
        ("c2_e", "N=64,L=2".into(), 64, 0, 2, 0),
        ("c2_e", "N=400,L=4".into(), 400, 0, 4, 0),
    ];

    let mut calibration = Vec::new();
    let mut by_algo: HashMap<&str, Vec<f64>> = HashMap::new();

    for (algo, label, n, k, l, upl) in probes {
        eprint!("calibrate {algo} {label} … ");
        let (mean, _) = match algo {
            "baseline" => bench_baseline(cfg, n, k),
            "c2_a" => bench_c2_a(cfg, n, l, upl),
            "c2_b" => bench_c2_b(cfg, n, l, k),
            "c2_c" => bench_c2_c(cfg, l, k),
            "c2_d" => bench_c2_d(cfg, n, upl),
            "c2_e" => bench_c2_e(cfg, n, l),
            _ => (0.0, vec![]),
        };
        eprintln!("{mean:.3} ms");
        calibration.push(CalProbe {
            algorithm: algo,
            label,
            mean_ms: mean,
            n_particles: n,
            k_dim: k,
            n_lots: l,
            units_per_lot: upl,
        });
        by_algo.entry(algo).or_default().push(mean);
    }

    let full_cfg = BenchCfg {
        outer_runs: FULL_OUTER_RUNS,
        inner_reps: FULL_INNER_REPS,
        inner_warmup: FULL_INNER_WARMUP,
    };
    let cells = full_cell_count();
    let scale = (full_cfg.outer_runs * full_cfg.inner_reps) as f64
        / (cfg.outer_runs * cfg.inner_reps) as f64;
    let est = by_algo
        .values()
        .map(|v| v.iter().sum::<f64>() / v.len() as f64)
        .sum::<f64>()
        / by_algo.len() as f64
        * cells as f64
        * scale;

    eprintln!();
    eprintln!("=== calibration summary ===");
    eprintln!("full grid cells: {cells}");
    eprintln!(
        "full study: {} outer × {} inner reps",
        full_cfg.outer_runs, full_cfg.inner_reps
    );
    eprintln!("estimated full wall time: {est:.0}s ({:.1} min)", est / 60.0);

    StudyReport {
        mode: "calibrate",
        meta: StudyMeta {
            target_ms: 500.0,
            outer_runs: CAL_OUTER_RUNS,
            inner_reps: CAL_INNER_REPS,
            inner_warmup: CAL_INNER_WARMUP,
            mf_max_sweeps: MF_MAX_SWEEPS,
            cell_count: cells,
            estimated_full_wall_s: Some(est),
            algorithms: vec!["baseline", "c2_a", "c2_b", "c2_c", "c2_d", "c2_e"],
            disclaimer: "Calibration probes only",
            omp_threads: env::var("OMP_NUM_THREADS").unwrap_or_else(|_| "?".into()),
            complexity_notes: meta_notes(),
        },
        rows: Vec::new(),
        calibration,
        wall_seconds: t0.elapsed().as_secs_f64(),
    }
}

fn run_full_study() -> StudyReport {
    let t0 = Instant::now();
    let cfg = BenchCfg {
        outer_runs: FULL_OUTER_RUNS,
        inner_reps: FULL_INNER_REPS,
        inner_warmup: FULL_INNER_WARMUP,
    };
    let mut rows = Vec::new();

    eprintln!("baseline N×K (L={FILTER_L}) …");
    for &n in &FULL_N {
        for &k in &FULL_K {
            let (mean, runs) = bench_baseline(cfg, n, k);
            push_row(&mut rows, "baseline", n, k, FILTER_L, 0, mean, runs, cfg);
            eprintln!("  N={n} K={k} → {mean:.3} ms");
        }
    }

    eprintln!("c2_a N×L×units …");
    for &n in &FULL_N {
        for &l in &FULL_L_UNITS {
            for &upl in &FULL_UNITS_PER_LOT {
                let (mean, runs) = bench_c2_a(cfg, n, l, upl);
                push_row(&mut rows, "c2_a", n, 0, l, upl, mean, runs, cfg);
            }
        }
    }

    eprintln!("c2_b N×L×K (L≤4) …");
    for &n in &FULL_N {
        for &l in &FULL_L_LL {
            for &k in &FULL_K {
                let (mean, runs) = bench_c2_b(cfg, n, l, k);
                push_row(&mut rows, "c2_b", n, k, l, 0, mean, runs, cfg);
            }
        }
    }

    eprintln!("c2_c L×K (L≤4) …");
    for &l in &FULL_L_LL {
        for &k in &FULL_K {
            let (mean, runs) = bench_c2_c(cfg, l, k);
            push_row(&mut rows, "c2_c", 0, k, l, 0, mean, runs, cfg);
        }
    }

    eprintln!("c2_d N×units (filter L={FILTER_L}) …");
    for &n in &FULL_N {
        for &upl in &FULL_UNITS_PER_LOT {
            let (mean, runs) = bench_c2_d(cfg, n, upl);
            push_row(&mut rows, "c2_d", n, FILTER_K, FILTER_L, upl, mean, runs, cfg);
        }
    }

    eprintln!("c2_e N×L (L≤4) …");
    for &n in &FULL_N {
        for &l in &FULL_L_LL {
            let (mean, runs) = bench_c2_e(cfg, n, l);
            push_row(&mut rows, "c2_e", n, 0, l, 0, mean, runs, cfg);
        }
    }

    StudyReport {
        mode: "full",
        meta: StudyMeta {
            target_ms: 500.0,
            outer_runs: FULL_OUTER_RUNS,
            inner_reps: FULL_INNER_REPS,
            inner_warmup: FULL_INNER_WARMUP,
            mf_max_sweeps: MF_MAX_SWEEPS,
            cell_count: rows.len(),
            estimated_full_wall_s: None,
            algorithms: vec!["baseline", "c2_a", "c2_b", "c2_c", "c2_d", "c2_e"],
            disclaimer: "Kernel microbenches for C2 inference families; not production code paths",
            omp_threads: env::var("OMP_NUM_THREADS").unwrap_or_else(|_| "?".into()),
            complexity_notes: meta_notes(),
        },
        rows,
        calibration: Vec::new(),
        wall_seconds: t0.elapsed().as_secs_f64(),
    }
}

fn main() {
    let calibrate = env::args().any(|a| a == "--calibrate");
    let report = if calibrate {
        eprintln!("bench_c2_algorithms: CALIBRATION mode");
        run_calibration()
    } else {
        eprintln!(
            "bench_c2_algorithms: FULL study ({} outer × {} inner, {} cells)",
            FULL_OUTER_RUNS,
            FULL_INNER_REPS,
            full_cell_count()
        );
        run_full_study()
    };
    eprintln!("wall time: {:.1}s", report.wall_seconds);

    let json = serde_json::to_string_pretty(&report).expect("json");
    let args: Vec<String> = env::args().collect();
    if let Some(i) = args.iter().position(|a| a == "--output") {
        let path = args.get(i + 1).expect("--output requires a path");
        fs::write(path, &json).expect("write output");
        eprintln!("wrote {path}");
    }
}
