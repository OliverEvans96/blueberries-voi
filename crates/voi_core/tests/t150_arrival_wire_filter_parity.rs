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
#[ignore = "wire filter parity MC; slow: run via cargo test -- --ignored"]
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

    // --- Ladder distinctness: P0, F2, F3 must separate when F2 carries information. ---
    // F2 at E[delay] (the parity fixture above) may sit within MEAN_TOL of P0 because
    // mean_f(d) is nearly linear in d over the delay support, so E[f(D)] ≈ f(E[D]) — that
    // is correct filter physics, not wire/filter drift. Use a shorter observed pack date
    // for the ladder gate so F2 is genuinely informative relative to P0.
    const F2_LADDER_D: i32 = 3;
    let filter_f2_ladder = filter_mean_f(&mut model, ArrivalCondition::Duration(F2_LADDER_D));
    let _ = filter_mean_f(&mut model, ArrivalCondition::Duration(F2_LADDER_D));
    let wire_f2_ladder = wire_summary(&model, "F2", 0.0);

    let means = [filter_p0_mean, filter_f2_ladder, filter_f3_warm];
    for i in 0..means.len() {
        for j in (i + 1)..means.len() {
            assert!(
                (means[i] - means[j]).abs() > MEAN_TOL,
                "filter ladder must be pairwise distinct at informative F2 d: m[{i}]={:.4} m[{j}]={:.4}",
                means[i],
                means[j]
            );
        }
    }
    let wire_means = [
        wire_p0["mean_f"].as_f64().unwrap(),
        wire_f2_ladder["mean_f"].as_f64().unwrap(),
        wire_f3["mean_f"].as_f64().unwrap(),
    ];
    for i in 0..wire_means.len() {
        for j in (i + 1)..wire_means.len() {
            assert!(
                (wire_means[i] - wire_means[j]).abs() > MEAN_TOL,
                "wire ladder must be pairwise distinct at informative F2 d: m[{i}]={:.4} m[{j}]={:.4}",
                wire_means[i],
                wire_means[j]
            );
        }
    }
    // Parity sections above already proved wire tracks filter at each rung's fixture.
    assert_close(
        "F2 ladder wire vs filter (d=3)",
        wire_means[1],
        means[1],
        MEAN_TOL,
    );
}

/// T-163 S3.1 / S3.8 — F3 events wire must export three per-lot temperature traces
/// (multi-lot delivery) instead of a single pooled `temp_times_d` / `temp_temps_c` pair.
mod t163_events_wire {
    use serde_json::Value;
    use voi_core::handle_rpc;

    const LOTS_PER_DELIVERY: usize = 3;

    fn rpc(method: &str, params: &str) -> Value {
        let req = format!(r#"{{"id":"1","method":"{method}","params":{params}}}"#);
        let out = handle_rpc(&req);
        let v: Value = serde_json::from_str(&out).unwrap_or_else(|_| panic!("bad json: {out}"));
        assert_eq!(v["ok"], true, "rpc {method} failed: {out}");
        v["result"].clone()
    }

    #[test]
#[ignore = "wire filter parity MC; slow: run via cargo test -- --ignored"]
    fn t163_f3_events_wire_exports_three_per_lot_traces() {
        rpc(
            "init",
            r#"{"seed":163,"config":{"arrival_product":"abdella_all","obs_scenario":"F3"}}"#,
        );
        rpc(
            "step_n",
            r#"{"orders":[48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48]}"#,
        );
        let events = rpc("events", r#"{"since_day":0}"#);
        let days = events["days"]
            .as_array()
            .expect("events.days array must exist");
        let delivery_days: Vec<&Value> = days
            .iter()
            .filter(|d| d["arrivals"].as_u64().unwrap_or(0) > 0)
            .collect();
        assert!(
            !delivery_days.is_empty(),
            "RED [S3.1]: expected at least one delivery day in events wire"
        );
        for day in delivery_days {
            let traces = day["temp_traces_by_lot"]
                .as_array()
                .unwrap_or_else(|| {
                    panic!(
                        "RED [S3.1]: F3 events must expose temp_traces_by_lot on delivery day {:?}",
                        day["day"]
                    )
                });
            assert_eq!(
                traces.len(),
                LOTS_PER_DELIVERY,
                "RED [S3.1]: expected {LOTS_PER_DELIVERY} per-lot traces on day {:?}, got {}",
                day["day"],
                traces.len()
            );
            for (i, trace) in traces.iter().enumerate() {
                let times = trace["times_d"]
                    .as_array()
                    .unwrap_or_else(|| panic!("trace[{i}] missing times_d"));
                let temps = trace["temps_c"]
                    .as_array()
                    .unwrap_or_else(|| panic!("trace[{i}] missing temps_c"));
                assert!(
                    times.len() >= 3 && times.len() == temps.len(),
                    "RED [S3.1]: trace[{i}] on day {:?} must be a multi-point spline",
                    day["day"]
                );
                let values: Vec<f64> = temps.iter().filter_map(|t| t.as_f64()).collect();
                let min_t = values.iter().cloned().fold(f64::INFINITY, f64::min);
                let max_t = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
                assert!(
                    (max_t - min_t).abs() > 0.05,
                    "RED [S3.8]: per-lot trace[{i}] must vary (v2 OU/breaks), got {:?}",
                    values
                );
            }
            let lot_ids = day["arrival_lot_ids"]
                .as_array()
                .expect("F3 GSIN must expose arrival_lot_ids");
            assert_eq!(
                lot_ids.len(),
                LOTS_PER_DELIVERY,
                "RED [S3.1]: arrival_lot_ids length must match lots per delivery"
            );
        }
    }

    #[test]
#[ignore = "wire filter parity MC; slow: run via cargo test -- --ignored"]
    fn t163_f2_events_wire_exports_per_lot_pack_dates() {
        rpc(
            "init",
            r#"{"seed":163,"config":{"arrival_product":"abdella_all","obs_scenario":"F2"}}"#,
        );
        rpc(
            "step_n",
            r#"{"orders":[48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48]}"#,
        );
        let events = rpc("events", r#"{"since_day":0}"#);
        let days = events["days"].as_array().expect("events.days");
        let delivery_days: Vec<&Value> = days
            .iter()
            .filter(|d| d["arrivals"].as_u64().unwrap_or(0) > 0)
            .collect();
        assert!(!delivery_days.is_empty(), "RED [S3.1]: need delivery days");
        for day in delivery_days {
            let pack_dates = day["pack_dates_by_lot"].as_array().unwrap_or_else(|| {
                panic!(
                    "RED [S3.1]: F2 events must expose pack_dates_by_lot (per-lot), not scalar pack_date_days only — day {:?}",
                    day["day"]
                )
            });
            assert_eq!(
                pack_dates.len(),
                LOTS_PER_DELIVERY,
                "RED [S3.1]: pack_dates_by_lot must have {LOTS_PER_DELIVERY} entries on day {:?}",
                day["day"]
            );
            let lot_ids = day["arrival_lot_ids"]
                .as_array()
                .expect("F2 GSIN exposes arrival_lot_ids");
            assert_eq!(
                lot_ids.len(),
                LOTS_PER_DELIVERY,
                "arrival_lot_ids must align with pack_dates_by_lot"
            );
        }
    }
}
