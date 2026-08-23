//! T-150 — wire/filter parity guard (qa).
//!
//! `arrival_wire.rs` must publish the same arrival law the filter uses in `arrival.rs`.
//! Session-free AC2.11a / AC2.19 exercise only the filter path; this file closes the gap
//! that let a second, incorrect integration reach the studio chart.

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};
use voi_core::arrival_wire::arrival_summary_wire;
use voi_core::obs::channels_for_preset;
use voi_core::shipments::{arrival_exposure_from_path, ShipmentTrace};

const PRODUCT: &str = "abdella_all";
const MEAN_TOL: f64 = 0.02;
const SD_TOL: f64 = 0.025;
const CDF_TOL: f64 = 0.03;
const ATOM_TOL: f64 = 0.02;

fn expected_delay(corridor: &voi_core::arrival::ArrivalCorridor) -> f64 {
    corridor.d_min + corridor.delay_shape * corridor.delay_scale
}

fn wire_summary(
    model: &ArrivalModel,
    preset: &str,
    transit_temp_bias_c: f64,
) -> serde_json::Value {
    let channels = channels_for_preset(preset).expect("known preset");
    arrival_summary_wire(model, PRODUCT, channels, transit_temp_bias_c)
}

fn filter_mean_f(model: &mut ArrivalModel, condition: ArrivalCondition) -> f64 {
    model.filter_law_mean_f(condition)
}

fn filter_sd_and_atom(model: &mut ArrivalModel, condition: ArrivalCondition) -> (f64, f64) {
    let mut rng = Pcg64::seed_from_u64(150_331);
    let n = 25_000usize;
    let mut samples = Vec::with_capacity(n);
    for _ in 0..n {
        samples.push(model.sample_filter_birth_units(condition, 1, &mut rng)[0]);
    }
    let atom = samples.iter().filter(|&&f| f <= 0.0).count() as f64 / n as f64;
    let mean = samples.iter().sum::<f64>() / n as f64;
    let var = samples
        .iter()
        .map(|x| (x - mean).powi(2))
        .sum::<f64>()
        / n as f64;
    (var.sqrt(), atom)
}

