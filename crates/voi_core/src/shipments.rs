//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use rand::Rng;
use rand_distr::{Distribution, Gamma, Normal};

use crate::physics::{age_to_f, f_to_age, q10_age_increment};
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

/// Calendar transit duration (days), not Q10-warped age.
pub fn calendar_transit_days(trace: &ShipmentTrace) -> f64 {
    let t = &trace.times_d;
    if t.len() < 2 {
        return 0.0;
    }
    (t[t.len() - 1] - t[0]).max(0.0)
}

/// Duration-averaged Q10 factor Λ/d for a trace (ADR 0141 φ̄ prior).
pub fn phi_bar_from_trace(trace: &ShipmentTrace, q10: f64, t_ref_c: f64) -> f64 {
    let d = calendar_transit_days(trace);
    if d <= 1e-12 {
        return 1.0;
    }
    shipment_arrival_age(trace, q10, t_ref_c) / d
}

/// φ̄ summaries for every trace in a fleet.
pub fn phi_bar_fleet(shipments: &[ShipmentTrace], q10: f64, t_ref_c: f64) -> Vec<f64> {
    shipments
        .iter()
        .map(|s| phi_bar_from_trace(s, q10, t_ref_c))
        .collect()
}

/// Expected warped transit age E[age | Λ] under Gamma(kΛ, θ).
pub fn mean_age_from_lambda(lambda: f64, params: &ModelParams) -> f64 {
    params.gamma_shape * lambda * params.gamma_scale
}

/// One unit's transit age ~ Gamma(kΛ, θ) (ADR 0141).
pub fn draw_gamma_arrival_age<R: Rng + ?Sized>(
    rng: &mut R,
    lambda: f64,
    params: &ModelParams,
) -> f64 {
    let shape = (params.gamma_shape * lambda).max(1e-9);
    let dist = Gamma::new(shape, params.gamma_scale).expect("gamma arrival params");
    dist.sample(rng)
}

/// Per-unit birth freshness from unified gamma-in-warped-time model.
pub fn birth_f_units_gamma<R: Rng + ?Sized>(
    lambda: f64,
    n: usize,
    params: &ModelParams,
    rng: &mut R,
) -> Vec<f64> {
    (0..n)
        .map(|_| {
            age_to_f(
                draw_gamma_arrival_age(rng, lambda, params),
                params.eta_ref,
            )
        })
        .collect()
}

/// Bootstrap φ̄ from fleet for pack-date epistemic uncertainty.
pub fn sample_phi_bar_from_fleet<R: Rng + ?Sized>(
    rng: &mut R,
    shipments: &[ShipmentTrace],
    q10: f64,
    t_ref_c: f64,
) -> f64 {
    if shipments.is_empty() {
        panic!("shipments must be non-empty");
    }
    let idx = rng.random_range(0..shipments.len());
    phi_bar_from_trace(&shipments[idx], q10, t_ref_c)
}

