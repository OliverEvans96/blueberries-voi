//! Shared helpers for T-163 joint arrival calibration examples.
//!
//! **Production path:** per-trial evaluator `t163_eval_trial` + Ax notebook 14 /
//! `scripts/run_arrival_calib_bo.py` (subprocess JSON).
//!
//! **Legacy / diagnostic grids** (superseded by BO — do not run for calibration):
//! - `t163_joint_fast_grid` — ac2_19-only two-pass screen
//! - `t163_joint_constraint_search` — full grid with phase-2 ac2_11a on survivors
//!
//! **Legacy / diagnostic only** — exhaustive grid search is superseded by Ax BO in
//! `notebooks/14_arrival_calibration_joint_bo.ipynb` and `scripts/run_arrival_calib_bo.py`.

use std::sync::Arc;
use std::thread;

pub use voi_core::joint_arrival_calib::{
    ac2_19_d8_margin, ac2_19_min_margin, apply_config, configured_model, embedded_base,
};

/// Narrowed grid around fast-screen winners (~60 configs with parallel eval).
pub const P_SHORT_GRID: [f64; 5] = [0.68, 0.69, 0.70, 0.71, 0.72];
pub const Q10_GRID: [f64; 4] = [2.5, 2.8, 3.0, 3.2];
pub const DELTA_C_GRID: [f64; 3] = [-1.0, -0.5, 0.0];

/// ac2_19-only fast screen: fix δc at 0 (passes concentrate there; saves prior rebuilds).
pub const FAST_DELTA_C_GRID: [f64; 1] = [0.0];

pub type GridPoint = (f64, f64, f64);

pub fn grid_points() -> Vec<GridPoint> {
    grid_points_for(&P_SHORT_GRID, &Q10_GRID, &DELTA_C_GRID)
}

pub fn fast_grid_points() -> Vec<GridPoint> {
    grid_points_for(&P_SHORT_GRID, &Q10_GRID, &FAST_DELTA_C_GRID)
}

fn grid_points_for(
    p_short_grid: &[f64],
    q10_grid: &[f64],
    delta_c_grid: &[f64],
) -> Vec<GridPoint> {
    let mut out = Vec::with_capacity(p_short_grid.len() * q10_grid.len() * delta_c_grid.len());
    for &p_short in p_short_grid {
        for &q10 in q10_grid {
            for &delta_c in delta_c_grid {
                out.push((p_short, q10, delta_c));
            }
        }
    }
    out
}

pub fn grid_size() -> usize {
    P_SHORT_GRID.len() * Q10_GRID.len() * DELTA_C_GRID.len()
}

pub fn fast_grid_size() -> usize {
    P_SHORT_GRID.len() * Q10_GRID.len() * FAST_DELTA_C_GRID.len()
}

pub fn progress(label: &str, done: usize, total: usize) {
    if done == total || done % 10 == 0 || done == 1 {
        eprintln!("{label}: {done}/{total}");
    }
}

/// Evaluate the grid in parallel (one model + prior rebuild per point).
pub fn par_map_grid<T, F>(label: &str, f: F) -> Vec<T>
where
    T: Send + 'static,
    F: Fn(GridPoint) -> T + Send + Sync + 'static,
{
    par_map_points(label, grid_points(), f)
}

pub fn par_map_fast_grid<T, F>(label: &str, f: F) -> Vec<T>
where
    T: Send + 'static,
    F: Fn(GridPoint) -> T + Send + Sync + 'static,
{
    par_map_points(label, fast_grid_points(), f)
}

pub fn par_map_points<T, F>(label: &str, points: Vec<GridPoint>, f: F) -> Vec<T>
where
    T: Send + 'static,
    F: Fn(GridPoint) -> T + Send + Sync + 'static,
{
    let total = points.len();
    let done = Arc::new(std::sync::Mutex::new(0usize));
    let f = Arc::new(f);
    let n_workers = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4)
        .min(total.max(1));
    let chunk = (total + n_workers - 1) / n_workers;

    thread::scope(|scope| {
        points
            .chunks(chunk)
            .map(|chunk| {
                let done = Arc::clone(&done);
                let f = Arc::clone(&f);
                let chunk = chunk.to_vec();
                scope.spawn(move || {
                    let mut out = Vec::with_capacity(chunk.len());
                    for &(p_short, q10, delta_c) in &chunk {
                        out.push(f((p_short, q10, delta_c)));
                        let mut n = done.lock().expect("progress lock");
                        *n += 1;
                        progress(label, *n, total);
                    }
                    out
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .flat_map(|h| h.join().expect("grid worker"))
            .collect()
    })
}
