//! Joint constraint search over mixture weight, q10, and leg-setpoint shift.
//!
//! **Legacy / diagnostic** — superseded by Ax BO (`t163_eval_trial` + notebook 14).
//! Run only for grid sanity checks, not production calibration.
//!
//! Run: `cargo run -p voi_core --release --example t163_joint_constraint_search`

#[path = "support/t163_joint_search_common.rs"]
mod common;

use serde_json::json;
use voi_core::{ac2_11a_ratio, configured_model, evaluate_fast_trial};

use common::{grid_size, par_map_grid};

const PHASE2_TOP_N: usize = 10;
const AC2_11A_MIN_RATIO: f64 = 2.18;

#[derive(Clone, Copy)]
struct Phase1Row {
    p_short: f64,
    q10: f64,
    delta_c: f64,
    ac2_19_margin: f64,
    p50: f64,
    pct_60_90: f64,
    session_f: f64,
}

fn main() {
    let total = grid_size();
    eprintln!("phase1 (legacy grid): {total} configs");

    let phase1: Vec<Phase1Row> = par_map_grid("phase1", |(p_short, q10, delta_c)| {
        let result = evaluate_fast_trial(p_short, q10, delta_c, false, 150_211);
        Phase1Row {
            p_short,
            q10,
            delta_c,
            ac2_19_margin: result.ac2_19_margin,
            p50: result.p50,
            pct_60_90: result.pct_60_90,
            session_f: result.session_f,
        }
    });

    let mut fast_pass: Vec<Phase1Row> = phase1
        .iter()
        .copied()
        .filter(|row| {
            row.ac2_19_margin > 0.0
                && row.session_f >= 0.55
                && row.p50 >= 0.65
                && row.pct_60_90 >= 0.45
        })
        .collect();
    fast_pass.sort_by(|a, b| {
        b.ac2_19_margin
            .partial_cmp(&a.ac2_19_margin)
            .unwrap()
    });
    fast_pass.truncate(PHASE2_TOP_N);

    eprintln!(
        "phase2: ac2_11a on {} survivors (top {} by ac2_19 among fast gates)",
        fast_pass.len(),
        PHASE2_TOP_N
    );

    let mut passing = Vec::new();
    let mut best_ratio = Vec::new();
    for (i, row) in fast_pass.iter().enumerate() {
        eprintln!("phase2: {}/{}", i + 1, fast_pass.len());
        let mut model = configured_model(row.p_short, row.q10, row.delta_c);
        let ratio = ac2_11a_ratio(&mut model);
        let json_row = json!({
            "p_short": row.p_short,
            "q10": row.q10,
            "delta_c": row.delta_c,
            "ac2_19_margin": row.ac2_19_margin,
            "p50": row.p50,
            "pct_60_90": row.pct_60_90,
            "session_f": row.session_f,
            "ac2_11a_ratio": ratio,
        });
        if ratio >= AC2_11A_MIN_RATIO {
            passing.push(json_row.clone());
        }
        best_ratio.push(json_row);
    }

    passing.sort_by(|a, b| {
        b["ac2_11a_ratio"]
            .as_f64()
            .unwrap()
            .partial_cmp(&a["ac2_11a_ratio"].as_f64().unwrap())
            .unwrap()
    });
    best_ratio.sort_by(|a, b| {
        b["ac2_11a_ratio"]
            .as_f64()
            .unwrap()
            .partial_cmp(&a["ac2_11a_ratio"].as_f64().unwrap())
            .unwrap()
    });

    println!(
        "{}",
        json!({
            "phase1_configs": total,
            "fast_pass_count": fast_pass.len(),
            "passing_all_four": passing,
            "best_ac2_11a_ratio": best_ratio.into_iter().take(20).collect::<Vec<_>>(),
        })
    );
}
