//! CTL-02/04 one-step rollout (Python `bakeoff_rollout`).

use std::collections::BTreeMap;

use crate::arrival::{
    ArrivalModel, STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS,
    STREAM_ARRIVAL_TEMP,
};
use crate::day_step::{unit_day_step_with_birth, UnitDayStepIn};
use crate::params::ModelParams;
use crate::physics::{draw_demand_spawn, f_to_age, weibull_survival};
use crate::policy::{damped_sw_order_f_belief, effective_inventory_f_belief};
use crate::schedule::OrderSchedule;
use crate::shipments::ShipmentTrace;
use crate::spawn_rng::SpawnRng;
use crate::voi::truth_f_belief;

const STREAM_DEMAND: &str = ":demand";
const STREAM_ALLOC: &str = ":alloc";
const STREAM_SPOIL: &str = ":spoil";
const STREAM_BIRTH: &str = ":birth";
const ORACLE_K: usize = 5;

/// SIM-01=B profit coefficients for rollout path scoring.
#[derive(Clone, Debug)]
pub struct RolloutCosts {
    pub unit_margin: f64,
    pub waste_cost: f64,
    pub stockout_penalty: f64,
}

impl Default for RolloutCosts {
    fn default() -> Self {
        Self {
            unit_margin: 2.0,
            waste_cost: 1.5,
            stockout_penalty: 3.0,
        }
    }
}

/// Shared rollout forward-sim context (CRN addressing + continuation policy).
#[derive(Clone, Debug)]
pub struct RolloutContext {
    pub root_seed: u64,
    pub run_id: String,
    pub day0: u32,
    pub lead_time: u32,
    pub schedule: OrderSchedule,
    pub alpha: f64,
    pub rho: f64,
    pub costs: RolloutCosts,
    pub shipments: Vec<ShipmentTrace>,
    pub f_pipeline_default: f64,
    pub h: u32,
    pub n_paths: u32,
    pub radius: i32,
}

pub fn candidate_orders(base_q: u32, case_size: u32, radius: i32) -> Vec<u32> {
    let cs = case_size.max(1);
    let base_cases = (base_q / cs) as i32;
    let mut out = Vec::new();
    for d in -radius..=radius {
        let c = (base_cases + d).max(0) as u32;
        out.push(c * cs);
    }
    out.sort_unstable();
    out.dedup();
    if out.is_empty() {
        out.push(0);
    }
    out
}

/// Weibull survival weight at effective age τ (ADR 0061).
pub fn w_long(tau: f64, params: &ModelParams) -> f64 {
    weibull_survival(tau, params.beta, params.eta_ref)
}

/// Terminal salvage from unit freshness state: V_T = m * Σ w_long(τ_i) over alive units.
pub fn terminal_salvage_unit_state(
    freshness: &[f64],
    margin: f64,
    params: &ModelParams,
) -> f64 {
    let mut taus: Vec<f64> = freshness
        .iter()
        .filter(|&&f| f > 0.0)
        .map(|&f| f_to_age(f, params.eta_ref))
        .collect();
    taus.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    let weighted: f64 = taus.iter().map(|&tau| w_long(tau, params)).sum();
    margin * weighted
}

/// Terminal salvage V_T = m * E[f]-weighted on-hand at horizon (ADR 0061 / 0130 f-native).
pub fn terminal_salvage_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    margin: f64,
) -> f64 {
    margin * effective_inventory_f_belief(lot_counts, f_marginals, f_grid, 0, 0.0)
}

pub fn day_profit(
    sales: u32,
    waste: u32,
    demand: u32,
    margin: f64,
    waste_cost: f64,
    stockout: f64,
) -> f64 {
    let lost = demand.saturating_sub(sales);
    margin * f64::from(sales) - waste_cost * f64::from(waste) - stockout * f64::from(lost)
}

