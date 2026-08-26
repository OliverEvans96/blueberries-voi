//! Cold-chain break model (compound-Poisson excursions on a legged baseline).
//!
//! Replaces the truncated-normal mean-transit-temperature draw. The trace is now the
//! generative primitive: breaks are punched into a deterministic legged baseline and Λ is
//! integrated back out of the resulting path, rather than a path being fitted to a
//! pre-drawn φ̄.

use rand::SeedableRng;
use rand_pcg::Pcg64;

use voi_core::arrival::{resolve_arrival_exposure, ArrivalCondition, ArrivalModel};
use voi_core::shipments::{calendar_transit_days, truth_transit_trace};

fn model() -> ArrivalModel {
    ArrivalModel::embedded()
}

/// The artifact no longer carries a truncated-normal transit temperature.
#[test]
fn artifact_drops_truncated_normal_fields() {
    let json: serde_json::Value =
        serde_json::from_str(voi_core::arrival::embedded_arrival_model()).expect("artifact json");
    for gone in ["mu_T", "sigma_T", "temp_floor_c"] {
        assert!(
            json.get(gone).is_none(),
            "artifact must not still carry {gone}"
        );
    }
    for want in ["legs", "T_break", "rho", "tau_bar"] {
        assert!(
            json.get(want).is_some(),
            "artifact must carry break-model field {want}"
        );
    }
}

/// φ_set is the duration-weighted Q10 factor of the deterministic legs, so a break-free
/// trip has exposure exactly `d · φ_set` — no stochastic thermal wobble at all.
#[test]
fn break_free_trip_has_deterministic_exposure() {
    let m = model();
    let d = 5.0;
    let lambda = m.lambda_from_breaks(d, &[]);
    let expected = d * m.phi_set();
    assert!(
        (lambda - expected).abs() < 1e-9,
        "break-free Λ={lambda} must equal d·φ_set={expected}"
    );
}

/// The additive form `Λ = d·φ_set + Σ ε_j` is exact, not an approximation: the trip clock
/// runs during a break, so the baseline is credited only for `d − Στ`.
#[test]
fn break_exposure_is_exactly_additive() {
    let m = model();
    let d = 6.0;
    let taus = [0.4_f64, 0.9];
    let lambda = m.lambda_from_breaks(d, &taus);

    let phi_set = m.phi_set();
    let phi_break = m.phi_break();
    let tau_sum: f64 = taus.iter().sum();
    let long_form = (d - tau_sum) * phi_set + tau_sum * phi_break;
    let additive = d * phi_set + tau_sum * (phi_break - phi_set);

    assert!(
        (lambda - long_form).abs() < 1e-9,
        "Λ={lambda} vs long form {long_form}"
    );
    assert!(
        (lambda - additive).abs() < 1e-9,
        "Λ={lambda} vs additive form {additive}"
    );
}

/// A break strictly increases exposure — that is the whole point of the channel.
#[test]
fn breaks_increase_exposure_monotonically() {
    let m = model();
    let d = 5.0;
    let none = m.lambda_from_breaks(d, &[]);
    let one = m.lambda_from_breaks(d, &[0.5]);
    let two = m.lambda_from_breaks(d, &[0.5, 0.5]);
    assert!(none < one && one < two, "{none} < {one} < {two}");
}

/// The trace is the primitive: integrating the generated path back through the Q10
/// kernel must reproduce the Λ the draw reports, to trapezoid accuracy.
#[test]
fn trace_integrates_back_to_reported_lambda() {
    let m = model();
    let mut checked = 0;
    for seed in 0..40u64 {
        let mut rd = Pcg64::seed_from_u64(1_000 + seed);
        let mut rt = Pcg64::seed_from_u64(2_000 + seed);
        let mut rp = Pcg64::seed_from_u64(3_000 + seed);
        let mut rg = Pcg64::seed_from_u64(4_000 + seed);
        let draw = m.draw_truth_delivery("abdella_all", 4, &mut rd, &mut rt, &mut rp, &mut rg);
        let lambda_from_trace = resolve_arrival_exposure(
            Some(&draw.trace.temps_c),
            Some(&draw.trace.times_d),
            m.q10,
            m.t_ref,
        )
        .expect("trace integrates");
        let reported = draw.lambda;
        assert!(
            (lambda_from_trace - reported).abs() < 1e-3 * reported.max(1.0),
            "seed {seed}: trace Λ={lambda_from_trace} vs reported Λ={reported}",
        );
        checked += 1;
    }
    assert_eq!(checked, 40);
}

