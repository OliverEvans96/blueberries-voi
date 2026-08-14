//! Counts-only RBPF batch step (ADR 0105). Full particle bank stays in-Rust.

use crate::wor::sequential_wor_composition_prob;

/// Log-likelihood of a sales composition under sequential WOR (exact LL).
pub fn exact_wor_loglik(counts: &[u32], sales: &[u32], weights: &[f64]) -> f64 {
    let p = sequential_wor_composition_prob(counts, sales, weights);
    if p <= 0.0 {
        f64::NEG_INFINITY
    } else {
        p.ln()
    }
}

/// One multinomial-style resample of particle indices given unnormalized log-weights.
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

#[cfg(test)]
mod tests {
    use super::*;

    /// Mirrors `test_log_p_finite_for_feasible_and_neg_inf_for_impossible` (WOR slice).
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
}
