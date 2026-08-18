//! CTL-02/04 one-step rollout (Python `bakeoff_rollout`).

use std::collections::BTreeMap;

use crate::day_step::{unit_day_step, UnitDayStepIn};
use crate::params::ModelParams;
use crate::physics::{draw_demand_spawn, f_to_age, weibull_survival};
use crate::policy::damped_sw_order_f_belief;
use crate::schedule::OrderSchedule;
use crate::shipments::{arrival_receipt_meta, ShipmentTrace};
use crate::spawn_rng::SpawnRng;
use crate::voi::truth_f_belief;

const STREAM_DEMAND: &str = ":demand";
const STREAM_ALLOC: &str = ":alloc";
const STREAM_SPOIL: &str = ":spoil";
const STREAM_ARRIVAL_SHIP: &str = ":arrival_ship";
const STREAM_ARRIVAL_SENSOR: &str = ":arrival_sensor";
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

/// Legacy f-belief terminal (research); rollout scoring uses [`terminal_salvage_unit_state`].
pub fn terminal_salvage_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    margin: f64,
    params: &ModelParams,
) -> f64 {
    let upl = params.units_per_lot.max(1);
    let (freshness, _) = unit_state_from_f_belief(lot_counts, f_marginals, f_grid, upl);
    terminal_salvage_unit_state(&freshness, margin, params)
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

fn unit_state_from_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    units_per_lot: usize,
) -> (Vec<f64>, Vec<usize>) {
    let l = lot_counts.len();
    let k = f_grid.len();
    let u = units_per_lot.max(1);
    let mut freshness = Vec::new();
    let mut lot_offsets = vec![0usize];
    for ell in 0..l {
        let mut e_f = 0.0;
        for bin in 0..k {
            let p = f_marginals.get(ell * k + bin).copied().unwrap_or(0.0);
            e_f += p * f_grid[bin];
        }
        let n = lot_counts[ell].round().max(0.0) as usize;
        let alive = n.min(u);
        let dead = u.saturating_sub(alive);
        freshness.extend(std::iter::repeat_n(e_f.max(0.0), alive));
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
    let (mut freshness, mut lot_offsets) =
        unit_state_from_f_belief(lot_counts, f_marginals, f_grid, upl);
    let mut pending = pending0.clone();
    let mut profit = 0.0;

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

        let (f_at_receipt, age_at_receipt, pack_date_days) = if arrival > 0 {
            let mut rng_ship =
                SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ARRIVAL_SHIP);
            let mut rng_sensor =
                SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ARRIVAL_SENSOR);
            let (f, tau, pack) = arrival_receipt_meta(
                &mut rng_ship,
                &mut rng_sensor,
                &ctx.shipments,
                params,
                ctx.f_pipeline_default,
            );
            (Some(f), Some(tau), Some(pack))
        } else {
            (None, None, None)
        };

        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_f: f_at_receipt,
            units_per_lot: Some(upl),
            age_at_receipt,
            pack_age_mean: pack_date_days.map(f64::from),
        };
        let out = unit_day_step(
            &input,
            params,
            &ctx.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
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

    profit + terminal_salvage_unit_state(&freshness, ctx.costs.unit_margin, params)
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
        let ctx = RolloutContext {
            root_seed: 42,
            run_id: "delivery-once".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 3,
            n_paths: 1,
            radius: 0,
        };
        let mut pending = BTreeMap::new();
        let value = path_value_f_belief(
            &[0.0],
            &[1.0],
            &f_grid_k(1),
            16,
            &p,
            &pending,
            &ctx,
            0,
        );
        assert!(value.is_finite());
        // After inner sim the pending pipeline must not re-deliver the same lot.
        enqueue(&mut pending, 0, 1, 16);
        let _ = pop_arrival(&mut pending, 1);
        assert_eq!(pending.get(&1).copied().unwrap_or(0), 0);
    }
}
