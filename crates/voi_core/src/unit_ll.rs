//! Unit-level observation log-likelihoods (C2 Algorithm A / ADR 0130, 0135, 0143).
//!
//! Spoilage is scored with an exact **Poisson-binomial** DP under independent per-unit
//! gamma decrements. Every weight term is deterministic given particle state; stochastic
//! draws live in the adapted proposal (`pb_sample_deaths`, truncated survivor aging) and
//! unscored WOR sales removal.

use rand::Rng;

use crate::physics::{draw_gamma_decrement_truncated, picking_weights_f, GammaDecrementTable};
use crate::ModelParams;

/// Per-unit spoil probabilities `P(δ ≥ f_i)` for live slots.
pub fn spoil_probs_from_freshness(
    freshness: &[f64],
    table: &GammaDecrementTable,
) -> Vec<f64> {
    freshness
        .iter()
        .copied()
        .filter(|&f| f > 0.0)
        .map(|f| table.spoil_prob(f))
        .collect()
}

/// Log PMF of exactly `w` spoils among independent Bernoulli trials with probs `p`.
pub fn pb_log_pmf(probs: &[f64], w: usize) -> f64 {
    let n = probs.len();
    if w > n {
        return f64::NEG_INFINITY;
    }
    let mut dp = vec![0.0f64; w + 1];
    dp[0] = 1.0;
    for &p in probs {
        let p = p.clamp(0.0, 1.0);
        let mut next = vec![0.0; w + 1];
        for j in 0..=w {
            if dp[j] == 0.0 {
                continue;
            }
            next[j] += dp[j] * (1.0 - p);
            if j + 1 <= w {
                next[j + 1] += dp[j] * p;
            }
        }
        dp = next;
    }
    let prob = dp[w];
    if prob > 0.0 {
        prob.ln()
    } else {
        f64::NEG_INFINITY
    }
}

/// GSIN: sum of per-lot Poisson-binomial log PMFs.
pub fn pb_loglik_by_lot(
    freshness: &[f64],
    offsets: &[usize],
    waste_by: &[u32],
    table: &GammaDecrementTable,
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    if waste_by.len() != n_lots {
        return f64::NEG_INFINITY;
    }
    let mut ll = 0.0;
    for ell in 0..n_lots {
        let start = offsets[ell].min(freshness.len());
        let end = offsets[ell + 1].min(freshness.len());
        let probs = spoil_probs_from_freshness(&freshness[start..end], table);
        let term = pb_log_pmf(&probs, waste_by[ell] as usize);
        if !term.is_finite() {
            return f64::NEG_INFINITY;
        }
        ll += term;
    }
    ll
}

/// UPC pooled alive-set Poisson-binomial log PMF.
pub fn pb_loglik_pooled(freshness: &[f64], waste_tot: u32, table: &GammaDecrementTable) -> f64 {
    let probs = spoil_probs_from_freshness(freshness, table);
    pb_log_pmf(&probs, waste_tot as usize)
}

fn pb_alpha(probs: &[f64], w: usize) -> Vec<f64> {
    let n = probs.len();
    let mut alpha = vec![0.0; w + 1];
    alpha[0] = 1.0;
    for &p in probs {
        let p = p.clamp(0.0, 1.0);
        let mut next = vec![0.0; w + 1];
        for j in 0..=w {
            if alpha[j] == 0.0 {
                continue;
            }
            next[j] += alpha[j] * (1.0 - p);
            if j + 1 <= w {
                next[j + 1] += alpha[j] * p;
            }
        }
        alpha = next;
    }
    alpha
}

/// Backward-sample which live units spoil; returns `(indices, log q)`.
pub fn pb_sample_deaths<R: Rng + ?Sized>(
    freshness: &[f64],
    w: usize,
    table: &GammaDecrementTable,
    rng: &mut R,
) -> (Vec<usize>, f64) {
    let live_idx: Vec<usize> = freshness
        .iter()
        .enumerate()
        .filter(|(_, &f)| f > 0.0)
        .map(|(i, _)| i)
        .collect();
    let probs: Vec<f64> = live_idx
        .iter()
        .map(|&i| table.spoil_prob(freshness[i]))
        .collect();
    let n = probs.len();
    if w > n {
        return (Vec::new(), f64::NEG_INFINITY);
    }
    if w == 0 {
        return (Vec::new(), 0.0);
    }

    let mut alpha = vec![vec![0.0f64; w + 1]; n + 1];
    alpha[0][0] = 1.0;
    for i in 0..n {
        let p = probs[i].clamp(0.0, 1.0);
        for j in 0..=w {
            if alpha[i][j] == 0.0 {
                continue;
            }
            alpha[i + 1][j] += alpha[i][j] * (1.0 - p);
            if j + 1 <= w {
                alpha[i + 1][j + 1] += alpha[i][j] * p;
            }
        }
    }
    if alpha[n][w] <= 0.0 {
        return (Vec::new(), f64::NEG_INFINITY);
    }

    let mut deaths = Vec::with_capacity(w);
    let mut j = w;
    let mut log_q = 0.0f64;
    for i in (0..n).rev() {
        let p = probs[i].clamp(0.0, 1.0);
        let denom = alpha[i + 1][j];
        if j > 0 {
            let p_die = if denom > 0.0 {
                p * alpha[i][j - 1] / denom
            } else {
                0.0
            };
            if rng.random::<f64>() < p_die {
                deaths.push(live_idx[i]);
                log_q += p_die.max(1e-300).ln();
                j -= 1;
            } else {
                log_q += (1.0 - p_die).max(1e-300).ln();
            }
        } else {
            log_q += (1.0 - p).max(1e-300).ln();
        }
    }
    deaths.reverse();
    (deaths, log_q)
}

