//! T-163 joint arrival calibration evaluators (Ax BO + diagnostic grids).
//!
//! Shared between PyO3 (`evaluate_joint_calib_trial_py`), Rust examples, and notebooks.

use std::sync::OnceLock;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde::{Deserialize, Serialize};

use crate::arrival::{ArrivalCondition, ArrivalModel, DEFAULT_ARRIVAL_CORRIDOR};
use crate::demand_profile::DemandProfile;
use crate::EngineSession;

const AC2_19_DAYS_BEFORE_D8: [i32; 4] = [2, 4, 5, 6];
const AC2_19_D8: i32 = 8;
const N_TRUTH: usize = 400;
const AC2_11A_MIN_RATIO: f64 = 2.18;

static EMBEDDED_BASE: OnceLock<ArrivalModel> = OnceLock::new();

/// Snapshot the committed embedded model once; evaluators clone from this.
pub fn embedded_base() -> &'static ArrivalModel {
    EMBEDDED_BASE.get_or_init(ArrivalModel::embedded)
}

/// Build a configured model for one candidate (single embedded snapshot clone).
pub fn configured_model(p_short: f64, q10: f64, delta_c: f64) -> ArrivalModel {
    let base = embedded_base();
    let mut model = base.clone();
    if let Some(mix) = model.corridor_mixtures.get_mut("abdella_mix") {
        mix.components[0].weight = p_short;
        mix.components[1].weight = 1.0 - p_short;
    }
    model.q10 = q10;
    for (leg, base_leg) in model.legs.iter_mut().zip(base.legs.iter()) {
        leg.setpoint_c = base_leg.setpoint_c + delta_c;
    }
    model.reference_life_days = 14.0;
    model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
    model.refresh_filter_laws();
    model
}

/// Apply mixture weight, q10, leg-setpoint shift, and η_ref — one prior rebuild at the end.
pub fn apply_config(model: &mut ArrivalModel, p_short: f64, q10: f64, delta_c: f64) {
    *model = configured_model(p_short, q10, delta_c);
}

/// AC2-19 d=8 proxy: Prior variance minus F2 variance at the longest ladder day.
pub fn ac2_19_d8_margin(model: &mut ArrivalModel) -> f64 {
    let prior_var = model.marginal_variance_f();
    prior_var - model.variance_f_given_d(AC2_19_D8)
}

/// AC2-19: min margin of Prior variance over F2 variance across the duration ladder.
pub fn ac2_19_min_margin(model: &mut ArrivalModel) -> f64 {
    let prior_var = model.marginal_variance_f();
    let d8_margin = prior_var - model.variance_f_given_d(AC2_19_D8);
    if d8_margin <= 0.0 {
        return d8_margin;
    }
    let mut min_margin = d8_margin;
    for &d in &AC2_19_DAYS_BEFORE_D8 {
        min_margin = min_margin.min(prior_var - model.variance_f_given_d(d));
    }
    min_margin
}

const SESSION_SEED: u64 = 163_503;
const TRUTH_BAND_SEED_BASE: u64 = 0;

/// Truth-band p50 and fraction of deliveries with mean f in [0.6, 0.9] (fixed RNG seeds).
pub fn truth_band(model: &ArrivalModel) -> (f64, f64) {
    truth_band_seeded(model, TRUTH_BAND_SEED_BASE)
}

