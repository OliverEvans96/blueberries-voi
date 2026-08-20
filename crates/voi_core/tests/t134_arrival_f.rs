//! T-134 — arrival freshness birth wiring (RED until implement).

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::obs::FilterObs;
use voi_core::params::ModelParams;
use voi_core::shipments::{birth_f_f2_dirac, mod21_demo_shipments, truth_birth_from_trace};
use voi_core::unit_pf::{filter_step_unit, UnitParticleBank};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("read src/{name}: {err}"))
}

#[test]
fn session_passes_precomputed_delivery_f() {
    let src = read_src("session.rs");
    assert!(
        src.contains("delivery_f: f_at_receipt"),
        "session must pass pre-sampled delivery_f like rollout.rs"
    );
    assert!(
        !src.contains("delivery_f: None,"),
        "session must not leave delivery_f unset on the delivery path"
    );
}

#[test]
fn voi_passes_precomputed_delivery_f() {
    let src = read_src("voi.rs");
    assert!(
        src.contains("delivery_f: f_at_receipt"),
        "voi must pass pre-sampled delivery_f like rollout.rs"
    );
}

#[test]
fn filter_birth_f2_dirac_from_age_at_receipt() {
    let params = ModelParams::default();
    let upl = params.units_per_lot.max(1);
    let age = 2.5;
    let expected = birth_f_f2_dirac(age, params.eta_ref);
    let mut bank = UnitParticleBank {
        weights: vec![1.0],
        freshness: vec![vec![0.4; upl]],
    };
    let mut rng = Pcg64::seed_from_u64(99);
    let obs = FilterObs {
        arrivals: upl as u32,
        age_at_receipt: Some(age),
        ..Default::default()
    };
    filter_step_unit(&mut bank, &obs, &params, &mut rng);
    let row = &bank.freshness[0];
    assert_eq!(row.len(), upl, "birth must inject upl units");
    for &f in row {
        assert!(
            (f - expected).abs() < 1e-12,
            "F2 birth f {f} != dirac({expected})"
        );
    }
}

#[test]
fn mod21_demo_shipments_product_mix() {
    assert_eq!(mod21_demo_shipments("abdella_all").len(), 6);
    assert_eq!(mod21_demo_shipments("long_haul").len(), 5);
    assert_eq!(mod21_demo_shipments("short_haul").len(), 1);
    assert!(
        mod21_demo_shipments("short_haul")[0].times_d.len() >= 2,
        "demo trace must be usable"
    );
}

#[test]
fn truth_birth_from_trace_matches_age_to_f() {
    let params = ModelParams::default();
    let trace = mod21_demo_shipments("short_haul")[0].clone();
    let f = truth_birth_from_trace(&trace, &params);
    assert!(
        f > 0.0 && f <= 1.0,
        "truth birth f must lie in (0, 1]: {f}"
    );
    let short = truth_birth_from_trace(&mod21_demo_shipments("short_haul")[0], &params);
    let all_mean: f64 = mod21_demo_shipments("abdella_all")
        .iter()
        .map(|t| truth_birth_from_trace(t, &params))
        .sum::<f64>()
        / 6.0;
    assert!(
        short > all_mean - 0.05,
        "short haul S2 should be fresher than six-shipment mean ({short} vs {all_mean})"
    );
}
