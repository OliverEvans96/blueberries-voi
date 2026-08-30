//! Damped survival-weighted base-stock (algorithm from `damped_sw.py`).

use crate::schedule::OrderSchedule;
use crate::ModelParams;
use rand::SeedableRng;
use rand_pcg::Pcg64;
use crate::spawn_rng::negative_binomial_gamma_poisson;

/// Fixed seed component mixed into every derived Monte Carlo seed, so runs are
/// reproducible unless the caller supplies an explicit `mc_seed`.
const PROTECTION_MC_BASE_SEED: u32 = 0xC41B_4B4D;
/// Default sample count for the Monte Carlo protection-quantile estimate.
const PROTECTION_MC_DEFAULT_N: u32 = 20_000;
/// Tolerance below which per-day demand means are treated as flat, so the closed-form
/// quantile is used instead of falling back to Monte Carlo.
const FLAT_MU_ATOL: f64 = 1e-9;

/// Derives a deterministic 32-bit seed for the protection-window Monte Carlo quantile
/// from the query parameters that identify it, so repeated calls with the same inputs
/// reproduce the same samples. An explicit `mc_seed` overrides the derivation entirely.
pub fn derive_protection_mc_seed(
    start_day: u32,
    protection_days: u32,
    alpha: f64,
    mc_seed: Option<u64>,
) -> u64 {
    if let Some(seed) = mc_seed {
        return seed & 0xFFFF_FFFF;
    }
    let alpha_bits = (alpha as f32).to_bits() as u64;
    let mixed = u64::from(PROTECTION_MC_BASE_SEED)
        ^ (u64::from(start_day) * 1_314_542_391)
        ^ (u64::from(protection_days) * 2_654_435_761)
        ^ alpha_bits;
    mixed & 0xFFFF_FFFF
}

/// Closed-form negative-binomial quantile of total demand over `protection_days`, valid
/// only when every day in the window shares the same mean `mu`. The per-day NB dispersion
/// is reparameterized to `(r, p)` and summed across days by scaling `r`, since a sum of
/// i.i.d. negative binomials with a common `p` is itself negative binomial.
fn homogeneous_closed_form(
    alpha: f64,
    mu: f64,
    demand_vm: f64,
    protection_days: u32,
) -> f64 {
    let r_day = mu / (demand_vm - 1.0);
    let r_sum = r_day * f64::from(protection_days);
    let p = r_day / (r_day + mu);
    nbinom_ppf(alpha, r_sum, p)
}

