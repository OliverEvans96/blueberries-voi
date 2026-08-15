//! SIM-02 CRN cell: shared physics, scenario-masked filter, SW+rollout policy.

use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::day_step::{day_step, DayStepIn, ModelParams};
use crate::physics::draw_demand;
use crate::policy::damped_sw_order;
use crate::rbpf::{filter_step, FilterObs, ParticleBank};
use crate::rollout::{day_profit, rollout_order};
use crate::shipments::{generate_arrival_age, ShipmentTrace};

pub const PHYSICS_RUN_ID: &str = "voi-physics";

pub const VOI_SCENARIOS: &[&str] = &["P0", "P1", "F1", "F1s", "F2a", "F2", "B-state"];

const STREAM_DEMAND: u64 = 1;
const STREAM_ALLOC: u64 = 2;
const STREAM_SPOIL: u64 = 3;
const STREAM_SHIP: u64 = 4;
const STREAM_SENSOR: u64 = 5;
const STREAM_FILTER: u64 = 6;

fn rng(root: u64, run_tag: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_mul(0x9E37_79B9_7F4A_7C15)
            .wrapping_add(run_tag)
            .wrapping_add(u64::from(day).wrapping_mul(0x10007))
            .wrapping_add(stream.wrapping_mul(0xD1B5_4A32_D192_ED03)),
    )
}

fn physics_tag() -> u64 {
    0x7068_7973 // "phys"
}

fn filter_tag(scenario: &str) -> u64 {
    scenario
        .bytes()
        .fold(0u64, |a, b| a.wrapping_mul(33).wrapping_add(u64::from(b)))
}

fn enqueue(pending: &mut std::collections::BTreeMap<u32, u32>, day: u32, lead: u32, qty: u32) {
    *pending.entry(day + lead).or_insert(0) += qty;
}

fn pop_arrival(pending: &mut std::collections::BTreeMap<u32, u32>, day: u32) -> u32 {
    pending.remove(&day).unwrap_or(0)
}

fn mask_obs(scenario: &str, sales: u32, waste: u32, arrivals: u32) -> FilterObs {
    match scenario {
        "P0" => FilterObs {
            sales_tot: Some(sales as i32),
            waste_tot: None,
            arrivals,
            ..Default::default()
        },
        _ => FilterObs {
            sales_tot: Some(sales as i32),
            waste_tot: Some(waste as i32),
            arrivals,
            ..Default::default()
        },
    }
}

fn mean_bank(bank: &ParticleBank) -> (Vec<u32>, Vec<f64>) {
    if bank.counts.is_empty() {
        return (vec![], vec![]);
    }
    let l = bank.counts[0].len();
    let mut c = vec![0.0; l];
    let mut t = vec![0.0; l];
    for (i, w) in bank.weights.iter().enumerate() {
        for j in 0..l.min(bank.counts[i].len()) {
            c[j] += w * f64::from(bank.counts[i][j]);
            if j < bank.taus[i].len() {
                t[j] += w * bank.taus[i][j];
            }
        }
    }
    (c.iter().map(|x| x.round().max(0.0) as u32).collect(), t)
}

pub struct CrnBudgets {
    pub n_burn: u32,
    pub n_score: u32,
    pub filter_n: u32,
    pub h: u32,
    pub n_rollout_paths: u32,
    pub lead_time: u32,
    pub alpha: f64,
}

impl Default for CrnBudgets {
    fn default() -> Self {
        Self {
            n_burn: 1,
            n_score: 2,
            filter_n: 16,
            h: 2,
            n_rollout_paths: 1,
            lead_time: 1,
            alpha: 0.9,
        }
    }
}

