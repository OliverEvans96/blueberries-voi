//! T-163 v2-guards — clean-chain φ̄ calibration moments (S1.3).

use std::fs;
use std::path::PathBuf;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::arrival::ArrivalModel;

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn empirical_mean_sd(samples: &[f64]) -> (f64, f64) {
    let n = samples.len() as f64;
    let mean = samples.iter().sum::<f64>() / n;
    let var = samples.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
    (mean, var.sqrt())
}

/// Abdella six-shipment φ̄ overlay (v2 §3.4.2; T-163 S1.3).
const ABDELLA_PHI_BAR_MEAN: f64 = 1.36;
const ABDELLA_PHI_BAR_SD: f64 = 0.075;
const PHI_BAR_MEAN_TOL: f64 = 0.02;
const PHI_BAR_SD_TOL: f64 = 0.015;

/// Mean Λ = d·φ̄ over the six committed shipments.
const ABDELLA_LAMBDA_MEAN: f64 = 6.342;
const LAMBDA_MEAN_TOL: f64 = 0.35;

fn require_v2_artifact_fields() {
    let json: serde_json::Value =
        serde_json::from_str(voi_core::arrival::embedded_arrival_model()).expect("artifact json");
    for key in ["sigma_hour", "thermal_modes"] {
        assert!(
            json.get(key).is_some(),
            "RED: arrival artifact must carry v2 field {key}"
        );
    }
}

fn clean_chain_model() -> ArrivalModel {
    let mut model = ArrivalModel::embedded();
    model.set_break_rate(0.0);
    model
}

/// S1.3: at ρ = 0, simulated φ̄ mean/SD match the six Abdella shipments after v2 tuning.
#[test]
#[ignore = "T-163 v2 calibration MC; slow: run via cargo test -- --ignored"]
fn clean_chain_phi_bar_moments() {
    require_v2_artifact_fields();

    let model = clean_chain_model();
    let mut rng_duration = Pcg64::seed_from_u64(163_003);
    let mut rng_temp = Pcg64::seed_from_u64(163_004);
    let mut rng_pos = Pcg64::seed_from_u64(163_005);
    let mut rng_gamma = Pcg64::seed_from_u64(163_006);
    let mut rng_regime = Pcg64::seed_from_u64(163_007);

    let n_draws = 4_000usize;
    let mut phi_bars = Vec::with_capacity(n_draws);
    let mut lambdas = Vec::with_capacity(n_draws);
    for _ in 0..n_draws {
        let draw = model.draw_truth_delivery(
            "abdella_all",
            8,
            &mut rng_duration,
            &mut rng_temp,
            &mut rng_pos,
            &mut rng_gamma,
            &mut rng_regime,
        );
        phi_bars.push(draw.phi_bar);
        lambdas.push(draw.lambda);
    }

    let (mean_phi, sd_phi) = empirical_mean_sd(&phi_bars);
    let (mean_lambda, _) = empirical_mean_sd(&lambdas);

    assert!(
        (mean_phi - ABDELLA_PHI_BAR_MEAN).abs() <= PHI_BAR_MEAN_TOL,
        "RED: clean-chain mean φ̄={mean_phi:.4} must be within {PHI_BAR_MEAN_TOL} of Abdella {ABDELLA_PHI_BAR_MEAN}"
    );
    assert!(
        (sd_phi - ABDELLA_PHI_BAR_SD).abs() <= PHI_BAR_SD_TOL,
        "RED: clean-chain SD φ̄={sd_phi:.4} must be within {PHI_BAR_SD_TOL} of Abdella {ABDELLA_PHI_BAR_SD} (modes + OU scatter at ρ=0)"
    );
    assert!(
        sd_phi >= ABDELLA_PHI_BAR_SD - PHI_BAR_SD_TOL,
        "RED: deterministic legged baseline gives near-zero φ̄ spread (sd={sd_phi:.4}); v2 thermal modes + hourly OU required"
    );
    assert!(
        (mean_lambda - ABDELLA_LAMBDA_MEAN).abs() <= LAMBDA_MEAN_TOL,
        "RED: clean-chain mean Λ={mean_lambda:.3} must track Abdella shipments (~{ABDELLA_LAMBDA_MEAN})"
    );

    // Guard against a no-op v2 artifact: generative path must reference OU / modes in source.
    let shipments = fs::read_to_string(manifest_dir().join("src/shipments.rs"))
        .expect("read shipments.rs");
    assert!(
        shipments.contains("sigma_hour")
            || shipments.contains("thermal_mode")
            || shipments.contains("trip_mode"),
        "RED: truth_transit_trace must wire v2 thermal modes / hourly OU"
    );
}