/// Monte Carlo quantile of total demand over `protection_days` when the calendar profile
/// gives each day a different mean, so the sum no longer has a closed-form negative-binomial
/// distribution. Draws `n_mc` independent realizations of the summed demand (one negative
/// binomial per day, accumulated per sample) and reads off the empirical `alpha` quantile.
/// The seed is derived deterministically from the query parameters so results are
/// reproducible across calls.
fn heterogeneous_nb_sum_quantile_mc(
    alpha: f64,
    mus: &[f64],
    demand_vm: f64,
    start_day: u32,
    protection_days: u32,
    n_mc: u32,
    mc_seed: Option<u64>,
) -> f64 {
    if mus.is_empty() {
        return 0.0;
    }
    let seed = derive_protection_mc_seed(start_day, protection_days, alpha, mc_seed);
    let mut seed_bytes = [0u8; 32];
    seed_bytes[..8].copy_from_slice(&seed.to_le_bytes());
    let mut rng = Pcg64::from_seed(seed_bytes);
    let mut samples = vec![0.0f64; n_mc as usize];
    for &mu in mus {
        let r = mu / (demand_vm - 1.0);
        let p = r / (r + mu);
        for s in &mut samples {
            *s += f64::from(negative_binomial_gamma_poisson(&mut rng, r, p));
        }
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let idx = ((alpha * f64::from(n_mc)).ceil() as usize)
        .saturating_sub(1)
        .min(samples.len() - 1);
    samples[idx]
}

/// Rounds `x` to the nearest multiple of `case_size` (ties round up). Panics if
/// `case_size` is zero or `x` is negative, since neither is a valid order quantity.
pub fn case_round(x: f64, case_size: u32) -> u32 {
    if case_size == 0 {
        panic!("case_size must be positive");
    }
    if x < 0.0 {
        panic!("x must be non-negative");
    }
    let n = x / f64::from(case_size);
    (n + 0.5).floor() as u32 * case_size
}

/// Rounds `qty` up to the next multiple of `case_size` (always up, never down), unlike
/// [`case_round`]'s nearest-with-ties-up rule. Returns 0 if either input is 0.
pub fn case_round_ceil(qty: u32, case_size: u32) -> u32 {
    if qty == 0 || case_size == 0 {
        return 0;
    }
    let cases = qty.div_ceil(case_size);
    cases * case_size
}

/// Percent-point function (inverse CDF) of the negative binomial distribution with
/// dispersion `r` and success probability `p`, returning the smallest `k` whose CDF
/// reaches `alpha`. Walks the CDF upward term-by-term via the standard PMF recurrence
/// rather than inverting a closed form, capped at `k = 10_000` and bailing out early if
/// the running CDF stops being finite.
pub fn nbinom_ppf(alpha: f64, r: f64, p: f64) -> f64 {
    if !(0.0..=1.0).contains(&p) || r <= 0.0 {
        return 0.0;
    }
    let q = 1.0 - p;
    let mut pmf = p.powf(r);
    let mut cdf = pmf;
    let mut k = 0u32;
    while cdf < alpha && k < 10_000 {
        k += 1;
        pmf *= (r + f64::from(k) - 1.0) / f64::from(k) * q;
        cdf += pmf;
        if !cdf.is_finite() {
            break;
        }
    }
    f64::from(k)
}

/// The `alpha`-quantile of total demand over the protection window, `F^-1(alpha)`, used
/// as the base-stock target in the ordering rule. Dispatches to a closed-form
/// negative-binomial quantile when the calendar demand profile is flat (or absent) over
/// the window, and falls back to Monte Carlo when day-of-week/week variation makes the
/// per-day means differ. Panics if `alpha` is not in `(0, 1)`.
pub fn protection_demand_quantile(
    alpha: f64,
    params: &ModelParams,
    protection_days: u32,
    start_day: u32,
) -> f64 {
    if !(0.0 < alpha && alpha < 1.0) {
        panic!("alpha must be in (0,1)");
    }
    if protection_days == 0 {
        return 0.0;
    }
    if params.demand_profile.is_none() {
        return homogeneous_closed_form(
            alpha,
            params.demand_mu,
            params.demand_vm,
            protection_days,
        );
    }
    let mut mus = Vec::with_capacity(protection_days as usize);
    for k in 0..protection_days {
        mus.push(params.demand_mu_for_day(start_day + k));
    }
    let mu_min = mus.iter().copied().fold(f64::INFINITY, f64::min);
    let mu_max = mus.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    if mu_max - mu_min <= FLAT_MU_ATOL {
        return homogeneous_closed_form(alpha, mu_min, params.demand_vm, protection_days);
    }
    heterogeneous_nb_sum_quantile_mc(
        alpha,
        &mus,
        params.demand_vm,
        start_day,
        protection_days,
        PROTECTION_MC_DEFAULT_N,
        None,
    )
}

/// Rung 0 corrected age-blind order from oracle lot counts (CTL-05).
pub fn rung0_order_f_belief(
    lot_counts: &[f64],
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    rho: f64,
    schedule: &OrderSchedule,
    mean_survival_weight: f64,
    pipeline_weight: f64,
    demand_target: f64,
) -> u32 {
    if !schedule.can_order(day) {
        return 0;
    }
    let total_on_hand: f64 = lot_counts.iter().sum();
    let inv = mean_survival_weight * total_on_hand
        + f64::from(pending_sum) * pipeline_weight;
    let raw = rho * (demand_target - inv).max(0.0);
    case_round(raw, params.case_size)
}

/// Fixed-q constant order (Python `ConstantOrderPolicy`: nearest `case_round`).
pub fn constant_order(q: u32, case_size: u32) -> u32 {
    case_round(f64::from(q), case_size)
}

/// `E[f]`-weighted on-hand from f-belief plus pipeline term (ADR 0130).
///
/// This is `I_tilde`: on-hand units are weighted by their expected freshness (read off
/// `f_marginals` against `f_grid` per lot) rather than counted at face value, so a shelf
/// full of nearly-spoiled stock contributes less to "effective inventory" than the same
/// count of fresh stock. Units still in transit contribute at a fixed default freshness
/// (`f_pipeline_default`) since their belief hasn't been observed yet.
pub fn effective_inventory_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    pending_sum: u32,
    f_pipeline_default: f64,
) -> f64 {
    let l = lot_counts.len();
    let k = f_grid.len();
    let mut on_hand = 0.0;
    for ell in 0..l {
        let mut e_f = 0.0;
        for bin in 0..k {
            let p = f_marginals.get(ell * k + bin).copied().unwrap_or(0.0);
            e_f += p * f_grid[bin];
        }
        on_hand += lot_counts[ell] * e_f;
    }
    on_hand + f64::from(pending_sum) * f_pipeline_default
}

