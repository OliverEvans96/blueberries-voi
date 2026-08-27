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
use rand_distr::{Distribution, LogNormal};
use rand_pcg::Pcg64;
use serde_json::json;
use voi_core::arrival::{split_delivery_qty, ArrivalCondition, ArrivalModel, LOTS_PER_DELIVERY};

/// Mirrors the private `SHARED_LEG_FRAC` in `crates/voi_core/src/arrival.rs` (line 38),
/// whose own doc comment says "remainder is upstream per lot" — i.e. the documented
/// intent is that a lot's own upstream duration is `(1 - SHARED_LEG_FRAC)` of *one*
/// corridor-typical trip, not a second, independent, full-length draw.
const SHARED_LEG_FRAC: f64 = 0.28;

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

/// Sensitivity sweep: hold `eta_ref = 14` (unified) and the full Abdella-fit corridor
/// duration fixed, vary only `gamma_shape` (k). Because the arrival draw derives
/// `gamma_scale = 1/(k * eta_ref)`, `mean(D | Lambda) = k*Lambda*theta = Lambda/eta_ref`
/// is exactly `k`-invariant — this sweep exists to demonstrate that algebraically, not to
/// find a value that moves the mean/median (it can't). What `k` *does* move is the
/// variance/atom mass around that fixed mean.
fn gamma_shape_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &k in &[0.5, 1.0, 2.0, 4.0, 8.0] {
        let mut model = base.clone();
        model.reference_life_days = 14.0;
        model.gamma_shape = k;
        model.gamma_scale = 1.0 / (k * 14.0);
        let mut samples = truth_multilot_delivery_means(&model, 300, 900_300 + (k * 100.0) as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 =
            samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        let prior = model.rung_law_on_grid(ArrivalCondition::Prior, CORRIDOR, GRID_LEN);
        rows.push(json!({
            "gamma_shape": k,
            "truth_mean": mean,
            "truth_p50": p50,
            "truth_sd": sd(&samples, mean),
            "truth_pct_below_0_5": pct_below_0_5 * 100.0,
            "prior_atom_f0": prior.atom_f0,
        }));
    }
    json!(rows)
}

/// Sensitivity sweep: hold `eta_ref = 14` and the full corridor duration fixed, vary only
/// `q10`. NOTE: in production, `ArrivalModel::sync_params` forces `self.q10 =
/// params.q10`, i.e. the transit and in-store Q10 are already the *same* number by
/// construction — this sweep is exploring "what if that shared Q10 were lower", which
/// would change in-store aging's temperature sensitivity too, not just transit.
fn q10_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &q10 in &[1.0, 1.5, 2.0, 2.5, 3.0] {
        let mut model = base.clone();
        model.reference_life_days = 14.0;
        model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
        model.q10 = q10;
        let mut samples = truth_multilot_delivery_means(&model, 300, 900_400 + (q10 * 100.0) as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 =
            samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        rows.push(json!({
            "q10": q10,
            "truth_mean": mean,
            "truth_p50": p50,
            "truth_pct_below_0_5": pct_below_0_5 * 100.0,
        }));
    }
    json!(rows)
}

/// Sensitivity sweep: hold `eta_ref = 14`, full corridor duration, and `q10 = 3.0`
/// (current) fixed, shift every leg setpoint colder by a uniform `delta_c`. Leg
/// setpoints are arrival-only (no coupling to store aging), and the artifact provenance
/// already documents them as "ASSUMED anchors", not fit from the six shipments — so this
/// is the one lever here with no offsetting external-data or store-physics cost.
fn leg_setpoint_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &delta_c in &[0.0, -1.0, -2.0, -3.0, -4.0] {
        let mut model = base.clone();
        model.reference_life_days = 14.0;
        model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
        for leg in model.legs.iter_mut() {
            leg.setpoint_c += delta_c;
        }
        let mut samples =
            truth_multilot_delivery_means(&model, 300, 900_500 + (-delta_c * 100.0) as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 =
            samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        rows.push(json!({
            "delta_c": delta_c,
            "leg_setpoints_c": model.legs.iter().map(|l| l.setpoint_c).collect::<Vec<_>>(),
            "truth_mean": mean,
            "truth_p50": p50,
            "truth_pct_below_0_5": pct_below_0_5 * 100.0,
        }));
    }
    json!(rows)
}