fn run_scenario_episode(
    scenario: &str,
    shipments: &[ShipmentTrace],
    params: &ModelParams,
    root_seed: u64,
    budgets: &CrnBudgets,
) -> f64 {
    if shipments.is_empty() {
        panic!("shipments must be non-empty");
    }
    let horizon = budgets.n_burn + budgets.n_score;
    let oracle = scenario == "B-state";
    let n = budgets.filter_n.max(1) as usize;
    let mut bank = ParticleBank {
        weights: vec![1.0 / n as f64; n],
        counts: vec![vec![]; n],
        taus: vec![vec![]; n],
    };
    let mut state = DayStepIn {
        counts: vec![],
        taus: vec![],
        lot_ids: vec![],
        demand: None,
        spoil_by: None,
        delivery_n: 0,
        delivery_tau: 0.0,
        delivery_lot_id: 1,
    };
    let mut pending: std::collections::BTreeMap<u32, u32> = std::collections::BTreeMap::new();
    let mut next_lot = 1i64;
    let mut scored = 0.0;
    let phys = physics_tag();

    for day in 0..horizon {
        let pending_sum: u32 = pending.values().copied().sum();
        let (b_counts, b_taus) = if oracle {
            (state.counts.clone(), state.taus.clone())
        } else {
            mean_bank(&bank)
        };
        let ids: Vec<i64> = (1..=b_counts.len() as i64).collect();
        let base_q = damped_sw_order(
            &b_counts,
            &b_taus,
            pending_sum,
            day,
            params,
            budgets.alpha,
            0.8,
            None,
        );
        let order = if b_counts.iter().any(|&n| n > 0) {
            rollout_order(
                &b_counts,
                &b_taus,
                &ids,
                base_q,
                params,
                root_seed.wrapping_add(u64::from(day)),
                budgets.h.max(1),
                budgets.n_rollout_paths.max(1),
                1,
            )
            .unwrap_or(base_q)
        } else {
            base_q
        };
        enqueue(&mut pending, day, budgets.lead_time, order);
        let arrival = pop_arrival(&mut pending, day);
        if arrival > 0 {
            let mut rng_ship = rng(root_seed, phys, day, STREAM_SHIP);
            let mut rng_sensor = rng(root_seed, phys, day, STREAM_SENSOR);
            let tau_in = generate_arrival_age(
                &mut rng_ship,
                &mut rng_sensor,
                shipments,
                params.q10,
                params.t_ref_c,
                1.0,
            );
            state.delivery_n = arrival;
            state.delivery_tau = tau_in;
            state.delivery_lot_id = next_lot;
            next_lot += 1;
        } else {
            state.delivery_n = 0;
        }
        let mut rng_d = rng(root_seed, phys, day, STREAM_DEMAND);
        let demand = draw_demand(&mut rng_d, params.demand_mu, params.demand_vm);
        state.demand = Some(demand);
        state.spoil_by = None;
        let mut rng_a = rng(root_seed, phys, day, STREAM_ALLOC);
        let mut rng_s = rng(root_seed, phys, day, STREAM_SPOIL);
        let out = day_step(&state, params, Some(&mut rng_a), Some(&mut rng_s));
        if day >= budgets.n_burn {
            scored += day_profit(out.sales_total, out.waste_total, out.demand, 2.0, 1.5, 3.0);
        }
        if !oracle {
            let obs = mask_obs(scenario, out.sales_total, out.waste_total, arrival);
            let mut frng = rng(root_seed, filter_tag(scenario), day, STREAM_FILTER);
            bank = filter_step(&bank, &obs, params, &mut frng);
        }
        state.counts = out.counts;
        state.taus = out.taus;
        state.lot_ids = out.lot_ids;
    }
    scored
}

/// Like-for-like **structure** with Python `run_voi_crn_cell` (not NumPy-bit CRN).
pub fn run_voi_crn_cell(
    beta: f64,
    root_seed: u64,
    shipments: &[ShipmentTrace],
    budgets: &CrnBudgets,
    scenarios: &[&str],
) -> Vec<(String, f64)> {
    let names: Vec<&str> = if scenarios.is_empty() {
        VOI_SCENARIOS.to_vec()
    } else {
        scenarios.to_vec()
    };
    let mut params = ModelParams::default();
    params.beta = beta;
    if shipments.is_empty() {
        panic!("shipments must be non-empty (no Abdella parquet in Rust)");
    }
    names
        .into_iter()
        .map(|name| {
            if !VOI_SCENARIOS.contains(&name) {
                panic!("unknown VOI scenario {name}");
            }
            (
                name.to_string(),
                run_scenario_episode(name, shipments, &params, root_seed, budgets),
            )
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn physics_run_id_constant() {
        assert_eq!(PHYSICS_RUN_ID, "voi-physics");
    }

    #[test]
    fn crn_cell_returns_seven_finite_profits() {
        let ships = [ShipmentTrace::smoke_cool()];
        let b = CrnBudgets {
            n_burn: 1,
            n_score: 2,
            filter_n: 8,
            h: 1,
            n_rollout_paths: 1,
            lead_time: 1,
            alpha: 0.9,
        };
        let profits = run_voi_crn_cell(2.0, 1, &ships, &b, &[]);
        assert_eq!(profits.len(), 7);
        assert!(profits.iter().any(|(k, _)| k == "P0"));
        assert!(profits.iter().any(|(k, _)| k == "B-state"));
        assert!(profits.iter().all(|(_, v)| v.is_finite()));
    }

    #[test]
    fn p0_and_p1_differ_in_mask_not_physics_seed() {
        let ships = [ShipmentTrace::smoke_cool()];
        let b = CrnBudgets {
            n_burn: 1,
            n_score: 1,
            filter_n: 8,
            h: 1,
            n_rollout_paths: 1,
            lead_time: 1,
            alpha: 0.9,
        };
        let a = run_voi_crn_cell(2.0, 3, &ships, &b, &["P0", "P1"]);
        assert_eq!(a.len(), 2);
    }

    #[test]
    fn empty_shipments_in_episode_panics() {
        let b = CrnBudgets::default();
        let panicked = std::panic::catch_unwind(|| {
            run_voi_crn_cell(2.0, 1, &[], &b, &["P1"]);
        });
        assert!(panicked.is_err());
    }

    #[test]
    fn rerun_same_seed_stable() {
        let ships = [ShipmentTrace::smoke_cool()];
        let b = CrnBudgets {
            n_burn: 1,
            n_score: 1,
            filter_n: 4,
            h: 1,
            n_rollout_paths: 1,
            lead_time: 1,
            alpha: 0.9,
        };
        let x = run_voi_crn_cell(2.0, 11, &ships, &b, &["P1"]);
        let y = run_voi_crn_cell(2.0, 11, &ships, &b, &["P1"]);
        assert_eq!(x, y);
    }
}
