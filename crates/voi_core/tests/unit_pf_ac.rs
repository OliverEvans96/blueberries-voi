//! T-C2-A AC-unit-pf: unit_ll / unit_pf wiring and observation router (RED until implemented).

use std::fs;
use std::path::PathBuf;

use voi_core::obs::{mask_for, RichDay};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("failed to read src/{name}: {err}"))
}

fn read_lib_rs() -> String {
    read_src("lib.rs")
}

fn unit_ll_wired() -> bool {
    manifest_dir().join("src/unit_ll.rs").is_file() && read_lib_rs().contains("pub mod unit_ll")
}

fn unit_pf_wired() -> bool {
    manifest_dir().join("src/unit_pf.rs").is_file() && read_lib_rs().contains("pub mod unit_pf")
}

fn require_unit_ll() {
    if !manifest_dir().join("src/unit_ll.rs").is_file() {
        panic!("AC-unit-pf: missing crates/voi_core/src/unit_ll.rs");
    }
    let lib = read_lib_rs();
    if !lib.contains("pub mod unit_ll") {
        panic!("AC-unit-pf: lib.rs must declare `pub mod unit_ll`");
    }
    let body = read_src("unit_ll.rs");
    for sym in [
        "sequential_kernel_path_logprob",
        "p1_totals_loglik",
        "loglik_sales_by_units",
    ] {
        if !body.contains(sym) && !lib.contains(sym) {
            panic!("AC-unit-pf: unit_ll must export `{sym}`");
        }
    }
}

fn require_unit_pf() {
    if !manifest_dir().join("src/unit_pf.rs").is_file() {
        panic!("AC-unit-pf: missing crates/voi_core/src/unit_pf.rs");
    }
    let lib = read_lib_rs();
    if !lib.contains("pub mod unit_pf") {
        panic!("AC-unit-pf: lib.rs must declare `pub mod unit_pf`");
    }
    let body = read_src("unit_pf.rs");
    for sym in ["UnitParticleBank", "filter_step_unit"] {
        if !body.contains(sym) && !lib.contains(sym) {
            panic!("AC-unit-pf: unit_pf must export `{sym}`");
        }
    }
}

#[test]
fn unit_ll_module_file_present() {
    require_unit_ll();
}

#[test]
fn unit_pf_module_file_present() {
    require_unit_pf();
}

#[test]
fn filter_step_unit_uses_systematic_resample_not_multinomial() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("systematic_resample"),
        "filter_step_unit must resample via production systematic_resample"
    );
    assert!(
        !body.contains("fn resample(") || body.contains("systematic_resample"),
        "unit_pf must not use bench-style multinomial resample helper"
    );
}

#[test]
fn p1_router_scores_via_p1_totals_loglik() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("p1_totals_loglik"),
        "P1 totals path must call unit_ll::p1_totals_loglik"
    );
}

#[test]
fn f1_router_scores_via_loglik_sales_by_units() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("loglik_sales_by_units"),
        "sales_by path must call unit_ll::loglik_sales_by_units"
    );
}

#[test]
fn filter_never_synthesizes_sales_by_from_totals() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    let lowered = body.to_lowercase();
    assert!(
        !lowered.contains("sales_by = some") && !lowered.contains("sales_by=some"),
        "filter_step_unit must not invent sales_by from totals"
    );
}

#[test]
fn p1_mask_obs_sales_by_stays_none() {
    let rich = RichDay {
        sales_total: 5,
        waste_total: 2,
        arrivals: 0,
        sales_by: vec![3, 2],
        waste_by: vec![1, 1],
        lot_ids: vec![1, 2],
        age_at_receipt: None,
        pack_date_days: None,
    };
    let obs = mask_for("P1").expect("P1").apply(&rich);
    assert_eq!(obs.sales_tot, Some(5));
    assert_eq!(obs.waste_tot, Some(2));
    assert!(obs.sales_by.is_none(), "P1 mask must not expose sales_by");
}

#[test]
fn f1_mask_exposes_sales_by_for_router() {
    let rich = RichDay {
        sales_total: 5,
        waste_total: 2,
        arrivals: 0,
        sales_by: vec![3, 2],
        waste_by: vec![1, 1],
        lot_ids: vec![10, 11],
        age_at_receipt: None,
        pack_date_days: None,
    };
    let obs = mask_for("F1").expect("F1").apply(&rich);
    assert_eq!(obs.sales_by.as_deref(), Some(&[3u32, 2][..]));
    assert!(obs.sales_tot.is_some());
}

#[test]
fn sequential_kernel_path_logprob_feasible_finite() {
    require_unit_ll();
    panic!("AC-unit-pf: wire unit_ll API test for sequential_kernel_path_logprob");
}

#[test]
fn p1_totals_loglik_impossible_sales_neg_inf() {
    require_unit_ll();
    panic!("AC-unit-pf: wire unit_ll API test for infeasible p1_totals_loglik");
}

#[test]
fn unit_pf_l20_scripted_mean_f_mae_and_order_match() {
    require_unit_pf();
    require_unit_ll();
    panic!(
        "AC-unit-pf: scripted L=20 N=200 U=15 study must achieve mean_f MAE < 0.02 and 100% order match"
    );
}

#[test]
fn bench_c2_a_totals_study_uses_unit_ll_not_inline_copy() {
    let bench = read_src("bin/bench_c2_a_totals_study.rs");
    assert!(
        bench.contains("voi_core::unit_ll::") || bench.contains("use voi_core::unit_ll"),
        "bench_c2_a_totals_study must call production unit_ll, not duplicate inline LL"
    );
}
