//! T-163 freshness calibration — arrival f distribution and Prior coherence (fast MC).

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};
use voi_core::ModelParams;

const N_DRAWS: usize = 400;

fn empirical_quantiles(samples: &mut [f64]) -> (f64, f64, f64, f64) {
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = samples.len();
    let mean = samples.iter().sum::<f64>() / n as f64;
    let p10 = samples[n / 10];
    let p50 = samples[n / 2];
    let p90 = samples[n * 9 / 10];
    (mean, p10, p50, p90)
}

fn truth_arrival_f_samples(model: &ArrivalModel, n: usize, seed: u64) -> Vec<f64> {
    let mut rng_d = Pcg64::seed_from_u64(seed);
    let mut rng_t = Pcg64::seed_from_u64(seed + 1);
    let mut rng_p = Pcg64::seed_from_u64(seed + 2);
    let mut rng_g = Pcg64::seed_from_u64(seed + 3);
    (0..n)
        .map(|_| {
            let draw = model.draw_truth_multilot_delivery_biased(
                "abdella_all",
                45,
                0.0,
                &mut rng_d,
                &mut rng_t,
                &mut rng_p,
                &mut rng_g,
            );
            draw.lots
                .iter()
                .flat_map(|lot| lot.unit_f.iter().copied())
                .sum::<f64>()
                / draw
                    .lots
                    .iter()
                    .map(|lot| lot.unit_f.len())
                    .sum::<usize>() as f64
        })
        .collect()
}

/// Multilot session-path arrival freshness should sit in a realistic US retail band.
#[test]
fn arrival_f_distribution_realistic_band() {
    let model = ArrivalModel::embedded();
    assert!(
        (model.reference_life_days - 26.0).abs() < 1e-9,
        "artifact reference_life_days should be 26 for calibrated arrival f; got {}",
        model.reference_life_days
    );
    let mut samples = truth_arrival_f_samples(&model, N_DRAWS, 163_501);
    let (mean, p10, p50, p90) = empirical_quantiles(&mut samples);
    let pct_60_90 = samples
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / N_DRAWS as f64;
    assert!(
        p50 >= 0.65,
        "median multilot arrival f should be >= 0.65 for US retail cold chain; got p50={p50:.3} mean={mean:.3} p10={p10:.3} p90={p90:.3}"
    );
    assert!(
        pct_60_90 >= 0.45,
        "at least ~45% of deliveries should land in [0.6, 0.9]; got {:.1}% (mean={mean:.3})",
        pct_60_90 * 100.0
    );
}

/// `sync_params` must not collapse artifact arrival gamma back to store `eta_ref=14`.
#[test]
fn sync_params_preserves_artifact_arrival_reference_life() {
    let mut model = ArrivalModel::embedded();
    let artifact_life = model.reference_life_days;
    assert!(
        artifact_life > ModelParams::default().eta_ref + 1.0,
        "test assumes decoupled arrival reference life"
    );
    model.sync_params(&ModelParams::default());
    assert!(
        (model.reference_life_days - artifact_life).abs() < 1e-12,
        "sync_params must preserve artifact reference_life_days; got {} vs {}",
        model.reference_life_days,
        artifact_life
    );
    assert!(
        (model.gamma_scale - 1.0 / (2.0 * artifact_life)).abs() < 1e-12,
        "sync_params must preserve artifact gamma_scale"
    );
}

/// Prior birth law mean should track generative multilot mean (no systematic upward bias).
#[test]
fn prior_mean_f_matches_generative_multilot() {
    let mut model = ArrivalModel::embedded();
    model.sync_params(&ModelParams::default());
    let mut samples = truth_arrival_f_samples(&model, N_DRAWS, 163_502);
    let (truth_mean, _, _, _) = empirical_quantiles(&mut samples);
    let prior = model.rung_law_on_grid(ArrivalCondition::Prior, "abdella_all", 64);
    assert!(
        (prior.mean_f - truth_mean).abs() <= 0.03,
        "Prior mean_f={:.3} must track generative multilot mean {:.3} within 0.03",
        prior.mean_f,
        truth_mean
    );
}

/// Session-path delivery freshness must match multilot draw (not one-lot padded artifact).
#[test]
fn session_arrival_f_matches_multilot_draw() {
    use voi_core::{DemandProfile, EngineSession};

    let seed = 163_503u64;
    let mut sess = EngineSession::new(seed);
    sess.set_demand_profile(
        DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("profile"),
    );
    sess.init(seed);
    let _ = sess.step(64);
    let delta = sess.step(0);
    assert!(delta.arrivals > 0, "fixture must deliver units after lead_time");
    let snap = sess.snapshot_value();
    let lots = snap["live_lots"].as_array().expect("live_lots");
    assert_eq!(lots.len(), 3, "multilot delivery must surface three lots");
    let weighted: f64 = lots
        .iter()
        .map(|lot| {
            lot["n"].as_u64().unwrap() as f64 * lot["mean_f"].as_f64().unwrap()
        })
        .sum::<f64>()
        / delta.arrivals as f64;
    assert!(
        weighted >= 0.55,
        "session weighted arrival mean_f should be mid-band; got {weighted:.3}"
    );
}
