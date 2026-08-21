//! Weibull / Q10 / picking / sequential allocation (Python `model.physics`).
//!
//! Production f-native helpers (`picking_weights_f`, gamma aging, `age_to_f`) live on the
//! hot path; legacy Weibull / τ picking remain for cohort research and test goldens.

use rand::Rng;
use rand_distr::{Distribution, Gamma};

use crate::params::ModelParams;
use crate::spawn_rng::{negative_binomial_gamma_poisson, SpawnRng};

const SURV_FLOOR: f64 = 1e-300;

/// Map effective age τ (days) to unit freshness `f ∈ [0, 1]` (bench C2-A convention).
pub fn age_to_f(tau: f64, eta_ref: f64) -> f64 {
    if eta_ref <= 0.0 {
        panic!("eta_ref must be positive");
    }
    (1.0 - tau / eta_ref).clamp(0.0, 1.0)
}

/// Inverse of [`age_to_f`]: freshness to effective age τ days.
pub fn f_to_age(f: f64, eta_ref: f64) -> f64 {
    if eta_ref <= 0.0 {
        panic!("eta_ref must be positive");
    }
    (1.0 - f.clamp(0.0, 1.0)) * eta_ref
}

/// Q10 temperature factor for store-aging rates (shared with legacy τ clock).
pub fn store_temp_factor(t_store_c: f64, t_ref_c: f64, q10: f64) -> f64 {
    q10.powf((t_store_c - t_ref_c) / 10.0)
}

/// Expected daily gamma freshness decrement at store temperature.
pub fn gamma_decrement_for_store(params: &ModelParams) -> f64 {
    let factor = store_temp_factor(params.t_store_c, params.t_ref_c, params.q10);
    params.gamma_shape * params.gamma_scale * factor
}

/// Draw a stochastic gamma freshness decrement (shape fixed, scale × Q10 factor).
pub fn draw_gamma_decrement<R: Rng + ?Sized>(rng: &mut R, params: &ModelParams) -> f64 {
    let factor = store_temp_factor(params.t_store_c, params.t_ref_c, params.q10);
    let scale = params.gamma_scale * factor;
    let dist = Gamma::new(params.gamma_shape, scale).expect("gamma params");
    dist.sample(rng)
}

/// Store-temperature-adjusted scale of the daily gamma freshness decrement.
pub fn gamma_decrement_scale(params: &ModelParams) -> f64 {
    params.gamma_scale * store_temp_factor(params.t_store_c, params.t_ref_c, params.q10)
}

/// Lanczos `ln Γ(x)` (g = 7, n = 9); ~15 significant digits on `x > 0`.
pub fn ln_gamma(x: f64) -> f64 {
    const C: [f64; 9] = [
        0.999_999_999_999_809_9,
        676.520_368_121_885_1,
        -1_259.139_216_722_402_8,
        771.323_428_777_653_1,
        -176.615_029_162_140_6,
        12.507_343_278_686_905,
        -0.138_571_095_265_720_12,
        9.984_369_578_019_572e-6,
        1.505_632_735_149_311_6e-7,
    ];
    if x < 0.5 {
        // Reflection: Γ(x)Γ(1-x) = π / sin(πx).
        return (std::f64::consts::PI / (std::f64::consts::PI * x).sin()).ln() - ln_gamma(1.0 - x);
    }
    let z = x - 1.0;
    let mut a = C[0];
    for (i, &c) in C.iter().enumerate().skip(1) {
        a += c / (z + i as f64);
    }
    let t = z + 7.5;
    0.5 * (2.0 * std::f64::consts::PI).ln() + (z + 0.5) * t.ln() - t + a.ln()
}

/// Series expansion of the regularized lower incomplete gamma `P(a, x)` (`x < a + 1`).
fn gamma_p_series(a: f64, x: f64) -> f64 {
    let mut ap = a;
    let mut del = 1.0 / a;
    let mut sum = del;
    for _ in 0..500 {
        ap += 1.0;
        del *= x / ap;
        sum += del;
        if del.abs() < sum.abs() * 1e-16 {
            break;
        }
    }
    sum * (-x + a * x.ln() - ln_gamma(a)).exp()
}

