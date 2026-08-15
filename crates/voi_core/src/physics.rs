//! Weibull / Q10 / picking / sequential allocation (Python `model.physics`).

use rand::Rng;
use rand_distr::{Distribution, Gamma, Poisson};

const SURV_FLOOR: f64 = 1e-300;

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
pub fn draw_demand<R: Rng + ?Sized>(rng: &mut R, mu: f64, demand_vm: f64) -> u32 {
    if demand_vm <= 1.0 {
        panic!("demand_vm must be > 1 for overdispersed NB");
    }
    let r = mu / (demand_vm - 1.0);
    let p = r / (r + mu);
    // Gamma-Poisson mixture ≡ NB (numpy Generator.negative_binomial).
    let scale = (1.0 - p) / p;
    let gamma = Gamma::new(r, scale).expect("gamma");
    let lam = gamma.sample(rng);
    if lam <= 0.0 {
        return 0;
    }
    let pois = Poisson::new(lam).expect("poisson");
    pois.sample(rng) as u32
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
        let mut acc = 0.0;
        let n = 2000u32;
        for _ in 0..n {
            acc += f64::from(draw_demand(&mut rng, 30.0, 2.0));
        }
        let mean = acc / f64::from(n);
        assert!(mean > 20.0 && mean < 40.0, "mean={mean}");
    }

    #[test]
    fn picking_empty_and_uniform_flag() {
        assert!(picking_weights(&[], 0.5, 2.0, 14.0, false).is_empty());
        let u = picking_weights(&[1.0, 2.0], 0.5, 2.0, 14.0, true);
        close(u[0], 0.5);
        close(u[1], 0.5);
    }
}
