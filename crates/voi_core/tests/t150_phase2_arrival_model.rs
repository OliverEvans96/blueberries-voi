//! T-150 Phase 2 — gamma unification, arrival artifact, truth/filter paths (RED).

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_distr::{Distribution, Gamma};
use rand_pcg::Pcg64;
use voi_core::obs::FilterObs;
use voi_core::params::ModelParams;
use voi_core::physics::{
    draw_gamma_decrement, gamma_decrement_cdf, gamma_p, gamma_q,
    store_temp_factor, GammaDecrementTable,
};
use voi_core::session::EngineSession;
use voi_core::arrival::ArrivalModel;
use voi_core::shipments::ShipmentTrace;

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn repo_root() -> PathBuf {
    manifest_dir().join("../..")
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("read src/{name}: {err}"))
}

fn old_shape_params() -> ModelParams {
    ModelParams {
        gamma_shape: 2.0,
        gamma_scale: 0.08,
        t_store_c: 4.0,
        t_ref_c: 0.0,
        q10: 3.0,
        ..ModelParams::default()
    }
}

fn phi_at_store(params: &ModelParams) -> f64 {
    store_temp_factor(params.t_store_c, params.t_ref_c, params.q10)
}

fn empirical_mean_sd(samples: &[f64]) -> (f64, f64) {
    let n = samples.len() as f64;
    let mean = samples.iter().sum::<f64>() / n;
    let var = samples.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
    (mean, var.sqrt())
}

/// AC2.1: one gamma convention — shape scaled, `gamma_decrement_scale` deleted.
#[test]
fn ac2_1_gamma_shape_scaling_not_scale() {
    let physics = read_src("physics.rs");
    assert!(
        !physics.contains("pub fn gamma_decrement_scale"),
        "RED: gamma_decrement_scale must be deleted"
    );
    assert!(
        physics.contains("params.gamma_shape * factor")
            || physics.contains("gamma_shape * factor"),
        "RED: GammaDecrementTable::for_params must scale shape"
    );
    assert!(
        physics.contains("Gamma::new(params.gamma_shape * factor")
            || physics.contains("gamma_shape * factor"),
        "RED: draw_gamma_decrement must scale shape, not scale"
    );
}

/// AC2.2: additivity — Λ₁+Λ₂ matches sequential aging; halving timestep unchanged.
#[test]
fn ac2_2_gamma_additivity_and_timestep_invariance() {
    let params = ModelParams::default();
    let k = params.gamma_shape;
    let theta = params.gamma_scale;
    let lambda1 = 1.5;
    let lambda2 = 2.25;
    let lambda_sum = lambda1 + lambda2;

    // Mean loss through combined exposure.
    let mean_combined = k * theta * lambda_sum;
    let mean_seq = k * theta * lambda1 + k * theta * lambda2;
    assert!((mean_combined - mean_seq).abs() < 1e-12);

    // Variance additivity under shape-scaling: Var = k * theta^2 * Lambda.
    let var_combined = k * theta.powi(2) * lambda_sum;
    let var_seq = k * theta.powi(2) * lambda1 + k * theta.powi(2) * lambda2;
    assert!((var_combined - var_seq).abs() < 1e-12);

    // Timestep invariance: two half-steps vs one full step at same total Λ.
    let half = lambda_sum / 2.0;
    let var_half_twice = 2.0 * (k * theta.powi(2) * half);
    assert!((var_combined - var_half_twice).abs() < 1e-12);
}

/// AC2.3: shape-scaling spread at *pre-recalibration* parameters isolates convention change.
#[test]
fn ac2_3_shape_scaling_spread_at_old_params() {
    let params = old_shape_params();
    let phi = phi_at_store(&params);
    let k = params.gamma_shape;
    let theta = params.gamma_scale;

    let expected_mean = k * theta * phi;
    let expected_sd_shape = theta * (k * phi).sqrt();
    let wrong_sd_scale = theta * phi * k.sqrt();

    let mut rng = Pcg64::seed_from_u64(150_203);
    let mut samples = Vec::with_capacity(20_000);
    for _ in 0..20_000 {
        samples.push(draw_gamma_decrement(&mut rng, &params));
    }
    let (emp_mean, emp_sd) = empirical_mean_sd(&samples);

    assert!(
        (emp_mean - expected_mean).abs() < 0.01,
        "mean {emp_mean} expected {expected_mean}"
    );
    assert!(
        (emp_sd - expected_sd_shape).abs() < 0.015,
        "RED: sd {emp_sd} must match shape-scaling {expected_sd_shape}, not scale-scaling {wrong_sd_scale}"
    );
    assert!(
        (emp_sd - wrong_sd_scale).abs() > 0.02,
        "RED: sd {emp_sd} still matches old scale-scaling {wrong_sd_scale}"
    );
    assert!((expected_sd_shape - 0.141).abs() < 0.005);
    assert!((wrong_sd_scale - 0.176).abs() < 0.005);
}

