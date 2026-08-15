//! Counts-only RBPF batch step (ADR 0105). Full particle bank stays in-Rust.

use rand::Rng;
use rand_distr::{Binomial, Distribution, Normal};

use crate::exact_ll::{binom_pmf, iter_compositions, log_p_sales_waste_given_ages};
use crate::physics::{
    allocate_sales, death_prob_survival_ratio, picking_weights, q10_age_increment,
};
use crate::shipments::{shipment_arrival_age, ShipmentTrace};
use crate::wor::sequential_wor_composition_prob;
use crate::ModelParams;

pub use crate::obs::FilterObs;

const F2A_BIRTH_SD: f64 = 0.75;

/// Log-likelihood of a known sales composition (plus waste total when present).
fn log_p_known_sales_and_waste(
    n: &[u32],
    tau: &[f64],
    sales: &[u32],
    waste_tot: Option<i32>,
    params: &ModelParams,
) -> f64 {
    if n.len() != tau.len() {
        return f64::NEG_INFINITY;
    }
    let sales = align_lot_map(sales, n.len());
    let w = picking_weights(
        tau,
        params.sigma,
        params.beta,
        params.eta_ref,
        params.uniform_picking,
    );
    let ll_sales = exact_wor_loglik(n, &sales, &w);
    if !ll_sales.is_finite() {
        return f64::NEG_INFINITY;
    }
    let Some(wt) = waste_tot else {
        return ll_sales;
    };
    let remaining: Vec<u32> = n
        .iter()
        .zip(sales.iter())
        .map(|(ni, si)| ni.saturating_sub(*si))
        .collect();
    let on_rem: i32 = remaining.iter().map(|&x| x as i32).sum();
    if wt < 0 || wt > on_rem {
        return f64::NEG_INFINITY;
    }
    let dtau = q10_age_increment(1.0, params.t_store_c, params.t_ref_c, params.q10);
    let p_die: Vec<f64> = tau
        .iter()
        .map(|&t| death_prob_survival_ratio(t, dtau, params.beta, params.eta_ref))
        .collect();
    let mut p_waste = 0.0;
    for waste in iter_compositions(&remaining, wt) {
        let mut term = 1.0;
        for j in 0..remaining.len() {
            term *= binom_pmf(waste[j] as i32, remaining[j] as i32, p_die[j]);
        }
        p_waste += term;
    }
    if p_waste <= 0.0 {
        f64::NEG_INFINITY
    } else {
        ll_sales + p_waste.ln()
    }
}

fn align_lot_map(sales: &[u32], l: usize) -> Vec<u32> {
    if sales.len() == l {
        return sales.to_vec();
    }
    if sales.len() > l {
        return sales[sales.len() - l..].to_vec();
    }
    let mut padded = vec![0u32; l - sales.len()];
    padded.extend_from_slice(sales);
    padded
}

fn birth_tau<R: Rng + ?Sized>(obs: &FilterObs, params: &ModelParams, rng: &mut R) -> f64 {
    if let Some(age) = obs.age_at_receipt {
        return age;
    }
    if let Some(pack) = obs.pack_date_days {
        let dist = Normal::new(f64::from(pack), F2A_BIRTH_SD).expect("sd > 0");
        return dist.sample(rng).max(0.0);
    }
    mix_arrival_age(rng, params)
}

