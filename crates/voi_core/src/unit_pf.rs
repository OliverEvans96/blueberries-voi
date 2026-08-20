//! Unit-level particle filter for C2 Algorithm A (ADR 0130 / ADR 0135).

use rand::Rng;
use rand_distr::{Distribution, Normal};
use rand_pcg::Pcg64;
use rand::SeedableRng;

use crate::obs::FilterObs;
use crate::physics::{apply_gamma_aging, age_to_f};
use crate::shipments::{arrival_age_from_path, shipment_arrival_age, ShipmentTrace};
use crate::unit_ll::{
    align_lot_map, loglik_sales_by_units, loglik_waste_by_units, loglik_waste_tot_after_sales_by,
    p1_totals_loglik, sequential_kernel_path_logprob,
};
use crate::ModelParams;

#[derive(Clone, Debug)]
pub struct UnitParticleBank {
    pub weights: Vec<f64>,
    pub freshness: Vec<Vec<f64>>,
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

fn lot_offsets(n_lots: usize, units_per_lot: usize) -> Vec<usize> {
    (0..=n_lots).map(|i| i * units_per_lot).collect()
}

/// Lot boundaries clamped to actual particle row length (ADR 0136 variable arrivals).
fn lot_offsets_for_len(len: usize, units_per_lot: usize) -> Vec<usize> {
    if len == 0 {
        return vec![0];
    }
    let upl = units_per_lot.max(1);
    let n_lots = len.div_ceil(upl);
    (0..=n_lots).map(|i| (i * upl).min(len)).collect()
}

fn n_lots_from_units(units: usize, units_per_lot: usize) -> usize {
    if units_per_lot == 0 || units == 0 {
        return 0;
    }
    units.div_ceil(units_per_lot)
}

fn mix_arrival_f<R: Rng + ?Sized>(rng: &mut R, params: &ModelParams) -> f64 {
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
    age_to_f(mean + (age - mean), params.eta_ref)
}

fn birth_f<R: Rng + ?Sized>(obs: &FilterObs, params: &ModelParams, rng: &mut R) -> f64 {
    if let (Some(times), Some(temps)) = (&obs.temp_times_d, &obs.temp_temps_c) {
        if times.len() >= 2 && temps.len() == times.len() {
            let age = arrival_age_from_path(temps, times, params.q10, params.t_ref_c);
            return age_to_f(age, params.eta_ref);
        }
    }
    if let Some(pack) = obs.pack_date_days {
        let sd = params.f2a_transit_uncertainty_sd;
        let dist = Normal::new(f64::from(pack), sd).expect("sd > 0");
        let age = dist.sample(rng).max(0.0);
        return age_to_f(age, params.eta_ref);
    }
    mix_arrival_f(rng, params)
}

/// Score particle and apply unscored sales removal after a finite likelihood (ADR 0135).
///
/// Waste terms are evaluated on **pre-removal** freshness; WOR removal runs only when the
/// sales (+ waste) likelihood is finite.
fn score_particle<R: Rng + ?Sized>(
    freshness: &mut [f64],
    obs: &FilterObs,
    params: &ModelParams,
    path_rng: &mut R,
) -> f64 {
    let upl = params.units_per_lot.max(1);
    let offsets = lot_offsets_for_len(freshness.len(), upl);
    if let Some(ref sales_by) = obs.sales_by {
        let n_lots = offsets.len().saturating_sub(1);
        let aligned = align_lot_map(sales_by, n_lots);
        if aligned.iter().sum::<u32>() == 0 {
            let wt = obs.waste_tot.unwrap_or(0);
            let ll = p1_totals_loglik(freshness, 0, wt, params);
            if !ll.is_finite() {
                return ll;
            }
            return ll;
        }
        let mut ll = loglik_sales_by_units(freshness, &aligned, &offsets, params);
        if !ll.is_finite() {
            return ll;
        }
        if let Some(ref waste_by) = obs.waste_by {
            let wl = loglik_waste_by_units(freshness, &aligned, waste_by, &offsets);
            if !wl.is_finite() {
                return wl;
            }
            ll += wl;
        } else if let Some(wt) = obs.waste_tot {
            let wl = loglik_waste_tot_after_sales_by(freshness, &aligned, wt, &offsets);
            if !wl.is_finite() {
                return wl;
            }
            ll += wl;
        }
        // Unscored state transition: per-lot WOR removal conditional on sales_by.
        for ell in 0..offsets.len().saturating_sub(1) {
            let sales = aligned[ell] as usize;
            if sales > 0 {
                let sl = &mut freshness[offsets[ell]..offsets[ell + 1]];
                let _ = sequential_kernel_path_logprob(sl, sales, params, path_rng);
            }
        }
        return ll;
    }
    match (obs.sales_tot, obs.waste_tot) {
        (Some(sales), waste) => {
            let waste = waste.unwrap_or(0);
            let ll = p1_totals_loglik(freshness, sales, waste, params);
            if !ll.is_finite() {
                return ll;
            }
            // Unscored pooled WOR removal (matches truth pick_units_f).
            let _ = sequential_kernel_path_logprob(
                freshness,
                sales as usize,
                params,
                path_rng,
            );
            ll
        }
        (None, None) => 0.0,
        (None, Some(_)) => 0.0,
    }
}

/// One unit-PF observation update: gamma age, score via obs router, systematic resample.
pub fn filter_step_unit<R: Rng + ?Sized>(
    bank: &mut UnitParticleBank,
    obs: &FilterObs,
    params: &ModelParams,
    rng: &mut R,
) {
    let n = bank.weights.len();
    if n == 0 {
        return;
    }
    let upl = params.units_per_lot.max(1);
    let step_seed = rng.random::<u64>();

    for row in &mut bank.freshness {
        apply_gamma_aging(row, rng, params);
    }

    let mut log_like = vec![0.0f64; n];
    for p in 0..n {
        let mut path_rng = Pcg64::seed_from_u64(step_seed.wrapping_add(p as u64));
        let ll = score_particle(
            &mut bank.freshness[p],
            obs,
            params,
            &mut path_rng,
        );
        log_like[p] = if ll.is_finite() { ll } else { -1e300 };
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

    if obs.arrivals > 0 {
        let n_birth = obs.arrivals as usize;
        for p in 0..n {
            let birth = birth_f(obs, params, rng);
            let row = &mut bank.freshness[p];
            if row.len() >= upl {
                row.drain(0..upl);
            }
            row.extend(vec![birth; n_birth]);
        }
    }

    let idx = systematic_resample(&log_w);
    bank.freshness = idx.iter().map(|&j| bank.freshness[j].clone()).collect();
    bank.weights = vec![1.0 / n as f64; n];
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;

    #[test]
    fn unit_pf_filter_step_p1_updates_weights() {
        let upl = 15;
        let units = upl * 2;
        let n = 4;
        let mut rng = Pcg64::seed_from_u64(1);
        let mut bank = UnitParticleBank {
            weights: vec![0.25; n],
            freshness: (0..n)
                .map(|_| (0..units).map(|_| 0.5 + rng.random::<f64>() * 0.3).collect())
                .collect(),
        };
        let obs = FilterObs {
            sales_tot: Some(3),
            waste_tot: Some(1),
            arrivals: 0,
            ..Default::default()
        };
        let params = ModelParams::default();
        filter_step_unit(&mut bank, &obs, &params, &mut rng);
        let s: f64 = bank.weights.iter().sum();
        assert!((s - 1.0).abs() < 1e-9);
        assert_eq!(bank.freshness.len(), n);
    }

    #[test]
    fn unit_pf_router_sales_by_scores_finite() {
        let upl = 15;
        let units = upl * 2;
        let n = 2;
        let mut rng = Pcg64::seed_from_u64(2);
        let bank = UnitParticleBank {
            weights: vec![0.5, 0.5],
            freshness: vec![
                vec![0.8; units],
                vec![0.6; units],
            ],
        };
        let mut bank = bank;
        let obs = FilterObs {
            sales_tot: Some(4),
            waste_tot: Some(0),
            arrivals: 0,
            sales_by: Some(vec![2, 2]),
            ..Default::default()
        };
        filter_step_unit(&mut bank, &obs, &ModelParams::default(), &mut rng);
        assert_eq!(bank.freshness.len(), n);
    }
}