/// Apply adapted aging: sampled deaths spoil; survivors get truncated gamma decrements.
pub fn apply_pb_aging_proposal<R: Rng + ?Sized>(
    freshness: &mut [f64],
    death_indices: &[usize],
    params: &ModelParams,
    rng: &mut R,
) {
    let dead: std::collections::HashSet<usize> = death_indices.iter().copied().collect();
    for (i, f) in freshness.iter_mut().enumerate() {
        if *f <= 0.0 {
            continue;
        }
        if dead.contains(&i) {
            *f = 0.0;
        } else {
            let dec = draw_gamma_decrement_truncated(rng, params, 0.0, *f);
            *f = (*f - dec).max(0.0);
        }
    }
}

/// Normalized lot shares from pooled picking weights over **pre-removal** freshness.
pub fn lot_shares_from_freshness(
    freshness: &[f64],
    offsets: &[usize],
    params: &ModelParams,
) -> Vec<f64> {
    let n_lots = offsets.len().saturating_sub(1);
    let pooled_w = picking_weights_f(freshness, params.sigma, params.uniform_picking);
    let mut lot_share = vec![0.0; n_lots];
    for ell in 0..n_lots {
        lot_share[ell] = pooled_w[offsets[ell]..offsets[ell + 1]].iter().sum();
    }
    let z: f64 = lot_share.iter().sum();
    if z <= 0.0 {
        lot_share
    } else {
        lot_share.iter_mut().for_each(|s| *s /= z);
        lot_share
    }
}

/// Log-PMF of `Multinomial(counts; n = sum(counts), p = probs)`.
pub fn multinomial_log_pmf(counts: &[u32], probs: &[f64]) -> f64 {
    let n: u32 = counts.iter().sum();
    if n == 0 {
        return 0.0;
    }
    if counts.len() != probs.len() {
        return f64::NEG_INFINITY;
    }
    let mut log_coef = 0.0f64;
    let mut nn = n as f64;
    for &k in counts {
        for i in 0..k {
            log_coef += (nn - i as f64).ln() - (i as f64 + 1.0).ln();
        }
        nn -= k as f64;
    }
    let mut log_p = log_coef;
    for (&k, &p) in counts.iter().zip(probs.iter()) {
        if p <= 0.0 && k > 0 {
            return f64::NEG_INFINITY;
        }
        if p > 0.0 && k > 0 {
            log_p += k as f64 * p.ln();
        }
    }
    log_p
}

/// Draw and apply a sequential WOR sales path; **mutates** picked slots to `0.0`.
pub fn sequential_kernel_path_logprob<R: Rng + ?Sized>(
    freshness: &mut [f64],
    sales: usize,
    params: &ModelParams,
    rng: &mut R,
) -> f64 {
    let base_w = picking_weights_f(freshness, params.sigma, params.uniform_picking);
    let mut alive = vec![true; freshness.len()];
    let mut log_p = 0.0;
    for _ in 0..sales {
        let mut tot = 0.0;
        for i in 0..freshness.len() {
            if alive[i] && freshness[i] > 0.0 {
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
            if !alive[i] || freshness[i] <= 0.0 {
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
        freshness[picked] = 0.0;
    }
    log_p
}

/// F1 lot-resolved sales log-likelihood: per-lot feasibility + multinomial cross-lot split.
pub fn loglik_sales_by_units(
    freshness: &[f64],
    sales_by: &[u32],
    offsets: &[usize],
    params: &ModelParams,
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    let sales_by = align_lot_map(sales_by, n_lots);
    for ell in 0..n_lots {
        let start = offsets[ell].min(freshness.len());
        let end = offsets[ell + 1].min(freshness.len());
        if start >= end {
            if sales_by[ell] > 0 {
                return f64::NEG_INFINITY;
            }
            continue;
        }
        let sl = &freshness[start..end];
        let alive = sl.iter().filter(|&&f| f > 0.0).count();
        let sales = sales_by[ell] as usize;
        if alive < sales {
            return f64::NEG_INFINITY;
        }
    }
    let sales_tot: u32 = sales_by.iter().sum();
    if sales_tot == 0 {
        return 0.0;
    }
    let lot_share = lot_shares_from_freshness(freshness, offsets, params);
    for (ell, &share) in lot_share.iter().enumerate() {
        if share <= 0.0 && sales_by[ell] > 0 {
            return f64::NEG_INFINITY;
        }
    }
    multinomial_log_pmf(&sales_by, &lot_share)
}

pub(crate) fn align_lot_map(values: &[u32], l: usize) -> Vec<u32> {
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