/// Unlabeled (P0/P1/F1) birth: mix of cool-path lengths, wider than F2a SD=0.75.
fn mix_arrival_age<R: Rng + ?Sized>(rng: &mut R, params: &ModelParams) -> f64 {
    let ships = [
        ShipmentTrace {
            times_d: vec![0.0, 0.5],
            temps_c: vec![1.0, 1.0],
        },
        ShipmentTrace::smoke_cool(),
        ShipmentTrace {
            times_d: vec![0.0, 4.0],
            temps_c: vec![1.0, 1.0],
        },
    ];
    let idx = rng.random_range(0..ships.len());
    let _: f64 = rng.random();
    let ages: Vec<f64> = ships
        .iter()
        .map(|s| shipment_arrival_age(s, params.q10, params.t_ref_c))
        .collect();
    let mean: f64 = ages.iter().sum::<f64>() / ages.len() as f64;
    let age = ages[idx];
    mean + (age - mean)
}

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
        if let Some(ref sales_by) = obs.sales_by {
            let ll = log_p_known_sales_and_waste(
                &bank.counts[i],
                &taus[i],
                sales_by,
                obs.waste_tot,
                params,
            );
            log_like[i] = if ll.is_finite() { ll } else { -1e300 };
        } else {
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
            taus[i].push(birth_tau(obs, params, rng));
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
            ..Default::default()
        };
        let out = filter_step(&bank, &obs, &ModelParams::default(), &mut rng);
        let s: f64 = out.weights.iter().sum();
        assert!((s - 1.0).abs() < 1e-9, "{s}");
        assert_eq!(out.counts.len(), 2);
    }

    fn emptyish_bank(n: usize) -> ParticleBank {
        ParticleBank {
            weights: vec![1.0 / n as f64; n],
            counts: vec![vec![]; n],
            taus: vec![vec![]; n],
        }
    }

    /// F2: Dirac birth on `age_at_receipt`, not τ=0 (clock already applied to old lots).
    #[test]
    fn filter_step_f2_births_dirac_on_age_at_receipt() {
        let mut rng = Pcg64::seed_from_u64(9);
        let bank = emptyish_bank(8);
        let obs = FilterObs {
            arrivals: 6,
            age_at_receipt: Some(2.25),
            ..Default::default()
        };
        let out = filter_step(&bank, &obs, &ModelParams::default(), &mut rng);
        for row in &out.taus {
            let born = *row.last().expect("birth slot");
            assert!(
                (born - 2.25).abs() < 1e-9,
                "F2 birth must be Dirac at 2.25, got {born}"
            );
        }
    }

    /// F2a: Gaussian birth, mean = calendar transit encoded in `pack_date_days`, SD=0.75.
    #[test]
    fn filter_step_f2a_gaussian_birth_mean_calendar_sd_075() {
        let mut rng = Pcg64::seed_from_u64(3);
        let n = 400usize;
        let bank = emptyish_bank(n);
        let mean = 2.0;
        let obs = FilterObs {
            arrivals: 8,
            pack_date_days: Some(mean as i32),
            ..Default::default()
        };
        let out = filter_step(&bank, &obs, &ModelParams::default(), &mut rng);
        let births: Vec<f64> = out
            .taus
            .iter()
            .map(|row| *row.last().expect("birth"))
            .collect();
        let m = births.iter().sum::<f64>() / n as f64;
        let var = births.iter().map(|t| (t - m) * (t - m)).sum::<f64>() / n as f64;
        assert!(
            (m - mean).abs() < 0.2,
            "F2a birth mean should be calendar transit {mean}, got {m}"
        );
        assert!(
            (var.sqrt() - 0.75).abs() < 0.15,
            "F2a SD should be 0.75, got {}",
            var.sqrt()
        );
        assert!(
            births.iter().any(|t| (*t - 0.0).abs() > 0.05),
            "must not birth every particle at τ=0"
        );
    }

    /// P0/P1 mix: arrivals without receipt fields must not all sit at τ=0.
    #[test]
    fn filter_step_p0_birth_not_always_zero() {
        let mut rng = Pcg64::seed_from_u64(5);
        let bank = emptyish_bank(64);
        let obs = FilterObs {
            sales_tot: Some(0),
            waste_tot: None,
            arrivals: 8,
            ..Default::default()
        };
        let out = filter_step(&bank, &obs, &ModelParams::default(), &mut rng);
        let any_nonzero = out
            .taus
            .iter()
            .any(|row| row.last().is_some_and(|t| *t > 0.05));
        assert!(
            any_nonzero,
            "P0/P1/F1 birth should sample the shipments mix, not always τ=0"
        );
    }

    #[test]
    fn filter_step_lot_map_sales_by_changes_weights_vs_totals() {
        let bank = ParticleBank {
            weights: vec![0.5, 0.5],
            counts: vec![vec![10, 0], vec![0, 10]],
            taus: vec![vec![1.0, 3.0], vec![1.0, 3.0]],
        };
        let totals = FilterObs {
            sales_tot: Some(4),
            waste_tot: Some(0),
            arrivals: 0,
            ..Default::default()
        };
        let mapped = FilterObs {
            sales_tot: Some(4),
            waste_tot: Some(0),
            arrivals: 0,
            sales_by: Some(vec![4, 0]),
            lot_ids_live: Some(vec![1, 2]),
            ..Default::default()
        };
        let mut rng_a = Pcg64::seed_from_u64(21);
        let mut rng_b = Pcg64::seed_from_u64(21);
        let out_p1 = filter_step(&bank, &totals, &ModelParams::default(), &mut rng_a);
        let out_f1 = filter_step(&bank, &mapped, &ModelParams::default(), &mut rng_b);
        let d: f64 = out_p1
            .weights
            .iter()
            .zip(out_f1.weights.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        assert!(
            d > 1e-9,
            "F1 sales_by should reweight vs P1 totals-only; L1={d}"
        );
    }
}
