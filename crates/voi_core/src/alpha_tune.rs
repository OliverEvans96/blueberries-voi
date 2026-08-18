//! CTL-03 α grid search: closed-loop episode profit on the f-native kernel (T-029).

use std::collections::BTreeMap;

use crate::day_step::{unit_day_step, UnitDayStepIn};
use crate::params::ModelParams;
use crate::physics::draw_demand_spawn;
use crate::policy::{
    constant_order, damped_sw_order_f_belief, protection_demand_quantile, rung0_order_f_belief,
};
use crate::rollout::{day_profit, rollout_order, RolloutContext, RolloutCosts};
use crate::schedule::OrderSchedule;
use crate::shipments::{arrival_receipt_meta, ShipmentTrace};
use crate::spawn_rng::SpawnRng;
use crate::voi::truth_f_belief;

const RUN_ID: &str = "alpha-tune";
const ORACLE_K: usize = 5;
const STREAM_DEMAND: &str = ":demand";
const STREAM_ALLOC: &str = ":alloc";
const STREAM_SPOIL: &str = ":spoil";
const STREAM_ARRIVAL_SHIP: &str = ":arrival_ship";
const STREAM_ARRIVAL_SENSOR: &str = ":arrival_sensor";

/// Ladder arms available for automated alpha tuning (`dp` remains a placeholder).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AlphaTuneArm {
    Constant,
    Rung0,
    Sw,
    Rollout,
}

/// Rollout compute budgets for the rollout ladder arm (CTL-02/04).
#[derive(Clone, Debug)]
pub struct AlphaTuneRolloutBudgets {
    pub h: u32,
    pub n_rollout_paths: u32,
    pub candidate_case_radius: i32,
}

impl Default for AlphaTuneRolloutBudgets {
    fn default() -> Self {
        Self {
            h: 2,
            n_rollout_paths: 1,
            candidate_case_radius: 1,
        }
    }
}

#[derive(Clone, Debug)]
pub struct AlphaTuneCosts {
    pub unit_margin: f64,
    pub waste_cost: f64,
    pub stockout_penalty: f64,
}

impl Default for AlphaTuneCosts {
    fn default() -> Self {
        Self {
            unit_margin: 2.0,
            waste_cost: 1.5,
            stockout_penalty: 3.0,
        }
    }
}

#[derive(Clone, Debug)]
pub struct AlphaTuneEpisodeResult {
    pub n_burn: u32,
    pub n_score: u32,
    pub n_days: u32,
    pub scored_profit: f64,
    pub scored_waste: u32,
    pub scored_lost_sales: u32,
}

fn enqueue(pending: &mut BTreeMap<u32, u32>, day: u32, lead: u32, qty: u32) {
    *pending.entry(day + lead).or_insert(0) += qty;
}

fn pop_arrival(pending: &mut BTreeMap<u32, u32>, day: u32) -> u32 {
    pending.remove(&day).unwrap_or(0)
}

fn seed_order_day(schedule: &OrderSchedule) -> u32 {
    for day in 0..7 {
        if schedule.can_order(day) {
            return day;
        }
    }
    0
}

fn protection_target_at_seed(alpha: f64, params: &ModelParams, schedule: &OrderSchedule) -> f64 {
    let seed_day = seed_order_day(schedule);
    let prot = schedule.protection_days(seed_day);
    protection_demand_quantile(alpha, params, prot, seed_day)
}

