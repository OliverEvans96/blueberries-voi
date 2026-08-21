//! Display-only tradeoff forecast (ADR 0130) — bank-resampled paths, CRN across q.

use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::json;

use crate::day_step::{unit_day_step, UnitDayStepIn};
use crate::physics::{draw_demand, gamma_decrement_for_store};
use crate::schedule::OrderSchedule;
use crate::shipments::ShipmentTrace;
use crate::unit_pf::{systematic_resample, UnitParticleBank};
use crate::ModelParams;

/// Case-snapped q sweep for DecisionRail slider parity.
pub fn full_tradeoff_q_candidates(case_size: u32) -> Vec<u32> {
    let cs = case_size.max(1);
    let max_q = 160.max(cs * 20);
    (0..=max_q).step_by(cs as usize).collect()
}

fn path_rng(seed: u64, path: u32, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        seed.wrapping_add(u64::from(path).wrapping_mul(1_000_003))
            .wrapping_add(u64::from(day).wrapping_mul(97))
            .wrapping_add(stream),
    )
}

fn bank_start_state(
    bank: &UnitParticleBank,
    path: u32,
    l_dim: usize,
    units_per_lot: usize,
) -> (Vec<f64>, Vec<usize>) {
    let log_w: Vec<f64> = bank
        .weights
        .iter()
        .map(|w| if *w > 0.0 { w.ln() } else { f64::NEG_INFINITY })
        .collect();
    let indices = systematic_resample(&log_w);
    let pidx = indices[path as usize % indices.len().max(1)];
    let mut freshness = bank.freshness.get(pidx).cloned().unwrap_or_default();
    let upl = units_per_lot.max(1);
    let lots = l_dim.max(1);
    if freshness.is_empty() {
        freshness = vec![1.0; lots * upl];
    }
    let lot_offsets: Vec<usize> = (0..=lots).map(|i| i * upl).collect();
    (freshness, lot_offsets)
}

fn simulate_protection_path(
    start_freshness: &[f64],
    start_offsets: &[usize],
    params: &ModelParams,
    seed: u64,
    path: u32,
    protection_days: u32,
    order_q: u32,
    lead_time: u32,
    current_day: u32,
) -> (u32, u32) {
    let mut freshness = start_freshness.to_vec();
    let mut lot_offsets = start_offsets.to_vec();
    let shipments = [ShipmentTrace::smoke_cool()];
    let mut waste_total = 0u32;
    let mut missed_total = 0u32;

    for d in 0..protection_days {
        let day = current_day + d;
        let arrival = if d == lead_time { order_q } else { 0 };
        let mut rng_gamma = path_rng(seed, path, d, 3);
        let mut rng_alloc = path_rng(seed, path, d, 2);
        let mut rng_demand = path_rng(seed, path, d, 1);
        let demand = draw_demand(&mut rng_demand, params, Some(day));
        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: Some(gamma_decrement_for_store(params)),
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_f: Some(1.0),
            delivery_lambda: None,
            units_per_lot: Some(params.units_per_lot),
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let out = unit_day_step(
            &input,
            params,
            &shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
        );
        waste_total = waste_total.saturating_add(out.waste_total);
        missed_total = missed_total.saturating_add(out.demand.saturating_sub(out.sales_total));
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }
    (waste_total, missed_total)
}

fn percentile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((sorted.len() - 1) as f64 * p).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn bin_index(v: f64, bins: &[f64]) -> usize {
    for i in 0..bins.len().saturating_sub(1) {
        if v < bins[i + 1] {
            return i;
        }
    }
    bins.len().saturating_sub(2)
}

pub fn tradeoff_forecast(
    bank: &UnitParticleBank,
    l_dim: usize,
    params: &ModelParams,
    schedule: &OrderSchedule,
    current_day: u32,
    seed: u64,
    n_paths: u32,
    protection_days: Option<u32>,
) -> serde_json::Value {
    let prot = protection_days.unwrap_or_else(|| schedule.protection_days(current_day));
    let candidates = full_tradeoff_q_candidates(params.case_size);
    let lead_time = schedule.lead_time_days;
    let n = n_paths.max(1) as usize;

    let starts: Vec<(Vec<f64>, Vec<usize>)> = (0..n)
        .map(|path| bank_start_state(bank, path as u32, l_dim, params.units_per_lot))
        .collect();

    let mut out_candidates = Vec::with_capacity(candidates.len());
    for &q in &candidates {
        let mut waste_samples = Vec::with_capacity(n);
        let mut missed_samples = Vec::with_capacity(n);
        for (path, (f0, o0)) in starts.iter().enumerate() {
            let (w, m) = simulate_protection_path(
                f0,
                o0,
                params,
                seed,
                path as u32,
                prot,
                q,
                lead_time,
                current_day,
            );
            waste_samples.push(w as f64);
            missed_samples.push(m as f64);
        }
        waste_samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        missed_samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let waste_mean = waste_samples.iter().sum::<f64>() / n as f64;
        let missed_mean = missed_samples.iter().sum::<f64>() / n as f64;
        let waste_bins = vec![0.0, 1.0, 2.0, 4.0, 8.0, 16.0];
        let missed_bins = vec![0.0, 2.0, 4.0, 8.0, 16.0, 32.0];
        let mut counts = vec![vec![0u32; missed_bins.len() - 1]; waste_bins.len() - 1];
        for i in 0..waste_samples.len() {
            let wi = bin_index(waste_samples[i], &waste_bins);
            let mi = bin_index(missed_samples[i], &missed_bins);
            if wi < counts.len() && mi < counts[wi].len() {
                counts[wi][mi] += 1;
            }
        }
        out_candidates.push(json!({
            "q": q,
            "waste_mean": waste_mean,
            "waste_p10": percentile(&waste_samples, 0.10),
            "waste_p50": percentile(&waste_samples, 0.50),
            "waste_p90": percentile(&waste_samples, 0.90),
            "missed_mean": missed_mean,
            "missed_p10": percentile(&missed_samples, 0.10),
            "missed_p50": percentile(&missed_samples, 0.50),
            "missed_p90": percentile(&missed_samples, 0.90),
            "joint_hist": {
                "waste_bins": waste_bins,
                "missed_bins": missed_bins,
                "counts": counts,
            }
        }));
    }
    json!({ "candidates": out_candidates })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit_pf::UnitParticleBank;

    #[test]
    fn full_q_sweep_includes_zero_and_case_multiples() {
        let c = full_tradeoff_q_candidates(8);
        assert_eq!(c[0], 0);
        assert!(c.iter().all(|q| q % 8 == 0));
        assert!(*c.last().unwrap() >= 160);
    }

    #[test]
    fn tradeoff_returns_candidates_with_bands() {
        let bank = UnitParticleBank::from_rows_uniform_lots(
            vec![0.5, 0.5],
            vec![vec![1.0, 0.9], vec![0.8, 0.7]],
            2,
        );
        let params = ModelParams::default();
        let schedule = OrderSchedule::default();
        let v = tradeoff_forecast(&bank, 2, &params, &schedule, 0, 42, 4, Some(3));
        let cands = v["candidates"].as_array().unwrap();
        assert!(!cands.is_empty());
        assert!(cands[0]["waste_p90"].as_f64().unwrap() >= cands[0]["waste_p10"].as_f64().unwrap());
    }
}
