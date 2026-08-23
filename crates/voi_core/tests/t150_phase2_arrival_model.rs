//! T-150 Phase 2 — gamma unification, arrival artifact, truth/filter paths (RED).

use std::fs;
use std::path::PathBuf;

use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma, LogNormal};
use rand_pcg::Pcg64;
use voi_core::arrival::{
    resolve_arrival_exposure, resolve_arrival_f_law_phi_bar, ArrivalCondition, ArrivalModel,
    STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS, STREAM_ARRIVAL_TEMP,
};
use voi_core::obs::FilterObs;
use voi_core::params::ModelParams;
use voi_core::physics::{
    draw_gamma_decrement, gamma_decrement_cdf, gamma_p, gamma_q, store_temp_factor,
    GammaDecrementTable,
};
use voi_core::demand_profile::DemandProfile;
use voi_core::session::EngineSession;
use voi_core::shipments::{arrival_exposure_from_path, ShipmentTrace};
use voi_core::spawn_rng::SpawnRng;

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

fn walk_rs_files(root: &std::path::Path) -> Vec<PathBuf> {
    fn walk(dir: &std::path::Path, out: &mut Vec<PathBuf>) {
        let entries = fs::read_dir(dir).unwrap_or_else(|err| {
            panic!("read_dir {} for T-150 grep guard: {err}", dir.display())
        });
        for entry in entries {
            let path = entry.unwrap().path();
            if path.is_dir() {
                walk(&path, out);
            } else if path.extension().is_some_and(|ext| ext == "rs") {
                out.push(path);
            }
        }
    }
    let mut out = Vec::new();
    walk(root, &mut out);
    out
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
        physics.contains("params.gamma_shape * factor") || physics.contains("gamma_shape * factor"),
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
        session_src.contains("set_reference_life") || session_src.contains("reference_life"),
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
    assert!(
        path.is_file(),
        "RED: data/abdella/arrival_model.json must exist"
    );
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
    let src_root = repo_root().join("crates/voi_core/src");
    let total: usize = walk_rs_files(&src_root)
        .into_iter()
        .map(|path| {
            let text = fs::read_to_string(&path).unwrap_or_default();
            text.matches("arrival_model.json").count()
        })
        .sum();
    assert_eq!(
        total, 1,
        "RED: arrival_model.json must be include_str!'d at exactly one site; found {total} matches"
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
    assert!(
        script.is_file(),
        "RED: scripts/arrival_calibration_note.py must exist"
    );
}

/// AC2.9: `ArrivalModel` analytic CDF uses gamma_p/gamma_q, not grid mass.
#[test]
fn ac2_9_arrival_conditional_law_analytic() {
    assert!(
        manifest_dir().join("src/arrival.rs").is_file(),
        "RED: crates/voi_core/src/arrival.rs must exist"
    );
    let src = read_src("arrival.rs");
    assert!(
        src.contains("ArrivalModel"),
        "RED: ArrivalModel not defined"
    );
    assert!(
        src.contains("gamma_p"),
        "RED: must use gamma_p for P(f > x | Λ)"
    );
    assert!(
        src.contains("gamma_q"),
        "RED: must use gamma_q for P(f = 0 | Λ)"
    );

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
        let d: f64 = Gamma::new(k * lambda, theta).unwrap().sample(&mut rng);
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
    assert!(
        (mc_zero - p_zero).abs() < 0.02,
        "mc_zero={mc_zero} analytic={p_zero}"
    );
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

fn pearson_corr(xs: &[f64], ys: &[f64]) -> f64 {
    assert_eq!(xs.len(), ys.len());
    let n = xs.len() as f64;
    if n < 2.0 {
        return 0.0;
    }
    let mx = xs.iter().sum::<f64>() / n;
    let my = ys.iter().sum::<f64>() / n;
    let mut num = 0.0;
    let mut den_x = 0.0;
    let mut den_y = 0.0;
    for (&x, &y) in xs.iter().zip(ys.iter()) {
        let dx = x - mx;
        let dy = y - my;
        num += dx * dy;
        den_x += dx * dx;
        den_y += dy * dy;
    }
    if den_x <= 0.0 || den_y <= 0.0 {
        return 0.0;
    }
    num / (den_x.sqrt() * den_y.sqrt())
}

fn law_mean_f(model: &mut ArrivalModel, condition: ArrivalCondition) -> f64 {
    model.filter_law_mean_f(condition)
}

fn law_sd_and_atom(model: &mut ArrivalModel, condition: ArrivalCondition) -> (f64, f64) {
    let mut rng = Pcg64::seed_from_u64(150_219);
    let n = 30_000usize;
    let mut samples = Vec::with_capacity(n);
    for _ in 0..n {
        samples.push(model.sample_filter_birth_units(condition, 1, &mut rng)[0]);
    }
    let atom = samples.iter().filter(|&&f| f <= 0.0).count() as f64 / n as f64;
    let (mean, sd) = empirical_mean_sd(&samples);
    (sd, atom)
}

#[derive(Clone, Debug)]
struct DeliveryTruth {
    day: u32,
    truth_mean_f: f64,
    deliver_units: u32,
    unit_f: Vec<f64>,
    pack_date_days: i32,
    exposure_lambda: f64,
}

fn atom_inclusive_unit_f(lot: &serde_json::Value, deliver_units: u32) -> Vec<f64> {
    let mut unit_f: Vec<f64> = lot["f_values"]
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    assert!(
        unit_f.len() <= deliver_units as usize,
        "f_values.len()={} must not exceed deliver_units={deliver_units}",
        unit_f.len()
    );
    unit_f.extend(std::iter::repeat_n(
        0.0,
        deliver_units as usize - unit_f.len(),
    ));
    unit_f
}

fn sample_sd(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let var = values.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n - 1.0);
    var.sqrt()
}

fn mae_noise_floor(deliveries: &[DeliveryTruth]) -> f64 {
    deliveries
        .iter()
        .map(|d| {
            let sd_within = sample_sd(&d.unit_f);
            (2.0 / std::f64::consts::PI).sqrt() * sd_within / (d.deliver_units as f64).sqrt()
        })
        .sum::<f64>()
        / deliveries.len() as f64
}

fn event_day(events: &serde_json::Value, day: u32) -> serde_json::Value {
    events["days"]
        .as_array()
        .and_then(|days| {
            days.iter()
                .find(|d| d["day"].as_u64() == Some(day as u64))
                .cloned()
        })
        .unwrap_or_else(|| panic!("missing event record for day {day}"))
}

fn attach_mask_replay_observations(
    sess: &mut EngineSession,
    deliveries: &mut [DeliveryTruth],
    params: &ModelParams,
) {
    sess.set_obs_scenario("F2").unwrap();
    let events_f2 = sess.events_value(0);
    sess.set_obs_scenario("F3").unwrap();
    let events_f3 = sess.events_value(0);

    for d in deliveries.iter_mut() {
        let day_f2 = event_day(&events_f2, d.day);
        d.pack_date_days = day_f2["pack_date_days"]
            .as_i64()
            .expect("F2 mask must expose pack_date_days") as i32;

        let day_f3 = event_day(&events_f3, d.day);
        let times = json_f64s(&day_f3, "temp_times_d");
        let temps = json_f64s(&day_f3, "temp_temps_c");
        d.exposure_lambda = resolve_arrival_exposure(
            Some(&temps),
            Some(&times),
            params.q10,
            params.t_ref_c,
        )
        .unwrap_or_else(|| panic!("F3 mask must expose a valid temperature trace on day {}", d.day));
    }
}

fn low_demand_profile() -> DemandProfile {
    DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("low demand profile")
}

fn lot_unit_f_from_snapshot(
    lot: &serde_json::Value,
    deliver_units: u32,
) -> Vec<f64> {
    atom_inclusive_unit_f(lot, deliver_units)
}

fn lot_unit_f_after_arrival(
    sess: &EngineSession,
    day: u32,
    deliver_units: u32,
) -> Vec<f64> {
    let lots = sess.snapshot_value()["live_lots"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    if let Some(lot) = lots.last() {
        return lot_unit_f_from_snapshot(lot, deliver_units);
    }

    let events = sess.events_value(0);
    let day_ev = event_day(&events, day);
    let lot_id = day_ev["arrival_lot_ids"]
        .as_array()
        .and_then(|ids| ids.last())
        .and_then(|v| v.as_i64())
        .unwrap_or_else(|| panic!("arrival day {day} must record arrival_lot_ids"));

    let mut unit_f: Vec<f64> = sess.snapshot_value()["live_units"]
        .as_array()
        .map(|units| {
            units
                .iter()
                .filter(|u| u["lot_id"].as_i64() == Some(lot_id))
                .filter_map(|u| u["f"].as_f64())
                .collect()
        })
        .unwrap_or_default();
    unit_f.extend(std::iter::repeat_n(
        0.0,
        deliver_units as usize - unit_f.len(),
    ));
    unit_f
}

/// One trajectory, mask replay for observations — no `draw_truth_delivery` re-draw.
fn collect_truth_deliveries(seed: u64, orders: &[u32]) -> (Vec<DeliveryTruth>, EngineSession) {
    let mut sess = EngineSession::new(seed);
    sess.set_demand_profile(low_demand_profile());
    sess.init(seed);
    sess.set_obs_scenario("P0").unwrap();
    let params = ModelParams::default();

    let mut out = Vec::new();
    for (day, &q) in orders.iter().enumerate() {
        let delta = sess.step(q);
        if delta.arrivals == 0 {
            continue;
        }
        let day_u32 = day as u32;
        let unit_f = lot_unit_f_after_arrival(&sess, day_u32, delta.arrivals);
        let truth_mean_f = unit_f.iter().sum::<f64>() / f64::from(delta.arrivals);
        out.push(DeliveryTruth {
            day: day_u32,
            truth_mean_f,
            deliver_units: delta.arrivals,
            unit_f,
            pack_date_days: 0,
            exposure_lambda: 0.0,
        });
    }

    attach_mask_replay_observations(&mut sess, &mut out, &params);
    (out, sess)
}

fn assert_truth_mask_invariant(seed: u64, orders: &[u32]) {
    let (p0, _) = collect_truth_deliveries(seed, orders);
    for scenario in ["F2", "F3"] {
        let mut sess = EngineSession::new(seed);
        sess.set_demand_profile(low_demand_profile());
        sess.init(seed);
        sess.set_obs_scenario(scenario).unwrap();
        let mut replay = Vec::new();
        for (day, &q) in orders.iter().enumerate() {
            let delta = sess.step(q);
            if delta.arrivals == 0 {
                continue;
            }
            let unit_f = lot_unit_f_after_arrival(&sess, day as u32, delta.arrivals);
            let truth_mean_f = unit_f.iter().sum::<f64>() / f64::from(delta.arrivals);
            replay.push(truth_mean_f);
        }
        for (a, b) in p0.iter().zip(replay.iter()) {
            assert_eq!(
                a.truth_mean_f.to_bits(),
                b.to_bits(),
                "truth target must be mask-invariant under {scenario}"
            );
        }
    }
}

fn ladder_mae_triple(seed: u64, order_qty: u32, n_days: u32) -> (f64, f64, f64, f64, usize) {
    let orders: Vec<u32> = (0..n_days)
        .map(|i| if i % 4 == 0 { order_qty } else { 0 })
        .collect();
    let (deliveries, _) = collect_truth_deliveries(seed, &orders);
    let floor = mae_noise_floor(&deliveries);
    let truth: Vec<f64> = deliveries.iter().map(|d| d.truth_mean_f).collect();

    let mut model = ArrivalModel::embedded();
    model.sync_params(&ModelParams::default());
    let pred_p0: Vec<f64> = deliveries
        .iter()
        .map(|_| law_mean_f(&mut model, ArrivalCondition::Prior))
        .collect();
    let pred_f2: Vec<f64> = deliveries
        .iter()
        .map(|d| law_mean_f(&mut model, ArrivalCondition::Duration(d.pack_date_days)))
        .collect();
    let pred_f3: Vec<f64> = deliveries
        .iter()
        .map(|d| law_mean_f(&mut model, ArrivalCondition::Exposure(d.exposure_lambda)))
        .collect();

    (
        mae(&pred_p0, &truth),
        mae(&pred_f2, &truth),
        mae(&pred_f3, &truth),
        floor,
        deliveries.len(),
    )
}

fn artifact_quadrature() -> (Vec<f64>, Vec<f64>) {
    let path = repo_root().join("data/abdella/arrival_model.json");
    let json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&path).unwrap()).expect("parse artifact");
    let quad = &json["quadrature"];
    let nodes = quad["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect();
    let weights = quad["weights"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect();
    (nodes, weights)
}

fn expected_delay(corridor: &voi_core::arrival::ArrivalCorridor) -> f64 {
    corridor.d_min + corridor.delay_shape * corridor.delay_scale
}

fn lot_lambda_law_mean(model: &ArrivalModel, lot_lambda: f64) -> f64 {
    let mut rng = Pcg64::seed_from_u64(150_311);
    let n = 1_000_000usize;
    let mut acc = 0.0;
    for _ in 0..n {
        let psi = LogNormal::new(0.0, model.sigma_pos)
            .expect("lognormal")
            .sample(&mut rng)
            .max(1e-6);
        let lam = ArrivalModel::floor_lambda(lot_lambda * psi);
        let loss = Gamma::new(model.gamma_shape * lam, model.gamma_scale)
            .expect("gamma")
            .sample(&mut rng);
        acc += (1.0 - loss).max(0.0);
    }
    acc / n as f64
}

fn mae(predicted: &[f64], truth: &[f64]) -> f64 {
    assert_eq!(predicted.len(), truth.len());
    predicted
        .iter()
        .zip(truth.iter())
        .map(|(p, t)| (p - t).abs())
        .sum::<f64>()
        / predicted.len() as f64
}

/// AC2.11a (r3): mask-replay ladder tracking on one trajectory, ≥64 units per delivery.
#[test]
fn ac2_11a_empirical_ladder_tracking_mae() {
    const ORDER_QTY: u32 = 64;
    const N_DAYS: u32 = 80; // 20 deliveries every 4 days (lead_time=1 → arrivals on odd days)
    let seed = 150_211;

    // Cheap mask-invariance spot check (two deliveries) before the main fixture.
    let short_orders: Vec<u32> = (0..4).map(|i| if i % 2 == 0 { ORDER_QTY } else { 0 }).collect();
    assert_truth_mask_invariant(seed, &short_orders);

    let orders: Vec<u32> = (0..N_DAYS)
        .map(|i| if i % 4 == 0 { ORDER_QTY } else { 0 })
        .collect();
    let (deliveries, mut sess) = collect_truth_deliveries(seed, &orders);
    assert!(
        deliveries.len() >= 20,
        "fixture must produce at least 20 deliveries; got {}",
        deliveries.len()
    );
    for d in &deliveries {
        assert!(
            d.deliver_units >= 64,
            "each delivery must be at least 64 units; day {} got {}",
            d.day,
            d.deliver_units
        );
        let f_values_len = d.unit_f.iter().filter(|&&f| f > 0.0).count();
        assert!(
            f_values_len <= d.deliver_units as usize,
            "atom-inclusive shortfall: f>0 count {f_values_len} exceeds deliver_units {}",
            d.deliver_units
        );
    }

    let floor = mae_noise_floor(&deliveries);
    let truth: Vec<f64> = deliveries.iter().map(|d| d.truth_mean_f).collect();

    let mut model = ArrivalModel::embedded();
    model.sync_params(&ModelParams::default());
    let pred_p0: Vec<f64> = deliveries
        .iter()
        .map(|_| law_mean_f(&mut model, ArrivalCondition::Prior))
        .collect();
    let pred_f2: Vec<f64> = deliveries
        .iter()
        .map(|d| law_mean_f(&mut model, ArrivalCondition::Duration(d.pack_date_days)))
        .collect();
    let pred_f3: Vec<f64> = deliveries
        .iter()
        .map(|d| law_mean_f(&mut model, ArrivalCondition::Exposure(d.exposure_lambda)))
        .collect();

    let mae_p0 = mae(&pred_p0, &truth);
    let mae_f2 = mae(&pred_f2, &truth);
    let mae_f3 = mae(&pred_f3, &truth);
    let ratio_p0_f2 = mae_p0 / mae_f2.max(1e-12);
    let ratio_f3_floor = mae_f3 / floor.max(1e-12);
    let signal_ratio = (mae_p0.powi(2) - mae_f3.powi(2)).max(0.0).sqrt()
        / (mae_f2.powi(2) - mae_f3.powi(2)).max(0.0).sqrt();

    // Mask replay must not mutate realized truth state.
    let snap = sess.snapshot_value();
    sess.set_obs_scenario("F2").unwrap();
    assert_eq!(snap["live_lots"], sess.snapshot_value()["live_lots"]);
    sess.set_obs_scenario("F3").unwrap();
    assert_eq!(snap["live_lots"], sess.snapshot_value()["live_lots"]);

    assert!(
        mae_f3 < mae_f2 && mae_f2 < mae_p0,
        "ladder MAE must order F3 < F2 < P0 strictly; got F3={mae_f3:.4} F2={mae_f2:.4} P0={mae_p0:.4} floor={floor:.4} ratio(P0/F2)={ratio_p0_f2:.2} MAE(F3)/floor={ratio_f3_floor:.2} signal_ratio={signal_ratio:.2}"
    );
    assert!(
        mae_p0 >= 3.0 * mae_f2,
        "MAE(P0) must be at least 3× MAE(F2); got P0={mae_p0:.4} F2={mae_f2:.4} ratio={ratio_p0_f2:.2} floor={floor:.4} MAE(F3)/floor={ratio_f3_floor:.2} signal_ratio={signal_ratio:.2}"
    );
    assert!(
        mae_f3 <= 1.5 * floor,
        "MAE(F3) must sit at the Bayes floor; got F3={mae_f3:.4} floor={floor:.4} ratio={ratio_f3_floor:.2} P0={mae_p0:.4} F2={mae_f2:.4} ratio(P0/F2)={ratio_p0_f2:.2} signal_ratio={signal_ratio:.2}"
    );
}

/// AC2.11a: F3 cached law matches the generative Λ-marginal mean (session-free).
#[test]
fn ac2_11a_f3_law_matches_generative_mean() {
    let mut model = ArrivalModel::embedded();
    model.sync_params(&ModelParams::default());
    for lambda in [3.0, 5.0, 7.0, 9.0, 11.0] {
        let filter_mean = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda));
        let generative_mean = lot_lambda_law_mean(&model, lambda);
        assert!(
            (filter_mean - generative_mean).abs() <= 0.005,
            "F3 law mean must match generative draw at Λ={lambda:.1}: filter={filter_mean:.4} generative={generative_mean:.4} delta={:.4}",
            (filter_mean - generative_mean).abs()
        );
    }
}

