//! Unit-level sequential picking log-likelihoods (C2 Algorithm A / ADR 0130).
//!
//! Promoted from `bench_c2_a_totals_study` and `bench_c2_accuracy`.

use rand::Rng;

use crate::physics::picking_weights_f;
use crate::ModelParams;

pub fn binom_pmf(k: i32, n: i32, p: f64) -> f64 {
    if k < 0 || k > n || n < 0 {
        return 0.0;
    }
    let p_c = p.clamp(0.0, 1.0);
    let mut coef = 1.0;
    for i in 0..k {
        coef *= f64::from(n - i) / f64::from(i + 1);
    }
    coef * p_c.powi(k) * (1.0 - p_c).powi(n - k)
}

pub fn iter_compositions(totals: &[u32], target: i32) -> Vec<Vec<u32>> {
    let l = totals.len();
    let mut out = Vec::new();
    if target < 0 || l == 0 {
        return out;
    }
    let mut acc = vec![0u32; l];
    fn rec(i: usize, left: i32, totals: &[u32], acc: &mut [u32], out: &mut Vec<Vec<u32>>) {
        let l = totals.len();
        if i == l - 1 {
            if left >= 0 && left <= totals[i] as i32 {
                acc[i] = left as u32;
                out.push(acc.to_vec());
            }
            return;
        }
        let maxv = (totals[i] as i32).min(left);
        for v in 0..=maxv {
            acc[i] = v as u32;
            rec(i + 1, left - v, totals, acc, out);
        }
    }
    rec(0, target, totals, &mut acc, &mut out);
    out
}

/// Log-probability of a sequential picking path selling `sales` units from alive slots.
///
/// Uses f-native picking weights (`picking_weights_f`). Alive units are those with
/// `f > 0`; picked slots are removed without replacement. `rng` drives the path draw sequence.
pub fn sequential_kernel_path_logprob<R: Rng + ?Sized>(
    freshness: &[f64],
    sales: usize,
    params: &ModelParams,
    rng: &mut R,
) -> f64 {
    let base_w = picking_weights_f(
        freshness,
        params.sigma,
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

fn align_lot_map(values: &[u32], l: usize) -> Vec<u32> {
    if values.len() == l {
        return values.to_vec();
    }
    if values.len() > l {
        return values[values.len() - l..].to_vec();
    }
    let mut padded = vec![0u32; l - values.len()];
    padded.extend_from_slice(values);
    padded
}

/// Per-lot binomial waste after observed `sales_by` (F2 / F1s lot-resolved wire).
pub fn loglik_waste_by_units(
    freshness: &[f64],
    sales_by: &[u32],
    waste_by: &[u32],
    offsets: &[usize],
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    if waste_by.len() != n_lots {
        return f64::NEG_INFINITY;
    }
    let sales = align_lot_map(sales_by, n_lots);
    let mut log_p = 0.0;
    for ell in 0..n_lots {
        let sl = &freshness[offsets[ell]..offsets[ell + 1]];
        if sl.is_empty() {
            continue;
        }
        let alive = sl.iter().filter(|&&f| f > 0.0).count();
        let sales_ell = sales[ell] as usize;
        if alive < sales_ell {
            return f64::NEG_INFINITY;
        }
        let rem = alive - sales_ell;
        let waste = waste_by[ell] as i32;
        if waste < 0 || waste > rem as i32 {
            return f64::NEG_INFINITY;
        }
        let dead = sl.iter().filter(|&&f| f <= 0.0).count();
        let p_die = (dead as f64 / sl.len() as f64).clamp(0.0, 1.0);
        let pw = binom_pmf(waste, rem as i32, p_die);
        if pw <= 0.0 {
            return f64::NEG_INFINITY;
        }
        log_p += pw.ln();
    }
    log_p
}

/// Aggregate waste total after lot-resolved sales (legacy `log_p_known_sales_and_waste`).
pub fn loglik_waste_tot_after_sales_by(
    freshness: &[f64],
    sales_by: &[u32],
    waste_tot: i32,
    offsets: &[usize],
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    let sales = align_lot_map(sales_by, n_lots);
    let mut remaining = Vec::with_capacity(n_lots);
    let mut p_die = Vec::with_capacity(n_lots);
    for ell in 0..n_lots {
        let sl = &freshness[offsets[ell]..offsets[ell + 1]];
        if sl.is_empty() {
            remaining.push(0u32);
            p_die.push(0.0);
            continue;
        }
        let alive = sl.iter().filter(|&&f| f > 0.0).count();
        let sales_ell = sales[ell] as usize;
        if alive < sales_ell {
            return f64::NEG_INFINITY;
        }
        remaining.push((alive - sales_ell) as u32);
        let dead = sl.iter().filter(|&&f| f <= 0.0).count();
        p_die.push((dead as f64 / sl.len() as f64).clamp(0.0, 1.0));
    }
    let on_rem: i32 = remaining.iter().map(|&x| x as i32).sum();
    if waste_tot < 0 || waste_tot > on_rem {
        return f64::NEG_INFINITY;
    }
    if waste_tot == 0 {
        let mut log_p = 0.0;
        for ell in 0..n_lots {
            if remaining[ell] == 0 {
                continue;
            }
            let pw = binom_pmf(0, remaining[ell] as i32, p_die[ell]);
            if pw <= 0.0 {
                return f64::NEG_INFINITY;
            }
            log_p += pw.ln();
        }
        return log_p;
    }
    let mut p_waste = 0.0;
    for waste in iter_compositions(&remaining, waste_tot) {
        let mut term = 1.0;
        for ell in 0..n_lots {
            term *= binom_pmf(waste[ell] as i32, remaining[ell] as i32, p_die[ell]);
        }
        p_waste += term;
    }
    if p_waste <= 0.0 {
        f64::NEG_INFINITY
    } else {
        p_waste.ln()
    }
}
