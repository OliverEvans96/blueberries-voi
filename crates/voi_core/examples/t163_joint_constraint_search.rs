//! Joint search over mixture weight, q10, and leg-setpoint shift against T-163 gates.
//!
//! Phase 1: ac2_19 + truth band + session (full grid). Phase 2: ac2_11a on top survivors only.
//!
//! Run: `cargo run -p voi_core --release --example t163_joint_constraint_search`

#[path = "support/t163_joint_search_common.rs"]
mod common;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;
use voi_core::arrival::{ArrivalCondition, ArrivalModel, DEFAULT_ARRIVAL_CORRIDOR};
use voi_core::demand_profile::DemandProfile;
use voi_core::EngineSession;

use common::{ac2_19_min_margin, configured_model, grid_size, par_map_grid};

const N_TRUTH: usize = 400;
const AC2_11A_MIN_RATIO: f64 = 2.18;
const PHASE2_TOP_N: usize = 10;

fn truth_band(model: &ArrivalModel) -> (f64, f64) {
    let mut rng_d = Pcg64::seed_from_u64(163_501);
    let mut rng_t = Pcg64::seed_from_u64(163_502);
    let mut rng_p = Pcg64::seed_from_u64(163_503);
    let mut rng_g = Pcg64::seed_from_u64(163_504);
    let mut rng_regime = Pcg64::seed_from_u64(163_505);
    let mut samples = Vec::with_capacity(N_TRUTH);
    for _ in 0..N_TRUTH {
        let draw = model.draw_truth_multilot_delivery_biased(
            DEFAULT_ARRIVAL_CORRIDOR,
            45,
            0.0,
            &mut rng_d,
            &mut rng_t,
            &mut rng_p,
            &mut rng_g,
            &mut rng_regime,
        );
        let total: usize = draw.lots.iter().map(|lot| lot.unit_f.len()).sum();
        let mean_f = draw
            .lots
            .iter()
            .flat_map(|lot| lot.unit_f.iter().copied())
            .sum::<f64>()
            / total as f64;
        samples.push(mean_f);
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = samples[samples.len() / 2];
    let pct_60_90 = samples
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / N_TRUTH as f64;
    (p50, pct_60_90)
}

fn session_weighted_mean_f(model: &ArrivalModel) -> f64 {
    let seed = 163_503u64;
    let mut sess = EngineSession::with_arrival_model(seed, model.clone());
    sess.set_demand_profile(
        DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("profile"),
    );
    sess.init(seed);
    let _ = sess.step(64);
    let delta = sess.step(0);
    let snap = sess.snapshot_value();
    let lots = snap["live_lots"].as_array().expect("live_lots");
    lots.iter()
        .map(|lot| lot["n"].as_u64().unwrap() as f64 * lot["mean_f"].as_f64().unwrap())
        .sum::<f64>()
        / delta.arrivals as f64
}

fn ac2_11a_ratio(model: &mut ArrivalModel) -> f64 {
    const ORDER_QTY: u32 = 64;
    const N_DAYS: u32 = 80;
    let seed = 150_211u64;
    let orders: Vec<u32> = (0..N_DAYS)
        .map(|i| if i % 4 == 0 { ORDER_QTY } else { 0 })
        .collect();

    let mut deliveries_truth = Vec::new();
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    let mut rng_regime = Pcg64::seed_from_u64(seed + 4);
    for (day, &qty) in orders.iter().enumerate() {
        if qty == 0 {
            continue;
        }
        let draw = model.draw_truth_multilot_delivery_biased(
            DEFAULT_ARRIVAL_CORRIDOR,
            qty as usize,
            0.0,
            &mut rng_d,
            &mut rng_t,
            &mut rng_p,
            &mut rng_g,
            &mut rng_regime,
        );
        let total: usize = draw.lots.iter().map(|lot| lot.unit_f.len()).sum();
        let truth_mean = draw
            .lots
            .iter()
            .flat_map(|lot| lot.unit_f.iter().copied())
            .sum::<f64>()
            / total as f64;
        deliveries_truth.push((
            day as u32,
            draw.lots[0].pack_date_days,
            draw.lots[0].lambda,
            truth_mean,
        ));
    }

    let mut mae_p0 = 0.0;
    let mut mae_f2 = 0.0;
    for &(_, pack_date, _lambda, truth) in &deliveries_truth {
        let p0 = model.filter_law_mean_f(ArrivalCondition::Prior);
        let f2 = model.filter_law_mean_f(ArrivalCondition::Duration(pack_date));
        mae_p0 += (p0 - truth).abs();
        mae_f2 += (f2 - truth).abs();
    }
    let n = deliveries_truth.len() as f64;
    mae_p0 / n / (mae_f2 / n).max(1e-12)
}

#[derive(Clone, Copy)]
struct Phase1Row {
    p_short: f64,
    q10: f64,
    delta_c: f64,
    ac2_19_margin: f64,
    p50: f64,
    pct_60_90: f64,
    session_f: f64,
}

fn main() {
    let total = grid_size();
    eprintln!("phase1: {total} configs");

    let phase1: Vec<Phase1Row> = par_map_grid("phase1", |(p_short, q10, delta_c)| {
        let mut model = configured_model(p_short, q10, delta_c);
        let ac2_19_margin = ac2_19_min_margin(&mut model);
        let (p50, pct_60_90) = truth_band(&model);
        let session_f = session_weighted_mean_f(&model);
        Phase1Row {
            p_short,
            q10,
            delta_c,
            ac2_19_margin,
            p50,
            pct_60_90,
            session_f,
        }
    });

    let mut fast_pass: Vec<Phase1Row> = phase1
        .iter()
        .copied()
        .filter(|row| {
            row.ac2_19_margin > 0.0
                && row.session_f >= 0.55
                && row.p50 >= 0.65
                && row.pct_60_90 >= 0.45
        })
        .collect();
    fast_pass.sort_by(|a, b| {
        b.ac2_19_margin
            .partial_cmp(&a.ac2_19_margin)
            .unwrap()
    });
    fast_pass.truncate(PHASE2_TOP_N);

    eprintln!(
        "phase2: ac2_11a on {} survivors (top {} by ac2_19 among fast gates)",
        fast_pass.len(),
        PHASE2_TOP_N
    );

    let mut passing = Vec::new();
    let mut best_ratio = Vec::new();
    for (i, row) in fast_pass.iter().enumerate() {
        eprintln!("phase2: {}/{}", i + 1, fast_pass.len());
        let mut model = configured_model(row.p_short, row.q10, row.delta_c);
        let ratio = ac2_11a_ratio(&mut model);
        let json_row = json!({
            "p_short": row.p_short,
            "q10": row.q10,
            "delta_c": row.delta_c,
            "ac2_19_margin": row.ac2_19_margin,
            "p50": row.p50,
            "pct_60_90": row.pct_60_90,
            "session_f": row.session_f,
            "ac2_11a_ratio": ratio,
        });
        if ratio >= AC2_11A_MIN_RATIO {
            passing.push(json_row.clone());
        }
        best_ratio.push(json_row);
    }

    passing.sort_by(|a, b| {
        b["ac2_11a_ratio"]
            .as_f64()
            .unwrap()
            .partial_cmp(&a["ac2_11a_ratio"].as_f64().unwrap())
            .unwrap()
    });
    best_ratio.sort_by(|a, b| {
        b["ac2_11a_ratio"]
            .as_f64()
            .unwrap()
            .partial_cmp(&a["ac2_11a_ratio"].as_f64().unwrap())
            .unwrap()
    });

    println!(
        "{}",
        json!({
            "phase1_configs": total,
            "fast_pass_count": fast_pass.len(),
            "passing_all_four": passing,
            "best_ac2_11a_ratio": best_ratio.into_iter().take(20).collect::<Vec<_>>(),
        })
    );
}
