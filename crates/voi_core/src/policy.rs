//! Damped survival-weighted base-stock (algorithm from `damped_sw.py`).

use crate::physics::weibull_survival;
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

pub fn effective_inventory(
    counts: &[u32],
    taus: &[f64],
    pending_sum: u32,
    params: &ModelParams,
) -> f64 {
    let mut on_hand = 0.0;
    for (n, tau) in counts.iter().zip(taus.iter()) {
        on_hand += f64::from(*n) * weibull_survival(*tau, params.beta, params.eta_ref);
    }
    let pipeline_w = weibull_survival(0.0, params.beta, params.eta_ref);
    on_hand + f64::from(pending_sum) * pipeline_w
}

pub fn damped_sw_order(
    counts: &[u32],
    taus: &[f64],
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    alpha: f64,
    rho: f64,
    schedule: Option<&OrderSchedule>,
) -> u32 {
    if let Some(s) = schedule {
        if !s.can_order(day) {
            return 0;
        }
    }
    let n_days = schedule.map(|s| s.protection_days(day)).unwrap_or(2);
    let i_tilde = effective_inventory(counts, taus, pending_sum, params);
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
        let q = damped_sw_order(&[], &[], 0, 0, &p, 0.9, 0.8, None);
        assert!(
            q >= 8,
            "empty shelf must still raise a case-rounded order, got {q}"
        );
    }

    #[test]
    fn sw_non_order_day_zero() {
        let p = ModelParams::default();
        let s = OrderSchedule::default();
        assert_eq!(
            damped_sw_order(&[10], &[0.0], 0, 0, &p, 0.9, 0.8, Some(&s)),
            0
        );
    }
}
