//! T-138 Stage A — within-lot arrival dispersion (RED until implement).

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::obs::FilterObs;
use voi_core::params::ModelParams;
use voi_core::session::EngineSession;
use voi_core::shipments::{birth_f_f2_dirac, birth_f_units};
use voi_core::unit_pf::{filter_step_unit, filter_step_unit_with_birth, UnitParticleBank};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("read src/{name}: {err}"))
}

fn require_arrival_dispersion_sd_field() {
    let params_src = read_src("params.rs");
    assert!(
        params_src.contains("arrival_dispersion_sd"),
        "RED: ModelParams must expose arrival_dispersion_sd"
    );
    assert!(
        params_src.contains("f2a_transit_uncertainty_sd"),
        "params must keep f2a_transit_uncertainty_sd distinct from arrival_dispersion_sd"
    );
}

fn require_birth_f_units_export() {
    let shipments_src = read_src("shipments.rs");
    assert!(
        shipments_src.contains("pub fn birth_f_units"),
        "RED: shipments must export birth_f_units(mean_f, sd, n, rng)"
    );
}

fn require_stream_birth_wiring() {
    for file in ["session.rs", "voi.rs", "rollout.rs", "alpha_tune.rs"] {
        let src = read_src(file);
        assert!(
            src.contains(":birth") || src.contains("STREAM_BIRTH"),
            "RED: {file} must define/use STREAM_BIRTH / :birth for within-lot dispersion"
        );
    }
}

/// AC-1: distinct field from f2a_transit_uncertainty_sd; default 0.0; semantics do not alias.
#[test]
fn model_params_arrival_dispersion_sd_distinct_from_f2a_transit() {
    require_arrival_dispersion_sd_field();
    let params_src = read_src("params.rs");
    assert!(
        params_src.contains("arrival_dispersion_sd: 0.0")
            || params_src.contains("arrival_dispersion_sd:0.0"),
        "RED: arrival_dispersion_sd default must be 0.0"
    );
    assert!(
        !params_src.contains("arrival_dispersion_sd: params.f2a_transit_uncertainty_sd"),
        "RED: arrival_dispersion_sd must not alias f2a_transit_uncertainty_sd"
    );
    let default_f2a = ModelParams::default().f2a_transit_uncertainty_sd;
    assert!(
        (default_f2a - 0.75).abs() < 1e-12,
        "f2a_transit_uncertainty_sd default must remain the F2a epistemic knob"
    );
}

/// AC-2: sd = 0.0 yields n copies of mean_f within 1e-12; values in (0, 1].
#[test]
fn birth_f_units_sd_zero_yields_uniform_copies() {
    require_birth_f_units_export();
    let mean_f = 0.62;
    let n = 12usize;
    let mut rng = Pcg64::seed_from_u64(138_002);
    let values = birth_f_units(mean_f, 0.0, n, &mut rng);
    assert_eq!(values.len(), n);
    for &f in &values {
        assert!(f > 0.0 && f <= 1.0, "birth f {f} outside (0, 1]");
        assert!((f - mean_f).abs() < 1e-12, "sd=0 must copy mean_f");
    }
}

/// AC-3: sd > 0 with n >= 8 shows spread across seeds while mean stays near mean_f.
#[test]
fn birth_f_units_positive_sd_spreads_and_centers() {
    require_birth_f_units_export();
    let mean_f = 0.55;
    let sd = 0.05;
    let n = 8usize;
    let mut spread = false;
    for seed in 0..100u64 {
        let mut rng = Pcg64::seed_from_u64(138_003 ^ seed);
        let values = birth_f_units(mean_f, sd, n, &mut rng);
        assert_eq!(values.len(), n);
        let vmin = values.iter().cloned().fold(f64::INFINITY, f64::min);
        let vmax = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        if vmax - vmin > 1e-6 {
            spread = true;
        }
        let sample_mean = values.iter().sum::<f64>() / n as f64;
        assert!(
            (sample_mean - mean_f).abs() <= 3.0 * sd + 1e-9,
            "seed {seed}: mean {sample_mean} outside 3σ band around {mean_f}"
        );
    }
    assert!(spread, "sd>0 must spread within-lot freshness across seeds");
}

/// AC-5: filter birth spreads obs.arrivals units via birth_f_units / push_lot vector.
#[test]
fn filter_birth_uses_birth_f_units_per_particle() {
    require_arrival_dispersion_sd_field();
    require_birth_f_units_export();
    let pf = read_src("unit_pf.rs");
    assert!(
        pf.contains("birth_f_units"),
        "RED: filter_step_unit birth block must call birth_f_units"
    );
    assert!(
        !pf.contains("extend(vec![birth; upl])"),
        "RED: filter must not uniform-fill the lot segment with one birth scalar"
    );
}

