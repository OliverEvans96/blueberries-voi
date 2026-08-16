//! Unit-level sequential picking log-likelihoods (C2 Algorithm A / ADR 0130).
//!
//! Promoted from `bench_c2_a_totals_study` and `bench_c2_accuracy`.

use rand::Rng;

use crate::exact_ll::binom_pmf;
use crate::physics::{f_to_age, picking_weights};
use crate::ModelParams;

fn unit_tau(f: f64, eta: f64) -> f64 {
    f_to_age(f, eta)
}

/// Log-probability of a sequential picking path selling `sales` units from alive slots.
///
/// Uses τ = (1 − f)·η_ref picking weights (bench C2-A convention). Alive units are those with
/// `f > 0`; picked slots are removed without replacement. `rng` drives the path draw sequence.
pub fn sequential_kernel_path_logprob<R: Rng + ?Sized>(
    freshness: &[f64],
    sales: usize,
    params: &ModelParams,
    rng: &mut R,
) -> f64 {
    let taus: Vec<f64> = freshness
        .iter()
        .map(|&f| unit_tau(f, params.eta_ref))
        .collect();
    let base_w = picking_weights(
        &taus,
        params.sigma,
        params.beta,
        params.eta_ref,
        params.uniform_picking,
    );
    let mut alive = vec![true; freshness.len()];
    let mut log_p = 0.0;
    for _ in 0..sales {
        let mut tot = 0.0;
        for i in 0..freshness.len() {
            if alive[i] {
                tot += base_w[i];
            }
        }
        if tot <= 0.0 {
            return f64::NEG_INFINITY;
        }
        let draw = rng.random::<f64>() * tot;
        let mut acc = 0.0;
        let mut picked = 0usize;
        for i in 0..freshness.len() {
            if !alive[i] {
                continue;
            }
            acc += base_w[i];
            if draw < acc {
                picked = i;
                break;
            }
        }
        log_p += (base_w[picked] / tot).ln();
        alive[picked] = false;
    }
    log_p
}

/// P1 totals-only log-likelihood: sequential sales kernel + binomial waste on remainders.
///
/// `waste_tot` is the observed spoil count among units still alive after sales. Returns
/// `-∞` when sales exceed alive count or waste is inconsistent with the dead-fraction model.
pub fn p1_totals_loglik<R: Rng + ?Sized>(
    freshness: &[f64],
    sales_tot: i32,
    waste_tot: i32,
    params: &ModelParams,
    rng: &mut R,
) -> f64 {
    let units = freshness.len();
    let alive = freshness.iter().filter(|&&f| f > 0.0).count();
    if alive < sales_tot as usize {
        return f64::NEG_INFINITY;
    }
    let ll_sales = sequential_kernel_path_logprob(freshness, sales_tot as usize, params, rng);
    if !ll_sales.is_finite() {
        return f64::NEG_INFINITY;
    }
    let dead = freshness.iter().filter(|&&f| f <= 0.0).count() as i32;
    let rem = alive as i32 - sales_tot;
    let p_die = (dead as f64 / units as f64).clamp(0.0, 1.0);
    let pw = binom_pmf(waste_tot, rem, p_die);
    if pw <= 0.0 {
        return f64::NEG_INFINITY;
    }
    ll_sales + pw.ln()
}

/// Per-lot factorized sequential kernel: sum of `sequential_kernel_path_logprob` on each lot slice.
///
/// `offsets` has length `L + 1` with `offsets[ell]..offsets[ell + 1]` the unit segment for lot
/// `ell`. `sales_by` must have length `L`.
pub fn loglik_sales_by_units<R: Rng + ?Sized>(
    freshness: &[f64],
    sales_by: &[u32],
    offsets: &[usize],
    params: &ModelParams,
    rng: &mut R,
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    if sales_by.len() != n_lots {
        return f64::NEG_INFINITY;
    }
    let mut log_p = 0.0;
    for ell in 0..n_lots {
        let sl = &freshness[offsets[ell]..offsets[ell + 1]];
        let alive = sl.iter().filter(|&&f| f > 0.0).count();
        let sales = sales_by[ell] as usize;
        if alive < sales {
            return f64::NEG_INFINITY;
        }
        let ll = sequential_kernel_path_logprob(sl, sales, params, rng);
        if !ll.is_finite() {
            return f64::NEG_INFINITY;
        }
        log_p += ll;
    }
    log_p
}