fn order_for_arm(
    arm: AlphaTuneArm,
    alpha: f64,
    rho: f64,
    root_seed: u64,
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    pending: &BTreeMap<u32, u32>,
    day: u32,
    params: &ModelParams,
    schedule: &OrderSchedule,
    shipments: &[ShipmentTrace],
    costs: &AlphaTuneCosts,
    constant_q: u32,
    rung0_target: f64,
    rollout: &AlphaTuneRolloutBudgets,
    lead_time: u32,
) -> u32 {
    let pending_sum: u32 = pending.values().copied().sum();
    match arm {
        AlphaTuneArm::Constant => {
            if !schedule.can_order(day) {
                0
            } else {
                constant_q
            }
        }
        AlphaTuneArm::Rung0 => rung0_order_f_belief(
            lot_counts,
            pending_sum,
            day,
            params,
            1.0,
            schedule,
            0.75,
            0.75,
            rung0_target,
        ),
        AlphaTuneArm::Sw => damped_sw_order_f_belief(
            lot_counts,
            f_marginals,
            f_grid,
            pending_sum,
            day,
            params,
            alpha,
            rho,
            Some(schedule),
            1.0,
        ),
        AlphaTuneArm::Rollout => {
            if !schedule.can_order(day) {
                return 0;
            }
            let base_q = damped_sw_order_f_belief(
                lot_counts,
                f_marginals,
                f_grid,
                pending_sum,
                day,
                params,
                alpha,
                rho,
                Some(schedule),
                1.0,
            );
            let ctx = RolloutContext {
                root_seed,
                run_id: format!("{RUN_ID}-d{day}"),
                day0: day,
                lead_time,
                schedule: schedule.clone(),
                alpha,
                rho,
                costs: RolloutCosts {
                    unit_margin: costs.unit_margin,
                    waste_cost: costs.waste_cost,
                    stockout_penalty: costs.stockout_penalty,
                },
                shipments: shipments.to_vec(),
                f_pipeline_default: 1.0,
                h: rollout.h.max(1),
                n_paths: rollout.n_rollout_paths.max(1),
                radius: rollout.candidate_case_radius,
            };
            rollout_order(
                lot_counts,
                f_marginals,
                f_grid,
                base_q,
                params,
                pending,
                &ctx,
            )
            .unwrap_or(base_q)
        }
    }
}

