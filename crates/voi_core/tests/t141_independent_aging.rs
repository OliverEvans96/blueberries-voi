//! AC-T2: independent per-unit gamma decrements in ground truth (T-141 / ADR 0143).

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::day_step::{unit_day_step, UnitDayStepIn};
use voi_core::ModelParams;

const PRE_AGING_F: f64 = 0.22;
const N_SEEDS: u64 = 5_000;

/// Two live units at identical freshness must be able to diverge under stochastic aging:
/// over many seeds, observe days where exactly one spoils (independent δ_i).
#[test]
fn t141_independent_aging_two_units_can_split_spoil() {
    let params = ModelParams::default();
    let mut split_spoil = false;

    for seed in 0..N_SEEDS {
        let mut rng_gamma = Pcg64::seed_from_u64(141_000 ^ seed);
        let input = UnitDayStepIn {
            freshness: vec![PRE_AGING_F, PRE_AGING_F],
            lot_offsets: vec![0, 2],
            demand: Some(0),
            gamma_decrement: None,
            deliver: false,
            deliver_units: None,
            delivery_f: None,
            units_per_lot: None,
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let out = unit_day_step(
            &input,
            &params,
            &[],
            Some(&mut rng_gamma),
            None,
            None,
            None,
        );
        assert_eq!(out.freshness.len(), 2);
        let alive: Vec<bool> = out.freshness.iter().map(|&f| f > 0.0).collect();
        if alive.iter().filter(|&&a| a).count() == 1 {
            split_spoil = true;
            break;
        }
    }

    assert!(
        split_spoil,
        "expected at least one seed where exactly one of two identical units spoils \
         (independent δ_i); shared decrement cannot produce this outcome"
    );
}
