//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use crate::physics::{age_to_f, q10_age_increment};

/// A shipment's recorded temperature history: elapsed-time / temperature sample pairs fed
/// into Q10 thermal-exposure integration for the arrival model.
#[derive(Clone, Debug)]
pub struct ShipmentTrace {
    /// Elapsed time since shipment start, in days, index-paired with `temps_c`.
    pub times_d: Vec<f64>,
    /// Temperature in °C at each sample time.
    pub temps_c: Vec<f64>,
}

impl ShipmentTrace {
    /// A two-day trace at a constant 1 °C -- a cool, uneventful transit used as a smoke-test fixture.
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

/// Cumulative thermal exposure for a shipment's full recorded trace.
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
}