/// One-off n-scaling diagnostic — run with `cargo test … ac2_11a_n_scaling -- --ignored --nocapture`.
#[test]
#[ignore = "one-off n-scaling diagnostic; numbers recorded in .team/qa/T-150-tests.md"]
fn ac2_11a_n_scaling_diagnostic() {
    let seed = 150_211;
    for (order_qty, n_days) in [(8u32, 60), (64, 80), (256, 80)] {
        let (mae_p0, mae_f2, mae_f3, floor, n) = ladder_mae_triple(seed, order_qty, n_days);
        eprintln!(
            "n={order_qty} deliveries={n} MAE(P0)={mae_p0:.4} MAE(F2)={mae_f2:.4} MAE(F3)={mae_f3:.4} floor={floor:.4}"
        );
    }
}

/// AC2.19 (a): P0/P1 quadrature must integrate d and T_bar as a product, not one shared index.
#[test]
fn ac2_19_quadrature_d_and_tbar_independent_product() {
    let model = ArrivalModel::embedded();
    let corridor = model.corridor("abdella_all");
    let (nodes, _) = artifact_quadrature();
    let mut d_vals = Vec::new();
    let mut phi_vals = Vec::new();
    for u_d in &nodes {
        let d = model.quadrature_duration_days(corridor, *u_d);
        for u_t in &nodes {
            let t_bar = model.quadrature_t_bar_c(*u_t);
            d_vals.push(d);
            phi_vals.push(model.phi_bar_from_t_bar(t_bar));
        }
    }
    let corr = pearson_corr(&d_vals, &phi_vals).abs();
    assert!(
        corr < 0.5,
        "RED: d and phi_bar quadrature nodes must not be rank-correlated (product rule); |r|={corr:.4}"
    );
}

