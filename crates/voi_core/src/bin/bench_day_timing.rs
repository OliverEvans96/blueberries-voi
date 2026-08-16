//! Native release benchmark: one-day EngineSession paths under DEMO_BUDGETS.
//!
//! Run: `OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_day_timing`

use std::time::Instant;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::belief_flat::belief_mean_from_bank;
use voi_core::{
    day_step, filter_step, mask_for, particle_bank_to_flat, rollout_order, DayStepIn,
    EngineSession, ModelParams, ParticleBank, RichDay, ShipmentTrace,
};

const N_PARTICLES: usize = 200;
const H: u32 = 7;
const N_PATHS: u32 = 2;
const RADIUS: i32 = 1;
const SEED: u64 = 42;
const ORDER_QTY: u32 = 16;
const WARM_DAYS: usize = 7;
const REPS: usize = 200;
const WARMUP_REPS: usize = 20;

fn smoke_shipment() -> ShipmentTrace {
    ShipmentTrace {
        times_d: vec![0.0, 1.0, 2.0],
        temps_c: vec![1.0, 1.0, 1.0],
    }
}

fn new_configured() -> EngineSession {
    let mut s = EngineSession::new(SEED);
    s.init(SEED);
    s.set_belief_dims(2, 4);
    s.configure(
        1,
        true,
        H,
        N_PATHS,
        RADIUS,
        vec![smoke_shipment()],
        N_PARTICLES,
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

#[derive(Clone, Debug)]
struct Stats {
    mean_ms: f64,
    p50_ms: f64,
    p95_ms: f64,
    min_ms: f64,
    max_ms: f64,
    n: usize,
}

fn stats_from_samples(mut xs: Vec<f64>) -> Stats {
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = xs.len();
    let sum: f64 = xs.iter().sum();
    Stats {
        mean_ms: sum / n as f64,
        p50_ms: xs[n / 2],
        p95_ms: xs[(0.95 * (n - 1) as f64).round() as usize],
        min_ms: xs[0],
        max_ms: xs[n - 1],
        n,
    }
}

/// Time only the final operation; session init + warm are outside the timer.
fn time_one_day<F: FnMut(&mut EngineSession)>(mut op: F) -> Stats {
    let total = REPS + WARMUP_REPS;
    let mut xs = Vec::with_capacity(total);
    for _ in 0..total {
        let mut s = new_configured();
        warm_session(&mut s);
        let t0 = Instant::now();
        op(&mut s);
        xs.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    stats_from_samples(xs[WARMUP_REPS..].to_vec())
}

fn time_micro<F: FnMut()>(mut f: F) -> Stats {
    let total = REPS + WARMUP_REPS;
    let mut xs = Vec::with_capacity(total);
    for _ in 0..total {
        let t0 = Instant::now();
        f();
        xs.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    stats_from_samples(xs[WARMUP_REPS..].to_vec())
}

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

/// Particle bank after warm session (realistic L=2 demo state).
fn warm_bank() -> (ParticleBank, RichDay, DayStepIn, ModelParams, u32) {
    let mut hold = new_configured();
    warm_session(&mut hold);
    let day = hold.episode_day();
    let bank = ParticleBank {
        weights: hold.bank_weights(),
        counts: vec![vec![4u32, 2u32]; N_PARTICLES],
        taus: vec![vec![1.2f64, 2.4f64]; N_PARTICLES],
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
    (bank, rich, state, params, day)
}

fn bench_end_to_end() -> (Stats, Stats, Stats) {
    let step = time_one_day(|s| {
        s.step(ORDER_QTY);
    });
    let damped = time_one_day(|s| {
        s.act(Some("damped_sw"), None, None, None, None, None, None);
    });
    let rollout = time_one_day(|s| {
        s.act(Some("rollout"), None, None, None, None, None, None);
    });
    (step, damped, rollout)
}

fn bench_decomposition() -> (Stats, Stats, Stats, Stats, Stats) {
    let (bank, rich, state, params, day) = warm_bank();
    let day_step_s = time_micro(|| {
        let mut rng_a = stream_rng(SEED, day, 2);
        let mut rng_s = stream_rng(SEED, day, 3);
        let _ = day_step(&state, &params, Some(&mut rng_a), Some(&mut rng_s));
    });
    let filter_s = time_micro(|| {
        let obs = mask_for("P1").unwrap().apply(&rich);
        let mut fr = stream_rng(SEED, day, 6);
        let _ = filter_step(&bank, &obs, &params, &mut fr);
    });
    let belief_s = time_micro(|| {
        let _ = particle_bank_to_flat(&bank, 2, 4);
    });
    let belief_mean_s = time_micro(|| {
        let _ = belief_mean_from_bank(&bank, 2, 4);
    });
    let rollout_s = time_micro(|| {
        let belief = belief_mean_from_bank(&bank, 2, 4);
        let mut counts = Vec::<u32>::new();
        let mut taus = Vec::<f64>::new();
        let mut ids = Vec::<i64>::new();
        for (i, &n_raw) in belief.lot_counts.iter().enumerate() {
            let n = n_raw.round().max(0.0) as u32;
            if n == 0 {
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
            counts.push(n);
            taus.push(tau);
            ids.push((i + 1) as i64);
        }
        let _ = rollout_order(
            &counts,
            &taus,
            &ids,
            16,
            &params,
            SEED,
            H,
            N_PATHS,
            RADIUS,
        );
    });
    (day_step_s, filter_s, belief_s, belief_mean_s, rollout_s)
}

fn bench_filter_scaled(multiplier: usize) -> Stats {
    let (bank, rich, _state, params, day) = warm_bank();
    time_micro(|| {
        let obs = mask_for("P1").unwrap().apply(&rich);
        let mut bank = bank.clone();
        for k in 0..multiplier {
            let mut fr = stream_rng(SEED.wrapping_add(k as u64), day, 6);
            bank = filter_step(&bank, &obs, &params, &mut fr);
        }
    })
}

fn print_stats(label: &str, s: &Stats) {
    println!(
        "{label:28} mean={:.3} ms  p50={:.3}  p95={:.3}  min={:.3}  max={:.3}  n={}",
        s.mean_ms, s.p50_ms, s.p95_ms, s.min_ms, s.max_ms, s.n
    );
}

fn main() {
    println!("bench_day_timing DEMO_BUDGETS (native release)");
    println!(
        "n_particles={N_PARTICLES} H={H} n_paths={N_PATHS} radius={RADIUS} warm_days={WARM_DAYS} reps={REPS}"
    );
    println!("Timer excludes init+warm; measures one advance from warm state.");
    println!();

    let (step, damped, rollout) = bench_end_to_end();
    println!("=== end-to-end (one advance only) ===");
    print_stats("step(order)", &step);
    print_stats("act(damped_sw)", &damped);
    print_stats("act(rollout)", &rollout);
    println!();

    let (day_step_s, filter_s, belief_s, belief_mean_s, rollout_s) = bench_decomposition();
    println!("=== decomposition (microbench components) ===");
    print_stats("day_step", &day_step_s);
    print_stats("filter_step", &filter_s);
    print_stats("belief_export (flat)", &belief_s);
    print_stats("belief_mean (policy)", &belief_mean_s);
    print_stats("rollout_order", &rollout_s);
    println!();

    println!("=== C1/C2/C3 filter scaling (measured repeated filter_step) ===");
    let f1 = bench_filter_scaled(1);
    let f2 = bench_filter_scaled(2);
    let f3 = bench_filter_scaled(3);
    let f5 = bench_filter_scaled(5);
    let f8 = bench_filter_scaled(8);
    print_stats("filter x1 (baseline)", &f1);
    print_stats("filter x2 (~C1 low)", &f2);
    print_stats("filter x3 (~C1 high)", &f3);
    print_stats("filter x5 (~C3 mid)", &f5);
    print_stats("filter x8 (~C2 high)", &f8);
}
