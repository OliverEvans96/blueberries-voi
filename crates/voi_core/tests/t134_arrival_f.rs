//! T-140 / T-134 — unified gamma arrival wiring guards.
//!
//! Superseded in T-150: `birth_f_units_gamma` and `delivery_f` moved to
//! `arrival::ArrivalModel` and `UnitDayStepIn::delivery_unit_f` respectively.

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::obs::FilterObs;
use voi_core::params::ModelParams;
use voi_core::session::EngineSession;
use voi_core::shipments::{mod21_demo_shipments, ShipmentTrace};
use voi_core::unit_pf::{filter_step_unit_with_birth, UnitParticleBank};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("read src/{name}: {err}"))
}

fn demo_shipments() -> Vec<ShipmentTrace> {
    mod21_demo_shipments("short_haul")
}

#[test]
fn unified_gamma_arrival_wiring_in_shipments_and_unit_pf() {
    let shipments_src = read_src("shipments.rs");
    for sym in [
        "pub fn calendar_transit_days",
        "pub fn phi_bar_from_trace",
        "pub fn arrival_exposure_from_path",
    ] {
        assert!(shipments_src.contains(sym), "shipments must export {sym}");
    }
    assert!(
        !shipments_src.contains("birth_f_units_gamma"),
        "T-150: birth_f_units_gamma removed from shipments.rs"
    );
    let arrival_src = read_src("arrival.rs");
    assert!(
        arrival_src.contains("sample_filter_birth_units"),
        "arrival.rs must provide channel-conditional filter birth"
    );
    let pf_src = read_src("unit_pf.rs");
    assert!(
        pf_src.contains("sample_filter_birth_units"),
        "filter birth must use ArrivalModel::sample_filter_birth_units"
    );
    assert!(
        !pf_src.contains("birth_f_units_gamma"),
        "T-150: birth_f_units_gamma removed from unit_pf"
    );
    assert!(
        !pf_src.contains("fn mix_arrival_f"),
        "mix_arrival_f must be removed"
    );
    let params_src = read_src("params.rs");
    assert!(
        !params_src.contains("f2a_transit_uncertainty_sd"),
        "f2a_transit_uncertainty_sd removed per ADR 0141"
    );
}

#[test]
fn filter_birth_spreads_units_under_gamma_arrival() {
    let params = ModelParams::default();
    let upl = 8usize;
    let mut bank = UnitParticleBank::from_rows_uniform_lots(
        vec![0.5, 0.5],
        vec![vec![0.4; upl], vec![0.4; upl]],
        upl,
    );
    let mut rng = Pcg64::seed_from_u64(140_006);
    let mut rng_birth = Pcg64::seed_from_u64(140_006 ^ 0xB177);
    let obs = FilterObs {
        arrivals: upl as u32,
        ..Default::default()
    };
    let ships = demo_shipments();
    filter_step_unit_with_birth(
        &mut bank,
        &obs,
        &params,
        &ships,
        &mut rng,
        Some(&mut rng_birth),
    );
    let any_within_spread = bank.freshness.iter().any(|row| {
        let n_lots = bank.lot_offsets.len().saturating_sub(1);
        if n_lots == 0 {
            return false;
        }
        let start = bank.lot_offsets[n_lots - 1];
        let end = bank.lot_offsets[n_lots];
        let seg = &row[start..end];
        let min = seg.iter().cloned().fold(f64::INFINITY, f64::min);
        let max = seg.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        max - min > 1e-6
    });
    assert!(
        any_within_spread,
        "gamma arrival must yield >=2 distinct unit f values within a lot segment"
    );
}

#[test]
fn filter_birth_alive_mass_matches_arrivals() {
    let params = ModelParams::default();
    let arrivals = 24u32;
    let n = 8usize;
    let mut bank = UnitParticleBank::empty(n);
    let mut rng = Pcg64::seed_from_u64(139_003);
    let mut rng_birth = Pcg64::seed_from_u64(139_003 ^ 0xB177);
    let obs = FilterObs {
        arrivals,
        ..Default::default()
    };
    let ships = demo_shipments();
    filter_step_unit_with_birth(
        &mut bank,
        &obs,
        &params,
        &ships,
        &mut rng,
        Some(&mut rng_birth),
    );
    // T-150: births may include f=0 units (p_f_zero); segment width must match arrivals.
    for row in &bank.freshness {
        assert_eq!(
            row.len(),
            arrivals as usize,
            "birth segment width must match arrivals count"
        );
    }
}

#[test]
fn session_lot_counts_track_arrivals_minus_decay() {
    for seed in 0..=200u64 {
        let mut session = EngineSession::new(seed);
        session.init(seed);
        let mut arrivals_total = 0u32;
        let mut last_on_hand = 0.0f64;
        for day in 0..20u32 {
            let order = if day % 4 == 0 { 30 } else { 0 };
            let delta = session.step(order);
            arrivals_total += delta.arrivals;
            let snap = session.snapshot_value();
            let lot_counts: Vec<f64> = snap["belief"]["lot_counts"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_f64().unwrap())
                .collect();
            last_on_hand = lot_counts.iter().sum();
        }
        assert!(
            last_on_hand <= f64::from(arrivals_total) + 1e-6,
            "seed {seed}: lot_counts sum {last_on_hand} > arrivals {arrivals_total}"
        );
    }
}

#[test]
fn session_passes_precomputed_delivery_unit_f() {
    let src = read_src("session.rs");
    assert!(
        src.contains("delivery_unit_f"),
        "session must pass per-unit delivery_unit_f into UnitDayStepIn"
    );
    assert!(
        !src.contains("delivery_f: f_at_receipt"),
        "T-150: delivery_f removed from session truth path"
    );
}

#[test]
fn voi_passes_precomputed_delivery_unit_f() {
    let src = read_src("voi.rs");
    assert!(
        src.contains("delivery_unit_f"),
        "voi must pass per-unit delivery_unit_f into UnitDayStepIn"
    );
    assert!(
        !src.contains("delivery_f: f_at_receipt"),
        "T-150: delivery_f removed from voi truth path"
    );
}
