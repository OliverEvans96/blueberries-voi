//! T-163 Phase 1 — freshness realism + knowledge-ladder belief-bias diagnostic.
//!
//! Independent (non-gating) exploratory diagnostic for the arrival-breaks Phase 1
//! notebook. Dumps a single JSON blob to stdout: multilot generative truth arrival-f
//! distribution, per-lot ladder bias/width across the three `ArrivalCondition` rungs
//! (Prior / Duration / Exposure), and a small parameter-sensitivity sweep (arrival
//! reference life, corridor duration scale) evaluated with the *unmodified* embedded
//! artifact plus in-memory field overrides — never writes `arrival_model.json`.
//!
//! Run: `cargo run -p voi_core --release --example t163_phase1_realism_diag > out.json`

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};

const CORRIDOR: &str = "abdella_all";
const UNITS_PER_LOT: usize = 45;
const N_DELIVERIES_TRUTH: usize = 500;
const N_DELIVERIES_LADDER: usize = 30;
const GRID_LEN: usize = 48;

fn quantiles(sorted: &[f64]) -> (f64, f64, f64, f64) {
    let n = sorted.len();
    let mean = sorted.iter().sum::<f64>() / n as f64;
    (mean, sorted[n / 10], sorted[n / 2], sorted[n * 9 / 10])
}

fn sd(values: &[f64], mean: f64) -> f64 {
    let n = values.len() as f64;
    (values.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n).sqrt()
}

