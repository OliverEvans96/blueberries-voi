//! JSON payload for T-163 Phase 2 notebook figures.
//!
//! Run: `cargo run -p voi_core --release --example t163_phase2_fig_data`

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;
use std::time::Instant;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};
use voi_core::shipments::truth_transit_trace;
use voi_core::{DemandProfile, EngineSession, ModelParams};

const N_FRESHNESS: usize = 400;

fn multilot_delivery_mean_f_samples(model: &ArrivalModel, n: usize, seed: u64) -> Vec<f64> {
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    let mut rng_regime = Pcg64::seed_from_u64(seed + 4);
    (0..n)
        .map(|_| {
            let draw = model.draw_truth_multilot_delivery_biased(
                "abdella_all",
                45,
                0.0,
                &mut rng_d,
                &mut rng_t,
                &mut rng_p,
                &mut rng_g,
                &mut rng_regime,
            );
            let total: usize = draw.lots.iter().map(|lot| lot.unit_f.len()).sum();
            draw.lots
                .iter()
                .flat_map(|lot| lot.unit_f.iter().copied())
                .sum::<f64>()
                / total as f64
        })
        .collect()
}

fn session_multilot_lots(seed: u64) -> serde_json::Value {
    let mut sess = EngineSession::new(seed);
    sess.set_demand_profile(
        DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("profile"),
    );
    sess.init(seed);
    let _ = sess.step(64);
    let delta = sess.step(0);
    assert!(delta.arrivals > 0, "fixture must deliver units");
    let snap = sess.snapshot_value();
    let lots = snap["live_lots"].as_array().expect("live_lots");
    let lot_rows: Vec<_> = lots
        .iter()
        .map(|lot| {
            json!({
                "lot_id": lot["lot_id"],
                "n": lot["n"],
                "mean_f": lot["mean_f"],
            })
        })
        .collect();
    let weighted: f64 = lots
        .iter()
        .map(|lot| lot["n"].as_u64().unwrap() as f64 * lot["mean_f"].as_f64().unwrap())
        .sum::<f64>()
        / delta.arrivals as f64;
    json!({
        "day": 1,
        "arrivals": delta.arrivals,
        "n_lots": lots.len(),
        "delivery_weighted_mean_f": weighted,
        "lots": lot_rows,
    })
}

fn main() {
    let t_embed = Instant::now();
    let mut model = ArrivalModel::embedded();
    let embed_ms = t_embed.elapsed().as_secs_f64() * 1000.0;

    model.sync_params(&ModelParams::default());
    let samples = multilot_delivery_mean_f_samples(&model, N_FRESHNESS, 163_701);
    let mut sorted = samples.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = sorted.len();
    let mean = sorted.iter().sum::<f64>() / n as f64;
    let p50 = sorted[n / 2];
    let pct_below_50 = sorted.iter().filter(|&&f| f < 0.5).count() as f64 / n as f64 * 100.0;

    let prior = model.rung_law_on_grid(ArrivalCondition::Prior, "abdella_all", 64);
    let prior_bias = prior.mean_f - mean;

    let mut rho_zero = model.clone();
    rho_zero.set_break_rate(0.0);
    let mut rng = Pcg64::seed_from_u64(163_004);
    let d = 5.5;
    let trace = truth_transit_trace(d, &rho_zero, 0.0, &mut rng);

    let session = session_multilot_lots(163_503);

    let payload = json!({
        "freshness": {
            "samples": samples,
            "mean": mean,
            "p50": p50,
            "pct_below_0_5": pct_below_50,
            "n": n,
        },
        "belief_vs_truth": {
            "prior_mean_f": prior.mean_f,
            "multilot_truth_mean_f": mean,
            "bias": prior_bias,
        },
        "rho_zero_trace": {
            "duration_d": d,
            "times_d": trace.times_d,
            "temps_c": trace.temps_c,
        },
        "session_multilot": session,
        "embedded_init_ms": embed_ms,
    });
    println!("{}", serde_json::to_string(&payload).expect("json"));
}
