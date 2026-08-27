//! Display-only tradeoff forecast (ADR 0130) — bank-resampled paths, CRN across q.

use serde_json::json;

use crate::protection_sim::{bank_start_state, simulate_protection_path};
use crate::schedule::OrderSchedule;
use crate::shipments::ShipmentTrace;
use crate::unit_pf::UnitParticleBank;
use crate::ModelParams;

/// Case-snapped q sweep for DecisionRail slider parity.
pub fn full_tradeoff_q_candidates(case_size: u32) -> Vec<u32> {
    let cs = case_size.max(1);
    let max_q = 160.max(cs * 20);
    (0..=max_q).step_by(cs as usize).collect()
}

/// Nearest-rank percentile `p` (in `[0, 1]`) of `sorted`, which must already be sorted
/// ascending.
fn percentile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((sorted.len() - 1) as f64 * p).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

/// Index of the bin containing `v` given ascending bin edges `bins`; values at or beyond
/// the last edge clamp into the final bin.
fn bin_index(v: f64, bins: &[f64]) -> usize {
    for i in 0..bins.len().saturating_sub(1) {
        if v < bins[i + 1] {
            return i;
        }
    }
    bins.len().saturating_sub(2)
}

/// Sweeps the case-snapped candidate order quantities from [`full_tradeoff_q_candidates`]
/// and, for each one, rolls forward `n_paths` bank-resampled particle continuations over
/// the protection window to estimate the waste/missed-demand tradeoff that quantity implies.
///
/// Every candidate reuses the same per-path, per-day random draws (see `path_rng`), so
/// the reported percentile bands and joint waste/missed histogram reflect the effect of `q`
/// alone rather than sampling noise between candidates. This backs the studio's tradeoff
/// display, not the ordering policy itself.
pub fn tradeoff_forecast(
    bank: &UnitParticleBank,
    _l_dim: usize,
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

    let shipments = [ShipmentTrace::smoke_cool()];
    let run_id = "tradeoff";
    let starts: Vec<(Vec<f64>, Vec<usize>)> = (0..n)
        .map(|path| bank_start_state(bank, path as u32))
        .collect();

    let mut out_candidates = Vec::with_capacity(candidates.len());
    for &q in &candidates {
        let mut waste_samples = Vec::with_capacity(n);
        let mut missed_samples = Vec::with_capacity(n);
        for (path, (f0, o0)) in starts.iter().enumerate() {
            let result = simulate_protection_path(
                f0,
                o0,
                params,
                &shipments,
                seed,
                run_id,
                path as u32,
                prot,
                q,
                lead_time,
                current_day,
            );
            waste_samples.push(result.waste_total as f64);
            missed_samples.push(result.missed_total as f64);
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
