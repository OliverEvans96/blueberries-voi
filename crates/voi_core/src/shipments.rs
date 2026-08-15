//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use crate::physics::q10_age_increment;

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

/// Bootstrap a shipment then shrink toward the mean (`generate_arrival_age`).
pub fn generate_arrival_age<R: rand::Rng + ?Sized>(
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
            generate_arrival_age(&mut a, &mut b, &[], 3.0, 0.0, 1.0);
        });
        assert!(result.is_err());
    }
}
