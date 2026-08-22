//! T-150 Phase 1 — terminology retirement and dead-code removal (RED until implement).

use std::fs;
use std::path::{Path, PathBuf};

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::day_step::{unit_day_step, UnitDayStepIn};
use voi_core::params::ModelParams;
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

fn read_web(rel: &str) -> String {
    fs::read_to_string(repo_root().join("web").join(rel))
        .unwrap_or_else(|err| panic!("read web/{rel}: {err}"))
}

fn rg_hits(root: &Path, pattern: &str) -> Vec<String> {
    let output = std::process::Command::new("rg")
        .args(["-n", pattern])
        .arg(root)
        .output()
        .expect("rg must be installed for T-150 grep guards");
    if !output.status.success() && output.stdout.is_empty() {
        return Vec::new();
    }
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(str::to_string)
        .collect()
}

/// AC1.1: `age_at_receipt` retired from Rust live path and TypeScript wire types.
#[test]
fn ac1_1_age_at_receipt_absent_from_live_path() {
    let crates_hits = rg_hits(&manifest_dir().join("src"), "age_at_receipt");
    assert!(
        crates_hits.is_empty(),
        "RED: age_at_receipt must be removed from crates/voi_core/src; found:\n{}",
        crates_hits.join("\n")
    );

    let web_hits = rg_hits(&repo_root().join("web/src"), "age_at_receipt");
    assert!(
        web_hits.is_empty(),
        "RED: age_at_receipt must be removed from web/src; found:\n{}",
        web_hits.join("\n")
    );

    let session = read_src("session.rs");
    assert!(
        !session.contains("\"age_at_receipt\""),
        "RED: session.rs must not wire age_at_receipt on the RPC path"
    );
}

/// AC1.2: F2 Dirac helpers and the `age_at_receipt` branch in `delivery_birth_f` removed.
#[test]
fn ac1_2_f_scalar_helpers_and_branch_removed() {
    let crates_hits = rg_hits(
        &manifest_dir().join("src"),
        "f_at_receipt_from_age|birth_f_f2_dirac",
    );
    assert!(
        crates_hits.is_empty(),
        "RED: f_at_receipt_from_age / birth_f_f2_dirac must be deleted; found:\n{}",
        crates_hits.join("\n")
    );

    let shipments = read_src("shipments.rs");
    assert!(
        !shipments.contains("age_at_receipt"),
        "RED: delivery_birth_f must not branch on age_at_receipt"
    );
}

/// AC1.3: grep guard with explicit allowlist for legacy research paths.
#[test]
fn ac1_3_effective_age_grep_guard_with_allowlist() {
    const FORBIDDEN: &[&str] = &["effective age", "age_at_receipt", "age_marginal"];

    let allow_physics = manifest_dir().join("src/physics.rs");
    let allow_rollout = manifest_dir().join("src/rollout.rs");
    let allow_py_filter = repo_root().join("src/blueberries_voi/filter");
    let allow_py_sim = repo_root().join("src/blueberries_voi/sim");

    fn collect_hits(root: &Path, pattern: &str) -> Vec<String> {
        rg_hits(root, pattern)
    }

    for pattern in FORBIDDEN {
        let web_hits = collect_hits(&repo_root().join("web/src"), pattern);
        assert!(
            web_hits.is_empty(),
            "RED: forbidden string {pattern:?} under web/src; found:\n{}",
            web_hits.join("\n")
        );

        let mut rust_hits: Vec<String> = collect_hits(&manifest_dir().join("src"), pattern)
            .into_iter()
            .filter(|line| {
                !line.contains("physics.rs")
                    && !line.contains("rollout.rs")
                    && !line.contains("/filter/")
                    && !line.contains("/sim/")
            })
            .collect();

        // age_to_f / f_to_age names are allowed on the legacy Weibull path.
        if *pattern == "effective age" {
            rust_hits.retain(|line| !line.contains("age_to_f") && !line.contains("f_to_age"));
        }

        assert!(
            rust_hits.is_empty(),
            "RED: forbidden string {pattern:?} on live Rust path (allowlist: physics.rs, rollout.rs, Python filter/sim); found:\n{}",
            rust_hits.join("\n")
        );
    }

    // Allowlist must remain readable for legacy goldens.
    let physics = read_src("physics.rs");
    assert!(physics.contains("age_to_f") && physics.contains("f_to_age"));
    assert!(allow_py_filter.is_dir());
    assert!(allow_py_sim.is_dir());
    let _ = (&allow_physics, &allow_rollout);
}