/// Continued fraction for the regularized upper incomplete gamma `Q(a, x)` (`x ≥ a + 1`).
fn gamma_q_continued_fraction(a: f64, x: f64) -> f64 {
    const TINY: f64 = 1e-300;
    let mut b = x + 1.0 - a;
    let mut c = 1.0 / TINY;
    let mut d = 1.0 / b;
    let mut h = d;
    for i in 1..500 {
        let an = -(i as f64) * (i as f64 - a);
        b += 2.0;
        d = an * d + b;
        if d.abs() < TINY {
            d = TINY;
        }
        c = b + an / c;
        if c.abs() < TINY {
            c = TINY;
        }
        d = 1.0 / d;
        let del = d * c;
        h *= del;
        if (del - 1.0).abs() < 1e-16 {
            break;
        }
    }
    (-x + a * x.ln() - ln_gamma(a)).exp() * h
}

/// Regularized lower incomplete gamma `P(a, x) = γ(a, x) / Γ(a)`.
pub fn gamma_p(a: f64, x: f64) -> f64 {
    if x <= 0.0 || a <= 0.0 {
        return 0.0;
    }
    if x.is_infinite() {
        return 1.0;
    }
    if x < a + 1.0 {
        gamma_p_series(a, x).clamp(0.0, 1.0)
    } else {
        (1.0 - gamma_q_continued_fraction(a, x)).clamp(0.0, 1.0)
    }
}

/// Regularized upper incomplete gamma `Q(a, x) = 1 - P(a, x)`, accurate in the tail.
pub fn gamma_q(a: f64, x: f64) -> f64 {
    if x <= 0.0 || a <= 0.0 {
        return 1.0;
    }
    if x.is_infinite() {
        return 0.0;
    }
    if x < a + 1.0 {
        (1.0 - gamma_p_series(a, x)).clamp(0.0, 1.0)
    } else {
        gamma_q_continued_fraction(a, x).clamp(0.0, 1.0)
    }
}

/// CDF of the daily store freshness decrement at `x`.
pub fn gamma_decrement_cdf(x: f64, params: &ModelParams) -> f64 {
    gamma_p(params.gamma_shape, x / gamma_decrement_scale(params))
}

/// `P(lo ≤ δ < hi)` for the daily decrement, evaluated on the better-conditioned tail.
pub fn gamma_decrement_interval_prob(lo: f64, hi: f64, params: &ModelParams) -> f64 {
    if !(hi > lo) {
        return 0.0;
    }
    let a = params.gamma_shape;
    let s = gamma_decrement_scale(params);
    let lo_s = (lo / s).max(0.0);
    let hi_s = hi / s;
    // Upper-tail difference avoids cancellation when both CDFs are near 1.
    if lo_s >= a + 1.0 {
        (gamma_q(a, lo_s) - gamma_q(a, hi_s)).max(0.0)
    } else {
        (gamma_p(a, hi_s) - gamma_p(a, lo_s)).max(0.0)
    }
}

