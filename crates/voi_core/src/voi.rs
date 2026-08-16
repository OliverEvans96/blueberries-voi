//! SIM-02 CRN cell: shared physics, scenario-masked filter, SW+rollout policy.

use rand::Rng;
use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::belief_flat::particle_bank_to_flat;
use crate::day_step::{day_step, DayStepIn, ModelParams};
use crate::demand_profile::DemandProfile;
use crate::obs::{mask_for, RichDay};
use crate::physics::{draw_demand, weibull_survival};
use crate::policy::{case_round, damped_sw_order, protection_demand_quantile};
use crate::particle_filter::{filter_step, ParticleBank};
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

const FILTER_INIT_L: usize = 3;
const FILTER_INIT_K: usize = 8;

fn init_filter_bank(n: usize, root_seed: u64, scenario: &str) -> ParticleBank {
    let tau_grid: Vec<f64> = if FILTER_INIT_K <= 1 {
        vec![0.0]
    } else {
        (0..FILTER_INIT_K)
            .map(|i| 8.0 * i as f64 / (FILTER_INIT_K - 1) as f64)
            .collect()
    };
    let mut frng = rng(root_seed, filter_tag(scenario), 0, STREAM_FILTER);
    let mut counts = Vec::with_capacity(n);
    let mut taus = Vec::with_capacity(n);
    for _ in 0..n {
        let mut c = Vec::with_capacity(FILTER_INIT_L);
        let mut t = Vec::with_capacity(FILTER_INIT_L);
        for _ in 0..FILTER_INIT_L {
            c.push(frng.random_range(0..8));
            t.push(tau_grid[frng.random_range(0..FILTER_INIT_K)]);
        }
        counts.push(c);
        taus.push(t);
    }
    ParticleBank {
        weights: vec![1.0 / n as f64; n],
        counts,
        taus,
    }
}

fn effective_inventory_from_bank(
    bank: &ParticleBank,
    pending_sum: u32,
    params: &ModelParams,
) -> f64 {
    let flat = particle_bank_to_flat(bank, FILTER_INIT_L, FILTER_INIT_K);
    let lot_counts = flat["lot_counts"].as_array().expect("lot_counts");
    let age_marginals = flat["age_marginals"].as_array().expect("age_marginals");
    let grid = flat["tau_grid"].as_array().expect("tau_grid");
    let mut on_hand = 0.0;
    for slot in 0..FILTER_INIT_L {
        let n = lot_counts[slot].as_f64().unwrap_or(0.0);
        if n <= 0.0 {
            continue;
        }
        for k in 0..FILTER_INIT_K {
            let p = age_marginals[slot * FILTER_INIT_K + k].as_f64().unwrap_or(0.0);
            let tau = grid[k].as_f64().unwrap_or(0.0);
            on_hand += n * p * weibull_survival(tau, params.beta, params.eta_ref);
        }
    }
    let pipeline_w = weibull_survival(0.0, params.beta, params.eta_ref);
    on_hand + f64::from(pending_sum) * pipeline_w
}

fn damped_sw_from_bank(
    bank: &ParticleBank,
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    alpha: f64,
    rho: f64,
) -> u32 {
    let _ = day;
    let i_tilde = effective_inventory_from_bank(bank, pending_sum, params);
    let d_star = protection_demand_quantile(alpha, params, 2);
    let raw = rho * (d_star - i_tilde).max(0.0);
    case_round(raw, params.case_size)
}

