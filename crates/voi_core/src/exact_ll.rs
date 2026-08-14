//! Exact sequential-WOR × binomial waste log-likelihood (Python exact_likelihood).

use crate::physics::{death_prob_survival_ratio, picking_weights, q10_age_increment};
use crate::wor::sequential_wor_composition_probs;
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

pub fn log_p_sales_waste_given_ages(
    n: &[u32],
    tau: &[f64],
    sales_tot: i32,
    waste_tot: i32,
    params: &ModelParams,
) -> f64 {
    if n.len() != tau.len() {
        panic!("n and tau must have the same length");
    }
    let on_hand: i32 = n.iter().map(|&x| x as i32).sum();
    if sales_tot < 0 || waste_tot < 0 || sales_tot > on_hand {
        return f64::NEG_INFINITY;
    }
    let max_waste = on_hand - sales_tot;
    if waste_tot > max_waste {
        return f64::NEG_INFINITY;
    }
    let dtau = q10_age_increment(1.0, params.t_store_c, params.t_ref_c, params.q10);
    let w = picking_weights(
        tau,
        params.sigma,
        params.beta,
        params.eta_ref,
        params.uniform_picking,
    );
    let p_die: Vec<f64> = tau
        .iter()
        .map(|&t| death_prob_survival_ratio(t, dtau, params.beta, params.eta_ref))
        .collect();

    let sales_map = if sales_tot == on_hand {
        vec![(n.to_vec(), 1.0)]
    } else {
        sequential_wor_composition_probs(n, sales_tot, &w)
    };

    let mut like = 0.0;
    for (sales, p_sales) in sales_map {
        if p_sales <= 0.0 {
            continue;
        }
        let remaining: Vec<u32> = n
            .iter()
            .zip(sales.iter())
            .map(|(ni, si)| ni.saturating_sub(*si))
            .collect();
        let mut p_waste = 0.0;
        for waste in iter_compositions(&remaining, waste_tot) {
            let mut term = 1.0;
            for j in 0..remaining.len() {
                term *= binom_pmf(waste[j] as i32, remaining[j] as i32, p_die[j]);
            }
            p_waste += term;
        }
        like += p_sales * p_waste;
    }
    if like <= 0.0 {
        f64::NEG_INFINITY
    } else {
        like.ln()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn impossible_sales_neg_inf() {
        let p = ModelParams::default();
        let ll = log_p_sales_waste_given_ages(&[2, 2], &[1.0, 2.0], 9, 0, &p);
        assert!(ll.is_infinite() && ll < 0.0);
    }

    #[test]
    fn feasible_sales_finite() {
        let p = ModelParams::default();
        let ll = log_p_sales_waste_given_ages(&[3, 3], &[1.0, 5.0], 2, 1, &p);
        assert!(ll.is_finite(), "{ll}");
    }
}
