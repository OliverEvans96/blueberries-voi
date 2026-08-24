//! Closed-loop episode with injected deliveries (no Abdella I/O).

use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::arrival::ArrivalModel;
use crate::day_step::{unit_day_step, UnitDayStepIn, ModelParams};
use crate::shipments::ShipmentTrace;

/// Totals from a closed-loop episode, split into the full horizon and the scored
/// tail. The first `n_burn` days let the system reach a steady state and are excluded
/// from the `scored_*` totals so startup transients don't bias the comparison.
#[derive(Clone, Debug)]
pub struct EpisodeResult {
    /// Number of burn-in days excluded from the `scored_*` totals.
    pub n_burn: u32,
    /// Number of days counted toward the `scored_*` totals.
    pub n_score: u32,
    /// Total simulated days, `n_burn + n_score`.
    pub n_days: u32,
    /// Units sold across the entire horizon, burn-in included.
    pub sales_total: u32,
    /// Units wasted across the entire horizon, burn-in included.
    pub waste_total: u32,
    /// Units sold during the scored tail only (days `>= n_burn`).
    pub scored_sales: u32,
    /// Units wasted during the scored tail only (days `>= n_burn`).
    pub scored_waste: u32,
}

/// MWF-like gate: order on days 0, 2, 4 of a 7-day week (monday0 Mon/Wed/Fri).
fn can_order(day: u32) -> bool {
    matches!(day % 7, 0 | 2 | 4)
}

/// Runs a fixed-order closed-loop episode over `n_burn + n_score` days, drawing
/// deliveries and demand from injected RNGs rather than any Abdella parquet input.
/// Every scheduled order is the same constant `constant_order` quantity, so this is a
/// smoke-test/harness episode rather than one driven by the ordering policy.
pub fn run_closed_loop_episode(
    n_burn: u32,
    n_score: u32,
    constant_order: u32,
    params: &ModelParams,
    seed: u64,
) -> Result<EpisodeResult, String> {
    let horizon = n_burn + n_score;
    let upl = params.units_per_lot.max(1);
    let mut freshness: Vec<f64> = vec![];
    let mut lot_offsets: Vec<usize> = vec![0];
    let shipments = [ShipmentTrace::smoke_cool()];
    let arrival_model = ArrivalModel::embedded();
    let mut sales_total = 0u32;
    let mut waste_total = 0u32;
    let mut scored_sales = 0u32;
    let mut scored_waste = 0u32;
    for day in 0..horizon {
        let order = if can_order(day) { constant_order } else { 0 };
        let delivery_unit_f = if order > 0 {
            let mut rng_d = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 7));
            let mut rng_t = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 11));
            let mut rng_p = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 13));
            let mut rng_g = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 17));
            Some(
                arrival_model
                    .draw_truth_delivery(
                        &params.arrival_product,
                        order as usize,
                        &mut rng_d,
                        &mut rng_t,
                        &mut rng_p,
                        &mut rng_g,
                    )
                    .unit_f,
            )
        } else {
            None
        };
        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(params.demand_mu.max(0.0) as u32),
            gamma_decrement: None,
            deliver: order > 0,
            deliver_units: if order > 0 { Some(order) } else { None },
            delivery_unit_f,
            units_per_lot: Some(upl),
        };
        let mut rng_gamma = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 3));
        let mut rng_alloc = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 5 + 1));
        let out = unit_day_step(
            &input,
            params,
            &shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
        );
        sales_total += out.sales_total;
        waste_total += out.waste_total;
        if day >= n_burn {
            scored_sales += out.sales_total;
            scored_waste += out.waste_total;
        }
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }
    Ok(EpisodeResult {
        n_burn,
        n_score,
        n_days: horizon,
        sales_total,
        waste_total,
        scored_sales,
        scored_waste,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn episode_exposes_n_burn_and_scored_slice() {
        let p = ModelParams::default();
        let ep = run_closed_loop_episode(2, 3, 8, &p, 1).unwrap();
        assert_eq!(ep.n_burn, 2);
        assert_eq!(ep.n_score, 3);
        assert_eq!(ep.n_days, 5);
    }

    #[test]
    fn n_burn_zero_scored_is_full_horizon() {
        let p = ModelParams::default();
        let ep = run_closed_loop_episode(0, 4, 8, &p, 2).unwrap();
        assert_eq!(ep.scored_sales, ep.sales_total);
        assert_eq!(ep.n_days, 4);
    }

    #[test]
    fn episode_totals_finite() {
        let p = ModelParams::default();
        let ep = run_closed_loop_episode(1, 2, 8, &p, 7).unwrap();
        assert!(ep.sales_total < 10_000);
    }
}