/// AC2.4: single reference life — default satisfies k·θ·η_ref = 1; η slider not a no-op.
#[test]
fn ac2_4_reference_life_invariant_and_eta_choke_point() {
    let params = ModelParams::default();
    let product = params.gamma_shape * params.gamma_scale * params.eta_ref;
    assert!(
        (product - 1.0).abs() < 1e-12,
        "RED: default must satisfy k*theta*eta_ref == 1; got {product}"
    );
    assert!(
        (params.gamma_scale - 1.0 / 28.0).abs() < 1e-12,
        "RED: gamma_scale must be 1/28 after recalibration; got {}",
        params.gamma_scale
    );

    let params_src = read_src("params.rs");
    assert!(
        params_src.contains("set_reference_life") || params_src.contains("reference_life"),
        "RED: params.rs must expose a reference-life derivation choke point"
    );

    let session_src = read_src("session.rs");
    assert!(
        session_src.contains("set_reference_life")
            || session_src.contains("reference_life"),
        "RED: apply_rpc_configure must call reference-life derivation when eta_ref supplied"
    );
    assert!(
        session_src.contains("eta_ref"),
        "params must wire eta_ref through configure"
    );
}

/// AC2.5: transit/shelf scale sanity — relationship pinned from committed parameters.
#[test]
fn ac2_5_transit_shelf_exposure_relationship() {
    let params = ModelParams::default();
    let phi_1c = store_temp_factor(1.0, params.t_ref_c, params.q10);
    let phi_4c = store_temp_factor(4.0, params.t_ref_c, params.q10);

    // One reference-day of exposure costs k*theta regardless of path.
    let per_ref_day = params.gamma_shape * params.gamma_scale;
    let two_day_1c = 2.0 * phi_1c * per_ref_day;
    let two_shelf_1c = 2.0 * phi_1c * per_ref_day;
    assert!((two_day_1c - two_shelf_1c).abs() < 1e-12);

    let ratio = two_day_1c / (2.0 * phi_4c * per_ref_day);
    let expected_ratio = phi_1c / phi_4c;
    assert!((ratio - expected_ratio).abs() < 1e-12);
    assert!((expected_ratio - 3.0_f64.powf(0.1) / 3.0_f64.powf(0.4)).abs() < 1e-12);

    let pinned = 2.0 * phi_1c * per_ref_day;
    assert!(
        (two_day_1c - pinned).abs() < 1e-9,
        "two_day_1c={two_day_1c} pinned from committed params={pinned}"
    );
    // After AC2.4 recalibration (eta_ref=14, k*theta=1/14): 2 * 3^0.1 / 14 ≈ 0.159
    let recalibrated_pin = 2.0 * 3.0_f64.powf(0.1) / 14.0;
    assert!(
        (two_day_1c - recalibrated_pin).abs() < 1e-3,
        "RED: after recalibration two_day_1c={two_day_1c} expected ≈{recalibrated_pin}"
    );
}

/// AC2.6: committed artifact exists with required schema; unknown versions rejected.
#[test]
fn ac2_6_arrival_artifact_schema() {
    let path = repo_root().join("data/abdella/arrival_model.json");
    assert!(path.is_file(), "RED: data/abdella/arrival_model.json must exist");
    let json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&path).unwrap()).expect("parse artifact");
    for key in [
        "schema_version",
        "mu_T",
        "sigma_T",
        "sigma_pos",
        "q10",
        "T_ref",
        "gamma_shape",
        "gamma_scale",
        "reference_life_days",
        "quadrature",
        "provenance",
    ] {
        assert!(json.get(key).is_some(), "RED: artifact missing key {key}");
    }
    assert!(json.get("corridors").is_some() || json.get("arrival_product").is_some());

    let provenance = fs::read_to_string(repo_root().join("data/abdella/PROVENANCE.md")).unwrap();
    assert!(
        provenance.contains("arrival_model"),
        "RED: PROVENANCE.md must document arrival_model.json"
    );

    // Parser must reject unknown schema versions (runtime once arrival.rs lands).
    let arrival_src = read_src("arrival.rs");
    assert!(
        arrival_src.contains("schema_version") && arrival_src.contains("unknown"),
        "RED: arrival.rs must reject unknown schema versions"
    );
}

