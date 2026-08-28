//! Fast grid (ac2_19 only): `cargo run -p voi_core --release --example t163_joint_fast_grid`
//!
//! Two-pass: d=8 screen on all points, then full ac2_19 ladder on survivors only.

#[path = "support/t163_joint_search_common.rs"]
mod common;

use serde_json::{json, Value};

use common::{
    ac2_19_d8_margin, ac2_19_min_margin, configured_model, fast_grid_points, fast_grid_size,
    par_map_points, GridPoint,
};

fn main() {
    let total = fast_grid_size();
    eprintln!(
        "t163_joint_fast_grid: {total} configs, {} threads",
        std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
    );

    let points = fast_grid_points();
    let d8_rows: Vec<(GridPoint, f64)> =
        par_map_points("d8_screen", points.clone(), |(p_short, q10, delta_c)| {
            let mut model = configured_model(p_short, q10, delta_c);
            let margin = ac2_19_d8_margin(&mut model);
            ((p_short, q10, delta_c), margin)
        });

    let survivors: Vec<GridPoint> = d8_rows
        .iter()
        .filter(|(_, margin)| *margin > 0.0)
        .map(|(pt, _)| *pt)
        .collect();
    let survivor_count = survivors.len();
    eprintln!(
        "d8_screen: {survivor_count} survivors of {total} (full ac2_19 on survivors only)",
    );

    let mut rows: Vec<Value> = if survivors.is_empty() {
        d8_rows
            .into_iter()
            .map(|((p_short, q10, delta_c), margin)| {
                json!({
                    "p_short": p_short,
                    "q10": q10,
                    "delta_c": delta_c,
                    "ac2_19_d8_margin": margin,
                    "ac2_19_margin": margin,
                    "full_ladder": false,
                })
            })
            .collect()
    } else {
        let full_rows: Vec<(GridPoint, f64)> =
            par_map_points("ac2_19_full", survivors, |(p_short, q10, delta_c)| {
                let mut model = configured_model(p_short, q10, delta_c);
                let margin = ac2_19_min_margin(&mut model);
                ((p_short, q10, delta_c), margin)
            });

        d8_rows
            .into_iter()
            .map(|((p_short, q10, delta_c), d8_margin)| {
                let full = full_rows
                    .iter()
                    .find(|((ps, q, dc), _)| {
                        (*ps - p_short).abs() < 1e-12
                            && (*q - q10).abs() < 1e-12
                            && (*dc - delta_c).abs() < 1e-12
                    })
                    .map(|(_, m)| *m);
                let (margin, full_ladder) = match full {
                    Some(m) => (m, true),
                    None => (d8_margin, false),
                };
                json!({
                    "p_short": p_short,
                    "q10": q10,
                    "delta_c": delta_c,
                    "ac2_19_d8_margin": d8_margin,
                    "ac2_19_margin": margin,
                    "full_ladder": full_ladder,
                })
            })
            .collect()
    };

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
            "d8_survivors": survivor_count,
            "passing_ac2_19_top20": pass,
            "total_pass": pass_count,
            "top5_margins": rows.iter().take(5).collect::<Vec<_>>(),
        })
    );
}
