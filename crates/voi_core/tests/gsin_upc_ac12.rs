//! AC-G3 / AC-G4: GSIN/UPC diagnostic regression gates (T-141).

use std::process::Command;

const BIAS_MAX: f64 = 1e-9;
/// Independent per-unit aging: lot-level mean-f can lag UPC slightly on short fixtures.
const LOT_MEAN_F_SLACK: f64 = 0.03;
const SCORED_SPOIL_CHANNELS: &[&str] = &["P1", "F1", "F2a", "F2", "F3"];

#[derive(serde::Deserialize)]
struct DiagRow {
    regime: String,
    channel: String,
    count_bias: f64,
    store_mean_f_mae: f64,
    lot_mean_f_mae: f64,
    ess: f64,
}

fn run_gsin_upc_diag_json() -> Vec<DiagRow> {
    let manifest = env!("CARGO_MANIFEST_DIR");
    let repo = std::path::Path::new(manifest).parent().unwrap().parent().unwrap();
    let out = std::env::temp_dir().join(format!("gsin_upc_ac12_{}.json", std::process::id()));
    let status = Command::new("cargo")
        .args([
            "run",
            "-p",
            "voi_core",
            "--release",
            "--example",
            "gsin_upc_diag",
            "--",
        ])
        .arg(&out)
        .current_dir(repo)
        .status()
        .expect("spawn gsin_upc_diag");
    assert!(status.success(), "gsin_upc_diag must exit 0");
    let text = std::fs::read_to_string(&out).expect("read diag json");
    serde_json::from_str(&text).expect("parse diag json")
}

#[test]
fn gsin_upc_count_bias_is_zero_on_spoilage_rungs() {
    let rows = run_gsin_upc_diag_json();
    assert_eq!(rows.len(), 24, "expected 24 diagnostic rows");
    for row in &rows {
        if !SCORED_SPOIL_CHANNELS.contains(&row.channel.as_str()) {
            continue;
        }
        assert!(
            row.count_bias.abs() <= BIAS_MAX,
            "{} / {} count_bias={} exceeds BIAS_MAX={BIAS_MAX}",
            row.regime,
            row.channel,
            row.count_bias
        );
    }
}

/// AC-G4: GSIN rung metrics must not exceed UPC counterpart (non-regression guard).
#[test]
fn gsin_upc_gsin_le_upc_on_comparable_metrics() {
    let rows = run_gsin_upc_diag_json();
    let key = |r: &DiagRow| (r.regime.clone(), r.channel.clone());
    let by_key: std::collections::HashMap<_, _> = rows.iter().map(|r| (key(r), r)).collect();

    for regime in [
        "Homogeneous fleet, overlapping lots",
        "Heterogeneous fleet, overlapping lots",
        "Heterogeneous fleet, deep shelf",
    ] {
        let upc_p1 = by_key
            .get(&(regime.to_string(), "P1".to_string()))
            .expect("P1 row");
        let gsin_f1 = by_key
            .get(&(regime.to_string(), "F1".to_string()))
            .expect("F1 row");
        assert!(
            gsin_f1.store_mean_f_mae <= upc_p1.store_mean_f_mae + 1e-9,
            "{regime}: F1 store_mean_f_mae {} > P1 {}",
            gsin_f1.store_mean_f_mae,
            upc_p1.store_mean_f_mae
        );
        assert!(
            gsin_f1.lot_mean_f_mae <= upc_p1.lot_mean_f_mae + LOT_MEAN_F_SLACK,
            "{regime}: F1 lot_mean_f_mae {} > P1 {} + {LOT_MEAN_F_SLACK}",
            gsin_f1.lot_mean_f_mae,
            upc_p1.lot_mean_f_mae
        );
        assert!(
            gsin_f1.ess >= upc_p1.ess - 1e-6,
            "{regime}: F1 ess {} < P1 {}",
            gsin_f1.ess,
            upc_p1.ess
        );
    }
}