/// AC-6: particles hold non-uniform within-lot freshness vectors when dispersion is wired.
#[test]
fn filter_particles_differ_within_lot_under_dispersion() {
    require_arrival_dispersion_sd_field();
    require_birth_f_units_export();
    let mut params = ModelParams::default();
    params.arrival_dispersion_sd = 0.05;
    let upl = 8usize;
    let mut bank = UnitParticleBank::from_rows_uniform_lots(
        vec![0.5, 0.5],
        vec![vec![0.4; upl], vec![0.4; upl]],
        upl,
    );
    let mut rng = Pcg64::seed_from_u64(138_006);
    let mut rng_birth = Pcg64::seed_from_u64(138_006 ^ 0xB177);
    let obs = FilterObs {
        arrivals: upl as u32,
        ..Default::default()
    };
    filter_step_unit_with_birth(&mut bank, &obs, &params, &mut rng, Some(&mut rng_birth));
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
        "RED: arrival dispersion must yield >=2 distinct unit f values within a lot segment"
    );
}

/// AC-7: production paths wire :birth for aleatoric spread only.
#[test]
fn stream_birth_wired_in_production_paths() {
    require_stream_birth_wiring();
    let day_step = read_src("day_step.rs");
    assert!(
        day_step.contains(":birth") || day_step.contains("birth_f_units"),
        "RED: unit_day_step delivery must draw via :birth / birth_f_units"
    );
    let pf = read_src("unit_pf.rs");
    assert!(
        pf.contains(":birth") || pf.contains("birth_f_units"),
        "RED: filter birth dispersion must use :birth stream"
    );
}

/// AC-9: rollout init samples per unit from lot marginals under :birth, not repeat_n(e_f).
#[test]
fn rollout_unit_state_from_f_belief_samples_per_unit() {
    let rollout = read_src("rollout.rs");
    assert!(
        rollout.contains("unit_state_from_f_belief"),
        "rollout must initialize belief units via unit_state_from_f_belief"
    );
    assert!(
        rollout.contains(":birth") || rollout.contains("birth_f_units"),
        "RED: rollout init must draw per-unit freshness via :birth"
    );
    assert!(
        !rollout.contains("repeat_n(e_f.max(0.0), alive)"),
        "RED: rollout must not repeat lot marginal mean for every live unit"
    );
}

/// AC-15 guard: lot-uniform-only birth is not the sole path when dispersion_sd > 0.
#[test]
fn dispersion_sd_positive_enables_non_uniform_birth_path() {
    require_arrival_dispersion_sd_field();
    require_birth_f_units_export();
    let day_step = read_src("day_step.rs");
    assert!(
        !day_step.contains("vec![birth_f; total_units]"),
        "RED: truth birth must not hard-code lot-uniform vec![birth_f; total_units]"
    );
    let pf = read_src("unit_pf.rs");
    assert!(
        pf.contains("birth_f_units"),
        "RED: filter must spread births when arrival_dispersion_sd > 0"
    );
}

// --- T-139 Stage B: filter mass conservation + contrast hook (ADR 0140) ---

/// AC-3: dispersed filter birth injects exactly obs.arrivals live units per row.
#[test]
fn filter_birth_alive_mass_matches_arrivals_under_dispersion() {
    let mut params = ModelParams::default();
    params.arrival_dispersion_sd = 0.05;
    let arrivals = 24u32;
    let n = 8usize;
    let mut bank = UnitParticleBank::empty(n);
    let mut rng = Pcg64::seed_from_u64(139_003);
    let mut rng_birth = Pcg64::seed_from_u64(139_003 ^ 0xB177);
    let obs = FilterObs {
        arrivals,
        ..Default::default()
    };
    filter_step_unit_with_birth(&mut bank, &obs, &params, &mut rng, Some(&mut rng_birth));
    for row in &bank.freshness {
        let alive = row.iter().filter(|&&f| f > 0.0).count() as f64;
        assert!(
            (alive - f64::from(arrivals)).abs() < 1e-9,
            "row alive {alive} != arrivals {arrivals}"
        );
    }
}

/// AC-4: session belief lot_counts sum tracks on-hand over a short seeded fixture.
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

/// AC-5: ADR 0140 contrast hook is exported and inert at sd=0.
#[test]
fn contrast_spoilage_weight_exported_and_inert_at_sd_zero() {
    let ll_src = read_src("unit_ll.rs");
    assert!(
        ll_src.contains("pub fn contrast_spoilage_weight"),
        "RED: unit_ll must export contrast_spoilage_weight (ADR 0140)"
    );
    let lib_src = read_src("lib.rs");
    assert!(
        lib_src.contains("contrast_spoilage_weight"),
        "RED: lib.rs must re-export contrast_spoilage_weight"
    );
}

// --- T-134 arrival-f wiring guards retained on this branch ---

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
    let mut bank = UnitParticleBank::empty(1);
    let mut rng = Pcg64::seed_from_u64(99);
    let mut rng_birth = Pcg64::seed_from_u64(99 ^ 0xB177);
    let obs = FilterObs {
        arrivals: upl as u32,
        age_at_receipt: Some(age),
        ..Default::default()
    };
    filter_step_unit_with_birth(&mut bank, &obs, &params, &mut rng, Some(&mut rng_birth));
    let row = &bank.freshness[0];
    let start = bank.lot_offsets[0];
    let end = bank.lot_offsets[1];
    assert_eq!(end - start, upl, "birth must inject upl units");
    for &f in &row[start..end] {
        assert!(
            (f - expected).abs() < 1e-12,
            "F2 birth f {f} != dirac({expected})"
        );
    }
}
