//! AC-G3 / AC-G4: LGTIN/UPC diagnostic regression gates (T-141).

const BIAS_MAX: f64 = 1e-9;
/// Effective sample size must stay healthy on every rung. This is a *floor*, not a
/// LGTIN-vs-UPC comparison: a richer likelihood legitimately concentrates weight and so
/// lowers ESS. Requiring `F1.ess >= P1.ess` asserted the opposite of what a more
/// informative channel does, and only ever passed because the harness read ESS back off
/// the post-resample (uniform) weights, where every rung reports exactly N.
const ESS_FLOOR_FRACTION: f64 = 0.25;
const N_PARTICLES: f64 = 200.0;
const SCORED_SPOIL_CHANNELS: &[&str] = &["P1", "F1", "F2a", "F2", "F3"];

const REGIMES: &[&str] = &[
    "Homogeneous fleet, overlapping lots",
    "Heterogeneous fleet, overlapping lots",
    "Heterogeneous fleet, deep shelf",
    "Thermal fleet, overlapping lots",
];

/// Regimes on which LGTIN must strictly win the *store aggregate* freshness metric. The
/// thermal fixture is excluded: pack date is uninformative there by construction, so P1
/// and F1 land within seed noise of each other (~0.4% at 12 seeds) and the sign of the
/// difference is not meaningful. Per-lot metrics below cover all four.
const STORE_MEAN_F_REGIMES: &[&str] = &[
    "Homogeneous fleet, overlapping lots",
    "Heterogeneous fleet, overlapping lots",
    "Heterogeneous fleet, deep shelf",
];

#[derive(serde::Deserialize, Clone)]
struct DiagRow {
    regime: String,
    channel: String,
    count_bias: f64,
    store_mean_f_mae: f64,
    lot_mean_f_mae: f64,
    lot_count_mae: f64,
    ess: f64,
}

fn load_lgtin_upc_diag_json() -> Vec<DiagRow> {
    let manifest = env!("CARGO_MANIFEST_DIR");
    let repo = std::path::Path::new(manifest)
        .parent()
        .unwrap()
        .parent()
        .unwrap();
    let path = repo.join("experiments/data/lgtin_upc_after.json");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("read committed {}: {e}", path.display()));
    serde_json::from_str(&text).expect("parse diag json")
}

fn row<'a>(rows: &'a [DiagRow], regime: &str, channel: &str) -> &'a DiagRow {
    rows.iter()
        .find(|r| r.regime == regime && r.channel == channel)
        .unwrap_or_else(|| panic!("missing row {regime} / {channel}"))
}

#[test]
fn lgtin_upc_count_bias_is_zero_on_spoilage_rungs() {
    let rows = load_lgtin_upc_diag_json();
    assert_eq!(rows.len(), 24, "expected 24 diagnostic rows");
    for row in rows {
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

/// AC-G4: LGTIN rung metrics must not exceed UPC counterpart (non-regression guard).
#[test]
fn lgtin_upc_lgtin_le_upc_on_comparable_metrics() {
    let rows = load_lgtin_upc_diag_json();

    for regime in STORE_MEAN_F_REGIMES {
        let (p1, f1) = (row(&rows, regime, "P1"), row(&rows, regime, "F1"));
        assert!(
            f1.store_mean_f_mae <= p1.store_mean_f_mae + 1e-9,
            "{regime}: F1 store_mean_f_mae {} > P1 {}",
            f1.store_mean_f_mae,
            p1.store_mean_f_mae
        );
    }

    for regime in REGIMES {
        let (p1, f1) = (row(&rows, regime, "P1"), row(&rows, regime, "F1"));

        // Per-lot freshness: independent per-unit aging (ADR 0143) makes lot-resolved
        // spoilage level-informative, so LGTIN wins outright rather than within a slack.
        assert!(
            f1.lot_mean_f_mae <= p1.lot_mean_f_mae + 1e-9,
            "{regime}: F1 lot_mean_f_mae {} > P1 {}",
            f1.lot_mean_f_mae,
            p1.lot_mean_f_mae
        );

        // Per-lot count is *exact* under LGTIN — sales and spoils are attributed to named
        // lots, so each segment conserves the way the store total does. UPC cannot do
        // this, and a UPC row reading 0.0 would mean the metric had stopped measuring.
        assert!(
            f1.lot_count_mae <= 1e-9,
            "{regime}: F1 lot_count_mae {} is not exact",
            f1.lot_count_mae
        );
        assert!(
            p1.lot_count_mae > 1e-6,
            "{regime}: P1 lot_count_mae {} — UPC cannot resolve per-lot counts, so a \
             zero here means the per-lot metric is not reading real lot boundaries",
            p1.lot_count_mae
        );

        for channel in SCORED_SPOIL_CHANNELS {
            let r = row(&rows, regime, channel);
            assert!(
                r.ess >= N_PARTICLES * ESS_FLOOR_FRACTION,
                "{regime} / {channel}: ess {} below floor {}",
                r.ess,
                N_PARTICLES * ESS_FLOOR_FRACTION
            );
            assert!(
                r.ess <= N_PARTICLES - 1e-6,
                "{regime} / {channel}: ess {} == N means ESS is being read off \
                 post-resample uniform weights, not the filter's pre-resample diagnostic",
                r.ess
            );
        }
    }
}
