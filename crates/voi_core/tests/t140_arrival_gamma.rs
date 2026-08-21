//! T-140 Stage C — unified gamma-in-warped-time arrival (RED until implement).

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::params::ModelParams;
use voi_core::shipments::{
    calendar_transit_days, phi_bar_fleet, phi_bar_from_trace, birth_f_units_gamma, ShipmentTrace,
};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("read src/{name}: {err}"))
}

fn read_example(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("examples").join(name))
        .unwrap_or_else(|err| panic!("read examples/{name}: {err}"))
}

/// AC-1: gamma arrival exports exist; f2a_transit_uncertainty_sd removed from params.
#[test]
fn unified_arrival_exports_and_params_cleanup() {
    let shipments_src = read_src("shipments.rs");
    for sym in [
        "pub fn calendar_transit_days",
        "pub fn phi_bar_from_trace",
        "pub fn phi_bar_fleet",
        "pub fn birth_f_units_gamma",
    ] {
        assert!(
            shipments_src.contains(sym),
            "RED: shipments.rs must export {sym}"
        );
    }
    let params_src = read_src("params.rs");
    assert!(
        !params_src.contains("f2a_transit_uncertainty_sd"),
        "RED: ModelParams must drop f2a_transit_uncertainty_sd (ADR 0141)"
    );
}

/// AC-3: mix_arrival_f deleted from unit_pf.
#[test]
fn mix_arrival_f_removed_from_unit_pf() {
    let pf_src = read_src("unit_pf.rs");
    assert!(
        !pf_src.contains("fn mix_arrival_f"),
        "RED: unit_pf must not define mix_arrival_f"
    );
}

/// AC-2: pack_date uses calendar duration, not rounded warped tau.
#[test]
fn arrival_meta_emits_calendar_pack_date_not_rounded_tau() {
    let shipments_src = read_src("shipments.rs");
    assert!(
        shipments_src.contains("calendar_transit_days"),
        "RED: arrival_receipt_meta must use calendar_transit_days for pack_date_days"
    );
    assert!(
        !shipments_src.contains("tau.round() as i32"),
        "RED: pack_date_days must not be round(tau)"
    );
}

/// AC-4: thermal fleet has non-degenerate phi_bar.
#[test]
fn shipments_thermal_phi_bar_non_degenerate() {
    let diag_src = read_example("gsin_upc_diag.rs");
    assert!(
        diag_src.contains("fn shipments_thermal"),
        "RED: gsin_upc_diag must define shipments_thermal()"
    );
    // Compile-time hook: if shipments_thermal exists, phi_bar must vary.
    let traces = shipments_thermal_traces();
    let params = ModelParams::default();
    let phis = phi_bar_fleet(&traces, params.q10, params.t_ref_c);
    let distinct: std::collections::HashSet<_> = phis
        .iter()
        .map(|p| (p * 1e6).round() as i64)
        .collect();
    assert!(
        distinct.len() >= 2,
        "thermal fleet phi_bar must be non-degenerate, got {phis:?}"
    );
}

/// AC-1: gamma birth spreads units at fixed Lambda.
#[test]
fn birth_f_units_gamma_spreads_at_fixed_lambda() {
    let params = ModelParams::default();
    let lambda = 2.0;
    let n = 12usize;
    let mut spread = false;
    for seed in 0..50u64 {
        let mut rng = Pcg64::seed_from_u64(140_001 ^ seed);
        let values = birth_f_units_gamma(lambda, n, &params, &mut rng);
        assert_eq!(values.len(), n);
        for &f in &values {
            assert!(f > 0.0 && f <= 1.0, "f={f}");
        }
        let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
        let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        if (max - min) > 1e-6 {
            spread = true;
            break;
        }
    }
    assert!(spread, "gamma birth must spread units at Lambda={lambda}");
}

/// AC-6: F3 birth uses gamma draws — filter source references birth_f_units_gamma.
#[test]
fn unit_pf_f3_uses_gamma_birth_path() {
    let pf_src = read_src("unit_pf.rs");
    assert!(
        pf_src.contains("birth_f_units_gamma"),
        "RED: unit_pf filter birth must call birth_f_units_gamma"
    );
}

/// Stand-in until gsin_upc_diag exports shipments_thermal (RED uses inline traces).
fn shipments_thermal_traces() -> Vec<ShipmentTrace> {
    let d = 2.0;
    vec![
        ShipmentTrace {
            times_d: vec![0.0, d],
            temps_c: vec![1.0, 1.0],
        },
        ShipmentTrace {
            times_d: vec![0.0, d],
            temps_c: vec![4.0, 4.0],
        },
        ShipmentTrace {
            times_d: vec![0.0, d],
            temps_c: vec![8.0, 8.0],
        },
    ]
}

#[test]
fn calendar_transit_matches_duration() {
    let trace = ShipmentTrace::smoke_cool();
    let d = calendar_transit_days(&trace);
    assert!((d - 2.0).abs() < 1e-12, "smoke_cool calendar d={d}");
    let phi = phi_bar_from_trace(&trace, 3.0, 0.0);
    assert!(phi > 1.0, "1C q10 factor phi_bar={phi}");
}