/// One joint scenario: combine a literature-supported lower `q10` with a modest,
/// still-plausible-for-reefer-transport leg-setpoint shift, holding `eta_ref = 14`
/// (unified) and the full Abdella-fit corridor duration (unchanged, so it still matches
/// the external dataset). Tests whether a *combination* of small, individually-defensible
/// changes reaches the target band where no single lever alone did (see notebook §3/§7).
fn joint_realistic_recalibration(base: &ArrivalModel) -> serde_json::Value {
    let mut model = base.clone();
    model.reference_life_days = 14.0;
    model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
    model.q10 = 2.0;
    for leg in model.legs.iter_mut() {
        leg.setpoint_c -= 1.0;
    }
    let mut samples = truth_multilot_delivery_means(&model, 500, 900_600);
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let (mean, p10, p50, p90) = quantiles(&samples);
    let pct_below_0_5 = samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
    let pct_60_90 = samples
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / samples.len() as f64;
    json!({
        "eta_ref": model.reference_life_days,
        "q10": model.q10,
        "leg_setpoints_c": model.legs.iter().map(|l| l.setpoint_c).collect::<Vec<_>>(),
        "corridor_unchanged": true,
        "truth_mean": mean,
        "truth_p10": p10,
        "truth_p50": p50,
        "truth_p90": p90,
        "truth_pct_below_0_5": pct_below_0_5 * 100.0,
        "truth_pct_60_90": pct_60_90 * 100.0,
    })
}

/// Direct measurement: does the multilot truth path's mean per-lot calendar duration
/// match the single-lot path's mean duration (both should equal the moment-matched
/// `abdella_all` corridor mean, `d_min + delay_shape*delay_scale`, if "remainder is
/// upstream per lot" is actually implemented)?
fn shared_leg_duration_audit(model: &ArrivalModel) -> serde_json::Value {
    let corridor = model.corridor(CORRIDOR);
    let corridor_mean_d = corridor.d_min + corridor.delay_shape * corridor.delay_scale;

    let n = 3000usize;
    let mut rng_d = Pcg64::seed_from_u64(700_001);
    let mut rng_t = Pcg64::seed_from_u64(700_002);
    let mut rng_p = Pcg64::seed_from_u64(700_003);
    let mut rng_g = Pcg64::seed_from_u64(700_004);

    let mut single_d = Vec::with_capacity(n);
    let mut single_lambda = Vec::with_capacity(n);
    for _ in 0..n {
        let draw = model.draw_truth_delivery(CORRIDOR, 1, &mut rng_d, &mut rng_t, &mut rng_p, &mut rng_g);
        single_d.push(draw.duration_d);
        single_lambda.push(draw.lambda);
    }

    let mut multi_d = Vec::with_capacity(n * LOTS_PER_DELIVERY);
    let mut multi_lambda = Vec::with_capacity(n * LOTS_PER_DELIVERY);
    for _ in 0..n {
        let draw = model.draw_truth_multilot_delivery_biased(
            CORRIDOR, UNITS_PER_LOT, 0.0, &mut rng_d, &mut rng_t, &mut rng_p, &mut rng_g,
        );
        for lot in &draw.lots {
            multi_d.push(lot.duration_d);
            multi_lambda.push(lot.lambda);
        }
    }

    let mean = |xs: &[f64]| xs.iter().sum::<f64>() / xs.len() as f64;
    let single_mean_d = mean(&single_d);
    let multi_mean_d = mean(&multi_d);
    json!({
        "corridor_theoretical_mean_duration_days": corridor_mean_d,
        "single_lot_mean_duration_days": single_mean_d,
        "multilot_per_lot_mean_duration_days": multi_mean_d,
        "multilot_vs_single_lot_duration_ratio": multi_mean_d / single_mean_d,
        "multilot_vs_corridor_theoretical_ratio": multi_mean_d / corridor_mean_d,
        "single_lot_mean_lambda": mean(&single_lambda),
        "multilot_per_lot_mean_lambda": mean(&multi_lambda),
        "multilot_vs_single_lot_lambda_ratio": mean(&multi_lambda) / mean(&single_lambda),
    })
}