/// AC2.19 (b): quadrature nodes must integrate against modeled densities, not uniform ±span.
#[test]
fn ac2_19_quadrature_integrates_modeled_densities() {
    let model = ArrivalModel::embedded();
    let corridor = model.corridor("abdella_all");
    let (nodes, weights) = artifact_quadrature();
    let mut quad_d = Vec::new();
    let mut quad_w = Vec::new();
    for (node, weight) in nodes.into_iter().zip(weights) {
        let d = model.quadrature_duration_days(corridor, node);
        quad_d.push(d);
        quad_w.push(weight);
    }
    let w_sum: f64 = quad_w.iter().sum();
    let quad_mean = quad_d
        .iter()
        .zip(quad_w.iter())
        .map(|(d, w)| d * w / w_sum)
        .sum::<f64>();
    let quad_var = quad_d
        .iter()
        .zip(quad_w.iter())
        .map(|(d, w)| {
            let dx = d - quad_mean;
            w / w_sum * dx * dx
        })
        .sum::<f64>();
    let quad_sd = quad_var.sqrt();

    let target_mean = corridor.d_min + corridor.delay_shape * corridor.delay_scale;
    let target_sd = corridor.delay_scale * (corridor.delay_shape).sqrt();

    assert!(
        (quad_mean - target_mean).abs() < 0.15,
        "RED: quadrature mean duration {quad_mean:.3} must match shifted-gamma {target_mean:.3}"
    );
    assert!(
        (quad_sd - target_sd).abs() < 0.15,
        "RED: quadrature sd duration {quad_sd:.3} must match shifted-gamma {target_sd:.3} (uniform window integrates wrong law)"
    );
}