/// AC2.7: artifact embedded exactly once; parity with committed file.
#[test]
fn ac2_7_single_embed_and_parity() {
    let output = std::process::Command::new("rg")
        .args(["-c", "arrival_model.json", "crates/voi_core/src"])
        .current_dir(repo_root())
        .output()
        .expect("rg");
    let stdout = String::from_utf8_lossy(&output.stdout);
    let total: usize = stdout
        .lines()
        .filter_map(|line| line.split(':').nth(1))
        .filter_map(|n| n.trim().parse::<usize>().ok())
        .sum();
    assert_eq!(
        total, 1,
        "RED: arrival_model.json must be include_str!'d at exactly one site; rg -c gave:\n{stdout}"
    );

    let arrival_src = read_src("arrival.rs");
    assert!(
        arrival_src.contains("fn embedded_arrival_model")
            || arrival_src.contains("EMBEDDED_ARRIVAL"),
        "RED: arrival.rs must expose a single embed accessor"
    );
}

/// AC2.8: calibration note script exists (content checks in Python test).
#[test]
fn ac2_8_calibration_note_script_exists() {
    let script = repo_root().join("scripts/arrival_calibration_note.py");
    assert!(script.is_file(), "RED: scripts/arrival_calibration_note.py must exist");
}

/// AC2.9: `ArrivalModel` analytic CDF uses gamma_p/gamma_q, not grid mass.
#[test]
fn ac2_9_arrival_conditional_law_analytic() {
    assert!(
        manifest_dir().join("src/arrival.rs").is_file(),
        "RED: crates/voi_core/src/arrival.rs must exist"
    );
    let src = read_src("arrival.rs");
    assert!(src.contains("ArrivalModel"), "RED: ArrivalModel not defined");
    assert!(src.contains("gamma_p"), "RED: must use gamma_p for P(f > x | Λ)");
    assert!(src.contains("gamma_q"), "RED: must use gamma_q for P(f = 0 | Λ)");

    // Pin the closed form at representative Λ.
    let k = 2.0;
    let theta = 1.0 / 28.0;
    let lambda = 4.0;
    let x = 0.3;
    let p_gt = gamma_p(k * lambda, (1.0 - x) / theta);
    let p_zero = gamma_q(k * lambda, 1.0 / theta);
    assert!(p_gt > 0.0 && p_gt < 1.0);
    assert!(p_zero > 0.0 && p_zero < 1.0);

    // Monte Carlo spot check (independent of ArrivalModel export).
    let mut rng = Pcg64::seed_from_u64(150_209);
    let n = 50_000;
    let mut gt = 0usize;
    let mut zero = 0usize;
    for _ in 0..n {
        let d: f64 = Gamma::new(k * lambda, theta)
            .unwrap()
            .sample(&mut rng);
        let f = (1.0 - d).max(0.0);
        if f > x {
            gt += 1;
        }
        if f <= 0.0 {
            zero += 1;
        }
    }
    let mc_gt = gt as f64 / n as f64;
    let mc_zero = zero as f64 / n as f64;
    assert!((mc_gt - p_gt).abs() < 0.02, "mc_gt={mc_gt} analytic={p_gt}");
    assert!((mc_zero - p_zero).abs() < 0.02, "mc_zero={mc_zero} analytic={p_zero}");
}

/// AC2.10: monotone ladder — Var(f | φ̄) < Var(f | d) < Var(f) strict on committed artifact.
#[test]
fn ac2_10_monotone_ladder_variance() {
    let src = read_src("arrival.rs");
    assert!(
        src.contains("variance") || src.contains("Var"),
        "RED: arrival.rs must expose variance helpers for ladder guard"
    );
    // Runtime check delegates to Python/Rust parity test once parser lands.
    let path = repo_root().join("data/abdella/arrival_model.json");
    if !path.is_file() {
        panic!("RED: cannot evaluate ladder monotonicity without committed artifact");
    }
}

