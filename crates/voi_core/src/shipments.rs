//! Injected shipment traces (no parquet). Python `ShipmentTrace` numeric path.

use rand::Rng;
use rand_distr::{Distribution, StandardNormal};

use crate::arrival::ArrivalModel;
use crate::physics::{age_to_f, q10_age_increment};

/// One hour in days — OU correlation time and trace sampling step.
const TRACE_HOUR_D: f64 = 1.0 / 24.0;
/// OU correlation time (1 hour) in days.
const OU_TAU_D: f64 = 1.0 / 24.0;

fn normal_sample<R: Rng + ?Sized>(rng: &mut R) -> f64 {
    StandardNormal.sample(rng)
}

fn ou_evolve<R: Rng + ?Sized>(state: &mut f64, dt_d: f64, sigma_hour: f64, rng: &mut R) {
    if dt_d <= 1e-12 || sigma_hour <= 0.0 {
        return;
    }
    let phi = (-dt_d / OU_TAU_D).exp();
    let innov = sigma_hour * (1.0 - phi * phi).max(0.0).sqrt();
    *state = phi * *state + innov * normal_sample(rng);
}

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
pub fn arrival_exposure_from_path(temps_c: &[f64], times_d: &[f64], q10: f64, t_ref_c: f64) -> f64 {
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

/// Generate one trip's temperature history: bottom-up stage durations, trip-wide thermal
/// mode, hourly OU noise, and cold-chain break pulses inside calendar `duration_d`.
///
/// This is the *generative primitive* of the arrival model. The path is built first and
/// the exposure Λ is integrated back out of it (see `ArrivalModel::draw_transit`), rather
/// than a decorative path being fitted to a scalar φ̄ that was already drawn.
pub fn truth_transit_trace<R: Rng + ?Sized>(
    duration_d: f64,
    model: &ArrivalModel,
    temp_bias_c: f64,
    rng: &mut R,
) -> ShipmentTrace {
    truth_transit_trace_for_corridor(
        duration_d,
        model,
        model.default_corridor.as_str(),
        temp_bias_c,
        rng,
    )
}

/// Like [`truth_transit_trace`] but uses the named corridor's gamma parameters for stage
/// decomposition.
pub fn truth_transit_trace_for_corridor<R: Rng + ?Sized>(
    duration_d: f64,
    model: &ArrivalModel,
    corridor_key: &str,
    temp_bias_c: f64,
    rng: &mut R,
) -> ShipmentTrace {
    let corridor = model.corridor(corridor_key);
    let stage_d = model.decompose_stages_for_duration(corridor, duration_d, rng);
    let mode_offset = model.draw_thermal_mode_offset(rng);

    if duration_d <= 1e-9 {
        let t0 = model
            .legs
            .first()
            .map_or(0.0, |l| l.setpoint_c + mode_offset + temp_bias_c);
        return ShipmentTrace {
            times_d: vec![0.0, 0.0],
            temps_c: vec![t0, t0],
        };
    }

    let mut stage_ends = Vec::with_capacity(stage_d.len());
    let mut acc = 0.0;
    for &dk in &stage_d {
        acc += dk;
        stage_ends.push(acc.min(duration_d));
    }
    if let Some(last) = stage_ends.last_mut() {
        *last = duration_d;
    }

    let stage_index_at = |t: f64| -> usize {
        for (i, &end) in stage_ends.iter().enumerate() {
            if t < end + 1e-12 {
                return i;
            }
        }
        stage_ends.len().saturating_sub(1)
    };

    let setpoint_at = |t: f64| -> f64 {
        let i = stage_index_at(t);
        model.legs[i].setpoint_c + mode_offset + temp_bias_c
    };

    // Break pulses as [start, end) intervals inside calendar d, merged for exposure.
    let taus = model.draw_break_taus(duration_d, rng);
    let mut pulses: Vec<(f64, f64)> = Vec::with_capacity(taus.len());
    for tau in taus {
        if tau <= 0.0 {
            continue;
        }
        let start = rng.random::<f64>() * (duration_d - tau).max(0.0);
        pulses.push((start, (start + tau).min(duration_d)));
    }
    pulses.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
    let mut merged: Vec<(f64, f64)> = Vec::with_capacity(pulses.len());
    for (start, end) in pulses {
        match merged.last_mut() {
            Some(last) if start <= last.1 => last.1 = last.1.max(end),
            _ => merged.push((start, end)),
        }
    }

    let in_pulse = |t: f64| merged.iter().any(|&(s, e)| t >= s - 1e-12 && t < e - 1e-12);

    // Hourly grid plus stage and break edges for exact trapezoid integration.
    let mut sample_times = vec![0.0, duration_d];
    let mut t = 0.0;
    while t < duration_d - 1e-12 {
        t = (t + TRACE_HOUR_D).min(duration_d);
        sample_times.push(t);
    }
    for &end in &stage_ends {
        if end > 0.0 && end < duration_d {
            sample_times.push(end);
        }
    }
    for &(start, end) in &merged {
        sample_times.push(start);
        sample_times.push(end);
    }
    sample_times.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    sample_times.dedup_by(|a, b| (*a - *b).abs() < 1e-12);

    let mut ou_state = 0.0;
    let mut temps: Vec<f64> = Vec::with_capacity(sample_times.len());
    let mut prev_stage = stage_index_at(sample_times[0]);
    for (i, &tt) in sample_times.iter().enumerate() {
        let stage = stage_index_at(tt);
        if stage != prev_stage {
            ou_state = 0.0;
            prev_stage = stage;
        }
        if i > 0 {
            // Hourly OU on line haul and dock only — precool stays flat so stage-boundary
            // timing is visible in traces (v2 chart + S1.1 share-variance guard).
            if stage > 0 && model.sigma_hour > 0.0 {
                ou_evolve(
                    &mut ou_state,
                    sample_times[i] - sample_times[i - 1],
                    model.sigma_hour,
                    rng,
                );
            }
        }
        let baseline = setpoint_at(tt);
        let temp = if in_pulse(tt) {
            model.t_break + temp_bias_c
        } else if stage > 0 {
            baseline + ou_state
        } else {
            baseline
        };
        temps.push(temp);
    }

    let mut times_d = Vec::with_capacity(sample_times.len() * 2);
    let mut temps_c = Vec::with_capacity(sample_times.len() * 2);
    for i in 0..sample_times.len().saturating_sub(1) {
        let lo = sample_times[i];
        let hi = sample_times[i + 1];
        if hi - lo <= 1e-12 {
            continue;
        }
        let temp = temps[i];
        times_d.push(lo);
        temps_c.push(temp);
        times_d.push(hi);
        temps_c.push(temp);
    }
    if times_d.len() < 2 {
        let t0 = setpoint_at(0.0);
        return ShipmentTrace {
            times_d: vec![0.0, duration_d],
            temps_c: vec![t0, t0],
        };
    }
    ShipmentTrace { times_d, temps_c }
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

    /// The legged baseline must produce a visibly stepped, non-constant path spanning
    /// exactly the trip duration. (Replaces the pre-break-model assertion that a
    /// fabricated trace matched a pre-drawn φ̄ by bisection — the trace is now the
    /// primitive, so there is no target to match.)
    #[test]
    fn truth_transit_trace_is_stepped_and_spans_duration() {
        use rand::SeedableRng;
        let mut model = crate::arrival::ArrivalModel::embedded();
        model.set_break_rate(0.0);
        let mut rng = rand::rngs::StdRng::seed_from_u64(7);
        let duration_d = 5.5;
        let trace = truth_transit_trace(duration_d, &model, 0.0, &mut rng);

        assert_eq!(trace.times_d.len(), trace.temps_c.len());
        assert!(
            (calendar_transit_days(&trace) - duration_d).abs() < 1e-9,
            "trace must span exactly the trip duration"
        );
        let min_t = trace.temps_c.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_t = trace
            .temps_c
            .iter()
            .cloned()
            .fold(f64::NEG_INFINITY, f64::max);
        assert!(
            (max_t - min_t).abs() > 0.05,
            "expected a stepped path across legs, got {:?}",
            trace.temps_c
        );
    }

    /// Trapezoidal Q10 integration of the generated path must be self-consistent with
    /// `resolve_arrival_exposure` — the trace is the primitive under v2.
    #[test]
    fn break_free_trace_integrates_consistently() {
        use crate::arrival::resolve_arrival_exposure;
        use rand::SeedableRng;
        let mut model = crate::arrival::ArrivalModel::embedded();
        model.set_break_rate(0.0);
        let mut rng = rand::rngs::StdRng::seed_from_u64(11);
        let duration_d = 4.25;
        let trace = truth_transit_trace(duration_d, &model, 0.0, &mut rng);
        let integrated = shipment_arrival_age(&trace, model.q10, model.t_ref);
        let from_resolve = resolve_arrival_exposure(
            Some(&trace.temps_c),
            Some(&trace.times_d),
            model.q10,
            model.t_ref,
        )
        .expect("trace integrates");
        assert!(
            (integrated - from_resolve).abs() < 1e-9,
            "integrated Λ={integrated} vs resolve {from_resolve}"
        );
    }
}