/// Closed-loop episode profit for one (arm, α) under shared CRN addressing (SIM-01=B).
pub fn run_alpha_tune_episode(
    arm: AlphaTuneArm,
    alpha: f64,
    rho: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    lead_time: u32,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    costs: &AlphaTuneCosts,
    rollout: &AlphaTuneRolloutBudgets,
) -> Result<AlphaTuneEpisodeResult, String> {
    if !(0.0 < alpha && alpha < 1.0) {
        return Err(format!("alpha must be in (0,1), got {alpha}"));
    }
    if !(0.0 < rho && rho <= 1.0) {
        return Err(format!("rho must be in (0,1], got {rho}"));
    }
    if shipments.is_empty() {
        return Err("shipments must be non-empty".to_string());
    }
    let schedule = OrderSchedule {
        lead_time_days: lead_time,
        ..OrderSchedule::default()
    };
    let horizon = n_burn + n_score;
    let upl = params.units_per_lot.max(1);
    let prot_target = protection_target_at_seed(alpha, params, &schedule);
    let constant_q = constant_order(prot_target.round() as u32, params.case_size);
    let rung0_target = prot_target;

    let mut freshness: Vec<f64> = vec![];
    let mut lot_offsets: Vec<usize> = vec![0];
    let mut pending: BTreeMap<u32, u32> = BTreeMap::new();
    let mut scored_profit = 0.0;
    let mut scored_waste = 0u32;
    let mut scored_lost_sales = 0u32;

    for day in 0..horizon {
        let (lot_counts, f_marginals, f_grid) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
        let order = order_for_arm(
            arm,
            alpha,
            rho,
            root_seed,
            &lot_counts,
            &f_marginals,
            &f_grid,
            &pending,
            day,
            params,
            &schedule,
            shipments,
            costs,
            constant_q,
            rung0_target,
            rollout,
            lead_time,
        );
        enqueue(&mut pending, day, lead_time, order);
        let arrival = pop_arrival(&mut pending, day);

        let mut rng_demand =
            SpawnRng::spawn_rng(root_seed, RUN_ID, day, STREAM_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(day));
        let mut rng_gamma = SpawnRng::spawn_rng(root_seed, RUN_ID, day, STREAM_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(root_seed, RUN_ID, day, STREAM_ALLOC);
        let mut rng_ship = if arrival > 0 {
            Some(SpawnRng::spawn_rng(root_seed, RUN_ID, day, STREAM_ARRIVAL_SHIP))
        } else {
            None
        };
        let mut rng_sensor = if arrival > 0 {
            Some(SpawnRng::spawn_rng(root_seed, RUN_ID, day, STREAM_ARRIVAL_SENSOR))
        } else {
            None
        };
        let (f_at_receipt, age_at_receipt, pack_date_days) = if arrival > 0 {
            let mut rng_ship = rng_ship.as_mut().expect("ship rng");
            let mut rng_sensor = rng_sensor.as_mut().expect("sensor rng");
            let (f, tau, pack) = arrival_receipt_meta(
                rng_ship,
                rng_sensor,
                shipments,
                params,
                1.0,
            );
            (Some(f), Some(tau), Some(pack))
        } else {
            (None, None, None)
        };

        let input = UnitDayStepIn {
            freshness,
            lot_offsets,
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
            shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            rng_ship.as_mut(),
            rng_sensor.as_mut(),
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;

        if day >= n_burn {
            scored_profit += day_profit(
                out.sales_total,
                out.waste_total,
                out.demand,
                costs.unit_margin,
                costs.waste_cost,
                costs.stockout_penalty,
            );
            scored_waste += out.waste_total;
            scored_lost_sales += out.demand.saturating_sub(out.sales_total);
        }
    }

    Ok(AlphaTuneEpisodeResult {
        n_burn,
        n_score,
        n_days: horizon,
        scored_profit,
        scored_waste,
        scored_lost_sales,
    })
}

pub fn parse_alpha_tune_arm(arm_id: &str) -> Result<AlphaTuneArm, String> {
    match arm_id {
        "constant" => Ok(AlphaTuneArm::Constant),
        "rung0" => Ok(AlphaTuneArm::Rung0),
        "sw" => Ok(AlphaTuneArm::Sw),
        "rollout" => Ok(AlphaTuneArm::Rollout),
        other => Err(format!("unknown alpha_tune arm {other:?}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::shipments::ShipmentTrace;

    #[test]
    fn alpha_tune_smoke_finite_profit() {
        let ships = [ShipmentTrace::smoke_cool()];
        let params = ModelParams::default();
        let costs = AlphaTuneCosts::default();
        let rollout = AlphaTuneRolloutBudgets::default();
        let ep = run_alpha_tune_episode(
            AlphaTuneArm::Sw,
            0.9,
            0.8,
            42,
            2,
            3,
            1,
            &params,
            &ships,
            &costs,
            &rollout,
        )
        .expect("episode");
        assert_eq!(ep.n_days, 5);
        assert!(ep.scored_profit.is_finite());
    }

    #[test]
    fn shared_seed_reproduces_profit() {
        let ships = [ShipmentTrace::smoke_cool()];
        let params = ModelParams::default();
        let costs = AlphaTuneCosts::default();
        let rollout = AlphaTuneRolloutBudgets::default();
        let a = run_alpha_tune_episode(
            AlphaTuneArm::Sw,
            0.8,
            0.8,
            7,
            2,
            2,
            1,
            &params,
            &ships,
            &costs,
            &rollout,
        )
        .expect("a");
        let b = run_alpha_tune_episode(
            AlphaTuneArm::Sw,
            0.8,
            0.8,
            7,
            2,
            2,
            1,
            &params,
            &ships,
            &costs,
            &rollout,
        )
        .expect("b");
        assert_eq!(a.scored_profit, b.scored_profit);
    }

    #[test]
    fn rollout_smoke_finite_profit() {
        let ships = [ShipmentTrace::smoke_cool()];
        let params = ModelParams::default();
        let costs = AlphaTuneCosts::default();
        let rollout = AlphaTuneRolloutBudgets::default();
        let ep = run_alpha_tune_episode(
            AlphaTuneArm::Rollout,
            0.9,
            0.8,
            42,
            2,
            3,
            1,
            &params,
            &ships,
            &costs,
            &rollout,
        )
        .expect("rollout episode");
        assert!(ep.scored_profit.is_finite());
    }

    #[test]
    fn rollout_tune_best_in_ci_grid() {
        let ships = [ShipmentTrace::smoke_cool()];
        let params = ModelParams::default();
        let costs = AlphaTuneCosts::default();
        let rollout = AlphaTuneRolloutBudgets::default();
        let grid = [0.7, 0.8, 0.9];
        let mut best_alpha = grid[0];
        let mut best_profit = f64::NEG_INFINITY;
        for alpha in grid {
            let ep = run_alpha_tune_episode(
                AlphaTuneArm::Rollout,
                alpha,
                0.8,
                99,
                2,
                3,
                1,
                &params,
                &ships,
                &costs,
                &rollout,
            )
            .expect("grid point");
            if ep.scored_profit > best_profit {
                best_profit = ep.scored_profit;
                best_alpha = alpha;
            }
        }
        assert!(grid.contains(&best_alpha));
        assert!(best_profit.is_finite());
    }
}
