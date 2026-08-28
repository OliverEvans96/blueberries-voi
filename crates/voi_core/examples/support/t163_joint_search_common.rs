//! Shared helpers for T-163 joint arrival calibration examples.

use std::sync::{Arc, Mutex, OnceLock};
use std::thread;

use voi_core::arrival::ArrivalModel;

/// Narrowed grid around fast-screen winners (~60 configs with parallel eval).
pub const P_SHORT_GRID: [f64; 5] = [0.68, 0.69, 0.70, 0.71, 0.72];
pub const Q10_GRID: [f64; 4] = [2.5, 2.8, 3.0, 3.2];
pub const DELTA_C_GRID: [f64; 3] = [-1.0, -0.5, 0.0];

/// ac2_19-only fast screen: fix δc at 0 (passes concentrate there; saves prior rebuilds).
pub const FAST_DELTA_C_GRID: [f64; 1] = [0.0];

const AC2_19_DAYS_BEFORE_D8: [i32; 4] = [2, 4, 5, 6];
const AC2_19_D8: i32 = 8;

pub type GridPoint = (f64, f64, f64);

static EMBEDDED_BASE: OnceLock<ArrivalModel> = OnceLock::new();

/// Snapshot the committed embedded model once; grid workers clone from this.
pub fn embedded_base() -> &'static ArrivalModel {
    EMBEDDED_BASE.get_or_init(ArrivalModel::embedded)
}

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

/// Build a configured model for one grid point (single embedded snapshot clone).
pub fn configured_model(p_short: f64, q10: f64, delta_c: f64) -> ArrivalModel {
    let base = embedded_base();
    let mut model = base.clone();
    if let Some(mix) = model.corridor_mixtures.get_mut("abdella_mix") {
        mix.components[0].weight = p_short;
        mix.components[1].weight = 1.0 - p_short;
    }
    model.q10 = q10;
    for (leg, base_leg) in model.legs.iter_mut().zip(base.legs.iter()) {
        leg.setpoint_c = base_leg.setpoint_c + delta_c;
    }
    model.reference_life_days = 14.0;
    model.gamma_scale = 1.0 / (model.gamma_shape * 14.0);
    model.refresh_filter_laws();
    model
}

/// Apply mixture weight, q10, leg-setpoint shift, and η_ref — one prior rebuild at the end.
pub fn apply_config(model: &mut ArrivalModel, p_short: f64, q10: f64, delta_c: f64) {
    *model = configured_model(p_short, q10, delta_c);
}

/// AC2-19 d=8 proxy: Prior variance minus F2 variance at the longest ladder day.
pub fn ac2_19_d8_margin(model: &mut ArrivalModel) -> f64 {
    let prior_var = model.marginal_variance_f();
    prior_var - model.variance_f_given_d(AC2_19_D8)
}

/// AC2-19: min margin of Prior variance over F2 variance across the duration ladder.
/// Checks d=8 first and skips shorter days when that binding constraint already fails.
pub fn ac2_19_min_margin(model: &mut ArrivalModel) -> f64 {
    let prior_var = model.marginal_variance_f();
    let d8_margin = prior_var - model.variance_f_given_d(AC2_19_D8);
    if d8_margin <= 0.0 {
        return d8_margin;
    }
    let mut min_margin = d8_margin;
    for &d in &AC2_19_DAYS_BEFORE_D8 {
        min_margin = min_margin.min(prior_var - model.variance_f_given_d(d));
    }
    min_margin
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
    let done = Arc::new(Mutex::new(0usize));
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