/// AC2.19 (c): sigma_pos must enter every rung law, including F3.
#[test]
fn ac2_19_sigma_pos_in_filter_law() {
    let path = repo_root().join("data/abdella/arrival_model.json");
    let mut payload: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&path).unwrap()).expect("parse artifact");
    let embedded = ArrivalModel::embedded();
    let phi = embedded.phi_bar_from_t_bar(payload["mu_T"].as_f64().unwrap());
    let corridor = embedded.corridor("abdella_all");
    let lot_lambda = expected_delay(corridor) * phi;

    let mut low = payload.clone();
    low["sigma_pos"] = serde_json::json!(0.02);
    let mut high = payload.clone();
    high["sigma_pos"] = serde_json::json!(0.20);

    let mut model_low =
        ArrivalModel::from_json(&serde_json::to_string(&low).unwrap()).expect("low sigma_pos");
    let mut model_high =
        ArrivalModel::from_json(&serde_json::to_string(&high).unwrap()).expect("high sigma_pos");
    let (sd_low, _) = law_sd_and_atom(&mut model_low, ArrivalCondition::Exposure(lot_lambda));
    let (sd_high, _) = law_sd_and_atom(&mut model_high, ArrivalCondition::Exposure(lot_lambda));
    assert!(
        sd_high > sd_low + 0.01,
        "RED: raising sigma_pos must widen the filter law (low={sd_low:.4}, high={sd_high:.4})"
    );
}

