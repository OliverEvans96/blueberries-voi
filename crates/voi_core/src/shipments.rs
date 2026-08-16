//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use rand::Rng;
use rand_distr::{Distribution, Normal};

use crate::physics::{age_to_f, q10_age_increment};
use crate::params::ModelParams;

#[derive(Clone, Debug)]
pub struct ShipmentTrace {
    pub times_d: Vec<f64>,
    pub temps_c: Vec<f64>,
}

impl ShipmentTrace {
    pub fn smoke_cool() -> Self {
        Self {
            times_d: vec![0.0, 1.0, 2.0],
            temps_c: vec![1.0, 1.0, 1.0],
        }
    }
}

pub fn arrival_age_from_path(temps_c: &[f64], times_d: &[f64], q10: f64, t_ref_c: f64) -> f64 {
    if temps_c.len() != times_d.len() || times_d.len() < 2 {
        panic!("temps_c and times_d must be same length >= 2");
    }
    let mut age = 0.0;
    for i in 0..times_d.len() - 1 {
        let dt = times_d[i + 1] - times_d[i];
        if dt <= 0.0 {
            continue;
        }
        let t_mid = 0.5 * (temps_c[i] + temps_c[i + 1]);
        age += q10_age_increment(dt, t_mid, t_ref_c, q10);
    }
    age
}

pub fn shipment_arrival_age(ship: &ShipmentTrace, q10: f64, t_ref_c: f64) -> f64 {
    arrival_age_from_path(&ship.temps_c, &ship.times_d, q10, t_ref_c)
}

/// Bootstrap a shipment then shrink toward the mean (τ days; legacy cohort path).
pub fn generate_arrival_tau<R: rand::Rng + ?Sized>(
    rng_ship: &mut R,
    rng_sensor: &mut R,
    shipments: &[ShipmentTrace],
    q10: f64,
    t_ref_c: f64,
    spread_scale: f64,
) -> f64 {
    if shipments.is_empty() {
        panic!("shipments must be non-empty");
    }
    let idx = rng_ship.random_range(0..shipments.len());
    let _: f64 = rng_sensor.random();
    let ages: Vec<f64> = shipments
        .iter()
        .map(|s| shipment_arrival_age(s, q10, t_ref_c))
        .collect();
    let mean: f64 = ages.iter().sum::<f64>() / ages.len() as f64;
    let age = ages[idx];
    mean + spread_scale * (age - mean)
}

/// Default arrival prior mapped to birth freshness `f ∈ [0, 1]`.
pub fn generate_arrival_age<R: rand::Rng + ?Sized>(
    rng_ship: &mut R,
    rng_sensor: &mut R,
    shipments: &[ShipmentTrace],
    q10: f64,
    t_ref_c: f64,
    spread_scale: f64,
    eta_ref: f64,
) -> f64 {
    let tau = generate_arrival_tau(
        rng_ship,
        rng_sensor,
        shipments,
        q10,
        t_ref_c,
        spread_scale,
    );
    age_to_f(tau, eta_ref)
}

/// F2: Dirac birth freshness from measured age at receipt (τ days).
pub fn birth_f_f2_dirac(age_at_receipt: f64, eta_ref: f64) -> f64 {
    age_to_f(age_at_receipt.max(0.0), eta_ref)
}

/// F2a: Gaussian draw on pack-date transit age (τ days) mapped to freshness.
pub fn birth_f_f2a_gaussian<R: Rng + ?Sized>(
    rng: &mut R,
    pack_age_mean: f64,
    eta_ref: f64,
    transit_sd: f64,
) -> f64 {
    let width = transit_sd.max(1e-9);
    let dist = Normal::new(pack_age_mean, width).expect("normal params");
    let age = dist.sample(rng).max(0.0);
    age_to_f(age, eta_ref)
}

/// Select birth freshness from arrival metadata (F2 / F2a / default shipments mix).
pub fn delivery_birth_f<R: Rng + ?Sized>(
    rng_ship: &mut R,
    rng_sensor: &mut R,
    shipments: &[ShipmentTrace],
    params: &ModelParams,
    spread_scale: f64,
    age_at_receipt: Option<f64>,
    pack_age_mean: Option<f64>,
) -> f64 {
    if let Some(age) = age_at_receipt {
        return birth_f_f2_dirac(age, params.eta_ref);
    }
    if let Some(mean) = pack_age_mean {
        return birth_f_f2a_gaussian(
            rng_sensor,
            mean,
            params.eta_ref,
            params.f2a_transit_uncertainty_sd,
        );
    }
    generate_arrival_age(
        rng_ship,
        rng_sensor,
        shipments,
        params.q10,
        params.t_ref_c,
        spread_scale,
        params.eta_ref,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::physics::q10_age_increment;

    #[test]
    fn smoke_cool_age_is_two_days_at_1c() {
        let s = ShipmentTrace::smoke_cool();
        let age = shipment_arrival_age(&s, 3.0, 0.0);
        let expected = 2.0 * q10_age_increment(1.0, 1.0, 0.0, 3.0);
        assert!((age - expected).abs() < 1e-12, "{age} vs {expected}");
    }

    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    #[test]
    fn empty_shipments_panic() {
        let result = std::panic::catch_unwind(|| {
            let mut a = Pcg64::seed_from_u64(0);
            let mut b = Pcg64::seed_from_u64(1);
            generate_arrival_tau(&mut a, &mut b, &[], 3.0, 0.0, 1.0);
        });
        assert!(result.is_err());
    }

    #[test]
    fn generate_arrival_age_maps_to_freshness() {
        let params = ModelParams::default();
        let shipments = [ShipmentTrace::smoke_cool()];
        let mut rng_ship = Pcg64::seed_from_u64(11);
        let mut rng_sensor = Pcg64::seed_from_u64(22);
        let birth_f = generate_arrival_age(
            &mut rng_ship,
            &mut rng_sensor,
            &shipments,
            params.q10,
            params.t_ref_c,
            1.0,
            params.eta_ref,
        );
        assert!(birth_f > 0.0 && birth_f <= 1.0, "birth f must lie in (0, 1]: {birth_f}");
    }

    #[test]
    fn f2_dirac_and_f2a_paths() {
        let params = ModelParams::default();
        let f2 = birth_f_f2_dirac(2.0, params.eta_ref);
        assert!((f2 - age_to_f(2.0, params.eta_ref)).abs() < 1e-12);
        let mut rng = Pcg64::seed_from_u64(7);
        let f2a = birth_f_f2a_gaussian(&mut rng, 3.0, params.eta_ref, 0.75);
        assert!(f2a >= 0.0 && f2a <= 1.0);
    }
}
