//! Compile-time baked default arrival Prior CDF (studio fast init).

use std::sync::Mutex;

use sha2::{Digest, Sha256};
use voi_core::arrival::{ArrivalModel, embedded_arrival_model, export_baked_prior};
use voi_core::handle_rpc;

static SERIAL: Mutex<()> = Mutex::new(());

fn serial_guard() -> std::sync::MutexGuard<'static, ()> {
    SERIAL.lock().unwrap_or_else(|e| e.into_inner())
}

fn sha256_hex(data: &[u8]) -> String {
    let hash = Sha256::digest(data);
    hash.iter().map(|b| format!("{:02x}", b)).collect()
}

#[test]
fn arrival_model_json_staleness_guard() {
    let _guard = serial_guard();
    let json = embedded_arrival_model();
    let hash = sha256_hex(json.as_bytes());
    let baked_hash = voi_core::arrival::baked_artifact_sha256_for_tests();
    assert_eq!(
        hash,
        baked_hash,
        "arrival_model.json hash mismatch — run ./scripts/regenerate-arrival-prior.sh"
    );
}

#[test]
fn baked_prior_matches_live_integration() {
    let _guard = serial_guard();
    let json = embedded_arrival_model();
    let live = export_baked_prior(json).expect("live");
    let (baked_cdf, baked_atom, baked_mean, baked_var) =
        ArrivalModel::embedded().export_marginal_prior_wire();
    assert!((live.atom_f0 - baked_atom).abs() < 1e-12, "atom_f0 mismatch");
    assert!((live.mean_f - baked_mean).abs() < 1e-12, "mean_f mismatch");
    assert!((live.variance_f - baked_var).abs() < 1e-12, "variance_f mismatch");
    for (a, b) in live.cdf.iter().zip(baked_cdf.iter()) {
        assert!((a - b).abs() < 1e-12, "cdf mismatch at grid point");
    }
}

#[test]
fn embedded_prior_load_fast() {
    let _guard = serial_guard();
    let t0 = std::time::Instant::now();
    let _ = ArrivalModel::embedded();
    let elapsed = t0.elapsed();
    if !cfg!(debug_assertions) {
        assert!(
            elapsed.as_secs() < 1,
            "embedded() took {elapsed:?}; expected baked fast path"
        );
    }
}

#[test]
fn sync_params_q10_change_rebuilds_prior() {
    let _guard = serial_guard();
    let mut model = ArrivalModel::embedded();
    model.clear_prior_rebuild_telemetry();
    let mut params = voi_core::ModelParams::default();
    params.q10 = 3.5;
    model.sync_params(&params);
    assert!(model.prior_rebuilt_since_clear());
}

#[test]
fn handle_rpc_second_init_fast() {
    let _guard = serial_guard();
    let params = serde_json::json!({
        "seed": 42,
        "n_particles": 16,
        "arrival_product": "abdella_all",
    });
    let req = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": params,
    });
    let req_str = req.to_string();
    handle_rpc(&req_str);
    let t0 = std::time::Instant::now();
    let out = handle_rpc(&req_str);
    let elapsed = t0.elapsed();
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true);
    assert_eq!(
        v["result"]["arrival_prior_rebuilt"], false,
        "second init must not rebuild the Prior CDF"
    );
    if !cfg!(debug_assertions) {
        assert!(
            elapsed.as_secs() < 5,
            "second handle_rpc init took {elapsed:?} (budget 5s without prior rebuild)"
        );
    }
}