/// Multilot generative truth: one mean-f sample per delivery (all lots pooled).
fn truth_multilot_delivery_means(model: &ArrivalModel, n: usize, seed: u64) -> Vec<f64> {
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    (0..n)
        .map(|_| {
            let draw = model.draw_truth_multilot_delivery_biased(
                CORRIDOR,
                UNITS_PER_LOT,
                0.0,
                &mut rng_d,
                &mut rng_t,
                &mut rng_p,
                &mut rng_g,
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

fn truth_summary(model: &ArrivalModel, n: usize, seed: u64) -> serde_json::Value {
    let mut samples = truth_multilot_delivery_means(model, n, seed);
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let (mean, p10, p50, p90) = quantiles(&samples);
    let pct_below_0_5 =
        samples.iter().filter(|&&f| f < 0.5).count() as f64 / n as f64;
    let pct_60_90 = samples
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / n as f64;
    json!({
        "n": n,
        "mean": mean,
        "sd": sd(&samples, mean),
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "pct_below_0_5": pct_below_0_5 * 100.0,
        "pct_60_90": pct_60_90 * 100.0,
        "samples": samples,
    })
}

/// Per-lot ladder diagnostic: for each drawn lot, compare truth mean_f against the
/// analytic rung law mean_f/sd_f under Prior / Duration(pack_date) / Exposure(lambda).
fn ladder_diagnostic(model: &ArrivalModel, n_deliveries: usize, seed: u64) -> serde_json::Value {
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);

    let prior_law = model.rung_law_on_grid(ArrivalCondition::Prior, CORRIDOR, GRID_LEN);

    let mut truth = Vec::new();
    let mut pred_p0 = Vec::new();
    let mut pred_f2 = Vec::new();
    let mut pred_f3 = Vec::new();
    let mut sd_f2 = Vec::new();
    let mut sd_f3 = Vec::new();
    let mut atom_f2 = Vec::new();
    let mut atom_f3 = Vec::new();
    let mut pack_dates = Vec::new();
    let mut lambdas = Vec::new();

    for _ in 0..n_deliveries {
        let draw = model.draw_truth_multilot_delivery_biased(
            CORRIDOR,
            UNITS_PER_LOT,
            0.0,
            &mut rng_d,
            &mut rng_t,
            &mut rng_p,
            &mut rng_g,
        );
        for lot in &draw.lots {
            let t = lot.unit_f.iter().sum::<f64>() / lot.unit_f.len() as f64;
            let f2_law = model.rung_law_on_grid(
                ArrivalCondition::Duration(lot.pack_date_days),
                CORRIDOR,
                GRID_LEN,
            );
            let f3_law =
                model.rung_law_on_grid(ArrivalCondition::Exposure(lot.lambda), CORRIDOR, GRID_LEN);

            truth.push(t);
            pred_p0.push(prior_law.mean_f);
            pred_f2.push(f2_law.mean_f);
            pred_f3.push(f3_law.mean_f);
            sd_f2.push(f2_law.sd_f);
            sd_f3.push(f3_law.sd_f);
            atom_f2.push(f2_law.atom_f0);
            atom_f3.push(f3_law.atom_f0);
            pack_dates.push(lot.pack_date_days);
            lambdas.push(lot.lambda);
        }
    }

    let n = truth.len() as f64;
    let mae = |pred: &[f64]| -> f64 {
        pred.iter()
            .zip(truth.iter())
            .map(|(p, t)| (p - t).abs())
            .sum::<f64>()
            / n
    };
    let bias = |pred: &[f64]| -> f64 {
        pred.iter()
            .zip(truth.iter())
            .map(|(p, t)| p - t)
            .sum::<f64>()
            / n
    };
    let avg = |xs: &[f64]| -> f64 { xs.iter().sum::<f64>() / xs.len() as f64 };

    let truth_mean = avg(&truth);
    let mae_p0 = mae(&pred_p0);
    let mae_f2 = mae(&pred_f2);
    let mae_f3 = mae(&pred_f3);

    json!({
        "n_lots": truth.len(),
        "truth": truth,
        "pred_p0": pred_p0,
        "pred_f2": pred_f2,
        "pred_f3": pred_f3,
        "sd_f2": sd_f2,
        "sd_f3": sd_f3,
        "atom_f2": atom_f2,
        "atom_f3": atom_f3,
        "pack_date_days": pack_dates,
        "lambda": lambdas,
        "truth_mean": truth_mean,
        "truth_sd": sd(&truth, truth_mean),
        "prior_mean_f": prior_law.mean_f,
        "prior_sd_f": prior_law.sd_f,
        "prior_atom_f0": prior_law.atom_f0,
        "mae_p0": mae_p0,
        "mae_f2": mae_f2,
        "mae_f3": mae_f3,
        "bias_p0": bias(&pred_p0),
        "bias_f2": bias(&pred_f2),
        "bias_f3": bias(&pred_f3),
        "avg_sd_f2": avg(&sd_f2),
        "avg_sd_f3": avg(&sd_f3),
        "ratio_p0_f2": mae_p0 / mae_f2.max(1e-12),
        "ratio_f2_f3": mae_f2 / mae_f3.max(1e-12),
    })
}

/// Sensitivity sweep: hold everything except `reference_life_days` (and the
/// dependent `gamma_scale = 1/(k * eta_ref)`) fixed, recompute truth + Prior summary.
/// Field mutation only — never touches the committed artifact on disk.
fn eta_ref_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &eta_ref in &[10.0, 14.0, 18.0, 22.0, 26.0, 30.0] {
        let mut model = base.clone();
        model.reference_life_days = eta_ref;
        model.gamma_scale = 1.0 / (model.gamma_shape * eta_ref);
        let mut samples = truth_multilot_delivery_means(&model, 300, 900_100 + eta_ref as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 =
            samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        let prior = model.rung_law_on_grid(ArrivalCondition::Prior, CORRIDOR, GRID_LEN);
        rows.push(json!({
            "eta_ref_arrival": eta_ref,
            "gamma_scale": model.gamma_scale,
            "truth_mean": mean,
            "truth_p50": p50,
            "truth_pct_below_0_5": pct_below_0_5 * 100.0,
            "prior_mean_f": prior.mean_f,
            "prior_atom_f0": prior.atom_f0,
        }));
    }
    json!(rows)
}

/// Sensitivity sweep: scale the `abdella_all` corridor's duration law toward shorter
/// (more domestic-transit-like) hauls, holding `eta_ref = 14` (unified with in-store
/// aging, i.e. testing whether a shorter/more-realistic corridor — rather than a
/// decoupled arrival reference life — can reach a realistic arrival-f band.
fn duration_scale_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &frac in &[1.0, 0.75, 0.5, 0.35, 0.25] {
        let mut model = base.clone();
        model.reference_life_days = 14.0;
        model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
        if let Some(c) = model.corridors.get_mut(CORRIDOR) {
            c.d_min *= frac;
            c.delay_scale *= frac;
        }
        let mut samples = truth_multilot_delivery_means(&model, 300, 900_200 + (frac * 1000.0) as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 =
            samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        let mean_d = model.corridor(CORRIDOR).d_min
            + model.corridor(CORRIDOR).delay_shape * model.corridor(CORRIDOR).delay_scale;
        rows.push(json!({
            "duration_scale_frac": frac,
            "implied_mean_duration_days": mean_d,
            "truth_mean": mean,
            "truth_p50": p50,
            "truth_pct_below_0_5": pct_below_0_5 * 100.0,
        }));
    }
    json!(rows)
}

fn main() {
    let t0 = std::time::Instant::now();
    let model = ArrivalModel::embedded();
    eprintln!("embedded: {:?}", t0.elapsed());

    let artifact_summary = json!({
        "reference_life_days": model.reference_life_days,
        "gamma_shape": model.gamma_shape,
        "gamma_scale": model.gamma_scale,
        "q10": model.q10,
        "t_ref": model.t_ref,
        "t_break": model.t_break,
        "rho": model.rho,
        "tau_bar": model.tau_bar,
        "sigma_pos": model.sigma_pos,
        "corridor_abdella_all": {
            "d_min": model.corridor(CORRIDOR).d_min,
            "delay_shape": model.corridor(CORRIDOR).delay_shape,
            "delay_scale": model.corridor(CORRIDOR).delay_scale,
        },
    });

    let truth_multilot = truth_summary(&model, N_DELIVERIES_TRUTH, 163_601);
    eprintln!("truth_summary: {:?}", t0.elapsed());
    // Seed-stability check: same N as the gating test (400), five independent seeds,
    // to see how much the p50 gate estimate itself moves under CRN reseeding.
    let seed_stability: Vec<serde_json::Value> = [163_501u64, 271_828, 314_159, 555_001, 999_331]
        .iter()
        .map(|&s| {
            let summ = truth_summary(&model, 400, s);
            json!({"seed": s, "p50": summ["p50"], "mean": summ["mean"]})
        })
        .collect();
    eprintln!("seed_stability: {:?}", t0.elapsed());
    let ladder = ladder_diagnostic(&model, N_DELIVERIES_LADDER, 163_602);
    eprintln!("ladder_diagnostic: {:?}", t0.elapsed());
    let sensitivity_eta_ref = eta_ref_sensitivity(&model);
    eprintln!("eta_ref_sensitivity: {:?}", t0.elapsed());
    let sensitivity_duration_scale = duration_scale_sensitivity(&model);
    eprintln!("duration_scale_sensitivity: {:?}", t0.elapsed());

    let out = json!({
        "artifact": artifact_summary,
        "truth_multilot": truth_multilot,
        "seed_stability": seed_stability,
        "ladder": ladder,
        "sensitivity_eta_ref": sensitivity_eta_ref,
        "sensitivity_duration_scale": sensitivity_duration_scale,
    });

    println!("{}", serde_json::to_string(&out).unwrap());
}
