//! JSON payload for arrival tuning sketch notebook (uncommitted helper).
//!
//! Run: `cargo run -p voi_core --release --example arrival_tuning_sketch_data`

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;
use voi_core::arrival::{resolve_arrival_exposure, ArrivalModel};
use voi_core::shipments::truth_transit_trace;

const MC_N: usize = 800;

fn empirical_var_log(samples: &[f64]) -> f64 {
    if samples.len() < 2 {
        return 0.0;
    }
    let logs: Vec<f64> = samples.iter().map(|l| l.max(1e-12).ln()).collect();
    let mean = logs.iter().sum::<f64>() / logs.len() as f64;
    logs.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (logs.len() - 1) as f64
}

fn mc_lambdas(model: &ArrivalModel, n: usize, seed: u64) -> Vec<f64> {
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    let mut rng_regime = Pcg64::seed_from_u64(seed + 4);
    (0..n)
        .map(|_| {
            model
                .draw_truth_delivery(
                    "abdella_all",
                    1,
                    &mut rng_d,
                    &mut rng_t,
                    &mut rng_p,
                    &mut rng_g,
                    &mut rng_regime,
                )
                .lambda
        })
        .collect()
}

fn var_log_decomposition(rho: f64) -> serde_json::Value {
    let mut full = ArrivalModel::embedded();
    full.set_break_rate(rho);
    let mut clean = ArrivalModel::embedded();
    clean.set_break_rate(0.0);
    let lam_full = mc_lambdas(&full, MC_N, 163_800 + (rho * 10_000.0) as u64);
    let lam_clean = mc_lambdas(&clean, MC_N, 163_800 + (rho * 10_000.0) as u64);
    let var_full = empirical_var_log(&lam_full);
    let var_clean = empirical_var_log(&lam_clean);
    let break_var = (var_full - var_clean).max(0.0);
    let duration_var = var_clean;
    let denom = duration_var + break_var;
    let (duration_share, break_share) = if denom <= 1e-18 {
        (1.0, 0.0)
    } else {
        (duration_var / denom, break_var / denom)
    };
    json!({
        "rho": rho,
        "var_log_lambda_full": var_full,
        "var_log_lambda_clean": var_clean,
        "duration_share": duration_share,
        "break_share": break_share,
    })
}

fn trace_payload(model: &ArrivalModel, duration_d: f64, seed: u64) -> serde_json::Value {
    let mut rng = Pcg64::seed_from_u64(seed);
    let trace = truth_transit_trace(duration_d, model, 0.0, &mut rng);
    let lambda = resolve_arrival_exposure(
        Some(&trace.temps_c),
        Some(&trace.times_d),
        model.q10,
        model.t_ref,
    )
    .expect("trace integrates");
    json!({
        "duration_d": duration_d,
        "times_d": trace.times_d,
        "temps_c": trace.temps_c,
        "lambda": lambda,
        "rho": model.rho,
        "tau_bar": model.tau_bar,
        "sigma_hour": model.sigma_hour,
        "phi_set": model.phi_set(),
        "phi_break": model.phi_break(),
    })
}

fn main() {
    let mut base = ArrivalModel::embedded();
    let phi_set = base.phi_set();
    let phi_break_default = base.phi_break();

    let rho_grid = [0.0_f64, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15];
    let mut decomp = Vec::new();
    for &rho in &rho_grid {
        decomp.push(var_log_decomposition(rho));
    }

    let tau_bars = [0.1_f64, 0.5, 1.0, 1.5];
    let mut tau_traces = Vec::new();
    for (i, &tb) in tau_bars.iter().enumerate() {
        let mut m = ArrivalModel::embedded();
        m.set_break_rate(0.12);
        m.tau_bar = tb;
        tau_traces.push(trace_payload(&m, 5.5, 163_900 + i as u64));
    }

    let payload = json!({
        "phi_set": phi_set,
        "phi_break_default": phi_break_default,
        "q10": base.q10,
        "t_ref": base.t_ref,
        "var_log_decomposition": decomp,
        "tau_bar_traces": tau_traces,
    });
    println!("{}", serde_json::to_string(&payload).expect("json"));
}
