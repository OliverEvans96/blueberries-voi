//! T-140 Stage C — unified gamma-in-warped-time arrival.
//!
//! Superseded in T-150 (AC2.15): `birth_f_units_gamma` and `arrival_receipt_meta*` moved to
//! `arrival::ArrivalModel`; this file now guards the surviving exposure helpers and the
//! channel-conditional filter birth path.

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};
use voi_core::params::ModelParams;
use voi_core::shipments::{
    calendar_transit_days, phi_bar_fleet, phi_bar_from_trace, ShipmentTrace,
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

/// AC-1 (T-150 supersession): exposure helpers remain; gamma birth lives in `arrival.rs`.
#[test]
fn unified_arrival_exports_and_params_cleanup() {
    let shipments_src = read_src("shipments.rs");
    for sym in [
        "pub fn calendar_transit_days",
        "pub fn phi_bar_from_trace",
        "pub fn phi_bar_fleet",
        "pub fn arrival_exposure_from_path",
    ] {
        assert!(
            shipments_src.contains(sym),
            "shipments.rs must export {sym}"
        );
    }
    assert!(
        !shipments_src.contains("birth_f_units_gamma"),
        "T-150: birth_f_units_gamma removed from shipments.rs"
    );
    let arrival_src = read_src("arrival.rs");
    assert!(
        arrival_src.contains("sample_filter_birth_units"),
        "arrival.rs must provide filter birth sampling"
    );
    let params_src = read_src("params.rs");
    assert!(
        !params_src.contains("f2a_transit_uncertainty_sd"),
        "ModelParams must drop f2a_transit_uncertainty_sd (ADR 0141)"
    );
}

/// AC-3: mix_arrival_f deleted from unit_pf.
#[test]
fn mix_arrival_f_removed_from_unit_pf() {
    let pf_src = read_src("unit_pf.rs");
    assert!(
        !pf_src.contains("fn mix_arrival_f"),
        "unit_pf must not define mix_arrival_f"
    );
}

/// AC-2 (T-150): pack date is calendar duration on the truth path in session, not rounded tau.
#[test]
fn pack_date_from_calendar_duration_not_rounded_tau() {
    let session_src = read_src("session.rs");
    assert!(
        session_src.contains("pack_date_days"),
        "session must emit pack_date_days on RichDay"
    );
    let shipments_src = read_src("shipments.rs");
    assert!(
        shipments_src.contains("calendar_transit_days"),
        "exposure helpers must retain calendar_transit_days"
    );
    assert!(
        !shipments_src.contains("tau.round() as i32"),
        "pack_date_days must not be round(tau)"
    );
}

/// AC-4 (T-155): shard mode for Modal batch map.
#[test]
fn gsin_upc_diag_supports_shard_cli() {
    let diag_src = read_example("gsin_upc_diag.rs");
    assert!(
        diag_src.contains("\"--shard\""),
        "gsin_upc_diag must support --shard <regime_idx> <seed_idx>"
    );
    assert!(
        diag_src.contains("fn run_shard"),
        "gsin_upc_diag must implement run_shard"
    );
}

/// AC-4: thermal fleet has non-degenerate phi_bar.
#[test]
fn shipments_thermal_phi_bar_non_degenerate() {
    let diag_src = read_example("gsin_upc_diag.rs");
    assert!(
        diag_src.contains("fn shipments_thermal"),
        "gsin_upc_diag must define shipments_thermal()"
    );
    let traces = shipments_thermal_traces();
    let params = ModelParams::default();
    let phis = phi_bar_fleet(&traces, params.q10, params.t_ref_c);
    let distinct: std::collections::HashSet<_> =
        phis.iter().map(|p| (p * 1e6).round() as i64).collect();
    assert!(
        distinct.len() >= 2,
        "thermal fleet phi_bar must be non-degenerate, got {phis:?}"
    );
}

/// AC-1: gamma birth spreads units at fixed exposure (via ArrivalModel after T-150).
#[test]
fn arrival_model_spreads_units_at_fixed_exposure() {
    let params = ModelParams::default();
    let mut model = ArrivalModel::embedded();
    model.sync_params(&params);
    let n = 12usize;
    let mut spread = false;
    for seed in 0..50u64 {
        let mut rng = Pcg64::seed_from_u64(140_001 ^ seed);
        let values = model.sample_filter_birth_units(ArrivalCondition::Duration(3), n, &mut rng);
        assert_eq!(values.len(), n);
        for &f in &values {
            assert!(f >= 0.0 && f <= 1.0, "f={f}");
        }
        let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
        let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        if (max - min) > 1e-6 {
            spread = true;
            break;
        }
    }
    assert!(spread, "gamma birth must spread units at fixed pack_date");
}

/// AC-6 (T-150): filter birth uses channel-conditional ArrivalModel sampling.
#[test]
fn unit_pf_uses_arrival_model_birth_path() {
    let pf_src = read_src("unit_pf.rs");
    assert!(
        pf_src.contains("sample_filter_birth_units") || pf_src.contains("resolve_arrival_f_law"),
        "unit_pf filter birth must use ArrivalModel channel-conditional law"
    );
    assert!(
        !pf_src.contains("birth_f_units_gamma"),
        "T-150: birth_f_units_gamma removed from unit_pf"
    );
}

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
