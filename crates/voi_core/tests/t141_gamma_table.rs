//! T-141 AC-P1/P2/P3: GammaDecrementTable.

use voi_core::physics::GammaDecrementTable;
use voi_core::{gamma_decrement_cdf, ModelParams};

const GRID: usize = 4096;

#[test]
fn gamma_table_has_4096_grid_entries() {
    let table = GammaDecrementTable::for_params(&ModelParams::default());
    assert_eq!(table.len(), GRID);
}

#[test]
fn gamma_table_cdf_matches_direct_gamma_decrement_cdf() {
    let params = ModelParams::default();
    let table = GammaDecrementTable::for_params(&params);
    for f in [0.01, 0.05, 0.2, 0.5, 0.9] {
        let direct = gamma_decrement_cdf(f, &params);
        assert!((direct - table.cdf(f)).abs() < 1e-5);
    }
}

#[test]
fn gamma_table_spoil_prob_matches_survival_complement() {
    let params = ModelParams::default();
    let table = GammaDecrementTable::for_params(&params);
    for f in [0.05, 0.15, 0.4, 0.8] {
        let expected = 1.0 - gamma_decrement_cdf(f, &params);
        assert!((expected - table.spoil_prob(f)).abs() < 1e-5);
    }
}
