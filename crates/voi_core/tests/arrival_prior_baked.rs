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
fn sync_params_store_q10_does_not_rebuild_arrival_prior() {
    let _guard = serial_guard();
    let mut model = ArrivalModel::embedded();
    model.clear_prior_rebuild_telemetry();
    let mut params = voi_core::ModelParams::default();
    params.q10 = 3.5;
    model.sync_params(&params);
    assert!(
        !model.prior_rebuilt_since_clear(),
        "store q10 must not rebuild transit Prior CDF (baked artifact q10)"
    );
}

#[test]
fn handle_rpc_studio_init_config_fast() {
    let _guard = serial_guard();
    let req = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {
            "config": {
                "seed": 42,
                "n_particles": 200,
                "q10": 3,
                "t_ref_c": 0,
                "arrival_product": "abdella_mix",
            }
        },
    });
    let t0 = std::time::Instant::now();
    let out = handle_rpc(&req.to_string());
    let elapsed = t0.elapsed();
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true);
    assert_eq!(
        v["result"]["arrival_prior_rebuilt"], false,
        "studio init with store q10=3 must keep baked abdella_mix prior"
    );
    if !cfg!(debug_assertions) {
        assert!(
            elapsed.as_secs() < 5,
            "studio-shaped init took {elapsed:?}; expected baked Prior wire + no prior rebuild"
        );
    }
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

#[test]
#[ignore = "debug probe"]
fn first_init_timing_probe() {
    let _guard = serial_guard();
    let req = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {"seed": 42, "n_particles": 16, "arrival_product": "abdella_all"},
    });
    let s = req.to_string();
    let t0 = std::time::Instant::now();
    let out = handle_rpc(&s);
    let e = t0.elapsed();
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    eprintln!("FIRST init: {:?} rebuilt={} rebuild_ms={}", e, v["result"]["arrival_prior_rebuilt"], v["result"]["arrival_prior_rebuild_ms"]);
}

#[test]
fn studio_shaped_init_abdella_mix_no_rebuild() {
    let _guard = serial_guard();
    let req = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {
            "seed": 42,
            "config": {
                "n_particles": 200,
                "H": 7,
                "arrival_product": "abdella_mix",
                "q10": 3.0,
                "t_ref_c": 0.0,
                "obs_scenario": "P1"
            }
        }
    });
    let s = req.to_string();
    let t0 = std::time::Instant::now();
    let out = handle_rpc(&s);
    let e = t0.elapsed();
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true);
    eprintln!(
        "STUDIO_MIX: {:?} rebuilt={} rebuild_ms={}",
        e,
        v["result"]["arrival_prior_rebuilt"],
        v["result"]["arrival_prior_rebuild_ms"]
    );
    assert_eq!(
        v["result"]["arrival_prior_rebuilt"], false,
        "studio default abdella_mix must not rebuild baked prior"
    );
}

#[test]
fn handle_rpc_init_omits_arrival_summary() {
    let _guard = serial_guard();
    let req = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {
            "seed": 42,
            "config": {
                "n_particles": 200,
                "arrival_product": "abdella_mix",
                "obs_scenario": "P1"
            }
        },
    });
    let out = handle_rpc(&req.to_string());
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true);
    assert!(
        v["result"].get("arrival_summary").is_none(),
        "init must omit arrival_summary for lazy chart load"
    );
}

#[test]
fn handle_rpc_arrival_summary_after_init() {
    let _guard = serial_guard();
    let init = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {"seed": 42, "config": {"obs_scenario": "P1"}},
    });
    handle_rpc(&init.to_string());
    let t0 = std::time::Instant::now();
    let out = handle_rpc(
        r#"{"id":2,"method":"arrival_summary","params":{}}"#,
    );
    let elapsed = t0.elapsed();
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true);
    assert!(v["result"]["curve"].is_array());
    assert_eq!(v["result"]["rung"], "P1");
    eprintln!("arrival_summary RPC: {:?}", elapsed);
}

#[test]
fn prior_wire_from_marginal_cache_matches_rung_law_on_grid() {
    use voi_core::arrival::{ArrivalCondition, ArrivalModel};
    use voi_core::arrival_wire::arrival_summary_wire;
    use voi_core::obs::channels_for_preset;

    let _guard = serial_guard();
    let model = ArrivalModel::embedded();
    let product = model.active_corridor();
    let channels = channels_for_preset("P1").unwrap();

    let cached = model.prior_rung_law_from_marginal_cache(81);
    let integrated = model.rung_law_on_grid(ArrivalCondition::Prior, product, 81);
    let (_, baked_atom, baked_mean, _) = model.export_marginal_prior_wire();
    assert!(
        (cached.mean_f - baked_mean).abs() < 1e-6,
        "cached wire mean must track filter prior: {} vs bake {}",
        cached.mean_f,
        baked_mean
    );
    assert!(
        (cached.atom_f0 - baked_atom).abs() < 1e-12,
        "atom_f0 must match baked prior"
    );
    assert!(
        (cached.mean_f - integrated.mean_f).abs() < 0.002,
        "mean_f vs 81-pt integration: cached {} vs integrated {}",
        cached.mean_f,
        integrated.mean_f
    );
    for (a, b) in cached.cdf.iter().zip(integrated.cdf.iter()) {
        assert!(
            (a - b).abs() < 0.002,
            "cdf mismatch at grid point: cached {a} vs integrated {b}"
        );
    }

    let summary = arrival_summary_wire(&model, product, channels, 0.0);
    assert_eq!(summary["rung"], "P1");
    assert!(
        (summary["mean_f"].as_f64().unwrap() - cached.mean_f).abs() < 1e-9
    );
}

#[test]
#[ignore = "debug probe"]
fn init_cost_breakdown_studio_mix() {
    use std::time::Instant;
    use voi_core::arrival_wire::arrival_summary_wire;
    use voi_core::obs::channels_for_preset;
    use voi_core::session::EngineSession;

    let _guard = serial_guard();
    let mut s = EngineSession::new(42);
    let t_embed = Instant::now();
    let _ = voi_core::arrival::shared_embedded_arrival();
    eprintln!("shared_embedded (warm): {:?}", t_embed.elapsed());

    let t0 = Instant::now();
    s.reset(42);
    eprintln!("reset: {:?}", t0.elapsed());

    let t1 = Instant::now();
    s.apply_configure(serde_json::json!({
        "seed": 42,
        "config": {
            "n_particles": 200,
            "H": 7,
            "arrival_product": "abdella_mix",
            "q10": 3.0,
            "t_ref_c": 0.0,
            "obs_scenario": "P1"
        }
    }));
    eprintln!("apply_configure: {:?}", t1.elapsed());
    let snap_cfg = s.snapshot_value();
    eprintln!(
        "after configure: rebuilt={} rebuild_ms={}",
        snap_cfg["arrival_prior_rebuilt"],
        snap_cfg["arrival_prior_rebuild_ms"]
    );

    let model = voi_core::arrival::ArrivalModel::embedded();
    let channels = channels_for_preset("P1").unwrap();
    let t2 = Instant::now();
    let _summary = arrival_summary_wire(&model, "abdella_mix", channels, 0.0);
    eprintln!("arrival_summary_wire alone: {:?}", t2.elapsed());

    let t3 = Instant::now();
    let _snap = s.snapshot_value_init();
    eprintln!("init snapshot (no arrival_summary): {:?}", t3.elapsed());
}
