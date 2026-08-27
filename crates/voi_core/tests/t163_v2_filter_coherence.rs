//! T-163 S1.7 — generative duration law matches filter (`Duration(d)`).
//!
//! v2 plan §2.6 / §3.4.7: Monte Carlo `Λ | d` (and `f | d`) mean/variance must track the
//! filter's pack-date channel law within tolerance at `ρ = 0` and at default `ρ`.

use rand::SeedableRng;
use rand_distr::{Distribution, Gamma, LogNormal};
use rand_pcg::Pcg64;

use voi_core::arrival::{resolve_arrival_exposure, ArrivalCondition, ArrivalModel};
use voi_core::physics::gamma_p;
use voi_core::shipments::truth_transit_trace;

const MAX_ENUMERATED_BREAKS: usize = 4;
const MC_SAMPLES: usize = 2048;
const MEAN_RTOL: f64 = 0.03;
const VAR_RTOL: f64 = 0.15;
/// At `ρ = 0`, v2 trip modes + hourly OU must spread `Λ | d` (v2 §1.3–§1.4, §2.6).
const RHO_ZERO_MIN_LAMBDA_VAR: f64 = 1e-4;

fn mean_var(samples: &[f64]) -> (f64, f64) {
    let n = samples.len() as f64;
    let mean = samples.iter().sum::<f64>() / n;
    let var = samples.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
    (mean, var)
}

fn assert_relative(actual: f64, expected: f64, rtol: f64, label: &str) {
    let denom = expected.abs().max(1e-6);
    let rel = (actual - expected).abs() / denom;
    assert!(
        rel <= rtol,
        "{label}: actual={actual:.6} expected={expected:.6} rel_err={rel:.4} (rtol={rtol})"
    );
}