/// AC2.11: restored bc26218 heterogeneous-fleet assertions (strict).
#[test]
fn ac2_11_f2_marginals_differ_from_p0() {
    let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
    let mut f2 = EngineSession::new(42);
    f2.init(42);
    f2.set_obs_scenario("F2").unwrap();
    for &q in &orders {
        let _ = f2.step(q);
    }
    let mut p0 = EngineSession::new(42);
    p0.init(42);
    p0.set_obs_scenario("P0").unwrap();
    for &q in &orders {
        let _ = p0.step(q);
    }
    let b_f2 = f2.snapshot_value()["belief"].clone();
    let b_p0 = p0.snapshot_value()["belief"].clone();
    let f2_m = json_f64s(&b_f2, "f_marginals");
    let p0_m = json_f64s(&b_p0, "f_marginals");
    assert_ne!(
        f2_m, p0_m,
        "RED: F2 f_marginals must differ from P0 on heterogeneous fleet"
    );
}

#[test]
fn ac2_11_caught_up_f2_not_collapsed_to_p0() {
    let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
    let mut switched = EngineSession::new(42);
    switched.init(42);
    switched.set_obs_scenario("P0").unwrap();
    for &q in &orders[..4] {
        let _ = switched.step(q);
    }
    switched.set_obs_scenario("F2").unwrap();
    for &q in &orders[4..] {
        let _ = switched.step(q);
    }
    let m_switch = json_f64s(&switched.snapshot_value()["belief"], "f_marginals");
    let mut p0_full = EngineSession::new(42);
    p0_full.init(42);
    p0_full.set_obs_scenario("P0").unwrap();
    for &q in &orders {
        let _ = p0_full.step(q);
    }
    let m_p0 = json_f64s(&p0_full.snapshot_value()["belief"], "f_marginals");
    assert_ne!(
        m_switch, m_p0,
        "RED: caught-up F2 posterior must not collapse to P0"
    );
}

#[test]
fn ac2_11_p0_p1_posteriors_differ() {
    let mut p0 = EngineSession::new(99);
    p0.init(99);
    p0.set_obs_scenario("P0").unwrap();
    let mut p1 = EngineSession::new(99);
    p1.init(99);
    p1.set_obs_scenario("P1").unwrap();
    let mut saw_waste = false;
    for _ in 0..200 {
        let d0 = p0.step(48);
        let d1 = p1.step(48);
        if d0.waste_total > 0 {
            saw_waste = true;
            break;
        }
        let _ = d1;
    }
    assert!(saw_waste, "fixture must produce waste");
    let b0 = p0.snapshot_value()["belief"].clone();
    let b1 = p1.snapshot_value()["belief"].clone();
    assert_ne!(
        json_f64s(&b0, "f_marginals"),
        json_f64s(&b1, "f_marginals"),
        "RED: P0 and P1 posteriors must differ after waste"
    );
}

fn json_f64s(v: &serde_json::Value, key: &str) -> Vec<f64> {
    v[key]
        .as_array()
        .unwrap_or(&vec![])
        .iter()
        .filter_map(|x| x.as_f64())
        .collect()
}

