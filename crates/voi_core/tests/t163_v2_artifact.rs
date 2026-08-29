//! T-163 v2-artifact shard — committed artifact schema and unified corridor defaults (RED).

use std::fs;

use voi_core::arrival::embedded_arrival_model;
use voi_core::session::EngineSession;

fn repo_root() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn parse_artifact_json() -> serde_json::Value {
    serde_json::from_str(embedded_arrival_model()).expect("embedded artifact json")
}

/// S1.9 — v2 thermal model fields: trip modes and hourly OU amplitude.
#[test]
fn artifact_has_v2_thermal_fields() {
    let json = parse_artifact_json();
    let modes = json.get("thermal_modes").unwrap_or_else(|| {
        panic!("artifact must include thermal_modes (cool/nominal/warm trip mode mix)")
    });
    for mode in ["cool", "nominal", "warm"] {
        let entry = modes.get(mode).unwrap_or_else(|| {
            panic!("thermal_modes must define {mode}")
        });
        assert!(
            entry.get("offset_c").is_some() && entry.get("p").is_some(),
            "thermal_modes.{mode} needs offset_c and p"
        );
    }
    let sigma = json
        .get("sigma_hour")
        .and_then(|v| v.as_f64())
        .unwrap_or_else(|| panic!("artifact must include sigma_hour (hourly OU amplitude)"));
    assert!(sigma > 0.0, "sigma_hour must be positive, got {sigma}");
}

/// S1.9 — extend truncated-normal retirement: v2 break + thermal fields present.
#[test]
fn artifact_drops_truncated_normal_and_carries_v2_break_fields() {
    let json = parse_artifact_json();
    for gone in ["mu_T", "sigma_T", "temp_floor_c"] {
        assert!(
            json.get(gone).is_none(),
            "artifact must not still carry retired key {gone}"
        );
    }
    for want in ["legs", "T_break", "rho", "tau_bar", "thermal_modes", "sigma_hour"] {
        assert!(
            json.get(want).is_some(),
            "artifact must carry v2 field {want}"
        );
    }
}

/// S1.11 — default session uses unified `abdella_mix`; haul chips demoted in studio.
#[test]
fn session_default_unified_corridor() {
    let snap = EngineSession::new(42).snapshot_value();
    let applied = snap["applied_config"]
        .as_object()
        .expect("applied_config object");
    assert_eq!(
        applied["arrival_product"].as_str(),
        Some("abdella_mix"),
        "default session must use unified abdella_mix corridor"
    );

    let controls = fs::read_to_string(repo_root().join("web/src/controls.ts"))
        .expect("read web controls");
    assert!(
        !controls.contains("data-arrival=\"short_haul\""),
        "studio must demote short_haul chip (unified transit law)"
    );
    assert!(
        !controls.contains("data-arrival=\"long_haul\""),
        "studio must demote long_haul chip (unified transit law)"
    );
}
