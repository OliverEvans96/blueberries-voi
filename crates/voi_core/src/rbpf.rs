//! Counts-only RBPF batch step (ADR 0105). Full particle bank stays in-Rust.

use rand::Rng;
use rand_distr::{Binomial, Distribution};

use crate::exact_ll::log_p_sales_waste_given_ages;
use crate::physics::{
    allocate_sales, death_prob_survival_ratio, picking_weights, q10_age_increment,
};
use crate::wor::sequential_wor_composition_prob;
use crate::ModelParams;

/// Log-likelihood of a sales composition under sequential WOR (exact LL).
pub fn exact_wor_loglik(counts: &[u32], sales: &[u32], weights: &[f64]) -> f64 {
    let p = sequential_wor_composition_prob(counts, sales, weights);
    if p <= 0.0 {
        f64::NEG_INFINITY
    } else {
        p.ln()
    }
}

pub fn systematic_resample(log_w: &[f64]) -> Vec<usize> {
    let n = log_w.len();
    if n == 0 {
        return Vec::new();
    }
    let max = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - max).exp()).collect();
    let z: f64 = w.iter().sum();
    if z <= 0.0 {
        return (0..n).collect();
    }
    for x in &mut w {
        *x /= z;
    }
    let mut cdf = vec![0.0; n];
    cdf[0] = w[0];
    for i in 1..n {
        cdf[i] = cdf[i - 1] + w[i];
    }
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let u = (i as f64 + 0.5) / n as f64;
        let idx = cdf.iter().position(|&c| c >= u).unwrap_or(n - 1);
        out.push(idx);
    }
    out
}

#[derive(Clone, Debug)]
pub struct ParticleBank {
    pub weights: Vec<f64>,
    pub counts: Vec<Vec<u32>>,
    pub taus: Vec<Vec<f64>>,
}

#[derive(Clone, Debug)]
pub struct FilterObs {
    pub sales_tot: Option<i32>,
    pub waste_tot: Option<i32>,
    pub arrivals: u32,
}

pub fn filter_step<R: Rng + ?Sized>(
    bank: &ParticleBank,
    obs: &FilterObs,
    params: &ModelParams,
    rng: &mut R,
) -> ParticleBank {
    let n = bank.weights.len();
    if n == 0 {
        return bank.clone();
    }
    let dtau = q10_age_increment(1.0, params.t_store_c, params.t_ref_c, params.q10);
    let mut taus: Vec<Vec<f64>> = bank
        .taus
        .iter()
        .map(|row| row.iter().map(|t| t + dtau).collect())
        .collect();
    let mut log_like = vec![0.0; n];
    for i in 0..n {
        match (obs.sales_tot, obs.waste_tot) {
            (None, None) => log_like[i] = 0.0,
            (Some(s), Some(w)) => {
                let ll = log_p_sales_waste_given_ages(&bank.counts[i], &taus[i], s, w, params);
                log_like[i] = if ll.is_finite() { ll } else { -1e300 };
            }
            (Some(s), None) => {
                let on_hand: i32 = bank.counts[i].iter().map(|&c| c as i32).sum();
                log_like[i] = if s >= 0 && s <= on_hand { 0.0 } else { -1e300 };
            }
            (None, Some(_)) => log_like[i] = 0.0,
        }
    }
    let mut log_w: Vec<f64> = bank
        .weights
        .iter()
        .zip(log_like.iter())
        .map(|(w, ll)| (w + 1e-300).ln() + ll)
        .collect();
    let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    for x in &mut log_w {
        *x -= mx;
    }
    let mut weights: Vec<f64> = log_w.iter().map(|lw| lw.exp()).collect();
    let z: f64 = weights.iter().sum();
    for w in &mut weights {
        *w /= z.max(1e-300);
    }

    let mut counts = vec![Vec::new(); n];
    for i in 0..n {
        let mut rem = bank.counts[i].clone();
        let tau = &taus[i];
        let on_hand: u32 = rem.iter().sum();
        if on_hand == 0 {
            counts[i] = rem;
            continue;
        }
        let demand = obs.sales_tot.map(|s| s.max(0) as u32).unwrap_or(0);
        let wts = picking_weights(
            tau,
            params.sigma,
            params.beta,
            params.eta_ref,
            params.uniform_picking,
        );
        let sold = allocate_sales(&rem, demand, &wts, rng);
        for (r, s) in rem.iter_mut().zip(sold.iter()) {
            *r = r.saturating_sub(*s);
        }
        for ell in 0..rem.len() {
            let n_left = rem[ell];
            if n_left == 0 {
                continue;
            }
            let p_die = death_prob_survival_ratio(tau[ell], dtau, params.beta, params.eta_ref)
                .clamp(0.0, 1.0);
            let dist = Binomial::new(u64::from(n_left), p_die).expect("binomial");
            let waste = dist.sample(rng) as u32;
            rem[ell] = n_left.saturating_sub(waste);
        }
        counts[i] = rem;
    }

    if obs.arrivals > 0 {
        for i in 0..n {
            if counts[i].len() > 1 {
                counts[i].remove(0);
                taus[i].remove(0);
            }
            counts[i].push(obs.arrivals);
            taus[i].push(0.0);
        }
    }

    let ess: f64 = 1.0 / weights.iter().map(|w| w * w).sum::<f64>();
    let (counts, taus, weights) = if ess < 0.5 * n as f64 {
        let idx = systematic_resample(&weights.iter().map(|w| w.ln()).collect::<Vec<_>>());
        let counts: Vec<Vec<u32>> = idx.iter().map(|&j| counts[j].clone()).collect();
        let taus: Vec<Vec<f64>> = idx.iter().map(|&j| taus[j].clone()).collect();
        (counts, taus, vec![1.0 / n as f64; n])
    } else {
        (counts, taus, weights)
    };

    ParticleBank {
        weights,
        counts,
        taus,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    #[test]
    fn feasible_ll_finite_impossible_neg_inf() {
        let counts = [2u32, 2];
        let w = [1.0, 1.0];
        let ll_ok = exact_wor_loglik(&counts, &[1, 0], &w);
        assert!(ll_ok.is_finite());
        let ll_bad = exact_wor_loglik(&counts, &[3, 0], &w);
        assert!(ll_bad.is_infinite() && ll_bad < 0.0);
    }

    #[test]
    fn resample_uniform_covers_all() {
        let log_w = vec![0.0, 0.0, 0.0, 0.0];
        let idx = systematic_resample(&log_w);
        assert_eq!(idx.len(), 4);
    }

    /// Mirrors counts-only step: weights remain a probability vector.
    #[test]
    fn filter_step_weights_sum_to_one() {
        let mut rng = Pcg64::seed_from_u64(1);
        let bank = ParticleBank {
            weights: vec![0.5, 0.5],
            counts: vec![vec![4, 4], vec![3, 5]],
            taus: vec![vec![1.0, 3.0], vec![1.0, 3.0]],
        };
        let obs = FilterObs {
            sales_tot: Some(2),
            waste_tot: Some(1),
            arrivals: 0,
        };
        let out = filter_step(&bank, &obs, &ModelParams::default(), &mut rng);
        let s: f64 = out.weights.iter().sum();
        assert!((s - 1.0).abs() < 1e-9, "{s}");
        assert_eq!(out.counts.len(), 2);
    }
}