/// Inverse CDF of the daily decrement by monotone bisection (`u ∈ [0, 1]`).
pub fn gamma_decrement_quantile(u: f64, params: &ModelParams) -> f64 {
    let u = u.clamp(0.0, 1.0);
    if u <= 0.0 {
        return 0.0;
    }
    let mean = gamma_decrement_for_store(params);
    let mut hi = mean.max(1e-12) * 4.0;
    while gamma_decrement_cdf(hi, params) < u && hi < 1e12 {
        hi *= 2.0;
    }
    let mut lo = 0.0;
    for _ in 0..80 {
        let mid = 0.5 * (lo + hi);
        if gamma_decrement_cdf(mid, params) < u {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}

/// Draw the daily decrement conditioned on `lo ≤ δ < hi` (fully adapted aging proposal).
///
/// Falls back to the interval floor when the conditioning event has no numerical mass.
pub fn draw_gamma_decrement_truncated<R: Rng + ?Sized>(
    rng: &mut R,
    params: &ModelParams,
    lo: f64,
    hi: f64,
) -> f64 {
    let c_lo = gamma_decrement_cdf(lo.max(0.0), params);
    let c_hi = if hi.is_infinite() {
        1.0
    } else {
        gamma_decrement_cdf(hi, params)
    };
    if !(c_hi > c_lo) {
        return lo.max(0.0);
    }
    let u = c_lo + rng.random::<f64>() * (c_hi - c_lo);
    let d = gamma_decrement_quantile(u, params);
    d.clamp(lo.max(0.0), if hi.is_infinite() { f64::MAX } else { hi })
}

/// Apply a fixed gamma decrement to alive slots; `f ≤ 0` marks spoil.
pub fn apply_gamma_decrement(freshness: &mut [f64], decrement: f64) {
    if decrement <= 0.0 {
        return;
    }
    for f in freshness.iter_mut() {
        if *f > 0.0 {
            *f = (*f - decrement).max(0.0);
        }
    }
}

/// Stochastic gamma aging step for unit freshness.
pub fn apply_gamma_aging<R: Rng + ?Sized>(
    freshness: &mut [f64],
    rng: &mut R,
    params: &ModelParams,
) {
    let decrement = draw_gamma_decrement(rng, params);
    apply_gamma_decrement(freshness, decrement);
}

/// Picking weights on freshness: `w_i ∝ max(f_i, 0)^σ`, normalized.
pub fn picking_weights_f(f: &[f64], sigma: f64, uniform: bool) -> Vec<f64> {
    let n = f.len();
    if n == 0 {
        return Vec::new();
    }
    if uniform || sigma <= 0.0 {
        return vec![1.0 / n as f64; n];
    }
    let mut raw: Vec<f64> = f.iter().map(|&fi| fi.max(0.0).powf(sigma)).collect();
    let total: f64 = raw.iter().sum();
    if total <= 0.0 {
        return vec![1.0 / n as f64; n];
    }
    for x in &mut raw {
        *x /= total;
    }
    raw
}

pub fn weibull_survival(tau: f64, beta: f64, eta: f64) -> f64 {
    if tau <= 0.0 {
        return 1.0;
    }
    if eta <= 0.0 {
        panic!("eta must be positive");
    }
    (-(tau / eta).powf(beta)).exp()
}

pub fn death_prob_survival_ratio(tau: f64, dtau: f64, beta: f64, eta: f64) -> f64 {
    if dtau <= 0.0 {
        return 0.0;
    }
    let s0 = weibull_survival(tau, beta, eta);
    if s0 <= 0.0 {
        return 1.0;
    }
    let s1 = weibull_survival(tau + dtau, beta, eta);
    1.0 - s1 / s0
}

pub fn death_prob_hazard_product(tau: f64, dtau: f64, beta: f64, eta: f64) -> f64 {
    if dtau <= 0.0 || tau < 0.0 {
        return 0.0;
    }
    if tau == 0.0 {
        if beta > 1.0 {
            return 0.0;
        }
        if beta < 1.0 {
            return 1.0;
        }
        return (1.0 / eta * dtau).clamp(0.0, 1.0);
    }
    let hazard = (beta / eta) * (tau / eta).powf(beta - 1.0);
    (hazard * dtau).clamp(0.0, 1.0)
}

pub fn q10_age_increment(dt_calendar: f64, t_store_c: f64, t_ref_c: f64, q10: f64) -> f64 {
    let factor = q10.powf((t_store_c - t_ref_c) / 10.0);
    dt_calendar * factor
}

pub fn picking_weights(taus: &[f64], sigma: f64, beta: f64, eta: f64, uniform: bool) -> Vec<f64> {
    let n = taus.len();
    if n == 0 {
        return Vec::new();
    }
    if uniform || sigma <= 0.0 {
        return vec![1.0 / n as f64; n];
    }
    let mut raw: Vec<f64> = taus
        .iter()
        .map(|&t| {
            weibull_survival(t, beta, eta)
                .max(SURV_FLOOR)
                .powf(1.0 / sigma)
        })
        .collect();
    let total: f64 = raw.iter().sum();
    if total <= 0.0 {
        return vec![1.0 / n as f64; n];
    }
    for x in &mut raw {
        *x /= total;
    }
    raw
}

/// Sequential without-replacement allocation (Wallenius simulation).
pub fn allocate_sales<R: Rng + ?Sized>(
    counts: &[u32],
    demand: u32,
    weights: &[f64],
    rng: &mut R,
) -> Vec<u32> {
    let n = counts.len();
    if weights.len() != n {
        panic!("weights must match cohort count");
    }
    let mut sales = vec![0u32; n];
    let mut remaining: Vec<u32> = counts.to_vec();
    let on_hand: u32 = remaining.iter().sum();
    let to_sell = demand.min(on_hand);
    for _ in 0..to_sell {
        let mut total = 0.0;
        for i in 0..n {
            if remaining[i] > 0 {
                total += weights[i];
            }
        }
        let use_uniform = total <= 0.0;
        if use_uniform {
            total = remaining.iter().filter(|&&c| c > 0).count() as f64;
        }
        if total <= 0.0 {
            break;
        }
        let draw: f64 = rng.random::<f64>() * total;
        let mut acc = 0.0;
        let mut idx = 0usize;
        for i in 0..n {
            if remaining[i] == 0 {
                continue;
            }
            let w = if use_uniform { 1.0 } else { weights[i] };
            acc += w;
            if draw < acc || i == n - 1 {
                idx = i;
                break;
            }
        }
        sales[idx] += 1;
        remaining[idx] -= 1;
    }
    sales
}

/// Negative binomial demand (numpy `negative_binomial(r, p)` failures-before-r-successes).
pub fn draw_demand<R: Rng + ?Sized>(rng: &mut R, params: &ModelParams, day: Option<u32>) -> u32 {
    let mu = if params.demand_profile.is_some() {
        params.demand_mu_for_day(day.unwrap_or(0))
    } else {
        params.demand_mu
    };
    draw_demand_from_mu(rng, mu, params.demand_vm)
}

fn draw_demand_from_mu<R: Rng + ?Sized>(rng: &mut R, mu: f64, demand_vm: f64) -> u32 {
    if demand_vm <= 1.0 {
        panic!("demand_vm must be > 1 for overdispersed NB");
    }
    let r = mu / (demand_vm - 1.0);
    let p = r / (r + mu);
    negative_binomial_gamma_poisson(rng, r, p)
}

/// Calendar/session demand draw using hierarchical `SpawnRng` streams.
pub fn draw_demand_spawn(rng: &mut SpawnRng, params: &ModelParams, day: Option<u32>) -> u32 {
    let mu = if params.demand_profile.is_some() {
        params.demand_mu_for_day(day.unwrap_or(0))
    } else {
        params.demand_mu
    };
    if params.demand_vm <= 1.0 {
        panic!("demand_vm must be > 1 for overdispersed NB");
    }
    let r = mu / (params.demand_vm - 1.0);
    let p = r / (r + mu);
    rng.negative_binomial(r, p)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    const ATOL: f64 = 1e-12;

    fn close(a: f64, b: f64) {
        assert!((a - b).abs() <= ATOL, "{a} vs {b}");
    }

    #[test]
    fn weibull_goldens() {
        close(weibull_survival(0.0, 2.0, 14.0), 1.0);
        close(weibull_survival(3.0, 2.0, 14.0), 0.955_119_927_982_107);
    }

    #[test]
    fn death_and_q10_goldens() {
        close(
            death_prob_survival_ratio(3.0, 1.0, 2.0, 14.0),
            0.035_084_055_627_629_95,
        );
        close(
            death_prob_hazard_product(3.0, 1.0, 2.0, 14.0),
            0.030_612_244_897_959_18,
        );
        close(
            q10_age_increment(1.0, 4.0, 0.0, 2.0),
            1.319_507_910_772_894_2,
        );
    }

    #[test]
    fn picking_weight_goldens() {
        let w = picking_weights(&[0.0, 3.0, 8.0], 1.0, 2.0, 14.0, false);
        close(w[0], 0.373_616_374_570_536_4);
        close(w[1], 0.356_848_444_772_746_7);
        close(w[2], 0.269_535_180_656_716_83);
        let s: f64 = w.iter().sum();
        close(s, 1.0);
    }

    #[test]
    fn allocate_sales_conserves() {
        let mut rng = Pcg64::seed_from_u64(1);
        let counts = [10u32, 5, 3];
        let w = picking_weights(&[0.0, 2.0, 5.0], 0.5, 2.0, 14.0, false);
        let sales = allocate_sales(&counts, 7, &w, &mut rng);
        assert_eq!(sales.iter().sum::<u32>(), 7);
        for i in 0..3 {
            assert!(sales[i] <= counts[i]);
        }
    }

    /// Mirrors `tests/test_model.py`.
    #[test]
    fn survival_ratio_diverges_from_hazard_at_beta4() {
        let tau = 8.0;
        let dtau = 2.0;
        let eta = 14.0;
        let beta = 4.0;
        let p_sr = death_prob_survival_ratio(tau, dtau, beta, eta);
        let p_h = death_prob_hazard_product(tau, dtau, beta, eta);
        assert!((p_sr - p_h).abs() > 0.02);
    }

    #[test]
    fn q10_one_day_at_4c() {
        let dtau = q10_age_increment(1.0, 4.0, 0.0, 3.0);
        let expected = 3.0_f64.powf(0.4);
        close(dtau, expected);
    }

    #[test]
    fn picking_weights_survival_power() {
        let w = picking_weights(&[1.0, 5.0, 10.0], 0.5, 2.0, 14.0, false);
        assert_eq!(w.len(), 3);
        close(w.iter().sum(), 1.0);
        assert!(w[0] > w[1] && w[1] > w[2]);
    }

    #[test]
    fn allocate_conserves_sales() {
        let mut rng = Pcg64::seed_from_u64(11);
        let counts = [20u32, 15, 10];
        let w = [0.5, 0.3, 0.2];
        let sales = allocate_sales(&counts, 40, &w, &mut rng);
        assert_eq!(sales.iter().sum::<u32>(), 40);
        for i in 0..3 {
            assert!(sales[i] <= counts[i]);
        }
    }

    #[test]
    fn beta1_death_is_memoryless() {
        let p0 = death_prob_survival_ratio(0.0, 1.0, 1.0, 14.0);
        let p5 = death_prob_survival_ratio(5.0, 1.0, 1.0, 14.0);
        close(p0, p5);
        let equal_s = picking_weights(&[3.0, 3.0, 3.0], 0.5, 1.0, 14.0, false);
        let uniform = picking_weights(&[3.0, 3.0, 3.0], 0.5, 1.0, 14.0, true);
        for i in 0..3 {
            close(equal_s[i], uniform[i]);
        }
    }

    #[test]
    fn demand_negative_binomial_mean_in_band() {
        let mut rng = Pcg64::seed_from_u64(99);
        let params = ModelParams::default();
        let mut acc = 0.0;
        let n = 2000u32;
        for _ in 0..n {
            acc += f64::from(draw_demand(&mut rng, &params, None));
        }
        let mean = acc / f64::from(n);
        assert!(mean > 20.0 && mean < 40.0, "mean={mean}");
    }

    #[test]
    fn session_stream_rng_calendar_mean_seed0() {
        use crate::demand_profile::DemandProfile;
        use crate::spawn_rng::SpawnRng;

        let profile =
            DemandProfile::from_json(include_str!("../../../data/freshnet/demand_profile.json"))
                .expect("embedded profile");
        let params_cal = ModelParams {
            demand_profile: Some(profile),
            ..ModelParams::default()
        };
        let params_flat = ModelParams::default();
        let mut sum_cal = 0u64;
        let mut sum_flat = 0u64;
        for day in 0..90u32 {
            let mut rng_cal = SpawnRng::spawn_rng(0, "session", day, ":demand");
            let mut rng_flat = SpawnRng::spawn_rng(0, "session", day, ":demand");
            sum_cal += u64::from(draw_demand_spawn(&mut rng_cal, &params_cal, Some(day)));
            sum_flat += u64::from(draw_demand_spawn(&mut rng_flat, &params_flat, None));
        }
        let mean_cal = f64::from(sum_cal as u32) / 90.0;
        let mean_flat = f64::from(sum_flat as u32) / 90.0;
        assert!(
            mean_cal > 20.0 && mean_cal < 40.0,
            "calendar mean {mean_cal} must fall in [20, 40]"
        );
        assert!(
            (mean_cal - mean_flat).abs() > 0.1,
            "calendar mean {mean_cal} must differ from flat baseline ({mean_flat})"
        );
    }

    #[test]
    fn draw_demand_profile_day7_mean_differs_from_flat_mu() {
        use crate::demand_profile::DemandProfile;

        let profile =
            DemandProfile::from_json(include_str!("../../../data/freshnet/demand_profile.json"))
                .expect("embedded profile");
        let flat_params = ModelParams::default();
        let profile_params = ModelParams {
            demand_profile: Some(profile),
            ..ModelParams::default()
        };
        let mut rng_flat = Pcg64::seed_from_u64(42);
        let mut rng_prof = Pcg64::seed_from_u64(42);
        let n = 10_000u32;
        let mut acc_flat = 0.0;
        let mut acc_prof = 0.0;
        for _ in 0..n {
            acc_flat += f64::from(draw_demand(&mut rng_flat, &flat_params, None));
            acc_prof += f64::from(draw_demand(&mut rng_prof, &profile_params, Some(7)));
        }
        let mean_flat = acc_flat / f64::from(n);
        let mean_prof = acc_prof / f64::from(n);
        assert!(
            (mean_prof - mean_flat).abs() > 1.0,
            "flat={mean_flat} profile_day7={mean_prof}"
        );
    }

    #[test]
    fn picking_empty_and_uniform_flag() {
        assert!(picking_weights(&[], 0.5, 2.0, 14.0, false).is_empty());
        let u = picking_weights(&[1.0, 2.0], 0.5, 2.0, 14.0, true);
        close(u[0], 0.5);
        close(u[1], 0.5);
    }

    #[test]
    fn picking_weights_f_monotone_normalized() {
        let w = picking_weights_f(&[0.2, 0.5, 0.9], 0.5, false);
        assert_eq!(w.len(), 3);
        close(w.iter().sum(), 1.0);
        assert!(w[0] < w[1] && w[1] < w[2]);
    }

    #[test]
    fn age_to_f_roundtrip() {
        close(age_to_f(0.0, 14.0), 1.0);
        close(age_to_f(14.0, 14.0), 0.0);
        close(f_to_age(0.75, 14.0), 3.5);
    }

    #[test]
    fn gamma_decrement_for_store_positive() {
        let params = ModelParams::default();
        let dec = gamma_decrement_for_store(&params);
        assert!(dec > 0.0);
        let mut f = vec![0.85, 0.0, 0.5];
        apply_gamma_decrement(&mut f, dec);
        assert!(f[0] < 0.85 && f[0] > 0.0);
        assert_eq!(f[1], 0.0);
        assert!(f[2] < 0.5);
    }
}
