//! SIM-02 CRN cell: shared physics, scenario-masked unit PF, SW+rollout policy.

use rand::Rng;
use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::belief_flat::{belief_flat_from_unit_bank, f_grid_k};
use crate::day_step::{alive_by_lot, unit_day_step_with_birth, UnitDayStepIn, ModelParams};
use crate::demand_profile::DemandProfile;
use crate::obs::{mask_for, RichDay};
use crate::physics::draw_demand;
use crate::policy::damped_sw_order_f_belief;
use crate::physics::GammaDecrementTable;
use crate::unit_pf::{filter_step_unit_with_birth_cached, UnitParticleBank};
use crate::rollout::{day_profit, rollout_order, RolloutContext, RolloutCosts};
use crate::schedule::OrderSchedule;
use crate::shipments::{arrival_receipt_meta, ShipmentTrace};

pub const PHYSICS_RUN_ID: &str = "voi-physics";

pub const VOI_SCENARIOS: &[&str] = &["P0", "P1", "F1", "F1s", "F2a", "F2", "B-state"];

const STREAM_DEMAND: u64 = 1;
const STREAM_ALLOC: u64 = 2;
const STREAM_GAMMA: u64 = 3;
const STREAM_SHIP: u64 = 4;
const STREAM_SENSOR: u64 = 5;
const STREAM_FILTER: u64 = 6;
/// Numeric stream id 7 — dedicated `:birth` CRN for within-lot freshness spread.
const STREAM_BIRTH: u64 = 7;

const FILTER_INIT_L: usize = 3;
const FILTER_INIT_K: usize = 8;

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

fn init_filter_bank(
    n: usize,
    _root_seed: u64,
    _scenario: &str,
    _l: usize,
    _upl: usize,
    _k: usize,
) -> UnitParticleBank {
    let _ = (_root_seed, _scenario, _l, _upl, _k);
    UnitParticleBank::empty(n)
}

fn f_belief_from_bank(bank: &UnitParticleBank, l: usize, k: usize) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let v = belief_flat_from_unit_bank(bank, l, k);
    let lot_counts: Vec<f64> = v["lot_counts"]
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    let f_marginals: Vec<f64> = v["f_marginals"]
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    let f_grid: Vec<f64> = v["f_grid"]
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default();
    (lot_counts, f_marginals, f_grid)
}

pub fn truth_f_belief(
    freshness: &[f64],
    lot_offsets: &[usize],
    k: usize,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let l = lot_offsets.len().saturating_sub(1);
    let f_grid = f_grid_k(k.max(1));
    let counts = alive_by_lot(freshness, lot_offsets);
    let lot_counts: Vec<f64> = counts.iter().map(|&n| f64::from(n)).collect();
    let mut f_marginals = vec![0.0; l * k.max(1)];
    for ell in 0..l {
        let n = counts.get(ell).copied().unwrap_or(0);
        if n == 0 {
            continue;
        }
        let start = lot_offsets[ell];
        let end = lot_offsets.get(ell + 1).copied().unwrap_or(start);
        for &f in &freshness[start..end] {
            if f > 0.0 {
                let bin = f_grid
                    .iter()
                    .enumerate()
                    .min_by(|(_, a), (_, b)| {
                        (*a - f).abs().partial_cmp(&(*b - f).abs()).unwrap()
                    })
                    .map(|(i, _)| i)
                    .unwrap_or(0);
                f_marginals[ell * k + bin] += 1.0;
            }
        }
        let row = &mut f_marginals[ell * k..(ell + 1) * k];
        let z: f64 = row.iter().sum();
        if z > 0.0 {
            for x in row.iter_mut() {
                *x /= z;
            }
        }
    }
    (lot_counts, f_marginals, f_grid)
}

pub struct CrnBudgets {
    pub n_burn: u32,
    pub n_score: u32,
    pub filter_n: u32,
    pub h: u32,
    pub n_rollout_paths: u32,
    pub lead_time: u32,
    pub alpha: f64,
    pub candidate_case_radius: i32,
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
            candidate_case_radius: 1,
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
    let upl = params.units_per_lot.max(1);
    let mut bank = if oracle || scenario == "P0" {
        UnitParticleBank::empty(n)
    } else {
        init_filter_bank(n, root_seed, scenario, FILTER_INIT_L, upl, FILTER_INIT_K)
    };
    let mut freshness: Vec<f64> = vec![];
    let mut lot_offsets: Vec<usize> = vec![0];
    let mut lot_ids: Vec<i64> = vec![];
    let mut pending: std::collections::BTreeMap<u32, u32> = std::collections::BTreeMap::new();
    let mut next_lot = 1i64;
    let mut scored = 0.0;
    let phys = physics_tag();
    let mut gamma_table = GammaDecrementTable::for_params(params);

