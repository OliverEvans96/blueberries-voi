//! Fast grid (ac2_19 only): `cargo run -p voi_core --release --example t163_joint_fast_grid`

#[path = "support/t163_joint_search_common.rs"]
mod common;

use serde_json::{json, Value};
use voi_core::arrival::ArrivalModel;

use common::{ac2_19_min_margin, apply_config, fast_grid_size, par_map_fast_grid};

fn main() {
    let total = fast_grid_size();
    eprintln!(
        "t163_joint_fast_grid: {total} configs, {} threads",
        std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
    );
    let rows: Vec<Value> = par_map_fast_grid("t163_joint_fast_grid", |(p_short, q10, delta_c)| {
        let mut model = ArrivalModel::embedded();
        apply_config(&mut model, p_short, q10, delta_c);
        let margin = ac2_19_min_margin(&mut model);
        json!({
            "p_short": p_short,
            "q10": q10,
            "delta_c": delta_c,
            "ac2_19_margin": margin,
        })
    });
    let mut rows = rows;
    rows.sort_by(|a, b| {
        b["ac2_19_margin"]
            .as_f64()
            .unwrap()
            .partial_cmp(&a["ac2_19_margin"].as_f64().unwrap())
            .unwrap()
    });
    let pass_count = rows
        .iter()
        .filter(|r| r["ac2_19_margin"].as_f64().unwrap() > 0.0)
        .count();
    let pass: Vec<_> = rows
        .iter()
        .filter(|r| r["ac2_19_margin"].as_f64().unwrap() > 0.0)
        .take(20)
        .collect();
    println!(
        "{}",
        json!({
            "grid_size": total,
            "passing_ac2_19_top20": pass,
            "total_pass": pass_count,
            "top5_margins": rows.iter().take(5).collect::<Vec<_>>(),
        })
    );
}