fn sample_f_from_lot_marginal(
    f_marginals: &[f64],
    ell: usize,
    k: usize,
    f_grid: &[f64],
    rng: &mut SpawnRng,
) -> f64 {
    let start = ell * k;
    let mut total = 0.0;
    for bin in 0..k {
        total += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
    }
    let u = if total > 0.0 {
        rng.next_f64() * total
    } else {
        0.0
    };
    let mut cum = 0.0;
    for bin in 0..k {
        cum += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
        if u <= cum {
            return f_grid[bin].clamp(1e-12, 1.0);
        }
    }
    f_grid[k.saturating_sub(1)].clamp(1e-12, 1.0)
}

fn unit_state_from_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    units_per_lot: usize,
    root_seed: u64,
    run_id: &str,
    day: u32,
) -> (Vec<f64>, Vec<usize>) {
    let l = lot_counts.len();
    let k = f_grid.len();
    let u = units_per_lot.max(1);
    let mut rng_birth = SpawnRng::spawn_rng(root_seed, run_id, day, STREAM_BIRTH);
    let mut freshness = Vec::new();
    let mut lot_offsets = vec![0usize];
    for ell in 0..l {
        let n = lot_counts[ell].round().max(0.0) as usize;
        let alive = n.min(u);
        let dead = u.saturating_sub(alive);
        for _ in 0..alive {
            freshness.push(sample_f_from_lot_marginal(
                f_marginals,
                ell,
                k,
                f_grid,
                &mut rng_birth,
            ));
        }
        freshness.extend(std::iter::repeat_n(0.0, dead));
        lot_offsets.push(freshness.len());
    }
    (freshness, lot_offsets)
}

fn enqueue(pending: &mut BTreeMap<u32, u32>, day: u32, lead: u32, qty: u32) {
    *pending.entry(day + lead).or_insert(0) += qty;
}

fn pop_arrival(pending: &mut BTreeMap<u32, u32>, day: u32) -> u32 {
    pending.remove(&day).unwrap_or(0)
}

/// One-step rollout: pick the case order with highest CRN-paired path value.
pub fn rollout_order(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    base_q: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
) -> Result<u32, String> {
    if ctx.h == 0 {
        return Err(format!("H must be positive, got {}", ctx.h));
    }
    if ctx.n_paths == 0 {
        return Err(format!(
            "n_rollout_paths must be positive, got {}",
            ctx.n_paths
        ));
    }
    let mut cands = candidate_orders(base_q, params.case_size, ctx.radius);
    if cands.is_empty() {
        return Err("candidates must be non-empty".into());
    }
    let mut unique = vec![base_q];
    for q in cands.drain(..) {
        if !unique.contains(&q) {
            unique.push(q);
        }
    }
    let mut best_q = unique[0];
    let mut best_score = f64::NEG_INFINITY;
    for q in unique {
        let mut acc = 0.0;
        for path in 0..ctx.n_paths {
            acc += path_value_f_belief(
                lot_counts,
                f_marginals,
                f_grid,
                q,
                params,
                pending0,
                ctx,
                path,
            );
        }
        let score = acc / f64::from(ctx.n_paths);
        if score > best_score {
            best_score = score;
            best_q = q;
        }
    }
    Ok(best_q)
}

fn truth_delivery_units(
    arrival_model: &ArrivalModel,
    arrival: u32,
    root_seed: u64,
    path_run: &str,
    sim_day: u32,
) -> Option<Vec<f64>> {
    if arrival == 0 {
        return None;
    }
    let mut rng_dur = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_DURATION);
    let mut rng_temp = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_TEMP);
    let mut rng_pos = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_POS);
    let mut rng_gamma = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_GAMMA);
    Some(
        arrival_model
            .draw_truth_delivery(
                "abdella_all",
                arrival as usize,
                &mut rng_dur,
                &mut rng_temp,
                &mut rng_pos,
                &mut rng_gamma,
            )
            .unit_f,
    )
}