/// Bootstrap a shipment then shrink toward the mean (τ days; private Q10 cache).
fn generate_arrival_tau<R: rand::Rng + ?Sized>(
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

/// Default arrival prior: birth freshness `f ∈ [0, 1]` from shipment mix.
pub fn generate_arrival_f<R: rand::Rng + ?Sized>(
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


/// Aleatoric within-lot birth spread on freshness `f` around lot mean.
///
/// `dispersion_sd = 0.0` returns `n` copies of `mean_f` (within `1e-12`).
/// For `dispersion_sd > 0`, draws truncated Normal on `f` in `(0, 1]`.
pub fn birth_f_units<R: Rng + ?Sized>(
    mean_f: f64,
    dispersion_sd: f64,
    n: usize,
    rng: &mut R,
) -> Vec<f64> {
    let center = mean_f.clamp(1e-12, 1.0);
    if dispersion_sd <= 0.0 {
        return vec![center; n];
    }
    let sd = dispersion_sd.max(1e-9);
    let dist = Normal::new(center, sd).expect("birth_f_units normal params");
    (0..n)
        .map(|_| {
            let mut f = dist.sample(rng);
            // truncate to (0, 1]
            if f <= 0.0 {
                f = 1e-12;
            } else if f > 1.0 {
                f = 1.0;
            }
            f
        })
        .collect()
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
    pack_age_mean: Option<f64>,
) -> f64 {
    if let Some(d) = pack_age_mean {
        let phi = sample_phi_bar_from_fleet(rng_sensor, shipments, params.q10, params.t_ref_c);
        let lambda = d.max(0.0) * phi;
        return age_to_f(mean_age_from_lambda(lambda, params), params.eta_ref);
    }
    generate_arrival_f(
        rng_ship,
        rng_sensor,
        shipments,
        params.q10,
        params.t_ref_c,
        spread_scale,
        params.eta_ref,
    )
}

/// Arrival metadata for wire + filter obs (physics birth uses shipments only).
pub fn arrival_receipt_meta<R: rand::Rng + ?Sized>(
    rng_ship: &mut R,
    rng_sensor: &mut R,
    shipments: &[ShipmentTrace],
    params: &ModelParams,
    spread_scale: f64,
) -> (f64, f64, i32) {
    let (f, tau, pack, _) = arrival_receipt_meta_with_trace(
        rng_ship,
        rng_sensor,
        shipments,
        params,
        spread_scale,
    );
    (f, tau, pack)
}

/// Teaching durations (days at 1 °C) calibrated to MOD-21 ages at q10=3, t_ref=0 °C (S1…S6).
const MOD21_DEMO_DURATIONS_D: [f64; 6] = [5.434, 2.194, 7.582, 6.865, 7.504, 5.405];

fn mod21_demo_trace(duration_d: f64) -> ShipmentTrace {
    ShipmentTrace {
        times_d: vec![0.0, duration_d],
        temps_c: vec![1.0, 1.0],
    }
}

/// Embedded Abdella MOD-21 demo traces for WASM / offline paths (no parquet).
pub fn mod21_demo_shipments(product: &str) -> Vec<ShipmentTrace> {
    match product {
        "short_haul" => vec![mod21_demo_trace(MOD21_DEMO_DURATIONS_D[1])],
        "long_haul" => MOD21_DEMO_DURATIONS_D
            .iter()
            .enumerate()
            .filter(|(i, _)| *i != 1)
            .map(|(_, &d)| mod21_demo_trace(d))
            .collect(),
        _ => MOD21_DEMO_DURATIONS_D
            .iter()
            .map(|&d| mod21_demo_trace(d))
            .collect(),
    }
}

/// Ground-truth birth freshness for a shipment trace under `params`.
pub fn truth_birth_from_trace(trace: &ShipmentTrace, params: &ModelParams) -> f64 {
    let age = shipment_arrival_age(trace, params.q10, params.t_ref_c);
    age_to_f(age, params.eta_ref)
}

/// Same as [`arrival_receipt_meta`] but returns the sampled shipment trace for obs wire.
pub fn arrival_receipt_meta_with_trace<R: rand::Rng + ?Sized>(
    rng_ship: &mut R,
    rng_sensor: &mut R,
    shipments: &[ShipmentTrace],
    params: &ModelParams,
    spread_scale: f64,
) -> (f64, f64, i32, ShipmentTrace) {
    if shipments.is_empty() {
        panic!("shipments must be non-empty");
    }
    let idx = rng_ship.random_range(0..shipments.len());
    let trace = shipments[idx].clone();
    let _: f64 = rng_sensor.random();
    let lambda = shipment_arrival_age(&trace, params.q10, params.t_ref_c);
    let tau = lambda;
    let pack = calendar_transit_days(&trace).round() as i32;
    let f = age_to_f(mean_age_from_lambda(lambda, params), params.eta_ref);
    (f, tau, pack, trace)
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
            generate_arrival_f(&mut a, &mut b, &[], 3.0, 0.0, 1.0, 14.0);
        });
        assert!(result.is_err());
    }

    #[test]
    fn generate_arrival_f_maps_to_unit_interval() {
        let params = ModelParams::default();
        let shipments = [ShipmentTrace::smoke_cool()];
        let mut rng_ship = Pcg64::seed_from_u64(11);
        let mut rng_sensor = Pcg64::seed_from_u64(22);
        let birth_f = generate_arrival_f(
            &mut rng_ship,
            &mut rng_sensor,
            &shipments,
            params.q10,
            params.t_ref_c,
            1.0,
            params.eta_ref,
        );
        assert!(
            birth_f > 0.0 && birth_f <= 1.0,
            "birth f must lie in (0, 1]: {birth_f}"
        );
    }

    #[test]
    fn f2a_path() {
        let params = ModelParams::default();
        let mut rng = Pcg64::seed_from_u64(7);
        let f2a = birth_f_f2a_gaussian(&mut rng, 3.0, params.eta_ref, 0.75);
        assert!(f2a >= 0.0 && f2a <= 1.0);
    }


    #[test]
    fn mod21_demo_shipments_product_mix() {
        assert_eq!(super::mod21_demo_shipments("abdella_all").len(), 6);
        assert_eq!(super::mod21_demo_shipments("long_haul").len(), 5);
        assert_eq!(super::mod21_demo_shipments("short_haul").len(), 1);
    }

    #[test]
    fn truth_birth_from_trace_in_unit_interval() {
        let params = ModelParams::default();
        let trace = super::mod21_demo_shipments("short_haul")[0].clone();
        let f = super::truth_birth_from_trace(&trace, &params);
        assert!(f > 0.0 && f <= 1.0, "f={f}");
    }
}