/// Damped survival-weighted order from f-belief.
///
/// Implements the base-stock rule `q = caseRound(rho * [F^-1(alpha) - I_tilde]_+)`:
/// order enough to bring quality-weighted effective inventory (`I_tilde`, see
/// [`effective_inventory_f_belief`]) up toward the protection-window demand quantile
/// (`F^-1(alpha)`, see [`protection_demand_quantile`]), damped by `rho` and rounded to a
/// whole number of cases. Returns 0 on a non-order day per `schedule` (when supplied)
/// without evaluating the rest of the rule.
pub fn damped_sw_order_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    alpha: f64,
    rho: f64,
    schedule: Option<&OrderSchedule>,
    f_pipeline_default: f64,
) -> u32 {
    if let Some(s) = schedule {
        if !s.can_order(day) {
            return 0;
        }
    }
    let n_days = schedule.map(|s| s.protection_days(day)).unwrap_or(2);
    let i_tilde = effective_inventory_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        pending_sum,
        f_pipeline_default,
    );
    let d_star = protection_demand_quantile(alpha, params, n_days, day);
    let raw = rho * (d_star - i_tilde).max(0.0);
    case_round(raw, params.case_size)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn case_round_nearest() {
        assert_eq!(case_round(12.0, 8), 16);
        assert_eq!(case_round(4.0, 8), 8);
        assert_eq!(case_round(0.0, 8), 0);
    }

    #[test]
    fn nbinom_ppf_matches_scipy_smoke() {
        assert_eq!(nbinom_ppf(0.9, 60.0, 0.5), 74.0);
    }

    #[test]
    fn sw_empty_shelf_orders_cases() {
        let p = ModelParams::default();
        let f_grid = vec![0.0, 1.0];
        let q = damped_sw_order_f_belief(&[], &[], &f_grid, 0, 0, &p, 0.9, 0.8, None, 1.0);
        assert!(
            q >= 8,
            "empty shelf must still raise a case-rounded order, got {q}"
        );
    }

    #[test]
    fn sw_non_order_day_zero() {
        let p = ModelParams::default();
        let s = OrderSchedule::default();
        let f_grid = vec![0.0, 1.0];
        let lot_counts = vec![10.0];
        let mut f_marginals = vec![0.0; 2];
        f_marginals[1] = 1.0;
        assert_eq!(
            damped_sw_order_f_belief(
                &lot_counts,
                &f_marginals,
                &f_grid,
                0,
                0,
                &p,
                0.9,
                0.8,
                Some(&s),
                1.0,
            ),
            0
        );
    }

    #[test]
    fn constant_order_nearest_case_round_representative_pairs() {
        let pairs = [(10, 8, 8), (12, 8, 16), (16, 8, 16), (0, 8, 0), (4, 8, 8), (2, 4, 4)];
        for (q, case_size, expected) in pairs {
            let got = constant_order(q, case_size);
            assert_eq!(got, expected, "constant_order({q}, {case_size})");
            assert_eq!(got % case_size, 0);
        }
    }

    #[test]
    fn constant_order_differs_from_damped_sw_when_demand_exceeds_q() {
        let p = ModelParams::default();
        let q = constant_order(8, p.case_size);
        assert!(q > 0);
        let f_grid = vec![0.0, 1.0];
        let sw = damped_sw_order_f_belief(&[], &[], &f_grid, 0, 0, &p, 0.9, 0.8, None, 1.0);
        assert!(
            sw > q,
            "damped_sw on empty shelf ({sw}) should exceed constant q={q}"
        );
    }

    fn f_belief_fixture() -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let k = 3usize;
        let f_grid: Vec<f64> = (0..k).map(|i| i as f64 / 2.0).collect();
        let lot_counts = vec![10.0, 5.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        (lot_counts, f_marginals, f_grid)
    }

    fn hand_effective_inventory_f(
        lot_counts: &[f64],
        f_marginals: &[f64],
        f_grid: &[f64],
        pending_sum: u32,
        f_pipeline_default: f64,
    ) -> f64 {
        let l = lot_counts.len();
        let k = f_grid.len();
        let mut on_hand = 0.0;
        for ell in 0..l {
            let mut e_f = 0.0;
            for bin in 0..k {
                let p = f_marginals.get(ell * k + bin).copied().unwrap_or(0.0);
                e_f += p * f_grid[bin];
            }
            on_hand += lot_counts[ell] * e_f;
        }
        on_hand + f64::from(pending_sum) * f_pipeline_default
    }

    #[test]
    fn effective_inventory_f_belief_matches_ef_weighted_sum() {
        let (lot_counts, f_marginals, f_grid) = f_belief_fixture();
        let pending = 8u32;
        let f_pipe = 1.0;
        let expected = hand_effective_inventory_f(
            &lot_counts,
            &f_marginals,
            &f_grid,
            pending,
            f_pipe,
        );
        assert!((expected - 18.0).abs() < 1e-9);
        let got = effective_inventory_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            pending,
            f_pipe,
        );
        assert!((got - expected).abs() < 1e-9);
    }

    #[test]
    fn effective_inventory_f_belief_empty_lots_pipeline_only() {
        let f_grid = vec![0.0, 0.5, 1.0];
        let f_marginals: Vec<f64> = vec![];
        let got = effective_inventory_f_belief(&[], &f_marginals, &f_grid, 4, 0.75);
        assert!((got - 3.0).abs() < 1e-9);
    }

    #[test]
    fn damped_sw_order_f_belief_matches_hand_formula() {
        let (lot_counts, f_marginals, f_grid) = f_belief_fixture();
        let params = ModelParams::default();
        let rho = 0.8;
        let alpha = 0.9;
        let pending = 8u32;
        let f_pipe = 1.0;
        let i_tilde = hand_effective_inventory_f(
            &lot_counts,
            &f_marginals,
            &f_grid,
            pending,
            f_pipe,
        );
        let d_star = protection_demand_quantile(alpha, &params, 2, 0);
        let expected = case_round(rho * (d_star - i_tilde).max(0.0), params.case_size);
        let got = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            pending,
            0,
            &params,
            alpha,
            rho,
            None,
            f_pipe,
        );
        assert_eq!(got, expected);
        assert_eq!(got % params.case_size, 0);
    }

    #[test]
    fn damped_sw_order_f_belief_non_order_day_zero() {
        let (lot_counts, f_marginals, f_grid) = f_belief_fixture();
        let params = ModelParams::default();
        let schedule = OrderSchedule::default();
        let got = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            0,
            0,
            &params,
            0.9,
            0.8,
            Some(&schedule),
            1.0,
        );
        assert_eq!(got, 0);
    }

    #[test]
    fn damped_sw_order_f_belief_positive_part_zero_when_inventory_covers_quantile() {
        let f_grid = vec![0.0, 1.0];
        let lot_counts = vec![200.0];
        let mut f_marginals = vec![0.0; 2];
        f_marginals[1] = 1.0;
        let params = ModelParams::default();
        let got = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            0,
            0,
            &params,
            0.9,
            0.8,
            None,
            1.0,
        );
        assert_eq!(got, 0);
    }
}