/// Break pulses must be visible as warm excursions above the legged baseline, and the
/// trace must never run past the trip duration.
#[test]
fn trace_shows_break_pulses_within_duration() {
    let m = model();
    let d = 6.0;
    let mut rng = Pcg64::seed_from_u64(151_002);
    let mut saw_pulse = false;
    for _ in 0..60 {
        let trace = truth_transit_trace(d, &m, 0.0, &mut rng);
        assert!(
            (calendar_transit_days(&trace) - d).abs() < 1e-9,
            "trace duration must equal d"
        );
        assert_eq!(trace.times_d.len(), trace.temps_c.len());
        assert!(
            trace.times_d.windows(2).all(|w| w[1] >= w[0]),
            "times must be non-decreasing"
        );
        let max_t = trace.temps_c.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        if max_t > m.t_break - 1e-6 {
            saw_pulse = true;
        }
    }
    assert!(
        saw_pulse,
        "over 60 draws at d=6 with rho>0 at least one break pulse should appear"
    );
}

/// With `rho = 0` the model degenerates to a purely deterministic thermal path, so every
/// trip of the same duration has identical exposure. This is the regime the six real
/// Abdella shipments actually sample.
#[test]
fn zero_break_rate_makes_exposure_a_function_of_duration_only() {
    let mut m = model();
    m.set_break_rate(0.0);
    let mut rng = Pcg64::seed_from_u64(151_003);
    let d = 4.25;
    let a = truth_transit_trace(d, &m, 0.0, &mut rng);
    let b = truth_transit_trace(d, &m, 0.0, &mut rng);
    let la = resolve_arrival_exposure(Some(&a.temps_c), Some(&a.times_d), m.q10, m.t_ref).unwrap();
    let lb = resolve_arrival_exposure(Some(&b.temps_c), Some(&b.times_d), m.q10, m.t_ref).unwrap();
    assert!(
        (la - lb).abs() < 1e-6,
        "rho=0 must give identical exposure: {la} vs {lb}"
    );
}

/// Breaks must widen the F2 (pack-date) law relative to the break-free model — that
/// widening is exactly the residual uncertainty a temperature trace resolves.
#[test]
fn breaks_widen_the_pack_date_law() {
    let mut with_breaks = model();
    let mut without = model();
    without.set_break_rate(0.0);

    let v_with = with_breaks.variance_f_given_d(5);
    let v_without = without.variance_f_given_d(5);
    assert!(
        v_with > v_without * 1.10,
        "break model must widen F2 law: var {v_with} vs {v_without}"
    );
}

/// The UPC cohort law is the equally-weighted mixture of its component laws. Its mean is
/// the average of component means, but its variance must EXCEED the average of component
/// variances, because a mixture picks up the between-component spread.
#[test]
fn mixture_law_mean_averages_but_variance_exceeds() {
    let mut m = model();
    let parts = [
        ArrivalCondition::Duration(2),
        ArrivalCondition::Duration(5),
        ArrivalCondition::Duration(8),
    ];

    let mix = m.mixture_law(&parts);
    let means: Vec<f64> = parts.iter().map(|&c| m.filter_law_mean_f(c)).collect();
    let vars: Vec<f64> = parts
        .iter()
        .map(|&c| match c {
            ArrivalCondition::Duration(d) => m.variance_f_given_d(d),
            _ => unreachable!(),
        })
        .collect();

    let mean_of_means = means.iter().sum::<f64>() / means.len() as f64;
    let mean_of_vars = vars.iter().sum::<f64>() / vars.len() as f64;

    assert!(
        (mix.mean_f - mean_of_means).abs() < 5e-3,
        "mixture mean {} should track average of component means {mean_of_means}",
        mix.mean_f
    );
    assert!(
        mix.sd_f * mix.sd_f > mean_of_vars * 1.05,
        "mixture variance {} must exceed average component variance {mean_of_vars} \
         (between-component spread)",
        mix.sd_f * mix.sd_f
    );
}

/// A one-component mixture must be exactly that component — the degenerate case has to be
/// a no-op or the UPC path would silently differ from GSIN at L=1.
#[test]
fn single_component_mixture_is_identity() {
    let mut m = model();
    let c = ArrivalCondition::Duration(4);
    let mix = m.mixture_law(&[c]);
    let solo_mean = m.filter_law_mean_f(c);
    assert!(
        (mix.mean_f - solo_mean).abs() < 1e-9,
        "single-component mixture must equal the component: {} vs {solo_mean}",
        mix.mean_f
    );
}
