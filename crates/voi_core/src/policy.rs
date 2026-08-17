//! Damped survival-weighted base-stock (algorithm from `damped_sw.py`).

use crate::schedule::OrderSchedule;
use crate::ModelParams;

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

pub fn case_round_ceil(qty: u32, case_size: u32) -> u32 {
    if qty == 0 || case_size == 0 {
        return 0;
    }
    let cases = qty.div_ceil(case_size);
    cases * case_size
}

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

pub fn protection_demand_quantile(alpha: f64, params: &ModelParams, protection_days: u32) -> f64 {
    if !(0.0 < alpha && alpha < 1.0) {
        panic!("alpha must be in (0,1)");
    }
    let r = (params.demand_mu / (params.demand_vm - 1.0)) * f64::from(protection_days);
    let p = (params.demand_mu / (params.demand_vm - 1.0))
        / (params.demand_mu / (params.demand_vm - 1.0) + params.demand_mu);
    nbinom_ppf(alpha, r, p)
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
    let d_star = protection_demand_quantile(alpha, params, n_days);
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
        let d_star = protection_demand_quantile(alpha, &params, 2);
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