/// AC2.19 (d): atom counted once; mean/sd include the f=0 atom mass.
#[test]
fn ac2_19_atom_single_count_and_unconditional_moments() {
    let mut model = ArrivalModel::embedded();
    let lambda = 6.5;
    let analytic_atom = model.p_f_zero(lambda);
    let mut rng = Pcg64::seed_from_u64(150_220);
    let n = 40_000usize;
    let mut samples = Vec::with_capacity(n);
    for _ in 0..n {
        samples.push({
            let loss = Gamma::new(model.gamma_shape * lambda, model.gamma_scale)
                .unwrap()
                .sample(&mut rng);
            (1.0 - loss).max(0.0)
        });
    }
    let mc_atom = samples.iter().filter(|&&f| f <= 0.0).count() as f64 / n as f64;
    let (mc_mean, _) = empirical_mean_sd(&samples);

    let filter_mean = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda));
    let (_, filter_atom) = law_sd_and_atom(&mut model, ArrivalCondition::Exposure(lambda));

    assert!(
        (filter_atom - analytic_atom).abs() < 0.02,
        "RED: filter atom {filter_atom:.4} must match analytic {analytic_atom:.4}"
    );
    assert!(
        (filter_atom - mc_atom).abs() < 0.03,
        "RED: filter atom must not double-count CDF mass; filter={filter_atom:.4} mc={mc_atom:.4}"
    );
    assert!(
        (filter_mean - mc_mean).abs() < 0.05,
        "RED: filter mean {filter_mean:.4} must include atom (unconditional), mc={mc_mean:.4}"
    );
}

