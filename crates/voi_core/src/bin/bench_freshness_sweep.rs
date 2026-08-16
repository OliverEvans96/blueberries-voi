//! Parameter sweep: current EngineSession paths + C1/C2/C3 freshness proxies.
//!
//! C1/C2/C3 are **not** implemented in production; proxies measure incremental
//! kernel cost on top of measured `filter_step` / `day_step` / `rollout_order`.
//!
//! Run: `OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_freshness_sweep`
//! Optional: `--output /path/to/freshness_timing_sweep.json`

use std::env;
use std::fs;
use std::time::Instant;

use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma};
use rand_pcg::Pcg64;
use serde::Serialize;
use voi_core::belief_flat::belief_mean_from_bank;
use voi_core::{
    day_step, filter_step, mask_for, rollout_order, DayStepIn, EngineSession, ModelParams,
    ParticleBank, RichDay, ShipmentTrace,
};

const SEED: u64 = 42;
const ORDER_QTY: u32 = 16;
const WARM_DAYS: usize = 7;
const E2E_REPS: usize = 80;
const E2E_WARMUP: usize = 15;
const MICRO_REPS: usize = 120;
const MICRO_WARMUP: usize = 20;
const DEFAULT_L: usize = 2;
const DEFAULT_K: usize = 4;
const DEFAULT_H: u32 = 7;
const DEFAULT_PATHS: u32 = 2;
const DEFAULT_RADIUS: i32 = 1;

#[derive(Clone, Debug, Serialize)]
struct Stats {
    mean_ms: f64,
    p50_ms: f64,
    p95_ms: f64,
    n: usize,
}

#[derive(Clone, Debug, Serialize)]
struct E2eRow {
    scenario: &'static str,
    path: &'static str,
    n_particles: usize,
    k_dim: usize,
    h: u32,
    n_paths: u32,
    radius: i32,
    stats: Stats,
}

#[derive(Clone, Debug, Serialize)]
struct ProxyRow {
    model: &'static str,
    n_particles: usize,
    n_lots: usize,
    k_bins: usize,
    units_total: usize,
    filter_only_ms: Stats,
    proxy_only_ms: Stats,
    combined_ms: Stats,
}

#[derive(Clone, Debug, Serialize)]
struct RolloutRow {
    n_particles: usize,
    h: u32,
    n_paths: u32,
    radius: i32,
    stats: Stats,
}

#[derive(Clone, Debug, Serialize)]
struct SweepReport {
    meta: Meta,
    current_e2e: Vec<E2eRow>,
    rollout_sweep: Vec<RolloutRow>,
    freshness_proxies: Vec<ProxyRow>,
}

#[derive(Clone, Debug, Serialize)]
struct Meta {
    sha_note: &'static str,
    omp_threads: String,
    e2e_reps: usize,
    micro_reps: usize,
    warm_days: usize,
    target_ms: f64,
    disclaimer: &'static str,
}

fn stats_from_samples(mut xs: Vec<f64>) -> Stats {
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = xs.len();
    let mean = xs.iter().sum::<f64>() / n as f64;
    Stats {
        mean_ms: mean,
        p50_ms: xs[n / 2],
        p95_ms: xs[(0.95 * (n - 1) as f64).round() as usize],
        n,
    }
}