/// AC1.4: freshness-grid identifiers renamed in web projector and charts.
#[test]
fn ac1_4_freshness_identifier_renames() {
    let projector = read_web("src/engine/projector.ts");
    assert!(
        projector.contains("fMarginalFromFlat"),
        "RED: projector must export fMarginalFromFlat"
    );
    assert!(
        !projector.contains("ageMarginalFromFlat"),
        "RED: ageMarginalFromFlat must be renamed"
    );

    let inventory = read_web("src/charts/inventoryTarget.ts");
    for old in [
        "AgeCompositionRow",
        "ageCompositionSeries",
        "expectedAgeBands",
        "renderAgeComposition",
        "age-young",
        "age-mid",
        "age-old",
        ".age-series",
    ] {
        assert!(
            !inventory.contains(old),
            "RED: inventoryTarget must rename {old}"
        );
    }
    for new in [
        "FreshnessCompositionRow",
        "fCompositionSeries",
        "expectedFreshnessBands",
        "renderFreshnessComposition",
        "freshness-young",
        "freshness-mid",
        "freshness-old",
        ".freshness-series",
    ] {
        assert!(
            inventory.contains(new),
            "RED: inventoryTarget must introduce {new}"
        );
    }
}

/// AC1.5: user-visible strings carry no age framing (tab label asserted here; axis in projector.test.ts).
#[test]
fn ac1_5_user_visible_strings_no_age_framing() {
    let tabs = read_web("src/react/StoreChartTabs.tsx");
    assert!(
        !tabs.contains("Age & spoilage"),
        "RED: tab label must not say Age & spoilage"
    );
    assert!(
        tabs.contains("Freshness & spoilage") || tabs.contains("freshness-spoilage"),
        "RED: tab must use freshness framing"
    );
    assert!(
        !tabs.contains("\"age-spoilage\""),
        "RED: view id age-spoilage must be renamed"
    );

    let inspector = read_web("src/react/DayInspector.tsx");
    assert!(
        !inspector.contains("Belief peaks near age bin"),
        "RED: DayInspector must not reference age bins"
    );

    let controls = read_web("src/controls.ts");
    for needle in ["arrival-age", "arrival age", "effective age"] {
        assert!(
            !controls.to_lowercase().contains(needle),
            "RED: controls.ts must not contain {needle:?}"
        );
    }
}

/// AC1.6: doc comments on the live path use exposure language for Λ.
#[test]
fn ac1_6_exposure_language_in_doc_comments() {
    let physics = read_src("physics.rs");
    for line in physics.lines().take(30) {
        let lower = line.to_lowercase();
        if lower.contains("eta_ref") || lower.contains("lambda") || lower.contains("exposure") {
            if lower.contains("age") && !lower.contains("age_to_f") && !lower.contains("f_to_age") {
                panic!("RED: physics.rs live doc still uses age framing: {line}");
            }
        }
    }
    assert!(
        physics.contains("cumulative thermal exposure")
            || physics.contains("reference-days"),
        "RED: physics.rs must describe Λ as cumulative thermal exposure"
    );

    let params_py = fs::read_to_string(repo_root().join("src/blueberries_voi/model/params.py"))
        .expect("params.py");
    assert!(
        !params_py.contains("effective age"),
        "RED: params.py must not describe cohorts as effective age on the live path"
    );
    assert!(
        params_py.contains("cumulative thermal exposure")
            || params_py.contains("reference-days"),
        "RED: params.py must use exposure language for Λ"
    );
}

/// AC1.7: pre-sampled `delivery_unit_f` (session truth path) yields deterministic delivery.
#[test]
fn ac1_7_delivery_unit_f_deterministic_on_production_path() {
    let params = ModelParams::default();
    let units = params.units_per_lot;
    let delivery_unit_f = vec![0.85; units];

    let base = UnitDayStepIn {
        freshness: vec![],
        lot_offsets: vec![0],
        demand: None,
        gamma_decrement: None,
        deliver: true,
        deliver_units: Some(units as u32),
        delivery_unit_f: Some(delivery_unit_f),
        units_per_lot: Some(units),
    };

    let mut rng_a = Pcg64::seed_from_u64(150);
    let out_a = unit_day_step(
        &base,
        &params,
        &[],
        Some(&mut rng_a),
        None,
        None,
        None,
    );

    let mut rng_b = Pcg64::seed_from_u64(150);
    let out_b = unit_day_step(
        &base,
        &params,
        &[],
        Some(&mut rng_b),
        None,
        None,
        None,
    );

    assert_eq!(
        out_a.freshness, out_b.freshness,
        "production delivery path must be deterministic when delivery_unit_f is pre-sampled"
    );
    assert_eq!(out_a.lot_offsets, out_b.lot_offsets);
}
