//! T-163 Stage 1 — transit generative v2 (bottom-up durations, trip mode, hourly OU).
//!
//! Authority: `.team/plans/arrival-transit-generative-v2.md` §1–§2; `.team/specs/T-163.md` S1.1,
//! S1.2, S1.4, S1.14, S1.16.

use rand::SeedableRng;
use rand_pcg::Pcg64;

use voi_core::arrival::{resolve_arrival_exposure, ArrivalModel};
use voi_core::shipments::{calendar_transit_days, phi_bar_from_trace, truth_transit_trace};

const ABDELLA_VAR_LOG_D: f64 = 0.205;
const VAR_LOG_D_TOL: f64 = 0.02;
const MC_SAMPLES: usize = 4_000;

fn model() -> ArrivalModel {
    ArrivalModel::embedded()
}

fn model_rho_zero() -> ArrivalModel {
    let mut m = model();
    m.set_break_rate(0.0);
    m
}

fn empirical_var_log(samples: &[f64]) -> f64 {
    let logs: Vec<f64> = samples.iter().map(|d| d.ln()).collect();
    let n = logs.len() as f64;
    let mean = logs.iter().sum::<f64>() / n;
    logs.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n
}

/// First leg end time / total duration — under v2 bottom-up draws this share is random.
fn first_stage_share(trace: &voi_core::shipments::ShipmentTrace) -> f64 {
    let d = calendar_transit_days(trace);
    assert!(d > 1e-6, "need positive duration");
    let t0 = trace.temps_c.first().copied().unwrap_or(0.0);
    let mut first_change = d;
    for (t, temp) in trace.times_d.iter().zip(trace.temps_c.iter()) {
        if *t <= 1e-9 {
            continue;
        }
        if (*temp - t0).abs() > 0.05 {
            first_change = *t;
            break;
        }
    }
    first_change / d
}

/// Temperature range on the line-haul segment (nominal share band 15%–75% of calendar d).
fn line_haul_temp_spread(trace: &voi_core::shipments::ShipmentTrace, d: f64) -> f64 {
    let lo = 0.15 * d + 1e-6;
    let hi = 0.75 * d - 1e-6;
    let mut temps = Vec::new();
    for (t, temp) in trace.times_d.iter().zip(trace.temps_c.iter()) {
        if *t >= lo && *t <= hi {
            temps.push(*temp);
        }
    }
    if temps.len() < 2 {
        return 0.0;
    }
    let min_t = temps.iter().cloned().fold(f64::INFINITY, f64::min);
    let max_t = temps.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    max_t - min_t
}

/// S1.1 — bottom-up stage draws yield pooled Abdella `d_min + Gamma(a, b)` marginal.
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn abdella_marginal_d_matches_pooled_gamma() {
    let m = model_rho_zero();
    let corridor = m.corridor("abdella_all");

    let mut durations = Vec::with_capacity(MC_SAMPLES);
    for i in 0..MC_SAMPLES {
        let mut rd = Pcg64::seed_from_u64(163_010 + i as u64);
        let mut rt = Pcg64::seed_from_u64(163_110 + i as u64);
        let mut rp = Pcg64::seed_from_u64(163_210 + i as u64);
        let mut rg = Pcg64::seed_from_u64(163_310 + i as u64);
        let mut rr = Pcg64::seed_from_u64(163_410 + i as u64);
        let draw = m.draw_truth_delivery("abdella_all", 1, &mut rd, &mut rt, &mut rp, &mut rg, &mut rr);
        durations.push(draw.duration_d);
    }

    let n = durations.len() as f64;
    let sample_mean = durations.iter().sum::<f64>() / n;
    let sample_var = durations.iter().map(|d| (d - sample_mean).powi(2)).sum::<f64>() / n;

    let theory_mean = corridor.d_min + corridor.delay_shape * corridor.delay_scale;
    let theory_var = corridor.delay_shape * corridor.delay_scale.powi(2);

    assert!(
        (sample_mean - theory_mean).abs() < 0.08,
        "mean d: sample={sample_mean} theory={theory_mean}"
    );
    assert!(
        (sample_var - theory_var).abs() < 0.12,
        "var d: sample={sample_var} theory={theory_var}"
    );

    // Bottom-up construction: at fixed calendar d, stage shares must vary (not fixed 0.15).
    let mut shares = Vec::with_capacity(60);
    for seed in 0..60u64 {
        let mut rng = Pcg64::seed_from_u64(163_002 + seed);
        let d = 5.0;
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        shares.push(first_stage_share(&trace));
    }
    let mean_share = shares.iter().sum::<f64>() / shares.len() as f64;
    let var_share = shares
        .iter()
        .map(|s| (s - mean_share).powi(2))
        .sum::<f64>()
        / shares.len() as f64;
    assert!(
        var_share > 1e-4,
        "v2 bottom-up stage shares must vary at fixed d (var={var_share}); fixed legs keep share at 0.15"
    );
}

/// S1.2 — at ρ=0, `Var(log d)` matches the six-shipment Abdella target (~0.205).
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn var_log_d_matches_abdella() {
    let m = model_rho_zero();
    let mut durations = Vec::with_capacity(MC_SAMPLES);
    for i in 0..MC_SAMPLES {
        let mut rd = Pcg64::seed_from_u64(163_020 + i as u64);
        let mut rt = Pcg64::seed_from_u64(163_120 + i as u64);
        let mut rp = Pcg64::seed_from_u64(163_220 + i as u64);
        let mut rg = Pcg64::seed_from_u64(163_320 + i as u64);
        let mut rr = Pcg64::seed_from_u64(163_420 + i as u64);
        let draw = m.draw_truth_delivery("abdella_all", 1, &mut rd, &mut rt, &mut rp, &mut rg, &mut rr);
        durations.push(draw.duration_d);
    }
    let var_log_d = empirical_var_log(&durations);
    assert!(
        (var_log_d - ABDELLA_VAR_LOG_D).abs() <= VAR_LOG_D_TOL,
        "Var(log d)={var_log_d} not within ±{VAR_LOG_D_TOL} of {ABDELLA_VAR_LOG_D}"
    );
}