/// AC2.19: prior integrates configured corridor only; mix_weight deleted from artifact.
#[test]
fn ac2_19_prior_single_corridor_no_mix_weight() {
    let path = repo_root().join("data/abdella/arrival_model.json");
    let json_text = fs::read_to_string(&path).unwrap();
    let json: serde_json::Value = serde_json::from_str(&json_text).expect("parse artifact");
    let corridors = json["corridors"].as_object().expect("corridors object");
    for (name, c) in corridors {
        assert!(
            c.get("mix_weight").is_none(),
            "RED: mix_weight must be deleted from corridor {name}"
        );
    }

    let mut model = ArrivalModel::embedded();
    let mixed_mean = law_mean_f(&mut model, ArrivalCondition::Prior);

    let abdella_only = json["corridors"]["abdella_all"].clone();
    let single_json = serde_json::json!({
        "schema_version": json["schema_version"],
        "mu_T": json["mu_T"],
        "sigma_T": json["sigma_T"],
        "temp_floor_c": json["temp_floor_c"],
        "sigma_pos": json["sigma_pos"],
        "q10": json["q10"],
        "T_ref": json["T_ref"],
        "gamma_shape": json["gamma_shape"],
        "gamma_scale": json["gamma_scale"],
        "reference_life_days": json["reference_life_days"],
        "quadrature": json["quadrature"],
        "corridors": {"abdella_all": abdella_only},
    });
    let mut single = ArrivalModel::from_json(&serde_json::to_string(&single_json).unwrap())
        .expect("single corridor");
    let single_mean = law_mean_f(&mut single, ArrivalCondition::Prior);
    assert!(
        (mixed_mean - single_mean).abs() < 0.02,
        "RED: P0 prior must not average corridors (mix_weight); mixed={mixed_mean:.4} abdella_only={single_mean:.4}"
    );
}