fn path_value_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    first_order: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
    path: u32,
) -> f64 {
    let path_run = format!("{}|rollout|p{path}", ctx.run_id);
    let upl = params.units_per_lot.max(1);
    let (mut freshness, mut lot_offsets) = unit_state_from_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        upl,
        ctx.root_seed,
        &path_run,
        ctx.day0,
    );
    let mut pending = pending0.clone();
    let mut profit = 0.0;
    let arrival_model = ArrivalModel::embedded();

    for h in 0..ctx.h {
        let sim_day = ctx.day0 + h;
        let pending_sum: u32 = pending.values().copied().sum();
        let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
        let order_qty = if h == 0 {
            first_order
        } else {
            damped_sw_order_f_belief(
                &lc,
                &fm,
                &fg,
                pending_sum,
                sim_day,
                params,
                ctx.alpha,
                ctx.rho,
                Some(&ctx.schedule),
                ctx.f_pipeline_default,
            )
        };
        enqueue(&mut pending, sim_day, ctx.lead_time, order_qty);
        let arrival = pop_arrival(&mut pending, sim_day);

        let mut rng_demand =
            SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(sim_day));
        let mut rng_gamma = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ALLOC);

        let delivery_unit_f =
            truth_delivery_units(&arrival_model, arrival, ctx.root_seed, &path_run, sim_day);
        let mut rng_birth = if arrival > 0 {
            Some(SpawnRng::spawn_rng(
                ctx.root_seed,
                &path_run,
                sim_day,
                STREAM_BIRTH,
            ))
        } else {
            None
        };

        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_unit_f,
            units_per_lot: Some(upl),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            &ctx.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        profit += day_profit(
            out.sales_total,
            out.waste_total,
            out.demand,
            ctx.costs.unit_margin,
            ctx.costs.waste_cost,
            ctx.costs.stockout_penalty,
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }

    let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
    profit + terminal_salvage_f_belief(&lc, &fm, &fg, ctx.costs.unit_margin)
}

