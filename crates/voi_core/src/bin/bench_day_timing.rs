//! Native release benchmark: one-day `EngineSession` cost under DEMO_BUDGETS.
//!
//! Run: `OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_day_timing`

use std::time::Instant;

use voi_core::{EngineSession, ShipmentTrace};

const N_PARTICLES: usize = 200;
const H: u32 = 7;
const N_PATHS: u32 = 2;
const RADIUS: i32 = 1;
const SEED: u64 = 42;
const ORDER_QTY: u32 = 16;
const WARM_DAYS: usize = 7;
const REPS: usize = 200;
const WARMUP_REPS: usize = 20;

fn new_configured() -> EngineSession {
    let mut s = EngineSession::new(SEED);
    s.init(SEED);
    s.configure(
        1,
        true,
        H,
        N_PATHS,
        RADIUS,
        vec![ShipmentTrace::smoke_cool()],
        N_PARTICLES,
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

fn print_stats(label: &str, s: &Stats) {
    println!(
        "{label:28} mean={:.3} ms  p50={:.3}  p95={:.3}  min={:.3}  max={:.3}  n={}",
        s.mean_ms, s.p50_ms, s.p95_ms, s.min_ms, s.max_ms, s.n
    );
}

fn main() {
    println!("bench_day_timing DEMO_BUDGETS (native release, f-native unit PF)");
    println!(
        "n_particles={N_PARTICLES} H={H} n_paths={N_PATHS} radius={RADIUS} warm_days={WARM_DAYS} reps={REPS}"
    );
    println!("Timer excludes init+warm; measures one advance from warm state.");
    println!();

    let step = time_one_day(|s| {
        s.step(ORDER_QTY);
    });
    let damped = time_one_day(|s| {
        s.act(Some("damped_sw"), None, None, None, None, None, None);
    });
    let rollout = time_one_day(|s| {
        s.act(Some("rollout"), None, None, None, None, None, None);
    });

    println!("=== end-to-end (one advance only) ===");
    print_stats("step(order)", &step);
    print_stats("act(damped_sw)", &damped);
    print_stats("act(rollout)", &rollout);
    println!();

    // Primary S1.12 gate: filter-dominated per-day cost @ N=200 (handoff baseline ~5.7 ms/day).
    println!("mean ms/day = {:.3}", step.mean_ms);
}