fn time_micro<F: FnMut()>(mut f: F) -> Stats {
    let total = MICRO_REPS + MICRO_WARMUP;
    let mut xs = Vec::with_capacity(total);
    for _ in 0..total {
        let t0 = Instant::now();
        f();
        xs.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    stats_from_samples(xs[MICRO_WARMUP..].to_vec())
}

fn smoke_shipment() -> ShipmentTrace {
    ShipmentTrace {
        times_d: vec![0.0, 1.0, 2.0],
        temps_c: vec![1.0, 1.0, 1.0],
    }
}

fn configured_session(
    n_particles: usize,
    k_dim: usize,
    h: u32,
    n_paths: u32,
    radius: i32,
) -> EngineSession {
    let mut s = EngineSession::new(SEED);
    s.init(SEED);
    s.set_belief_dims(DEFAULT_L, k_dim);
    s.configure(
        1,
        true,
        h,
        n_paths,
        radius,
        vec![smoke_shipment()],
        n_particles,
        None,
    );
    let _ = s.set_obs_scenario("P1");
    s
}

fn warm(s: &mut EngineSession) {
    for _ in 0..WARM_DAYS {
        s.step(ORDER_QTY);
    }
}

fn time_e2e<F: FnMut(&mut EngineSession)>(mut op: F, mk: impl Fn() -> EngineSession) -> Stats {
    let total = E2E_REPS + E2E_WARMUP;
    let mut xs = Vec::with_capacity(total);
    for _ in 0..total {
        let mut s = mk();
        warm(&mut s);
        let t0 = Instant::now();
        op(&mut s);
        xs.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    stats_from_samples(xs[E2E_WARMUP..].to_vec())
}

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

fn warm_bank(n_particles: usize) -> (ParticleBank, RichDay, ModelParams, u32) {
    let mut hold = configured_session(n_particles, DEFAULT_K, DEFAULT_H, DEFAULT_PATHS, DEFAULT_RADIUS);
    warm(&mut hold);
    let day = hold.episode_day();
    let bank = ParticleBank {
        weights: hold.bank_weights(),
        counts: vec![vec![4u32, 2u32]; n_particles],
        taus: vec![vec![1.2f64, 2.4f64]; n_particles],
    };
    let params = ModelParams::default();
    let state = DayStepIn {
        counts: vec![12, 6],
        taus: vec![1.4, 2.8],
        lot_ids: vec![3, 4],
        demand: Some(28),
        spoil_by: None,
        delivery_n: 0,
        delivery_tau: 0.0,
        delivery_lot_id: 0,
    };
    let mut rng_a = stream_rng(SEED, day, 2);
    let mut rng_s = stream_rng(SEED, day, 3);
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
    (bank, rich, params, day)
}

/// C1: one stochastic freshness decrement + first-passage check per lot per particle.
fn proxy_c1(n_particles: usize, n_lots: usize, rng: &mut Pcg64) {
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    for _ in 0..n_particles {
        for _ in 0..n_lots {
            let mut f = 0.65 + rng.random::<f64>() * 0.3;
            let y = gamma.sample(rng);
            f -= y;
            if f <= 0.0 {
                let _ = 1u32;
            }
        }
    }
}

/// C2: per-unit freshness decrement + first-passage (unit-level state).
fn proxy_c2(n_particles: usize, units_total: usize, rng: &mut Pcg64) {
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    for _ in 0..n_particles {
        for _ in 0..units_total {
            let mut f = 0.5 + rng.random::<f64>() * 0.45;
            let y = gamma.sample(rng);
            f -= y;
            if f <= 0.0 {
                let _ = 1u32;
            }
        }
    }
}

/// C3: histogram convolution per lot per particle (freshness bins).
fn proxy_c3(n_particles: usize, n_lots: usize, k_bins: usize) {
    let mut hist = vec![0.0f64; k_bins];
    let mut next = vec![0.0f64; k_bins];
    let mut kernel = vec![0.0f64; k_bins];
    for i in 0..k_bins {
        kernel[i] = 1.0 / k_bins as f64;
    }
    for _ in 0..n_particles {
        for _ in 0..n_lots {
            hist.fill(0.0);
            hist[k_bins / 2] = 1.0;
            next.fill(0.0);
            for i in 0..k_bins {
                for j in 0..k_bins {
                    let dst = i + j;
                    if dst < k_bins {
                        next[dst] += hist[i] * kernel[j];
                    }
                }
            }
            std::mem::swap(&mut hist, &mut next);
        }
    }
}

fn bench_filter_only(n_particles: usize) -> Stats {
    let (bank, rich, params, day) = warm_bank(n_particles);
    time_micro(|| {
        let obs = mask_for("P1").unwrap().apply(&rich);
        let mut fr = stream_rng(SEED, day, 6);
        let _ = filter_step(&bank, &obs, &params, &mut fr);
    })
}

fn bench_proxy_only(model: &str, n_particles: usize, n_lots: usize, k_bins: usize, units: usize) -> Stats {
    time_micro(|| {
        let mut rng = Pcg64::seed_from_u64(SEED);
        match model {
            "C1" => proxy_c1(n_particles, n_lots, &mut rng),
            "C2" => proxy_c2(n_particles, units, &mut rng),
            "C3" => proxy_c3(n_particles, n_lots, k_bins),
            _ => {}
        }
    })
}

fn bench_combined(model: &str, n_particles: usize, n_lots: usize, k_bins: usize, units: usize) -> Stats {
    let (bank, rich, params, day) = warm_bank(n_particles);
    time_micro(|| {
        let obs = mask_for("P1").unwrap().apply(&rich);
        let mut fr = stream_rng(SEED, day, 6);
        let _ = filter_step(&bank, &obs, &params, &mut fr);
        let mut rng = Pcg64::seed_from_u64(SEED);
        match model {
            "C1" => proxy_c1(n_particles, n_lots, &mut rng),
            "C2" => proxy_c2(n_particles, units, &mut rng),
            "C3" => proxy_c3(n_particles, n_lots, k_bins),
            _ => {}
        }
    })
}

fn sweep_current_e2e() -> Vec<E2eRow> {
    let particles = [64usize, 100, 200, 400];
    let k_dims = [4usize, 8, 16, 32];
    let mut out = Vec::new();

    for &n in &particles {
        for &k in &k_dims {
            let mk = || configured_session(n, k, DEFAULT_H, DEFAULT_PATHS, DEFAULT_RADIUS);
            let step = time_e2e(|s| {
                s.step(ORDER_QTY);
            }, mk);
            out.push(E2eRow {
                scenario: "current",
                path: "step",
                n_particles: n,
                k_dim: k,
                h: DEFAULT_H,
                n_paths: DEFAULT_PATHS,
                radius: DEFAULT_RADIUS,
                stats: step,
            });
        }
    }

    let n = 200usize;
    let k = DEFAULT_K;
    for &h in &[7u32, 14, 28] {
        for &paths in &[1u32, 2, 4, 8] {
            for &radius in &[0i32, 1, 2] {
                let mk = || configured_session(n, k, h, paths, radius);
                let act = time_e2e(
                    |s| {
                        s.act(Some("rollout"), None, None, None, None, None, None);
                    },
                    mk,
                );
                out.push(E2eRow {
                    scenario: "current",
                    path: "act_rollout",
                    n_particles: n,
                    k_dim: k,
                    h,
                    n_paths: paths,
                    radius,
                    stats: act,
                });
            }
        }
    }

    for &policy in &["damped_sw", "rollout"] {
        let mk = || configured_session(200, DEFAULT_K, DEFAULT_H, DEFAULT_PATHS, DEFAULT_RADIUS);
        let act = time_e2e(
            |s| {
                s.act(Some(policy), None, None, None, None, None, None);
            },
            mk,
        );
        out.push(E2eRow {
            scenario: "current",
            path: if policy == "damped_sw" {
                "act_damped_sw"
            } else {
                "act_rollout_demo"
            },
            n_particles: 200,
            k_dim: DEFAULT_K,
            h: DEFAULT_H,
            n_paths: DEFAULT_PATHS,
            radius: DEFAULT_RADIUS,
            stats: act,
        });
    }

    out
}

fn sweep_rollout_micro() -> Vec<RolloutRow> {
    let n = 200usize;
    let (bank, _rich, params, _day) = warm_bank(n);
    let belief = belief_mean_from_bank(&bank, DEFAULT_L, DEFAULT_K);
    let mut counts = Vec::<u32>::new();
    let mut taus = Vec::<f64>::new();
    let mut ids = Vec::<i64>::new();
    for (i, &n_raw) in belief.lot_counts.iter().enumerate() {
        let nc = n_raw.round().max(0.0) as u32;
        if nc == 0 {
            continue;
        }
        let k = belief.tau_grid.len();
        let mut tau = 0.0;
        if k > 0 && (i + 1) * k <= belief.age_marginals.len() {
            let row = &belief.age_marginals[i * k..(i + 1) * k];
            tau = row
                .iter()
                .zip(belief.tau_grid.iter())
                .map(|(&p, &t)| p * t)
                .sum();
        }
        counts.push(nc);
        taus.push(tau);
        ids.push((i + 1) as i64);
    }

    let mut out = Vec::new();
    for &h in &[7u32, 14, 28] {
        for &paths in &[1u32, 2, 4, 8] {
            for &radius in &[0i32, 1, 2] {
                let stats = time_micro(|| {
                    let _ = rollout_order(
                        &counts,
                        &taus,
                        &ids,
                        ORDER_QTY,
                        &params,
                        SEED,
                        h,
                        paths,
                        radius,
                    );
                });
                out.push(RolloutRow {
                    n_particles: n,
                    h,
                    n_paths: paths,
                    radius,
                    stats,
                });
            }
        }
    }
    out
}

fn sweep_freshness_proxies() -> Vec<ProxyRow> {
    let particles = [64usize, 100, 200, 400];
    let lots = [2usize, 4, 8];
    let k_bins = [8usize, 16, 32, 64];
    let units = [30usize, 60, 120, 200];
    let models = ["C1", "C2", "C3"];
    let mut out = Vec::new();

    for &model in &models {
        for &n in &particles {
            match model {
                "C1" => {
                    for &l in &lots {
                        let filter = bench_filter_only(n);
                        let proxy = bench_proxy_only("C1", n, l, 0, 0);
                        let combined = bench_combined("C1", n, l, 0, 0);
                        out.push(ProxyRow {
                            model: "C1",
                            n_particles: n,
                            n_lots: l,
                            k_bins: 0,
                            units_total: 0,
                            filter_only_ms: filter,
                            proxy_only_ms: proxy,
                            combined_ms: combined,
                        });
                    }
                }
                "C2" => {
                    for &u in &units {
                        let filter = bench_filter_only(n);
                        let proxy = bench_proxy_only("C2", n, 0, 0, u);
                        let combined = bench_combined("C2", n, 0, 0, u);
                        out.push(ProxyRow {
                            model: "C2",
                            n_particles: n,
                            n_lots: 0,
                            k_bins: 0,
                            units_total: u,
                            filter_only_ms: filter,
                            proxy_only_ms: proxy,
                            combined_ms: combined,
                        });
                    }
                }
                "C3" => {
                    for &l in &lots {
                        for &k in &k_bins {
                            let filter = bench_filter_only(n);
                            let proxy = bench_proxy_only("C3", n, l, k, 0);
                            let combined = bench_combined("C3", n, l, k, 0);
                            out.push(ProxyRow {
                                model: "C3",
                                n_particles: n,
                                n_lots: l,
                                k_bins: k,
                                units_total: 0,
                                filter_only_ms: filter,
                                proxy_only_ms: proxy,
                                combined_ms: combined,
                            });
                        }
                    }
                }
                _ => {}
            }
        }
    }
    out
}

fn main() {
    let omp = env::var("OMP_NUM_THREADS").unwrap_or_else(|_| "?".into());
    eprintln!("bench_freshness_sweep: OMP_NUM_THREADS={omp}");

    let report = SweepReport {
        meta: Meta {
            sha_note: "run from worktree team/timing-freshness/implement",
            omp_threads: omp,
            e2e_reps: E2E_REPS,
            micro_reps: MICRO_REPS,
            warm_days: WARM_DAYS,
            target_ms: 500.0,
            disclaimer: "C1/C2/C3 are kernel proxies + filter_step; not production freshness code",
        },
        current_e2e: sweep_current_e2e(),
        rollout_sweep: sweep_rollout_micro(),
        freshness_proxies: sweep_freshness_proxies(),
    };

    let json = serde_json::to_string_pretty(&report).expect("json");
    let args: Vec<String> = env::args().collect();
    if let Some(i) = args.iter().position(|a| a == "--output") {
        let path = args.get(i + 1).expect("--output requires a path");
        fs::write(path, &json).expect("write output");
        eprintln!("wrote {path}");
    } else {
        println!("{json}");
    }
}
