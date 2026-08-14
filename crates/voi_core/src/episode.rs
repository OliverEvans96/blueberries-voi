//! Closed-loop episode with injected deliveries (no Abdella I/O).

use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::day_step::{day_step, DayStepIn, ModelParams};

#[derive(Clone, Debug)]
pub struct EpisodeResult {
    pub n_burn: u32,
    pub n_score: u32,
    pub n_days: u32,
    pub sales_total: u32,
    pub waste_total: u32,
    pub scored_sales: u32,
    pub scored_waste: u32,
}

/// MWF-like gate: order on days 0, 2, 4 of a 7-day week (monday0 Mon/Wed/Fri).
fn can_order(day: u32) -> bool {
    matches!(day % 7, 0 | 2 | 4)
}

pub fn run_closed_loop_episode(
    n_burn: u32,
    n_score: u32,
    constant_order: u32,
    params: &ModelParams,
    seed: u64,
) -> Result<EpisodeResult, String> {
    let horizon = n_burn + n_score;
    let mut state = DayStepIn {
        counts: vec![],
        taus: vec![],
        lot_ids: vec![],
        demand: Some(params.demand_mu.max(0.0) as u32),
        spoil_by: Some(vec![]),
        delivery_n: 0,
        delivery_tau: 0.0,
        delivery_lot_id: 1,
    };
    let mut sales_total = 0u32;
    let mut waste_total = 0u32;
    let mut scored_sales = 0u32;
    let mut scored_waste = 0u32;
    let mut lot = 1i64;
    for day in 0..horizon {
        let order = if can_order(day) { constant_order } else { 0 };
        state.delivery_n = order;
        state.delivery_lot_id = lot;
        if order > 0 {
            lot += 1;
        }
        state.spoil_by = None;
        let mut rng_a = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 3));
        let mut rng_s = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(day) * 5 + 1));
        let out = day_step(&state, params, Some(&mut rng_a), Some(&mut rng_s));
        sales_total += out.sales_total;
        waste_total += out.waste_total;
        if day >= n_burn {
            scored_sales += out.sales_total;
            scored_waste += out.waste_total;
        }
        state.counts = out.counts;
        state.taus = out.taus;
        state.lot_ids = out.lot_ids;
        state.demand = Some(params.demand_mu.max(0.0) as u32);
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
