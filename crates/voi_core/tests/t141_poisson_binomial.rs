//! T-141 AC-L2: Poisson-binomial spoilage likelihood.

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::physics::{gamma_decrement_cdf, GammaDecrementTable};
use voi_core::unit_ll::{pb_log_pmf, pb_loglik_by_lot, pb_sample_deaths, spoil_probs_from_freshness};
use voi_core::ModelParams;

fn hand_spoil_prob(f: f64, params: &ModelParams) -> f64 {
    if f <= 0.0 {
        return 0.0;
    }
    (1.0 - gamma_decrement_cdf(f, params)).clamp(0.0, 1.0)
}

fn table(params: &ModelParams) -> GammaDecrementTable {
    GammaDecrementTable::for_params(params)
}

fn log_sum_exp(values: &[f64]) -> f64 {
    let mx = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    mx + values.iter().map(|&v| (v - mx).exp()).sum::<f64>().ln()
}

#[test]
fn pb_log_pmf_normalizes_on_small_n() {
    let params = ModelParams::default();
    let tbl = table(&params);
    let probs: Vec<f64> = spoil_probs_from_freshness(&[0.05, 0.10, 0.20], &tbl);
    let hand: Vec<f64> = [0.05, 0.10, 0.20]
        .iter()
        .map(|&f| hand_spoil_prob(f, &params))
        .collect();
    for (a, b) in probs.iter().zip(hand.iter()) {
        assert!((a - b).abs() < 1e-5);
    }
    let log_mass: Vec<f64> = (0..=probs.len())
        .map(|k| pb_log_pmf(&probs, k))
        .collect();
    assert!((log_sum_exp(&log_mass).abs()) < 1e-9);
}

#[test]
fn pb_loglik_by_lot_matches_brute_force() {
    let params = ModelParams::default();
    let tbl = table(&params);
    let freshness = vec![0.30, 0.32, 0.34, 0.20, 0.22, 0.24];
    let offsets = vec![0usize, 3, 6];
    let waste_by = vec![1u32, 0u32];
    let got = pb_loglik_by_lot(&freshness, &offsets, &waste_by, &tbl);
    let p0 = spoil_probs_from_freshness(&freshness[0..3], &tbl);
    let p1 = spoil_probs_from_freshness(&freshness[3..6], &tbl);
    let want = pb_log_pmf(&p0, 1) + pb_log_pmf(&p1, 0);
    assert!((got - want).abs() < 1e-9, "got={got} want={want}");
}

#[test]
fn pb_sample_deaths_respects_death_count() {
    let params = ModelParams::default();
    let tbl = table(&params);
    let freshness = vec![0.12, 0.18, 0.24, 0.30];
    let k = 2usize;
    let mut rng = Pcg64::seed_from_u64(141_002);
    for _ in 0..32 {
        let (deaths, log_q) = pb_sample_deaths(&freshness, k, &tbl, &mut rng);
        assert_eq!(deaths.len(), k);
        assert!(log_q.is_finite());
    }
}