/// Test helper: sum arrival units delivered across an inner rollout path.
#[cfg(test)]
fn path_arrival_units_sum(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    first_order: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
    path: u32,
) -> u32 {
    let path_run = format!("{}|rollout|p{path}", ctx.run_id);
    let upl = params.units_per_lot.max(1);
    let (mut freshness, mut lot_offsets) = unit_state_from_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        upl,
        ctx.root_seed,
        &path_run,
        ctx.day0,
    );
    let mut pending = pending0.clone();
    let mut delivered = 0u32;
    let arrival_model = ArrivalModel::embedded();

    for h in 0..ctx.h {
        let sim_day = ctx.day0 + h;
        let pending_sum: u32 = pending.values().copied().sum();
        let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
        let order_qty = if h == 0 {
            first_order
        } else {
            damped_sw_order_f_belief(
                &lc,
                &fm,
                &fg,
                pending_sum,
                sim_day,
                params,
                ctx.alpha,
                ctx.rho,
                Some(&ctx.schedule),
                ctx.f_pipeline_default,
            )
        };
        enqueue(&mut pending, sim_day, ctx.lead_time, order_qty);
        let arrival = pop_arrival(&mut pending, sim_day);
        if arrival > 0 {
            delivered += arrival;
        }

        let mut rng_demand =
            SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(sim_day));
        let mut rng_gamma = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ALLOC);

        let delivery_unit_f =
            truth_delivery_units(&arrival_model, arrival, ctx.root_seed, &path_run, sim_day);
        let mut rng_birth = if arrival > 0 {
            Some(SpawnRng::spawn_rng(
                ctx.root_seed,
                &path_run,
                sim_day,
                STREAM_BIRTH,
            ))
        } else {
            None
        };

        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_unit_f,
            units_per_lot: Some(upl),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            &ctx.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }
    delivered
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::belief_flat::f_grid_k;

    #[test]
    fn candidate_neighbourhood_plus_minus_radius() {
        let c = candidate_orders(16, 8, 2);
        assert!(c.contains(&0));
        assert!(c.contains(&16));
        assert!(c.contains(&32));
        assert!(c.iter().all(|q| q % 8 == 0));
    }

    #[test]
    fn terminal_salvage_unit_state_empty_is_zero() {
        assert_eq!(
            terminal_salvage_unit_state(&[], 2.0, &ModelParams::default()),
            0.0
        );
    }

    #[test]
    fn terminal_salvage_f_belief_matches_effective_inventory() {
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![4.0, 2.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[k - 1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let margin = 2.0;
        let expected =
            margin * effective_inventory_f_belief(&lot_counts, &f_marginals, &f_grid, 0, 0.0);
        assert_eq!(
            terminal_salvage_f_belief(&lot_counts, &f_marginals, &f_grid, margin),
            expected
        );
    }

    #[test]
    fn rollout_rejects_nonpositive_horizon() {
        let p = ModelParams::default();
        let ctx = RolloutContext {
            root_seed: 1,
            run_id: "t".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 0,
            n_paths: 1,
            radius: 1,
        };
        assert!(rollout_order(&[8.0], &[1.0], &f_grid_k(1), 8, &p, &BTreeMap::new(), &ctx).is_err());
    }

    #[test]
    fn rollout_order_returns_nonnegative_case_multiple() {
        let p = ModelParams::default();
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![10.0, 5.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let ctx = RolloutContext {
            root_seed: 3,
            run_id: "t".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 2,
            n_paths: 1,
            radius: 1,
        };
        let q = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            8,
            &p,
            &BTreeMap::new(),
            &ctx,
        )
        .unwrap();
        assert_eq!(q % p.case_size, 0);
    }

    #[test]
    fn no_repeat_delivery_over_horizon() {
        let p = ModelParams::default();
        let mut order_only_monday = [false; 7];
        order_only_monday[0] = true;
        let schedule = OrderSchedule {
            delivery_weekdays: OrderSchedule::default().delivery_weekdays,
            order_weekdays: order_only_monday,
            lead_time_days: 1,
        };
        let ctx = RolloutContext {
            root_seed: 42,
            run_id: "delivery-once".into(),
            day0: 0,
            lead_time: 1,
            schedule,
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 3,
            n_paths: 1,
            radius: 0,
        };
        let first_order = 16u32;
        let delivered = path_arrival_units_sum(
            &[0.0],
            &[1.0],
            &f_grid_k(1),
            first_order,
            &p,
            &BTreeMap::new(),
            &ctx,
            0,
        );
        assert_eq!(delivered, first_order, "pipeline delivers candidate order once");
        assert_ne!(
            delivered,
            first_order * ctx.h,
            "must not re-deliver first_order every inner day"
        );
    }

    #[test]
    fn rollout_costs_flip_winning_order() {
        let p = ModelParams::default();
        let k = 5usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![30.0, 15.0];
        let mut f_marginals = vec![0.0; 2 * k];
        // High stale inventory under independent per-unit aging: waste_cost flips winner.
        f_marginals[k - 1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let base = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            0,
            6,
            &p,
            0.9,
            0.8,
            Some(&OrderSchedule::default()),
            1.0,
        );
        assert!(base > 0, "fixture needs positive base_q");
        let mk_ctx = |waste: f64| RolloutContext {
            root_seed: 7,
            run_id: "cost-rank".into(),
            day0: 6,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts {
                unit_margin: 2.0,
                waste_cost: waste,
                stockout_penalty: 3.0,
            },
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 4,
            n_paths: 4,
            radius: 2,
        };
        let low = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base,
            &p,
            &BTreeMap::new(),
            &mk_ctx(0.05),
        )
        .unwrap();
        let high = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base,
            &p,
            &BTreeMap::new(),
            &mk_ctx(25.0),
        )
        .unwrap();
        assert_ne!(low, high, "waste_cost must flip rollout winner on fixture");
    }
}
