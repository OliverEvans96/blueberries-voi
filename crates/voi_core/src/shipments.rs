//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use rand::Rng;

use crate::physics::{age_to_f, q10_age_increment};

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

/// Cumulative thermal exposure along a temperature path (reference-days).
pub fn arrival_exposure_from_path(
    temps_c: &[f64],
    times_d: &[f64],
    q10: f64,
    t_ref_c: f64,
) -> f64 {
    if temps_c.len() != times_d.len() || times_d.len() < 2 {
        panic!("temps_c and times_d must be same length >= 2");
    }
    let mut exposure = 0.0;
    for i in 0..times_d.len() - 1 {
        let dt = times_d[i + 1] - times_d[i];
        if dt <= 0.0 {
            continue;
        }
        let t_mid = 0.5 * (temps_c[i] + temps_c[i + 1]);
        exposure += q10_age_increment(dt, t_mid, t_ref_c, q10);
    }
    exposure
}

/// Legacy name retained for calibration-note / research callers.
pub fn arrival_age_from_path(temps_c: &[f64], times_d: &[f64], q10: f64, t_ref_c: f64) -> f64 {
    arrival_exposure_from_path(temps_c, times_d, q10, t_ref_c)
}

pub fn shipment_arrival_age(ship: &ShipmentTrace, q10: f64, t_ref_c: f64) -> f64 {
    arrival_exposure_from_path(&ship.temps_c, &ship.times_d, q10, t_ref_c)
}

/// Calendar transit duration (days), not Q10-warped exposure.
pub fn calendar_transit_days(trace: &ShipmentTrace) -> f64 {
    let t = &trace.times_d;
    if t.len() < 2 {
        return 0.0;
    }
    (t[t.len() - 1] - t[0]).max(0.0)
}

/// Duration-averaged Q10 factor Λ/d for a trace.
pub fn phi_bar_from_trace(trace: &ShipmentTrace, q10: f64, t_ref_c: f64) -> f64 {
    let d = calendar_transit_days(trace);
    if d <= 1e-12 {
        return 1.0;
    }
    shipment_arrival_age(trace, q10, t_ref_c) / d
}

/// Stochastic piecewise transit profile for truth deliveries and F3 events.
///
/// Builds a visibly non-flat temperature path whose duration-averaged φ̄ matches
/// `phi_bar_target` (the same scalar the filter conditions on via `resolve_arrival_exposure`).
pub fn truth_transit_trace<R: Rng + ?Sized>(
    duration_d: f64,
    phi_bar_target: f64,
    t_anchor: f64,
    temp_floor_c: f64,
    q10: f64,
    t_ref_c: f64,
    rng: &mut R,
) -> ShipmentTrace {
    const KNOTS: usize = 5;
    if duration_d <= 1e-9 {
        return ShipmentTrace {
            times_d: vec![0.0, 0.0],
            temps_c: vec![t_anchor, t_anchor],
        };
    }
    let times: Vec<f64> = (0..KNOTS)
        .map(|i| duration_d * i as f64 / (KNOTS - 1) as f64)
        .collect();
    let ramp_amp = 2.0;
    let mut shape: Vec<f64> = (0..KNOTS)
        .map(|i| {
            let frac = i as f64 / (KNOTS - 1) as f64;
            2.0 * (0.5 - frac)
        })
        .collect();
    for i in 1..KNOTS - 1 {
        shape[i] += (rng.random::<f64>() - 0.5) * 1.0;
    }
    let base_temps: Vec<f64> = shape
        .iter()
        .map(|&s| (t_anchor + ramp_amp * s).max(temp_floor_c))
        .collect();
    let target_phi = phi_bar_target.max(1e-12);
    let mut lo = -20.0;
    let mut hi = 20.0;
    let mut best_temps = base_temps.clone();
    for _ in 0..48 {
        let mid = 0.5 * (lo + hi);
        let trial_temps: Vec<f64> = base_temps
            .iter()
            .map(|t| (t + mid).max(temp_floor_c))
            .collect();
        let trial = ShipmentTrace {
            times_d: times.clone(),
            temps_c: trial_temps.clone(),
        };
        let phi = phi_bar_from_trace(&trial, q10, t_ref_c);
        if phi < target_phi {
            lo = mid;
        } else {
            hi = mid;
        }
        best_temps = trial_temps;
    }
    ShipmentTrace {
        times_d: times,
        temps_c: best_temps,
    }
}

/// φ̄ summaries for every trace in a fleet.
pub fn phi_bar_fleet(shipments: &[ShipmentTrace], q10: f64, t_ref_c: f64) -> Vec<f64> {
    shipments
        .iter()
        .map(|s| phi_bar_from_trace(s, q10, t_ref_c))
        .collect()
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

/// Ground-truth birth freshness for a shipment trace under legacy Weibull mapping.
pub fn truth_birth_from_trace(trace: &ShipmentTrace, eta_ref: f64, q10: f64, t_ref_c: f64) -> f64 {
    let exposure = shipment_arrival_age(trace, q10, t_ref_c);
    age_to_f(exposure, eta_ref)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::params::ModelParams;
    use crate::physics::q10_age_increment;

    #[test]
    fn smoke_cool_age_is_two_days_at_1c() {
        let s = ShipmentTrace::smoke_cool();
        let age = shipment_arrival_age(&s, 3.0, 0.0);
        let expected = 2.0 * q10_age_increment(1.0, 1.0, 0.0, 3.0);
        assert!((age - expected).abs() < 1e-12, "{age} vs {expected}");
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
        let f = super::truth_birth_from_trace(&trace, params.eta_ref, params.q10, params.t_ref_c);
        assert!(f > 0.0 && f <= 1.0, "f={f}");
    }

    #[test]
    fn calendar_transit_matches_duration() {
        let trace = ShipmentTrace::smoke_cool();
        let d = calendar_transit_days(&trace);
        assert!((d - 2.0).abs() < 1e-12, "smoke_cool calendar d={d}");
        let phi = phi_bar_from_trace(&trace, 3.0, 0.0);
        assert!(phi > 1.0, "1C q10 factor phi_bar={phi}");
    }

    #[test]
    fn truth_transit_trace_is_non_constant_and_matches_phi_bar() {
        use rand::SeedableRng;
        let mut rng = rand::rngs::StdRng::seed_from_u64(7);
        let duration_d = 5.5;
        let phi_target = 1.35;
        let trace = truth_transit_trace(
            duration_d,
            phi_target,
            2.0,
            -2.0,
            3.0,
            0.0,
            &mut rng,
        );
        assert_eq!(trace.times_d.len(), trace.temps_c.len());
        assert!(trace.times_d.len() >= 3);
        let min_t = trace.temps_c.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_t = trace.temps_c.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        assert!(
            (max_t - min_t).abs() > 0.05,
            "expected varying temps, got {:?}",
            trace.temps_c
        );
        let phi = phi_bar_from_trace(&trace, 3.0, 0.0);
        assert!(
            (phi - phi_target).abs() < 1e-3,
            "phi_bar {phi} vs target {phi_target}"
        );
    }
}