fn filter_empirical_cdf(
    model: &mut ArrivalModel,
    condition: ArrivalCondition,
    f_grid: &[f64],
) -> Vec<f64> {
    let mut rng = Pcg64::seed_from_u64(150_332);
    let n = 30_000usize;
    let mut samples = Vec::with_capacity(n);
    for _ in 0..n {
        samples.push(model.sample_filter_birth_units(condition, 1, &mut rng)[0]);
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    f_grid
        .iter()
        .map(|&f| {
            let hi = samples.partition_point(|&x| x <= f);
            hi as f64 / n as f64
        })
        .collect()
}

fn wire_cdf_at(summary: &serde_json::Value, f: f64) -> f64 {
    summary["curve"]
        .as_array()
        .expect("curve array")
        .iter()
        .find(|pt| (pt["f"].as_f64().unwrap() - f).abs() < 1e-9)
        .and_then(|pt| pt["cdf"].as_f64())
        .unwrap_or_else(|| panic!("wire curve missing f={f}"))
}

fn assert_close(label: &str, got: f64, want: f64, tol: f64) {
    let delta = (got - want).abs();
    assert!(
        delta <= tol,
        "RED [{label}]: wire/filter parity — got {got:.4}, want {want:.4} (|Δ|={delta:.4}, tol={tol})"
    );
}

/// Wire chart summaries must match the filter's channel-conditional arrival laws.
#[test]
fn t150_wire_filter_parity_guard() {
    let mut model = ArrivalModel::embedded();
    let corridor = model.corridor(PRODUCT).clone();
    let pack_date_days = expected_delay(&corridor).round() as i32;

    // --- P0: atom-inclusive mean_f and full prior law (catches d_min double-count,
    // uniform d/T̄, missing Φ⁻¹ on psi_pos, and E[f|f>0] vs E[f] atom convention). ---
    let wire_p0 = wire_summary(&model, "P0", 0.0);
    let filter_p0_mean = filter_mean_f(&mut model, ArrivalCondition::Prior);
    let (filter_p0_sd, filter_p0_atom) =
        filter_sd_and_atom(&mut model, ArrivalCondition::Prior);
    assert_close(
        "P0 mean_f (atom-inclusive)",
        wire_p0["mean_f"].as_f64().unwrap(),
        filter_p0_mean,
        MEAN_TOL,
    );
    assert_close(
        "P0 sd_f (psi_pos / T̄ laws)",
        wire_p0["sd_f"].as_f64().unwrap(),
        filter_p0_sd,
        SD_TOL,
    );
    assert_close(
        "P0 f_zero atom",
        wire_p0["f_zero"].as_f64().unwrap(),
        filter_p0_atom,
        ATOM_TOL,
    );

    let cdf_f_grid = [0.0, 0.2, 0.4, 0.6, 0.8];
    let filter_p0_cdf = filter_empirical_cdf(&mut model, ArrivalCondition::Prior, &cdf_f_grid);
    for (&f, &emp) in cdf_f_grid.iter().zip(filter_p0_cdf.iter()) {
        assert_close(
            &format!("P0 CDF at f={f:.1} (transit quadrature)"),
            wire_cdf_at(&wire_p0, f),
            emp,
            CDF_TOL,
        );
    }

    // --- F2: duration-conditioned law at the pack-date rung. ---
    let wire_f2 = wire_summary(&model, "F2", 0.0);
    let f2_condition = ArrivalCondition::Duration(pack_date_days);
    let filter_f2_mean = filter_mean_f(&mut model, f2_condition);
    let (filter_f2_sd, filter_f2_atom) = filter_sd_and_atom(&mut model, f2_condition);
    assert_close(
        "F2 mean_f",
        wire_f2["mean_f"].as_f64().unwrap(),
        filter_f2_mean,
        MEAN_TOL,
    );
    assert_close(
        "F2 sd_f",
        wire_f2["sd_f"].as_f64().unwrap(),
        filter_f2_sd,
        SD_TOL,
    );
    assert_close(
        "F2 f_zero",
        wire_f2["f_zero"].as_f64().unwrap(),
        filter_f2_atom,
        ATOM_TOL,
    );

    // --- F3: exposure-conditioned law must track Λ, not a prior-mean φ̄ pin (ADR 0144 C1). ---
    let q10 = model.q10;
    let t_ref = model.t_ref;
    let trace_cool = ShipmentTrace {
        times_d: vec![0.0, 5.0],
        temps_c: vec![1.0, 1.0],
    };
    let trace_warm = ShipmentTrace {
        times_d: vec![0.0, 5.0],
        temps_c: vec![6.5, 6.5],
    };
    let lambda_cool =
        arrival_exposure_from_path(&trace_cool.temps_c, &trace_cool.times_d, q10, t_ref);
    let lambda_warm =
        arrival_exposure_from_path(&trace_warm.temps_c, &trace_warm.times_d, q10, t_ref);
    assert!(
        (lambda_warm - lambda_cool).abs() > 0.4,
        "fixture: cool vs warm exposures must differ (cool={lambda_cool:.3}, warm={lambda_warm:.3})"
    );

    let filter_f3_cool = filter_mean_f(&mut model, ArrivalCondition::Exposure(lambda_cool));
    let filter_f3_warm = filter_mean_f(&mut model, ArrivalCondition::Exposure(lambda_warm));
    assert!(
        (filter_f3_warm - filter_f3_cool).abs() > MEAN_TOL,
        "filter F3 must move with Λ (cool={filter_f3_cool:.4}, warm={filter_f3_warm:.4})"
    );

    let wire_f3 = wire_summary(&model, "F3", 0.0);
    // Warm trace is the "changed observation scenario" the user cares about.
    assert_close(
        "F3 mean_f at warm Λ (not prior-mean φ̄)",
        wire_f3["mean_f"].as_f64().unwrap(),
        filter_f3_warm,
        MEAN_TOL,
    );
    let (filter_f3_sd, filter_f3_atom) =
        filter_sd_and_atom(&mut model, ArrivalCondition::Exposure(lambda_warm));
    assert_close(
        "F3 sd_f at warm Λ",
        wire_f3["sd_f"].as_f64().unwrap(),
        filter_f3_sd,
        SD_TOL,
    );
    assert_close(
        "F3 f_zero at warm Λ",
        wire_f3["f_zero"].as_f64().unwrap(),
        filter_f3_atom,
        ATOM_TOL,
    );

    // --- Ladder distinctness: P0, F2, F3 pairwise different in the filter direction. ---
    let means = [filter_p0_mean, filter_f2_mean, filter_f3_warm];
    for i in 0..means.len() {
        for j in (i + 1)..means.len() {
            assert!(
                (means[i] - means[j]).abs() > MEAN_TOL,
                "filter ladder must be pairwise distinct: m[{i}]={:.4} m[{j}]={:.4}",
                means[i],
                means[j]
            );
        }
    }
    let wire_means = [
        wire_p0["mean_f"].as_f64().unwrap(),
        wire_f2["mean_f"].as_f64().unwrap(),
        wire_f3["mean_f"].as_f64().unwrap(),
    ];
    for i in 0..wire_means.len() {
        for j in (i + 1)..wire_means.len() {
            assert!(
                (wire_means[i] - wire_means[j]).abs() > MEAN_TOL,
                "wire ladder must be pairwise distinct: m[{i}]={:.4} m[{j}]={:.4}",
                wire_means[i],
                wire_means[j]
            );
        }
    }
    // Wire must track the same ordering as the filter on every rung.
    assert_close("P0 wire vs filter", wire_means[0], means[0], MEAN_TOL);
    assert_close("F2 wire vs filter", wire_means[1], means[1], MEAN_TOL);
    assert_close("F3 wire vs filter (warm Λ)", wire_means[2], means[2], MEAN_TOL);
}
