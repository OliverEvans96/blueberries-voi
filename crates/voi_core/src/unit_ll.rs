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
//! ## What GSIN adds over UPC, and what it does not
//!
//! UPC observes only the store total `w`, giving the pooled interval `I_pooled`. GSIN
//! observes `w_ℓ` per lot, giving `I_gsin = ⋂_ℓ I_ℓ`. Every `δ` consistent with the per-lot
//! counts is consistent with their sum, so `I_gsin ⊆ I_pooled` **always** — the richer
//! channel can never blur the posterior over `δ`.
//!
//! In *this* model it also never sharpens it. Births are lot-uniform (`unit_pf::push_lot`
//! writes one freshness to a whole delivery) and aging applies one shared decrement, so
//! every live unit in a lot carries the same `f` and a lot spoils **all or nothing**. Under
//! that structure the store's order statistics *are* the lot values, so the total already
//! determines which lots died: `I_gsin` is either exactly `I_pooled` or **empty**, never a
//! strictly tighter non-empty interval (pinned by
//! `unit_pf_ac::gsin_waste_never_narrows_the_pooled_interval`).
//!
//! So `waste_by` is a **falsification** channel rather than a sharpening one — it kills
//! particles whose lots are ordered wrongly by freshness. Like the multinomial cross-lot
//! sales split (the second term UPC cannot have), it is informative about the *contrast*
//! between lots, not about the overall freshness level. Level is bought on the orthogonal
//! `delivery_history` axis (ADR 0133).

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