fn gamma_dist_quantile(shape: f64, scale: f64, u: f64) -> f64 {
    let u = u.clamp(1e-12, 1.0 - 1e-12);
    if u <= 0.0 {
        return 0.0;
    }
    let mean = shape * scale;
    let mut hi = mean.max(1e-12) * 4.0;
    while gamma_p(shape, hi / scale) < u && hi < 1e12 {
        hi *= 2.0;
    }
    let mut lo = 0.0;
    for _ in 0..80 {
        let mid = 0.5 * (lo + hi);
        if gamma_p(shape, mid / scale) < u {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}

fn break_count_weights(m: &ArrivalModel, d: f64) -> Vec<f64> {
    let lam = (m.rho * d.max(0.0)).max(0.0);
    if lam <= 0.0 {
        let mut w = vec![0.0; MAX_ENUMERATED_BREAKS + 1];
        w[0] = 1.0;
        return w;
    }
    let mut w = Vec::with_capacity(MAX_ENUMERATED_BREAKS + 1);
    let mut term = (-lam).exp();
    w.push(term);
    for n in 1..=MAX_ENUMERATED_BREAKS {
        term *= lam / n as f64;
        w.push(term);
    }
    let total: f64 = w.iter().sum();
    if total > 0.0 {
        for x in &mut w {
            *x /= total;
        }
    }
    w
}

/// Filter `Duration(d)` thermal marginal over lot-level Λ (pre-ψ), mirroring `thermal_nodes`.
fn filter_lot_lambda_nodes(m: &ArrivalModel, d: f64) -> Vec<(f64, f64)> {
    fn phi_eff(m: &ArrivalModel, t_c: f64, ou: bool) -> f64 {
        let phi = voi_core::physics::store_temp_factor(t_c, m.t_ref, m.q10);
        if !ou || m.sigma_hour <= 0.0 {
            return phi;
        }
        let a = m.q10.ln() / 10.0;
        phi * (0.5 * a * a * m.sigma_hour * m.sigma_hour).exp()
    }

    let d = d.max(0.0);
    let corridor = m.corridor(&m.default_corridor);
    let counts = break_count_weights(m, d);
    let modes = [
        (&m.thermal_modes.cool, m.thermal_modes.cool.p),
        (&m.thermal_modes.nominal, m.thermal_modes.nominal.p),
        (&m.thermal_modes.warm, m.thermal_modes.warm.p),
    ];
    let mut out = Vec::new();
    for (mode, p_m) in modes {
        if p_m <= 0.0 {
            continue;
        }
        let phi_base_m: f64 = m
            .legs
            .iter()
            .enumerate()
            .map(|(k, leg)| leg.weight * phi_eff(m, leg.setpoint_c + mode.offset_c, k > 0))
            .sum();
        let break_rate =
            (voi_core::physics::store_temp_factor(m.t_break, m.t_ref, m.q10) - phi_base_m).max(0.0);
        let m_break = m.tau_bar * break_rate;
        let cap = d * break_rate;

        let rates: Vec<f64> = m
            .legs
            .iter()
            .enumerate()
            .map(|(k, leg)| phi_eff(m, leg.setpoint_c + mode.offset_c, k > 0))
            .collect();
        let alphas: Vec<f64> = m
            .legs
            .iter()
            .map(|leg| (leg.weight * corridor.delay_shape).max(1e-6))
            .collect();
        let alpha0: f64 = alphas.iter().sum();
        let mean_rate: f64 = alphas
            .iter()
            .zip(rates.iter())
            .map(|(&a, &r)| a / alpha0 * r)
            .sum();
        let mut var_rate = 0.0;
        for i in 0..alphas.len() {
            let vi = alphas[i] * (alpha0 - alphas[i]) / (alpha0 * alpha0 * (alpha0 + 1.0));
            var_rate += rates[i] * rates[i] * vi;
            for j in (i + 1)..alphas.len() {
                let cij = -alphas[i] * alphas[j] / (alpha0 * alpha0 * (alpha0 + 1.0));
                var_rate += 2.0 * rates[i] * rates[j] * cij;
            }
        }
        let mean = ArrivalModel::floor_lambda(d * mean_rate);
        let var = (d * d * var_rate).max(0.0);
        let mut baseline_nodes = Vec::with_capacity(m.quad_nodes.len());
        if var <= 1e-12 {
            baseline_nodes.push((mean, 1.0));
        } else {
            let shape = (mean * mean / var).max(1e-6);
            let scale = var / mean;
            for (&u, &w) in m.quad_nodes.iter().zip(m.quad_weights.iter()) {
                baseline_nodes.push((
                    ArrivalModel::floor_lambda(gamma_dist_quantile(shape, scale, u)),
                    w,
                ));
            }
        }

        for (n, &w_n) in counts.iter().enumerate() {
            if w_n <= 0.0 {
                continue;
            }
            for (base_lam, w_base) in &baseline_nodes {
                let w_outer = p_m * w_n * w_base;
                if n == 0 || m_break <= 0.0 {
                    out.push((*base_lam, w_outer));
                    continue;
                }
                for (&u, &w_q) in m.quad_nodes.iter().zip(m.quad_weights.iter()) {
                    let extra = gamma_dist_quantile(n as f64, m_break, u).min(cap);
                    out.push((ArrivalModel::floor_lambda(*base_lam + extra), w_outer * w_q));
                }
            }
        }
    }
    out
}

fn filter_lot_lambda_moments(m: &ArrivalModel, d: f64) -> (f64, f64) {
    let nodes = filter_lot_lambda_nodes(m, d);
    let w_sum: f64 = nodes.iter().map(|(_, w)| w).sum();
    assert!(w_sum > 0.0, "thermal nodes must carry mass");
    let mean = nodes.iter().map(|(x, w)| x * w).sum::<f64>() / w_sum;
    let var = nodes
        .iter()
        .map(|(x, w)| w * (x - mean).powi(2))
        .sum::<f64>()
        / w_sum;
    (mean, var)
}

fn mc_lot_lambda_given_d(m: &ArrivalModel, d: f64, n: usize, seed: u64) -> (f64, f64) {
    let mut rng = Pcg64::seed_from_u64(seed);
    let mut lambdas = Vec::with_capacity(n);
    for _ in 0..n {
        let trace = truth_transit_trace(d, m, 0.0, &mut rng);
        let lambda =
            resolve_arrival_exposure(Some(&trace.temps_c), Some(&trace.times_d), m.q10, m.t_ref)
                .unwrap_or_else(|| ArrivalModel::floor_lambda(d * m.phi_set()));
        lambdas.push(lambda);
    }
    mean_var(&lambdas)
}

fn mc_f_given_d(m: &ArrivalModel, d: f64, n: usize, seed: u64) -> (f64, f64) {
    let mut rng_trace = Pcg64::seed_from_u64(seed);
    let mut rng_pos = Pcg64::seed_from_u64(seed.wrapping_add(1));
    let mut rng_gamma = Pcg64::seed_from_u64(seed.wrapping_add(2));
    let lognormal = LogNormal::new(0.0, m.sigma_pos).expect("lognormal pos");
    let mut fs = Vec::with_capacity(n);
    for _ in 0..n {
        let trace = truth_transit_trace(d, m, 0.0, &mut rng_trace);
        let lot_lambda =
            resolve_arrival_exposure(Some(&trace.temps_c), Some(&trace.times_d), m.q10, m.t_ref)
                .unwrap_or_else(|| ArrivalModel::floor_lambda(d * m.phi_set()));
        let psi = lognormal.sample(&mut rng_pos).max(1e-6);
        let lambda = ArrivalModel::floor_lambda(lot_lambda * psi);
        let loss = Gamma::new(m.gamma_shape * lambda, m.gamma_scale)
            .expect("loss gamma")
            .sample(&mut rng_gamma);
        fs.push((1.0 - loss).max(0.0));
    }
    mean_var(&fs)
}

fn coherence_seed(d: f64, rho: f64, salt: u64) -> u64 {
    let d_bits = (d * 1000.0).round() as u64;
    let rho_bits = (rho * 10_000.0).round() as u64;
    163_007_u64
        .wrapping_mul(1_000_003)
        .wrapping_add(d_bits)
        .wrapping_add(rho_bits.wrapping_mul(97))
        .wrapping_add(salt)
}

fn check_coherence_at_rho(rho: f64) {
    let mut m = ArrivalModel::embedded();
    m.set_break_rate(rho);
    m.set_corridor("abdella_all");
    let default_rho = ArrivalModel::embedded().rho;
    assert!(
        (rho - 0.0).abs() < f64::EPSILON || (rho - default_rho).abs() < 1e-12,
        "coherence guard only runs at ρ=0 and default ρ={default_rho}"
    );

    for &d in &[3.5_f64, 5.0, 7.25] {
        let d_days = d.round() as i32;
        let d_cal = f64::from(d_days);
        let seed = coherence_seed(d, rho, 0);
        let (mc_mean_lam, mc_var_lam) = mc_lot_lambda_given_d(&m, d_cal, MC_SAMPLES, seed);

        if rho.abs() < f64::EPSILON {
            assert!(
                mc_var_lam > RHO_ZERO_MIN_LAMBDA_VAR,
                "v2 §2.6 at ρ=0: generative Λ|d must vary (trip modes + hourly OU); \
                 d={d} Var(Λ|d)={mc_var_lam}"
            );
        }

        let (filt_mean_lam, filt_var_lam) = filter_lot_lambda_moments(&m, d_cal);
        assert_relative(mc_mean_lam, filt_mean_lam, MEAN_RTOL, "E[Λ|d]");
        assert_relative(mc_var_lam, filt_var_lam, VAR_RTOL, "Var(Λ|d)");

        let (mc_mean_f, mc_var_f) = mc_f_given_d(&m, d_cal, MC_SAMPLES, seed.wrapping_add(10));
        let filt_mean_f = m.filter_law_mean_f(ArrivalCondition::Duration(d_days));
        let filt_var_f = m.variance_f_given_d(d_days);
        assert_relative(mc_mean_f, filt_mean_f, MEAN_RTOL, "E[f|d]");
        assert_relative(mc_var_f, filt_var_f, VAR_RTOL, "Var(f|d)");
    }
}

/// S1.7 — Monte Carlo generative `Λ | d` / `f | d` track filter `Duration(d)` (v2 §2.6).
#[test]
#[ignore = "T-163 filter coherence MC; slow: run via cargo test -- --ignored"]
fn generative_duration_law_matches_filter() {
    let default_rho = ArrivalModel::embedded().rho;
    check_coherence_at_rho(0.0);
    check_coherence_at_rho(default_rho);
}