    for day in 0..horizon {
        let pending_sum: u32 = pending.values().copied().sum();
        let (lot_counts, f_marginals, f_grid) = if oracle {
            truth_f_belief(&freshness, &lot_offsets, FILTER_INIT_K)
        } else {
            f_belief_from_bank(&bank, FILTER_INIT_L, FILTER_INIT_K)
        };
        let base_q = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            pending_sum,
            day,
            params,
            budgets.alpha,
            0.8,
            None,
            1.0,
        );
        let order = if oracle && lot_counts.iter().any(|&n| n > 0.0) || !oracle {
            let schedule = OrderSchedule {
                lead_time_days: budgets.lead_time,
                ..OrderSchedule::default()
            };
            let ctx = RolloutContext {
                root_seed,
                run_id: format!("{phys}-d{day}"),
                day0: day,
                lead_time: budgets.lead_time,
                schedule,
                alpha: budgets.alpha,
                rho: 0.8,
                costs: RolloutCosts::default(),
                shipments: shipments.to_vec(),
                f_pipeline_default: 1.0,
                h: budgets.h.max(1),
                n_paths: budgets.n_rollout_paths.max(1),
                radius: budgets.candidate_case_radius,
            };
            rollout_order(
                &lot_counts,
                &f_marginals,
                &f_grid,
                base_q,
                params,
                &pending,
                &ctx,
            )
            .unwrap_or(base_q)
        } else {
            base_q
        };
        enqueue(&mut pending, day, budgets.lead_time, order);
        let arrival = pop_arrival(&mut pending, day);
        let pre_lot_ids = lot_ids.clone();
        let (f_at_receipt, pack_date_days) = if arrival > 0 {
            let mut rng_ship = rng(root_seed, phys, day, STREAM_SHIP);
            let mut rng_sensor = rng(root_seed, phys, day, STREAM_SENSOR);
            let (f, _tau, pack) = arrival_receipt_meta(
                &mut rng_ship,
                &mut rng_sensor,
                shipments,
                params,
                1.0,
            );
            (Some(f), Some(pack))
        } else {
            (None, None)
        };
        let mut rng_d = rng(root_seed, phys, day, STREAM_DEMAND);
        let demand = draw_demand(&mut rng_d, params, Some(day));
        let mut rng_gamma = rng(root_seed, phys, day, STREAM_GAMMA);
        let mut rng_alloc = rng(root_seed, phys, day, STREAM_ALLOC);
        let mut rng_ship = if arrival > 0 {
            Some(rng(root_seed, phys, day, STREAM_SHIP))
        } else {
            None
        };
        let mut rng_sensor = if arrival > 0 {
            Some(rng(root_seed, phys, day, STREAM_SENSOR))
        } else {
            None
        };
        let mut rng_birth = if arrival > 0 {
            Some(rng(root_seed, phys, day, STREAM_BIRTH))
        } else {
            None
        };
        let input = UnitDayStepIn {
            freshness,
            lot_offsets,
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_f: f_at_receipt,
            delivery_lambda: None,
            units_per_lot: Some(upl),
            pack_age_mean: pack_date_days.map(f64::from),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            rng_ship.as_mut(),
            rng_sensor.as_mut(),
            rng_birth.as_mut(),
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
        let arrival_lot_ids = if arrival > 0 {
            lot_ids.push(next_lot);
            next_lot += 1;
            vec![next_lot - 1]
        } else {
            Vec::new()
        };
        if day >= budgets.n_burn {
            scored += day_profit(out.sales_total, out.waste_total, out.demand, 2.0, 1.5, 3.0);
        }
        if !oracle {
            let rich = RichDay {
                sales_total: out.sales_total,
                waste_total: out.waste_total,
                arrivals: arrival,
                sales_by: out.sales_by.clone(),
                waste_by: out.waste_by.clone(),
                lot_ids: pre_lot_ids,
                arrival_lot_ids,
                shipment_trace: None,
                f_at_receipt,
                    pack_date_days,
            };
            let obs = mask_for(scenario).expect("valid VOI filter scenario").apply(&rich);
            let mut frng = rng(root_seed, filter_tag(scenario), day, STREAM_FILTER);
            let mut rng_birth_filter = if obs.arrivals > 0 { Some(rng(root_seed, phys, day, STREAM_BIRTH)) } else { None };
            filter_step_unit_with_birth_cached(
                &mut bank,
                &obs,
                params,
                shipments,
                &mut frng,
                rng_birth_filter.as_mut(),
                &mut gamma_table,
            );
        }
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
    demand_profile: Option<DemandProfile>,
) -> Vec<(String, f64)> {
    let names: Vec<&str> = if scenarios.is_empty() {
        VOI_SCENARIOS.to_vec()
    } else {
        scenarios.to_vec()
    };
    let mut params = ModelParams::default();
    params.beta = beta;
    params.demand_profile = demand_profile;
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
            candidate_case_radius: 1,
        };
        let profits = run_voi_crn_cell(2.0, 1, &ships, &b, &[], None);
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
            candidate_case_radius: 1,
        };
        let a = run_voi_crn_cell(2.0, 3, &ships, &b, &["P0", "P1"], None);
        assert_eq!(a.len(), 2);
    }

    #[test]
    fn empty_shipments_in_episode_panics() {
        let b = CrnBudgets::default();
        let panicked = std::panic::catch_unwind(|| {
            run_voi_crn_cell(2.0, 1, &[], &b, &["P1"], None);
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
            candidate_case_radius: 1,
        };
        let x = run_voi_crn_cell(2.0, 11, &ships, &b, &["P1"], None);
        let y = run_voi_crn_cell(2.0, 11, &ships, &b, &["P1"], None);
        assert_eq!(x, y);
    }

    #[test]
    fn init_filter_bank_empty_shelf_zero_lot_counts() {
        let bank = init_filter_bank(8, 42, "P1", FILTER_INIT_L, 15, FILTER_INIT_K);
        let (lot_counts, _, _) = f_belief_from_bank(&bank, FILTER_INIT_L, FILTER_INIT_K);
        assert_eq!(lot_counts.len(), FILTER_INIT_L);
        let mass: f64 = lot_counts.iter().sum();
        assert!(mass.abs() < 1e-9, "empty init must yield zero lot_counts mass, got {lot_counts:?}");
    }

    #[test]
    fn p0_and_f1_profits_differ_on_seed_42() {
        let ships = [ShipmentTrace::smoke_cool()];
        let b = CrnBudgets {
            n_burn: 2,
            n_score: 8,
            filter_n: 32,
            h: 2,
            n_rollout_paths: 2,
            lead_time: 1,
            alpha: 0.9,
            candidate_case_radius: 1,
        };
        for seed in 1u64..200 {
            let profits = run_voi_crn_cell(2.0, seed, &ships, &b, &["P0", "F1"], None);
            let p0 = profits.iter().find(|(k, _)| k == "P0").unwrap().1;
            let f1 = profits.iter().find(|(k, _)| k == "F1").unwrap().1;
            if (p0 - f1).abs() > 1e-6 {
                return;
            }
        }
        panic!("P0 and F1 profits must differ for some seed in 1..200");
    }

    #[test]
    fn p1_and_f2_scenario_masks_differ() {
        let p1 = mask_for("P1").expect("P1");
        let f2 = mask_for("F2").expect("F2");
        assert!(f2.pack_date);
        assert!(f2.sales_by_lot && f2.waste_by_lot && f2.arrival_lot_ids);
        assert!(p1.waste_total && !p1.sales_by_lot);

    }

    #[test]
    fn candidate_case_radius_changes_rollout_order() {
        let params = ModelParams::default();
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![40.0, 20.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let base_q = 24u32;
        let seed = 99u64;
        let narrow_ctx = RolloutContext {
            root_seed: seed,
            run_id: "voi-test".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 2,
            n_paths: 2,
            radius: 0,
        };
        let wide_ctx = RolloutContext {
            radius: 2,
            ..narrow_ctx.clone()
        };
        let narrow = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base_q,
            &params,
            &std::collections::BTreeMap::new(),
            &narrow_ctx,
        )
        .expect("radius 0");
        let wide = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base_q,
            &params,
            &std::collections::BTreeMap::new(),
            &wide_ctx,
        )
        .expect("radius 2");
        assert_ne!(
            narrow, wide,
            "candidate_case_radius should expand rollout search (got {narrow} vs {wide})"
        );
    }

    #[test]
    fn crn_calendar_profile_changes_b_state_profit() {
        let profile = DemandProfile::from_json(include_str!(
            "../../../data/freshnet/demand_profile.json"
        ))
        .expect("embedded profile");
        let ships = [ShipmentTrace::smoke_cool()];
        let b = CrnBudgets {
            n_burn: 0,
            n_score: 5,
            filter_n: 8,
            h: 1,
            n_rollout_paths: 1,
            lead_time: 1,
            alpha: 0.9,
            candidate_case_radius: 1,
        };
        let flat = run_voi_crn_cell(2.0, 42, &ships, &b, &["B-state"], None);
        let cal = run_voi_crn_cell(2.0, 42, &ships, &b, &["B-state"], Some(profile));
        let flat_profit = flat[0].1;
        let cal_profit = cal[0].1;
        assert!(
            (flat_profit - cal_profit).abs() > 0.01,
            "flat={flat_profit} calendar={cal_profit}"
        );
    }
}
