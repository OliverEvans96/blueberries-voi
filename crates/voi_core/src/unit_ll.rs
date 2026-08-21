//! Unit-level observation log-likelihoods (C2 Algorithm A / ADR 0130, 0135, 0137).
//!
//! Every term is **deterministic** given the particle state. Stochastic draws live only in
//! `sequential_kernel_path_logprob` (unscored sales removal) and in the adapted aging
//! proposal, which samples the daily decrement from the interval this module derives.
//!
//! ## Spoilage is an interval constraint on one shared latent
//!
//! Ground truth ages the whole store with a **single** gamma decrement `δ` per day
//! (`physics::apply_gamma_aging`), so a unit with pre-aging freshness `f > 0` spoils iff
//! `f ≤ δ`. Observing that `w` units spoiled therefore does not merely *reweight* the
//! particle — it confines `δ` to the half-open interval `[g_w, g_{w+1})`, where `g_j` is
//! the `j`-th smallest pre-aging freshness in the observed group (`g_0 = 0`,
//! `g_{m+1} = ∞`). The likelihood is the gamma mass of that interval; the state update
//! samples `δ` from the gamma truncated to it.
//!
//! ## Why GSIN dominates UPC by construction
//!
//! UPC observes only the store total `w`, giving the pooled interval `I_pooled`.
//! GSIN observes `w_ℓ` per lot, giving `I_gsin = ⋂_ℓ I_ℓ`. Every `δ` consistent with the
//! per-lot counts is consistent with their sum, so `I_gsin ⊆ I_pooled` **always**: the
//! richer channel can only sharpen the posterior over `δ`, never blur it. GSIN adds a
//! second term UPC cannot have — the multinomial cross-lot sales split.

use rand::Rng;

use crate::physics::{gamma_decrement_interval_prob, picking_weights_f};
use crate::ModelParams;

/// Half-open interval `[lo, hi)` of daily decrements consistent with an observation.
pub type DeltaInterval = (f64, f64);

/// The unconstrained interval: any non-negative decrement.
pub const DELTA_ANY: DeltaInterval = (0.0, f64::INFINITY);

/// Decrements `δ` for which exactly `w` of `pre_f`'s live units spoil.
///
/// Returns `None` when no `δ` produces exactly `w` spoils — including the tie case where
/// two units share a freshness value and therefore always spoil together.
pub fn spoil_delta_interval(pre_f: &[f64], w: usize) -> Option<DeltaInterval> {
    let mut live: Vec<f64> = pre_f.iter().copied().filter(|&f| f > 0.0).collect();
    let m = live.len();
    if w > m {
        return None;
    }
    live.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let lo = if w == 0 { 0.0 } else { live[w - 1] };
    let hi = if w == m { f64::INFINITY } else { live[w] };
    if hi <= lo {
        return None;
    }
    Some((lo, hi))
}

/// Intersect the per-lot spoilage intervals (GSIN `waste_by`).
///
/// `waste_by` is indexed by the bank's own lot segments; callers must project the observed
/// map onto those segments first (`unit_pf::project_lot_map`).
pub fn spoil_delta_interval_by_lot(
    freshness: &[f64],
    offsets: &[usize],
    waste_by: &[u32],
) -> Option<DeltaInterval> {
    let n_lots = offsets.len().saturating_sub(1);
    if waste_by.len() != n_lots {
        return None;
    }
    let (mut lo, mut hi) = DELTA_ANY;
    for ell in 0..n_lots {
        let start = offsets[ell].min(freshness.len());
        let end = offsets[ell + 1].min(freshness.len());
        let (l, h) = spoil_delta_interval(&freshness[start..end], waste_by[ell] as usize)?;
        lo = lo.max(l);
        hi = hi.min(h);
    }
    if hi <= lo {
        return None;
    }
    Some((lo, hi))
}

/// Log gamma mass of a decrement interval — the spoilage log-likelihood term.
pub fn delta_interval_loglik(interval: Option<DeltaInterval>, params: &ModelParams) -> f64 {
    match interval {
        None => f64::NEG_INFINITY,
        Some((lo, hi)) => {
            let p = gamma_decrement_interval_prob(lo, hi, params);
            if p > 0.0 {
                p.ln()
            } else {
                f64::NEG_INFINITY
            }
        }
    }
}

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
///
/// Returns the realized path log-probability as a diagnostic value only — not for
/// importance weights (ADR 0135). Waste likelihood must be evaluated on freshness
/// **before** calling this function.
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

/// **Superseded (ADR 0137) — research/parity use only.**
///
/// P1 totals log-likelihood with an ad-hoc waste term: `Binomial(waste; alive - sales,
/// dead/units)`, treating the fraction of already-dead slots as a per-unit death
/// probability. That has no derivation from the physics: spoilage is not an independent
/// per-unit coin flip, it is the deterministic consequence of one shared gamma decrement
/// (`spoil_delta_interval`). Production scoring no longer calls this; it is kept for
/// PyO3 parity tests and the pre-0137 comparison in `experiments/`.
pub fn p1_totals_loglik(
    freshness: &[f64],
    sales_tot: i32,
    waste_tot: i32,
    params: &ModelParams,
) -> f64 {
    let _ = params;
    let units = freshness.len();
    let alive = freshness.iter().filter(|&&f| f > 0.0).count();
    if alive < sales_tot as usize {
        return f64::NEG_INFINITY;
    }
    let dead = freshness.iter().filter(|&&f| f <= 0.0).count() as i32;
    let rem = alive as i32 - sales_tot;
    let p_die = (dead as f64 / units as f64).clamp(0.0, 1.0);
    let pw = binom_pmf(waste_tot, rem, p_die);
    if pw <= 0.0 {
        return f64::NEG_INFINITY;
    }
    pw.ln()
}

/// F1 lot-resolved sales log-likelihood: per-lot feasibility + multinomial cross-lot split.
///
/// Deterministic; no RNG. P1 is the `n_lots = 1` degenerate case.
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

/// **Superseded (ADR 0137) — research/parity use only.** See `p1_totals_loglik`.
///
/// Per-lot binomial waste after observed `sales_by`; also factorizes over lots, which the
/// shared decrement makes false.
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

/// **Superseded (ADR 0137) — research/parity use only.** See `p1_totals_loglik`.
///
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