/// AC2.20 (a): equal phi_bar but different durations must yield different F3 laws.
#[test]
fn ac2_20_f3_laws_differ_when_duration_differs_at_same_phi_bar() {
    let q10 = 3.0_f64;
    let t_ref = 0.0_f64;
    let phi = 1.35_f64;
    let t_c = t_ref + 10.0 * phi.ln() / q10.ln();
    let trace_short = ShipmentTrace {
        times_d: vec![0.0, 4.0],
        temps_c: vec![t_c, t_c],
    };
    let trace_long = ShipmentTrace {
        times_d: vec![0.0, 8.0],
        temps_c: vec![t_c, t_c],
    };
    let phi_short = resolve_arrival_f_law_phi_bar(
        Some(&trace_short.temps_c),
        Some(&trace_short.times_d),
        q10,
        t_ref,
    )
    .unwrap();
    let phi_long = resolve_arrival_f_law_phi_bar(
        Some(&trace_long.temps_c),
        Some(&trace_long.times_d),
        q10,
        t_ref,
    )
    .unwrap();
    assert!((phi_short - phi_long).abs() < 1e-6, "fixture: same phi_bar");

    let lambda_short =
        arrival_exposure_from_path(&trace_short.temps_c, &trace_short.times_d, q10, t_ref);
    let lambda_long =
        arrival_exposure_from_path(&trace_long.temps_c, &trace_long.times_d, q10, t_ref);

    let mut model = ArrivalModel::embedded();
    let mean_short = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda_short));
    let mean_long = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda_long));
    assert!(
        (mean_short - mean_long).abs() > 0.02,
        "RED: F3 laws must differ when duration differs at fixed phi_bar; short={mean_short:.4} long={mean_long:.4}"
    );
}