/// Reconstruct the multilot truth draw with the shared-leg fraction applied as its own
/// doc comment describes ("remainder is upstream per lot"): `upstream_d = corridor_draw *
/// (1 - SHARED_LEG_FRAC)` instead of a full second independent corridor draw, so
/// `E[total_d] = E[upstream_d] + E[shared_d] = E[corridor_draw]` (no inflation). Uses only
/// public `ArrivalModel` API (`draw_bottom_up_duration`, `draw_break_taus`,
/// `lambda_from_breaks`, `phi_set`) plus a plain `LogNormal(0, sigma_pos)` psi draw
/// (the documented formula) — this does *not* patch `arrival.rs`, it's a diagnostic
/// side-by-side reconstruction to quantify the effect of the fix without applying it.
fn corrected_multilot_truth_means(model: &ArrivalModel, n: usize, seed: u64) -> Vec<f64> {
    let corridor = model.corridor(CORRIDOR);
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    let psi_dist = LogNormal::new(0.0, model.sigma_pos).expect("lognormal psi");

    (0..n)
        .map(|_| {
            let shared_d = model.draw_bottom_up_duration(corridor, &mut rng_d) * SHARED_LEG_FRAC;
            let arrivals_by = split_delivery_qty(UNITS_PER_LOT, LOTS_PER_DELIVERY);
            let mut total_units = 0usize;
            let mut total_f = 0.0;
            for &units in &arrivals_by {
                let upstream_d =
                    model.draw_bottom_up_duration(corridor, &mut rng_d) * (1.0 - SHARED_LEG_FRAC);
                let total_d = (upstream_d + shared_d).max(0.5);
                let taus = model.draw_break_taus(total_d, &mut rng_t);
                let lot_lambda = ArrivalModel::floor_lambda(model.lambda_from_breaks(total_d, &taus));
                for _ in 0..units {
                    let psi = psi_dist.sample(&mut rng_p).max(1e-6);
                    let lambda = ArrivalModel::floor_lambda(lot_lambda * psi);
                    let loss = rand_distr::Gamma::new(model.gamma_shape * lambda, model.gamma_scale)
                        .expect("loss gamma")
                        .sample(&mut rng_g);
                    total_f += (1.0 - loss).max(0.0);
                    total_units += 1;
                }
            }
            total_f / total_units as f64
        })
        .collect()
}

fn corrected_shared_leg_sensitivity(base: &ArrivalModel) -> serde_json::Value {
    let mut rows = Vec::new();
    for &eta_ref in &[14.0, 20.0, 26.0] {
        let mut model = base.clone();
        model.reference_life_days = eta_ref;
        model.gamma_scale = 1.0 / (model.gamma_shape * eta_ref);
        let mut samples = corrected_multilot_truth_means(&model, 500, 900_700 + eta_ref as u64);
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let (mean, _p10, p50, _p90) = quantiles(&samples);
        let pct_below_0_5 = samples.iter().filter(|&&f| f < 0.5).count() as f64 / samples.len() as f64;
        let pct_60_90 = samples
            .iter()
            .filter(|&&f| (0.6..=0.9).contains(&f))
            .count() as f64
            / samples.len() as f64;
        rows.push(json!({
            "eta_ref_arrival": eta_ref,
            "corrected_truth_mean": mean,
            "corrected_truth_p50": p50,
            "corrected_truth_pct_below_0_5": pct_below_0_5 * 100.0,
            "corrected_truth_pct_60_90": pct_60_90 * 100.0,
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
    let sensitivity_gamma_shape = gamma_shape_sensitivity(&model);
    eprintln!("gamma_shape_sensitivity: {:?}", t0.elapsed());
    let sensitivity_q10 = q10_sensitivity(&model);
    eprintln!("q10_sensitivity: {:?}", t0.elapsed());
    let sensitivity_leg_setpoint = leg_setpoint_sensitivity(&model);
    eprintln!("leg_setpoint_sensitivity: {:?}", t0.elapsed());
    let joint_recalibration = joint_realistic_recalibration(&model);
    eprintln!("joint_realistic_recalibration: {:?}", t0.elapsed());
    let shared_leg_audit = shared_leg_duration_audit(&model);
    eprintln!("shared_leg_duration_audit: {:?}", t0.elapsed());
    let corrected_shared_leg = corrected_shared_leg_sensitivity(&model);
    eprintln!("corrected_shared_leg_sensitivity: {:?}", t0.elapsed());

    let out = json!({
        "artifact": artifact_summary,
        "truth_multilot": truth_multilot,
        "seed_stability": seed_stability,
        "ladder": ladder,
        "sensitivity_eta_ref": sensitivity_eta_ref,
        "sensitivity_duration_scale": sensitivity_duration_scale,
        "sensitivity_gamma_shape": sensitivity_gamma_shape,
        "sensitivity_q10": sensitivity_q10,
        "sensitivity_leg_setpoint": sensitivity_leg_setpoint,
        "joint_recalibration": joint_recalibration,
        "shared_leg_duration_audit": shared_leg_audit,
        "corrected_shared_leg_sensitivity": corrected_shared_leg,
    });

    println!("{}", serde_json::to_string(&out).unwrap());
}
