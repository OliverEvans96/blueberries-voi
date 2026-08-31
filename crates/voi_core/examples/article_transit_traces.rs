//! JSON payload for article_figures.ipynb — model transit temperature traces.
//!
//! Matches production defaults in `t163_phase1_realism_diag` (`final_production_default`):
//! embedded artifact, `abdella_mix` corridor with regime stream, ρ=0.08, N=2000, seed 980_001.
//!
//! Run: `cargo run -p voi_core --release --example article_transit_traces`

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;
use voi_core::arrival::{ArrivalModel, DEFAULT_ARRIVAL_CORRIDOR};
use voi_core::shipments::truth_transit_trace_for_corridor;

const N_ENVELOPE: usize = 2000;
const N_SAMPLES: usize = 6;
const U_GRID: usize = 120;
/// Same seed as `final_production_default_summary` in `t163_phase1_realism_diag.rs`.
const SEED: u64 = 980_001;

fn interp_linear(x: f64, xs: &[f64], ys: &[f64]) -> f64 {
    if xs.is_empty() {
        return 0.0;
    }
    if x <= xs[0] {
        return ys[0];
    }
    if x >= *xs.last().unwrap() {
        return *ys.last().unwrap();
    }
    for i in 0..xs.len() - 1 {
        let x0 = xs[i];
        let x1 = xs[i + 1];
        if x >= x0 && x <= x1 {
            if (x1 - x0).abs() < 1e-12 {
                return ys[i];
            }
            let t = (x - x0) / (x1 - x0);
            return ys[i] + t * (ys[i + 1] - ys[i]);
        }
    }
    *ys.last().unwrap()
}

fn resample_to_u_grid(times_d: &[f64], temps_c: &[f64], n: usize) -> Vec<f64> {
    if times_d.len() < 2 || temps_c.len() < 2 {
        return vec![0.0; n];
    }
    let d = (times_d[times_d.len() - 1] - times_d[0]).max(0.0);
    if d <= 1e-12 {
        return vec![temps_c[0]; n];
    }
    (0..n)
        .map(|i| {
            let u = i as f64 / (n.saturating_sub(1).max(1) as f64);
            interp_linear(u * d, times_d, temps_c)
        })
        .collect()
}

fn median(mut values: Vec<f64>) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    values[values.len() / 2]
}

fn draw_trace(
    model: &ArrivalModel,
    rng_d: &mut Pcg64,
    rng_t: &mut Pcg64,
    rng_regime: &mut Pcg64,
) -> (String, f64, voi_core::ShipmentTrace) {
    let resolved_key = model.resolve_corridor_regime(DEFAULT_ARRIVAL_CORRIDOR, rng_regime);
    let d = model.draw_bottom_up_duration(&resolved_key, rng_d);
    let trace = truth_transit_trace_for_corridor(d, model, &resolved_key, 0.0, rng_t);
    (resolved_key, d, trace)
}

fn main() {
    let model = ArrivalModel::embedded();

    let u_grid: Vec<f64> = (0..U_GRID)
        .map(|i| i as f64 / (U_GRID.saturating_sub(1).max(1) as f64))
        .collect();

    let mut rng_d = Pcg64::seed_from_u64(SEED);
    let mut rng_t = Pcg64::seed_from_u64(SEED + 1);
    let mut rng_regime = Pcg64::seed_from_u64(SEED + 4);

    let mut envelope_temps = vec![vec![0.0; U_GRID]; N_ENVELOPE];
    let mut durations = Vec::with_capacity(N_ENVELOPE);
    for row in &mut envelope_temps {
        let (_resolved, d, trace) = draw_trace(&model, &mut rng_d, &mut rng_t, &mut rng_regime);
        durations.push(d);
        *row = resample_to_u_grid(&trace.times_d, &trace.temps_c, U_GRID);
    }

    let mean: Vec<f64> = (0..U_GRID)
        .map(|j| {
            envelope_temps
                .iter()
                .map(|row| row[j])
                .sum::<f64>()
                / N_ENVELOPE as f64
        })
        .collect();
    let std: Vec<f64> = (0..U_GRID)
        .map(|j| {
            let m = mean[j];
            (envelope_temps
                .iter()
                .map(|row| (row[j] - m).powi(2))
                .sum::<f64>()
                / N_ENVELOPE as f64)
            .sqrt()
        })
        .collect();

    let median_duration_d = median(durations);

    let mut sample_traces = Vec::with_capacity(N_SAMPLES);
    for k in 0..N_SAMPLES {
        let seed = SEED + 10_000 + k as u64;
        let mut rng_d_k = Pcg64::seed_from_u64(seed);
        let mut rng_t_k = Pcg64::seed_from_u64(seed + 1);
        let mut rng_regime_k = Pcg64::seed_from_u64(seed + 4);
        let (resolved_key, d, trace) =
            draw_trace(&model, &mut rng_d_k, &mut rng_t_k, &mut rng_regime_k);
        sample_traces.push(json!({
            "seed": seed,
            "resolved_corridor": resolved_key,
            "duration_d": d,
            "times_d": trace.times_d,
            "temps_c": trace.temps_c,
        }));
    }

    let payload = json!({
        "corridor": DEFAULT_ARRIVAL_CORRIDOR,
        "rho": model.rho,
        "q10": model.q10,
        "reference_life_days": model.reference_life_days,
        "seed": SEED,
        "n_envelope": N_ENVELOPE,
        "u_grid": u_grid,
        "envelope_mean_c": mean,
        "envelope_std_c": std,
        "median_duration_d": median_duration_d,
        "sample_traces": sample_traces,
    });
    println!("{}", serde_json::to_string(&payload).expect("json"));
}