/// Truth-band with per-draw RNG offsets keyed by ``seed`` (for multi-seed BO on slow leg only).
pub fn truth_band_seeded(model: &ArrivalModel, seed: u64) -> (f64, f64) {
    use std::sync::Arc;
    use std::thread;

    let model = Arc::new(model.clone());
    let n_workers = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
        .min(N_TRUTH.max(1));
    let chunk = (N_TRUTH + n_workers - 1) / n_workers;

    let samples: Vec<f64> = thread::scope(|scope| {
        (0..n_workers)
            .map(|worker| {
                let model = Arc::clone(&model);
                scope.spawn(move || {
                    let start = worker * chunk;
                    let end = (start + chunk).min(N_TRUTH);
                    let mut local = Vec::with_capacity(end - start);
                    for draw_idx in start..end {
                        let base = seed
                            .wrapping_add(worker as u64)
                            .wrapping_add(draw_idx as u64 * 9973);
                        let mut rng_d = Pcg64::seed_from_u64(base.wrapping_add(163_501));
                        let mut rng_t = Pcg64::seed_from_u64(base.wrapping_add(163_502));
                        let mut rng_p = Pcg64::seed_from_u64(base.wrapping_add(163_503));
                        let mut rng_g = Pcg64::seed_from_u64(base.wrapping_add(163_504));
                        let mut rng_regime = Pcg64::seed_from_u64(base.wrapping_add(163_505));
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
                        local.push(mean_f);
                    }
                    local
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .flat_map(|h| h.join().expect("truth_band worker"))
            .collect()
    });

    let mut samples = samples;
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let p50 = samples[samples.len() / 2];
    let pct_60_90 = samples
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / N_TRUTH as f64;
    (p50, pct_60_90)
}

/// Session weighted mean freshness after a 64-unit delivery (fixed seed 163503).
pub fn session_weighted_mean_f(model: &ArrivalModel) -> f64 {
    session_weighted_mean_f_seeded(model, SESSION_SEED)
}

/// Session weighted mean f with an explicit session RNG seed.
pub fn session_weighted_mean_f_seeded(model: &ArrivalModel, seed: u64) -> f64 {
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

/// AC2-11a ladder MAE ratio (expensive; run on promising trials only).
pub fn ac2_11a_ratio(model: &mut ArrivalModel) -> f64 {
    ac2_11a_ratio_seeded(model, 150_211)
}

/// AC2-11a with an explicit truth-draw seed (for K-seed BO aggregation).
pub fn ac2_11a_ratio_seeded(model: &mut ArrivalModel, seed: u64) -> f64 {
    const ORDER_QTY: u32 = 64;
    const N_DAYS: u32 = 80;
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

/// Per-trial fast metrics for Ax (fixed truth/session seeds; optional slow ac2_11a).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JointCalibFastResult {
    pub p_short: f64,
    pub q10: f64,
    pub delta_c: f64,
    pub ac2_19_margin: f64,
    pub ac2_19_d8_margin: f64,
    pub p50: f64,
    pub pct_60_90: f64,
    pub session_f: f64,
    pub ac2_11a_ratio: Option<f64>,
    pub rejected_ac2_19: bool,
    pub fast_gates_pass: bool,
    pub elapsed_s: f64,
}

/// Fast per-trial evaluator for Ax BO (~2–5s without ac2_11a).
pub fn evaluate_fast_trial(
    p_short: f64,
    q10: f64,
    delta_c: f64,
    include_ac2_11a: bool,
    ac2_11a_seed: u64,
) -> JointCalibFastResult {
    let start = std::time::Instant::now();
    let mut model = configured_model(p_short, q10, delta_c);
    let d8_margin = ac2_19_d8_margin(&mut model);
    let rejected_ac2_19 = d8_margin <= 0.0;
    let ac2_19_margin = if rejected_ac2_19 {
        d8_margin
    } else {
        ac2_19_min_margin(&mut model)
    };
    let (p50, pct_60_90, session_f) = if rejected_ac2_19 {
        (0.0, 0.0, 0.0)
    } else {
        let (p50, pct) = truth_band(&model);
        (p50, pct, session_weighted_mean_f(&model))
    };
    let fast_gates_pass = !rejected_ac2_19
        && session_f >= 0.55
        && p50 >= 0.65
        && pct_60_90 >= 0.45;
    let ac2_11a = if !rejected_ac2_19 && include_ac2_11a {
        Some(ac2_11a_ratio_seeded(&mut model, ac2_11a_seed))
    } else {
        None
    };
    JointCalibFastResult {
        p_short,
        q10,
        delta_c,
        ac2_19_margin,
        ac2_19_d8_margin: d8_margin,
        p50,
        pct_60_90,
        session_f,
        ac2_11a_ratio: ac2_11a,
        rejected_ac2_19,
        fast_gates_pass,
        elapsed_s: start.elapsed().as_secs_f64(),
    }
}

/// Time one representative fast trial (no ac2_11a).
pub fn benchmark_fast_trial() -> f64 {
    evaluate_fast_trial(0.70, 2.8, 0.0, false, 150_211).elapsed_s
}

/// Time fast vs slow (with ac2_11a) on the same representative point.
pub fn benchmark_fast_vs_slow() -> (f64, f64) {
    let fast = evaluate_fast_trial(0.70, 2.8, 0.0, false, 150_211).elapsed_s;
    let slow = evaluate_fast_trial(0.70, 2.8, 0.0, true, 150_211).elapsed_s;
    (fast, slow)
}

/// Per-seed metrics for one Ax candidate (legacy multi-seed truth/session path).
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct JointCalibTrialMetrics {
    pub p_short: f64,
    pub q10: f64,
    pub delta_c: f64,
    pub seed: u64,
    pub ac2_19_margin: f64,
    pub p50: f64,
    pub pct_60_90: f64,
    pub session_f: f64,
    pub ac2_11a_ratio: Option<f64>,
    pub rejected_ac2_19: bool,
}

/// Evaluate one candidate at one RNG seed. `ac2_19` is analytical; band/session vary with `seed`.
pub fn evaluate_trial(
    p_short: f64,
    q10: f64,
    delta_c: f64,
    seed: u64,
    include_ac2_11a: bool,
) -> JointCalibTrialMetrics {
    let mut model = configured_model(p_short, q10, delta_c);
    let ac2_19_margin = ac2_19_min_margin(&mut model);
    let rejected_ac2_19 = ac2_19_margin <= 0.0;
    let (p50, pct_60_90) = if rejected_ac2_19 {
        (0.0, 0.0)
    } else {
        truth_band_seeded(&model, seed)
    };
    let session_f = if rejected_ac2_19 {
        0.0
    } else {
        session_weighted_mean_f_seeded(&model, seed)
    };
    let ac2_11a = if !rejected_ac2_19 && include_ac2_11a {
        Some(ac2_11a_ratio(&mut model))
    } else {
        None
    };
    JointCalibTrialMetrics {
        p_short,
        q10,
        delta_c,
        seed,
        ac2_19_margin,
        p50,
        pct_60_90,
        session_f,
        ac2_11a_ratio: ac2_11a,
        rejected_ac2_19,
    }
}

/// Fast gates used before optional ac2_11a on grid survivors.
pub fn passes_fast_gates(metrics: &JointCalibTrialMetrics) -> bool {
    !metrics.rejected_ac2_19
        && metrics.session_f >= 0.55
        && metrics.p50 >= 0.65
        && metrics.pct_60_90 >= 0.45
}

/// Whether ac2_11a passes the T-163 ladder ratio gate.
pub fn passes_ac2_11a(metrics: &JointCalibTrialMetrics) -> bool {
    metrics
        .ac2_11a_ratio
        .is_some_and(|r| r >= AC2_11A_MIN_RATIO)
}