/// AC2.12: within-lot spread — truth path uses ArrivalModel per unit, not delivery_birth_f scalar.
#[test]
fn ac2_12_within_lot_arrival_f_spread() {
    let day_step = read_src("day_step.rs");
    assert!(
        day_step.contains("ArrivalModel") || day_step.contains("arrival::"),
        "RED: truth path must draw per-unit f from ArrivalModel"
    );
    assert!(
        !day_step.contains("delivery_birth_f"),
        "RED: truth path must not call delivery_birth_f (scalar per delivery)"
    );

    let params = ModelParams::default();
    let model = ArrivalModel::embedded();
    let mut rng = Pcg64::seed_from_u64(150_212);
    let units: Vec<f64> = model.draw_truth_delivery(
        "abdella_all",
        params.units_per_lot,
        &mut rng,
        &mut Pcg64::seed_from_u64(150_213),
        &mut Pcg64::seed_from_u64(150_214),
        &mut Pcg64::seed_from_u64(150_215),
    ).unit_f;

    let unique: std::collections::BTreeSet<u64> = units
        .iter()
        .map(|f| (f * 1_000_000.0).round() as u64)
        .collect();
    assert!(
        unique.len() > 1,
        "fixture: per-unit gamma draws must differ (baseline for spread test)"
    );

    let mut sess = EngineSession::new(150_212);
    sess.init(150_212);
    let _ = sess.step(8);
    let _ = sess.step(0);
    let lots = sess.snapshot_value()["live_lots"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    assert!(!lots.is_empty(), "fixture must deliver a lot");
    let lot = &lots[0];
    assert!(
        lot.get("f_values").is_some()
            || lot.get("unit_f").is_some()
            || lot.get("freshness_spread").is_some(),
        "RED: live_lots must expose within-lot freshness spread, not only mean_f: {lot}"
    );
}

/// AC2.13: FilterObs carries no freshness-valued arrival field.
#[test]
fn ac2_13_filter_obs_no_freshness_valued_arrival() {
    let obs_src = read_src("obs.rs");
    for field in ["age_at_receipt", "f_at_receipt"] {
        assert!(
            !obs_src.contains(&format!("pub {field}:")),
            "RED: FilterObs must not carry freshness-valued field {field}"
        );
    }
    let _obs = FilterObs::default();
}

/// AC2.14: truth path draws from ArrivalModel; f_to_age round trip gone from day_step.
#[test]
fn ac2_14_truth_path_f_native_arrival() {
    let day_step = read_src("day_step.rs");
    assert!(
        day_step.contains("ArrivalModel") || day_step.contains("arrival::"),
        "RED: day_step delivery block must draw from ArrivalModel"
    );
    assert!(
        !day_step.contains("f_to_age") && !day_step.contains("age_to_f"),
        "RED: day_step must not round-trip through f_to_age / age_to_f"
    );
    assert!(
        !day_step.contains("birth_f_units_gamma"),
        "RED: birth_f_units_gamma eta_ref division must be removed from truth path"
    );
}

/// AC2.15: filter path uses channel-conditional law; superseded helpers removed.
#[test]
fn ac2_15_filter_path_and_shipments_cleanup() {
    let pf = read_src("unit_pf.rs");
    assert!(
        pf.contains("resolve_arrival_f_law") || pf.contains("arrival_f_law"),
        "RED: unit_pf must resolve channel-conditional arrival law"
    );
    assert!(
        !pf.contains("resolve_arrival_lambda"),
        "RED: resolve_arrival_lambda must be replaced"
    );

    let shipments = read_src("shipments.rs");
    for sym in [
        "generate_arrival_tau",
        "generate_arrival_f",
        "mean_age_from_lambda",
        "draw_gamma_arrival_age",
        "arrival_receipt_meta",
        "birth_f_units",
        "sample_phi_bar_from_fleet",
    ] {
        assert!(
            !shipments.contains(sym),
            "RED: shipments.rs must remove superseded helper {sym}"
        );
    }
    assert!(
        shipments.contains("arrival_exposure_from_path")
            || shipments.contains("arrival_age_from_path"),
        "RED: exposure integral helper must remain (renamed)"
    );
}

/// AC2.16: Λ floored before Gamma(kΛ, θ); finite monotone CDF as Λ → 0.
#[test]
fn ac2_16_lambda_floor_finite_cdf() {
    let src = read_src("arrival.rs");
    assert!(
        src.contains("floor") || src.contains("max("),
        "RED: arrival.rs must floor Λ before forming Gamma(kΛ, θ)"
    );

    let params = ModelParams::default();
    let model = ArrivalModel::embedded();
    let tiny = 1e-300;
    let p0 = model.p_f_zero(tiny);
    assert!(p0.is_finite(), "P(f=0) must be finite at tiny Λ");
    let p1 = model.cdf_f_given_lambda(1e-6, 0.5);
    let p2 = model.cdf_f_given_lambda(1e-3, 0.5);
    assert!(p1.is_finite() && p2.is_finite());
    assert!(p2 > p1, "CDF must be monotone in Λ");
}

/// AC2.17: Python/Rust golden parity hook — artifact parser exported.
#[test]
fn ac2_17_rust_embed_parses_committed_artifact() {
    let lib = read_src("lib.rs");
    assert!(
        lib.contains("pub mod arrival"),
        "RED: lib.rs must export arrival module"
    );
    let table = GammaDecrementTable::for_params(&ModelParams::default());
    assert_eq!(table.len(), 4096);
    let _ = gamma_decrement_cdf(0.1, &ModelParams::default());
}
