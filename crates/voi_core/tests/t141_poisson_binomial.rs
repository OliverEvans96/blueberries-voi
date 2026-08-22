//! T-141 AC-L2: Poisson-binomial spoilage likelihood (RED until implemented).

use rand::{Rng, SeedableRng};
use rand_pcg::Pcg64;
use voi_core::physics::gamma_decrement_cdf;
use voi_core::unit_ll::{pb_log_pmf, pb_loglik_by_lot, pb_sample_deaths, spoil_probs_from_freshness};
use voi_core::ModelParams;

fn hand_spoil_prob(f: f64, params: &ModelParams) -> f64 {
    if f <= 0.0 {
        return 0.0;
    }
    (1.0 - gamma_decrement_cdf(f, params)).clamp(0.0, 1.0)
}

fn hand_spoil_probs_from_freshness(freshness: &[f64], params: &ModelParams) -> Vec<f64> {
    freshness
        .iter()
        .copied()
        .filter(|&f| f > 0.0)
        .map(|f| hand_spoil_prob(f, params))
        .collect()
}

fn brute_pb_log_pmf(probs: &[f64], k: usize) -> f64 {
    let n = probs.len();
    if k > n {
        return f64::NEG_INFINITY;
    }
    let mut total = 0.0f64;
    for mask in 0u32..(1u32 << n) {
        let deaths = (0..n).filter(|i| (mask >> i) & 1 == 1).count();
        if deaths != k {
            continue;
        }
        let mut p = 1.0;
        for (i, &pi) in probs.iter().enumerate() {
            if (mask >> i) & 1 == 1 {
                p *= pi;
            } else {
                p *= 1.0 - pi;
            }
        }
        total += p;
    }
    if total <= 0.0 {
        f64::NEG_INFINITY
    } else {
        total.ln()
    }
}

fn log_sum_exp(values: &[f64]) -> f64 {
    let mx = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    if !mx.is_finite() {
        return f64::NEG_INFINITY;
    }
    mx + values.iter().map(|&v| (v - mx).exp()).sum::<f64>().ln()
}

/// AC-L2: PMF entries sum to 1 in log space for small cohorts.
#[test]
fn pb_log_pmf_normalizes_on_small_n() {
    let params = ModelParams::default();
    let cases: &[&[f64]] = &[
        &[0.05, 0.10, 0.20],
        &[0.15, 0.15, 0.30, 0.45],
        &[0.08, 0.12, 0.18, 0.22, 0.26],
    ];
    for freshness in cases {
        let probs = spoil_probs_from_freshness(freshness, &params);
        assert_eq!(
            probs,
            hand_spoil_probs_from_freshness(freshness, &params),
            "spoil_probs_from_freshness must match gamma spoil mass"
        );
        let n = probs.len();
        let log_mass: Vec<f64> = (0..=n)
            .map(|k| pb_log_pmf(&probs, k))
            .collect();
        for (k, &ll) in log_mass.iter().enumerate() {
            let hand = brute_pb_log_pmf(&probs, k);
            assert!(
                (ll - hand).abs() < 1e-9,
                "pb_log_pmf({k})={ll} hand={hand}"
            );
        }
        let norm = log_sum_exp(&log_mass);
        assert!(
            (norm.abs()) < 1e-9,
            "PB log-PMF must normalize to 1, got exp(log_sum)={}",
            norm.exp()
        );
    }
}

fn brute_pb_loglik_by_lot(
    freshness: &[f64],
    offsets: &[usize],
    waste_by: &[u32],
    params: &ModelParams,
) -> f64 {
    let n_lots = offsets.len().saturating_sub(1);
    assert_eq!(waste_by.len(), n_lots);
    let mut ll = 0.0;
    for ell in 0..n_lots {
        let start = offsets[ell].min(freshness.len());
        let end = offsets[ell + 1].min(freshness.len());
        let seg: Vec<f64> = freshness[start..end]
            .iter()
            .copied()
            .filter(|&f| f > 0.0)
            .collect();
        let probs: Vec<f64> = seg.iter().map(|&f| hand_spoil_prob(f, params)).collect();
        ll += brute_pb_log_pmf(&probs, waste_by[ell] as usize);
    }
    ll
}

/// AC-L2: per-lot DP loglik matches exhaustive Poisson-binomial on tiny cohorts.
#[test]
fn pb_loglik_by_lot_matches_brute_force() {
    let params = ModelParams::default();
    let freshness = vec![0.30, 0.32, 0.34, 0.20, 0.22, 0.24];
    let offsets = vec![0usize, 3, 6];
    let waste_cases: &[Vec<u32>] = &[
        vec![0, 0],
        vec![1, 0],
        vec![0, 1],
        vec![2, 1],
    ];
    for waste_by in waste_cases {
        let got = pb_loglik_by_lot(&freshness, &offsets, waste_by, &params);
        let want = brute_pb_loglik_by_lot(&freshness, &offsets, waste_by, &params);
        assert!(
            (got - want).abs() < 1e-9,
            "waste_by={waste_by:?} got={got} want={want}"
        );
    }
}

/// AC-L2: backward sampler reports the exact PMF mass for the observed death count.
#[test]
fn pb_sample_deaths_weight_equals_exact_pmf() {
    let params = ModelParams::default();
    let freshness = vec![0.12, 0.18, 0.24, 0.30];
    let probs = spoil_probs_from_freshness(&freshness, &params);
    let mut rng = Pcg64::seed_from_u64(141_002);
    for k in 0..=probs.len() {
        let exact = pb_log_pmf(&probs, k);
        for _ in 0..32 {
            let (deaths, log_w) = pb_sample_deaths(&probs, k, &mut rng);
            assert_eq!(
                deaths.len(),
                probs.len(),
                "sampler must label every live unit"
            );
            assert_eq!(
                deaths.iter().filter(|&&d| d).count(),
                k,
                "sampler must respect requested death count"
            );
            assert!(
                (log_w - exact).abs() < 1e-9,
                "pb_sample_deaths weight must equal pb_log_pmf({k})"
            );
        }
    }

    // Exhaustive small case: every k-subset death pattern carries identical weight.
    let tiny = vec![0.10, 0.40, 0.70];
    let tiny_probs = spoil_probs_from_freshness(&tiny, &params);
    assert_eq!(tiny_probs, hand_spoil_probs_from_freshness(&tiny, &params));
    let k = 2usize;
    let exact = pb_log_pmf(&tiny_probs, k);
    let mut rng = Pcg64::seed_from_u64(141_003);
    let mut seen = 0usize;
    for _ in 0..512 {
        let (deaths, log_w) = pb_sample_deaths(&tiny_probs, k, &mut rng);
        if deaths.iter().filter(|&&d| d).count() == k {
            assert!((log_w - exact).abs() < 1e-9);
            seen += 1;
        }
    }
    assert!(seen > 0, "sampler must emit feasible death patterns");
}