/// Leaf corridors must resample empirical durations from their own provenance pool, not the
/// unconditional six-shipment mix (otherwise `resolve_corridor_regime` only controls ~22% of draws).
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn empirical_duration_respects_resolved_regime() {
    let m = model_rho_zero();
    let n = 2_000usize;
    let mut short = Vec::with_capacity(n);
    let mut long = Vec::with_capacity(n);
    for i in 0..n {
        let mut rng = Pcg64::seed_from_u64(163_025 + i as u64);
        short.push(m.draw_bottom_up_duration("short_haul", &mut rng));
        long.push(m.draw_bottom_up_duration("long_haul", &mut rng));
    }
    let short_frac_long = short.iter().filter(|&&d| d > 4.0).count() as f64 / n as f64;
    let long_frac_short = long.iter().filter(|&&d| d < 3.5).count() as f64 / n as f64;
    assert!(
        short_frac_long < 0.12,
        "short_haul empirical pool is S2 only; >4d draws should be rare, got {short_frac_long:.3}"
    );
    assert!(
        long_frac_short < 0.12,
        "long_haul empirical pool is S1,S3–S6; <3.5d draws should be rare, got {long_frac_short:.3}"
    );
}

/// S1.4 — hourly OU wiggle on the path even when ρ=0 (not flat within a stage).
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn rho_zero_trace_has_hourly_ou_variation() {
    let m = model_rho_zero();
    let mut rng = Pcg64::seed_from_u64(163_004);
    let d = 5.5;
    let mut saw_wiggle = false;
    for _ in 0..30 {
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        let spread = line_haul_temp_spread(&trace, d);
        if spread > 0.02 {
            saw_wiggle = true;
            break;
        }
    }
    assert!(
        saw_wiggle,
        "ρ=0 traces must show hourly OU variation within a stage, not piecewise-flat setpoints"
    );
}

/// S1.14 — breaks are periods *inside* calendar duration `d`, never extensions of the trip.
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn breaks_clamped_inside_calendar_duration() {
    let m = model();
    assert!(m.rho > 0.0, "need default break hazard");
    let mut rng = Pcg64::seed_from_u64(163_005);
    let d = 6.0;
    for _ in 0..80 {
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        let calendar = calendar_transit_days(&trace);
        assert!(
            (calendar - d).abs() < 1e-9,
            "calendar duration {calendar} must equal trip d={d} (breaks inside, not additive)"
        );
        let max_time = trace.times_d.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        assert!(
            max_time <= d + 1e-9,
            "trace must not run past calendar d={d}, got max_time={max_time}"
        );
    }

    for seed in 0..40u64 {
        let mut rd = Pcg64::seed_from_u64(10_000 + seed);
        let mut rt = Pcg64::seed_from_u64(20_000 + seed);
        let mut rp = Pcg64::seed_from_u64(30_000 + seed);
        let mut rg = Pcg64::seed_from_u64(40_000 + seed);
        let mut rr = Pcg64::seed_from_u64(50_000 + seed);
        let draw = m.draw_truth_delivery("abdella_all", 1, &mut rd, &mut rt, &mut rp, &mut rg, &mut rr);
        let calendar = calendar_transit_days(&draw.trace);
        assert!(
            (calendar - draw.duration_d).abs() < 1e-6,
            "delivery trace calendar {calendar} must match drawn duration_d={}",
            draw.duration_d
        );
    }
}

/// S1.16 — at ρ=0, trip mode + OU still scatter exposure; not deterministic `d·φ_set`.
#[test]
#[ignore = "T-163 v2 generative MC; slow: run via cargo test -- --ignored"]
fn rho_zero_exposure_varies_across_draws() {
    let m = model_rho_zero();
    let mut rng = Pcg64::seed_from_u64(163_006);
    let d = 4.25;
    let mut exposures = Vec::new();
    for _ in 0..25 {
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        let lambda = resolve_arrival_exposure(
            Some(&trace.temps_c),
            Some(&trace.times_d),
            m.q10,
            m.t_ref,
        )
        .expect("trace integrates");
        exposures.push(lambda);
    }
    let mean = exposures.iter().sum::<f64>() / exposures.len() as f64;
    let var = exposures
        .iter()
        .map(|x| (x - mean).powi(2))
        .sum::<f64>()
        / exposures.len() as f64;
    assert!(
        var > 1e-4,
        "ρ=0 exposure must vary across draws (modes + OU); got var={var}, samples={exposures:?}"
    );

    let mut phi_bars = Vec::with_capacity(25);
    for _ in 0..25 {
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        phi_bars.push(phi_bar_from_trace(&trace, m.q10, m.t_ref));
    }
    let phi_spread = phi_bars.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
        - phi_bars.iter().cloned().fold(f64::INFINITY, f64::min);
    let closed_phi = m.lambda_from_breaks(d, &[]) / d;
    assert!(
        phi_spread > 0.01,
        "φ̄ must scatter at ρ=0; spread={phi_spread}, closed-form φ_set={closed_phi}"
    );
}