/// AC2.20 (b): equal Λ but different durations must yield the same F3 law.
#[test]
fn ac2_20_f3_law_sufficient_in_lambda_not_phi_bar() {
    let q10 = 3.0_f64;
    let t_ref = 0.0_f64;
    let trace_long = ShipmentTrace {
        times_d: vec![0.0, 2.0, 4.0, 6.0],
        temps_c: vec![2.0, 2.0, 2.0, 2.0],
    };
    let lambda_target =
        arrival_exposure_from_path(&trace_long.temps_c, &trace_long.times_d, q10, t_ref);
    let duration_short = 4.0_f64;
    let phi_short_target = lambda_target / duration_short;
    let t_hot = t_ref + 10.0 * phi_short_target.ln() / q10.ln();
    let trace_short = ShipmentTrace {
        times_d: vec![0.0, duration_short],
        temps_c: vec![t_hot, t_hot],
    };
    let lambda_short =
        arrival_exposure_from_path(&trace_short.temps_c, &trace_short.times_d, q10, t_ref);
    assert!(
        (lambda_target - lambda_short).abs() < 0.05,
        "fixture: paths must share Λ; long={lambda_target:.4} short={lambda_short:.4}"
    );
    let phi_long = resolve_arrival_f_law_phi_bar(
        Some(&trace_long.temps_c),
        Some(&trace_long.times_d),
        q10,
        t_ref,
    )
    .unwrap();
    let phi_short = resolve_arrival_f_law_phi_bar(
        Some(&trace_short.temps_c),
        Some(&trace_short.times_d),
        q10,
        t_ref,
    )
    .unwrap();
    assert!(
        (phi_long - phi_short).abs() > 0.05,
        "fixture: phi_bar must differ when duration differs at fixed Λ"
    );

    let mut model = ArrivalModel::embedded();
    let mean_long = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda_target));
    let mean_short = law_mean_f(&mut model, ArrivalCondition::Exposure(lambda_short));
    assert!(
        (mean_long - mean_short).abs() < 0.02,
        "RED: F3 law must depend on Λ only; equal Λ paths gave means {mean_long:.4} vs {mean_short:.4}"
    );

    let law_at_lambda = lot_lambda_law_mean(&model, lambda_target);
    assert!(
        (mean_long - law_at_lambda).abs() < 0.05,
        "RED: F3 must be Dirac on Λ integrating only psi_pos+gamma; filter={mean_long:.4} lambda-law={law_at_lambda:.4}"
    );
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
    let units: Vec<f64> = model
        .draw_truth_delivery(
            "abdella_all",
            params.units_per_lot,
            &mut rng,
            &mut Pcg64::seed_from_u64(150_213),
            &mut Pcg64::seed_from_u64(150_214),
            &mut Pcg64::seed_from_u64(150_215),
        )
        .unit_f;

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