/// ShelfBelief-style counts and marginal-mean taus for rollout (ADR 0106).
fn ordering_belief_from_bank(bank: &ParticleBank) -> (Vec<u32>, Vec<f64>) {
    if bank.counts.is_empty() || bank.counts.iter().all(|row| row.is_empty()) {
        return (vec![], vec![]);
    }
    let flat = particle_bank_to_flat(bank, FILTER_INIT_L, FILTER_INIT_K);
    let lot_counts = flat["lot_counts"].as_array().expect("lot_counts");
    let age_marginals = flat["age_marginals"].as_array().expect("age_marginals");
    let grid = flat["tau_grid"].as_array().expect("tau_grid");
    let k = grid.len();
    let counts: Vec<u32> = lot_counts
        .iter()
        .map(|c| c.as_f64().unwrap_or(0.0).ceil().max(0.0) as u32)
        .collect();
    let mut taus = Vec::with_capacity(FILTER_INIT_L);
    for slot in 0..FILTER_INIT_L {
        let mut exp_tau = 0.0;
        let mut mass = 0.0;
        for bin in 0..k {
            let p = age_marginals[slot * k + bin].as_f64().unwrap_or(0.0);
            exp_tau += p * grid[bin].as_f64().unwrap_or(0.0);
            mass += p;
        }
        taus.push(if mass > 0.0 { exp_tau / mass } else { 0.0 });
    }
    (counts, taus)
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
    let mut bank = if oracle || scenario == "P0" {
        ParticleBank {
            weights: vec![1.0 / n as f64; n],
            counts: vec![vec![]; n],
            taus: vec![vec![]; n],
        }
    } else {
        init_filter_bank(n, root_seed, scenario)
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
            ordering_belief_from_bank(&bank)
        };
        let ids: Vec<i64> = (1..=b_counts.len().max(1) as i64).collect();
        let base_q = if oracle {
            damped_sw_order(
                &b_counts,
                &b_taus,
                pending_sum,
                day,
                params,
                budgets.alpha,
                0.8,
                None,
            )
        } else {
            damped_sw_from_bank(&bank, pending_sum, day, params, budgets.alpha, 0.8)
        };
        let order = if oracle && b_counts.iter().any(|&n| n > 0) || !oracle {
            rollout_order(
                &b_counts,
                &b_taus,
                &ids,
                base_q,
                params,
                root_seed.wrapping_add(u64::from(day)),
                budgets.h.max(1),
                budgets.n_rollout_paths.max(1),
                budgets.candidate_case_radius,
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
        let demand = draw_demand(&mut rng_d, params, Some(day));
        state.demand = Some(demand);
        state.spoil_by = None;
        let pre_lot_ids = state.lot_ids.clone();
        let mut rng_a = rng(root_seed, phys, day, STREAM_ALLOC);
        let mut rng_s = rng(root_seed, phys, day, STREAM_SPOIL);
        let out = day_step(&state, params, Some(&mut rng_a), Some(&mut rng_s));
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
                age_at_receipt: if arrival > 0 {
                    Some(state.delivery_tau)
                } else {
                    None
                },
                pack_date_days: if arrival > 0 {
                    Some(state.delivery_tau.round() as i32)
                } else {
                    None
                },
            };
            let obs = mask_for(scenario).expect("valid VOI filter scenario").apply(&rich);
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
    fn init_filter_bank_yields_nonempty_ordering_belief() {
        let bank = init_filter_bank(8, 42, "P0");
        let (c, t) = ordering_belief_from_bank(&bank);
        assert_eq!(c.len(), FILTER_INIT_L);
        assert_eq!(t.len(), FILTER_INIT_L);
        assert!(c.iter().any(|&n| n > 0), "counts {c:?} taus {t:?}");
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
        let profits = run_voi_crn_cell(2.0, 42, &ships, &b, &["P0", "F1"], None);
        let p0 = profits.iter().find(|(k, _)| k == "P0").unwrap().1;
        let f1 = profits.iter().find(|(k, _)| k == "F1").unwrap().1;
        assert!(
            (p0 - f1).abs() > 1e-6,
            "P0 and F1 must differ under masks (p0={p0}, f1={f1})"
        );
    }

    #[test]
    fn p1_and_f2_profits_differ_on_seed_42() {
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
        let profits = run_voi_crn_cell(2.0, 42, &ships, &b, &["P1", "F2"], None);
        let p1 = profits.iter().find(|(k, _)| k == "P1").unwrap().1;
        let f2 = profits.iter().find(|(k, _)| k == "F2").unwrap().1;
        assert!(
            (p1 - f2).abs() > 1e-6,
            "P1 and F2 must differ under masks (p1={p1}, f2={f2})"
        );
    }

    #[test]
    fn candidate_case_radius_changes_rollout_order() {
        let params = ModelParams::default();
        let counts = vec![40u32, 20];
        let taus = vec![1.0, 3.0];
        let lot_ids = vec![1i64, 2];
        let base_q = 24u32;
        let seed = 99u64;
        let narrow = rollout_order(
            &counts,
            &taus,
            &lot_ids,
            base_q,
            &params,
            seed,
            2,
            2,
            0,
        )
        .expect("radius 0");
        let wide = rollout_order(
            &counts,
            &taus,
            &lot_ids,
            base_q,
            &params,
            seed,
            2,
            2,
            2,
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
