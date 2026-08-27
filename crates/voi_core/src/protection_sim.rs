//! Protection-window path simulator and window-SLA ordering models (ADR 0151).

use std::collections::BTreeMap;

use crate::arrival::{
    ArrivalModel, STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS,
    STREAM_ARRIVAL_TEMP,
};
use crate::day_step::{unit_day_step_with_birth, UnitDayStepIn};
use crate::params::ModelParams;
use crate::physics::{draw_demand_spawn, GammaDecrementTable};
use crate::policy::{case_round, damped_sw_order_f_belief};
use crate::schedule::OrderSchedule;
use crate::shipments::ShipmentTrace;
use crate::spawn_rng::SpawnRng;
use crate::unit_pf::{systematic_resample, UnitParticleBank};

pub const STREAM_SLA_DEMAND: &str = ":sla-demand";
pub const STREAM_SLA_SPOIL: &str = ":sla-spoil";
pub const STREAM_SLA_ALLOC: &str = ":sla-alloc";
pub const STREAM_SLA_BIRTH: &str = ":sla-birth";

/// Protection window anchored at `start_day` with `n_days` cover and delivery `lead_time`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ProtectionWindow {
    pub start_day: u32,
    pub n_days: u32,
    pub lead_time: u32,
}

/// Per-path protection rollout totals and window stockout indicator `M_i(q)`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ProtectionPathResult {
    pub waste_total: u32,
    pub missed_total: u32,
    /// `1` if any day in the window had unmet demand, else `0`.
    pub stockout_indicator: u32,
}

/// Window-SLA model: joint no-stockout probability for a candidate order quantity.
pub trait SlaModel {
    fn p_no_stockout(&self, q: u32) -> f64;
}

/// Picks one particle hypothesis for `path` and returns its freshness row and the bank's
/// real `lot_offsets` (not a synthetic uniform segmentation).
pub fn bank_start_state(bank: &UnitParticleBank, path: u32) -> (Vec<f64>, Vec<usize>) {
    let log_w: Vec<f64> = bank
        .weights
        .iter()
        .map(|w| if *w > 0.0 { w.ln() } else { f64::NEG_INFINITY })
        .collect();
    let indices = systematic_resample(&log_w);
    let pidx = indices[path as usize % indices.len().max(1)];
    let freshness = bank.freshness.get(pidx).cloned().unwrap_or_default();
    let lot_offsets = bank.lot_offsets.clone();
    (freshness, lot_offsets)
}

fn truth_delivery_units(
    arrival_model: &ArrivalModel,
    arrival: u32,
    root_seed: u64,
    path_run: &str,
    sim_day: u32,
    corridor_key: &str,
) -> Option<Vec<f64>> {
    if arrival == 0 {
        return None;
    }
    let mut rng_dur =
        SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_DURATION);
    let mut rng_temp = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_TEMP);
    let mut rng_pos = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_POS);
    let mut rng_gamma =
        SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_GAMMA);
    Some(
        arrival_model
            .draw_truth_delivery(
                corridor_key,
                arrival as usize,
                &mut rng_dur,
                &mut rng_temp,
                &mut rng_pos,
                &mut rng_gamma,
            )
            .unit_f,
    )
}

/// Advances one particle through `protection_days` of `unit_day_step`, injecting `order_q`
/// on the lead-time offset, with stochastic spoilage and real arrival freshness draws.
pub fn simulate_protection_path(
    start_freshness: &[f64],
    start_offsets: &[usize],
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    root_seed: u64,
    run_id: &str,
    path: u32,
    protection_days: u32,
    order_q: u32,
    lead_time: u32,
    current_day: u32,
) -> ProtectionPathResult {
    let mut freshness = start_freshness.to_vec();
    let mut lot_offsets = start_offsets.to_vec();
    let arrival_model = ArrivalModel::embedded();
    let upl = params.units_per_lot.max(1);
    let mut waste_total = 0u32;
    let mut missed_total = 0u32;
    let mut stockout_indicator = 0u32;
    let path_run = format!("{run_id}|p{path}");

    for d in 0..protection_days {
        let sim_day = current_day + d;
        let arrival = if d == lead_time {
            order_q
        } else {
            0
        };
        if d < lead_time || d - lead_time >= protection_days {
            // guard: only land pipeline within the modeled window
        }

        let mut rng_demand =
            SpawnRng::spawn_rng(root_seed, &path_run, sim_day, STREAM_SLA_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(sim_day));
        let mut rng_gamma = SpawnRng::spawn_rng(root_seed, &path_run, sim_day, STREAM_SLA_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(root_seed, &path_run, sim_day, STREAM_SLA_ALLOC);

        let delivery_unit_f = truth_delivery_units(
            &arrival_model,
            arrival,
            root_seed,
            &path_run,
            sim_day,
            &params.arrival_product,
        );
        let mut rng_birth = if arrival > 0 {
            Some(SpawnRng::spawn_rng(
                root_seed,
                &path_run,
                sim_day,
                STREAM_SLA_BIRTH,
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
            delivery_lot_f: None,
            units_per_lot: Some(upl),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        waste_total = waste_total.saturating_add(out.waste_total);
        let missed = out.demand.saturating_sub(out.sales_total);
        missed_total = missed_total.saturating_add(missed);
        if missed > 0 {
            stockout_indicator = 1;
        }
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }

    ProtectionPathResult {
        waste_total,
        missed_total,
        stockout_indicator,
    }
}

/// Materializes per-unit freshness from lot-level belief marginals (shared with rollout).
pub(crate) fn unit_state_from_f_belief(
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
    let mut rng_birth = SpawnRng::spawn_rng(root_seed, run_id, day, STREAM_SLA_BIRTH);
    let mut freshness = Vec::new();
    let mut lot_offsets = vec![0usize];
    for ell in 0..l {
        let n = lot_counts[ell].round().max(0.0) as usize;
        let alive = n.min(u);
        let dead = u.saturating_sub(alive);
        for _ in 0..alive {
            let start = ell * k;
            let mut total = 0.0;
            for bin in 0..k {
                total += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
            }
            let u_draw = if total > 0.0 {
                rng_birth.next_f64() * total
            } else {
                0.0
            };
            let mut cum = 0.0;
            let mut f = f_grid[k.saturating_sub(1)];
            for bin in 0..k {
                cum += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
                if u_draw <= cum {
                    f = f_grid[bin];
                    break;
                }
            }
            freshness.push(f.clamp(1e-12, 1.0));
        }
        for _ in 0..dead {
            freshness.push(0.0);
        }
        lot_offsets.push(freshness.len());
    }
    (freshness, lot_offsets)
}

/// Cached survival probabilities `P(survive k agings)` on the freshness grid.
#[derive(Clone, Debug)]
pub struct SurvivalCurveCache {
    table: GammaDecrementTable,
    curves: Vec<Vec<f64>>,
}

impl SurvivalCurveCache {
    pub fn for_params(params: &ModelParams, max_agings: usize) -> Self {
        let table = GammaDecrementTable::for_params(params);
        let grid = GammaDecrementTable::GRID;
        let mut curves = Vec::with_capacity(max_agings + 1);
        curves.push(vec![1.0; grid]);
        for agings in 1..=max_agings {
            let mut row = Vec::with_capacity(grid);
            for i in 0..grid {
                let f0 = i as f64 / (grid - 1) as f64;
                row.push(survival_after_agings(&table, f0, agings));
            }
            curves.push(row);
        }
        Self { table, curves }
    }

    pub fn rebuild_if_needed(&mut self, params: &ModelParams, max_agings: usize) {
        if !self.table.matches_params(params) || self.curves.len() <= max_agings + 1 {
            *self = Self::for_params(params, max_agings);
        }
    }

    /// `agings` counts spoil draws; day `j` sellable units use `j + 1`.
    pub fn survival_at(&self, f: f64, agings: usize) -> f64 {
        if f <= 0.0 || agings == 0 {
            return if f > 0.0 { 1.0 } else { 0.0 };
        }
        let idx = (f * (GammaDecrementTable::GRID - 1) as f64).round() as usize;
        let i = idx.min(GammaDecrementTable::GRID - 1);
        self.curves
            .get(agings)
            .and_then(|row| row.get(i))
            .copied()
            .unwrap_or(0.0)
    }

    pub fn table(&self) -> &GammaDecrementTable {
        &self.table
    }
}

fn survival_after_agings(table: &GammaDecrementTable, f0: f64, agings: usize) -> f64 {
    if f0 <= 0.0 {
        return 0.0;
    }
    let mut surv = 1.0;
    let mut f = f0;
    for _ in 0..agings {
        let p_die = table.spoil_prob(f);
        surv *= (1.0 - p_die);
        f = (f - table.quantile(0.5)).max(0.0);
    }
    surv.clamp(0.0, 1.0)
}

fn nb_cdf_le(k: u32, mu: f64, vm: f64) -> f64 {
    if k == 0 {
        return if mu <= 0.0 { 1.0 } else { (vm - 1.0) / vm };
    }
    let r = mu / (vm - 1.0);
    let p = r / (r + mu);
    let mut pmf = p.powf(r);
    let mut cdf = pmf;
    let mut j = 0u32;
    while j < k {
        j += 1;
        pmf *= (r + f64::from(j) - 1.0) / f64::from(j) * (1.0 - p);
        cdf += pmf;
        if !cdf.is_finite() {
            break;
        }
    }
    cdf.clamp(0.0, 1.0)
}

fn alive_count_pmf(spoil_probs: &[f64]) -> Vec<f64> {
    let n = spoil_probs.len();
    if n == 0 {
        return vec![1.0];
    }
    let mut death_pmf = vec![0.0f64; n + 1];
    death_pmf[0] = 1.0;
    for &p in spoil_probs {
        let p = p.clamp(0.0, 1.0);
        let mut next = vec![0.0; n + 1];
        for j in 0..=n {
            if death_pmf[j] == 0.0 {
                continue;
            }
            next[j] += death_pmf[j] * (1.0 - p);
            if j + 1 <= n {
                next[j + 1] += death_pmf[j] * p;
            }
        }
        death_pmf = next;
    }
    let mut alive = vec![0.0; n + 1];
    for (deaths, pd) in death_pmf.iter().enumerate() {
        alive[n - deaths] += *pd;
    }
    alive
}

/// Monte Carlo window-SLA oracle with CRN paths.
pub struct McSlaModel<'a> {
    pub freshness: Vec<f64>,
    pub lot_offsets: Vec<usize>,
    pub pending: BTreeMap<u32, u32>,
    pub window: ProtectionWindow,
    pub params: &'a ModelParams,
    pub shipments: &'a [ShipmentTrace],
    pub root_seed: u64,
    pub run_id: String,
    pub n_paths: u32,
}

impl McSlaModel<'_> {
    fn path_result(&self, q: u32, path: u32) -> ProtectionPathResult {
        simulate_protection_path(
            &self.freshness,
            &self.lot_offsets,
            self.params,
            self.shipments,
            self.root_seed,
            &self.run_id,
            path,
            self.window.n_days,
            q,
            self.window.lead_time,
            self.window.start_day,
        )
    }
}

impl SlaModel for McSlaModel<'_> {
    fn p_no_stockout(&self, q: u32) -> f64 {
        let n = self.n_paths.max(1);
        let mut ok = 0u32;
        for path in 0..n {
            if self.path_result(q, path).stockout_indicator == 0 {
                ok += 1;
            }
        }
        ok as f64 / n as f64
    }
}

/// Poisson-binomial + Fisher day-joint fast path.
pub struct PbSlaModel<'a> {
    pub lot_counts: Vec<f64>,
    pub f_marginals: Vec<f64>,
    pub f_grid: Vec<f64>,
    pub pending: BTreeMap<u32, u32>,
    pub pending_sum: u32,
    pub window: ProtectionWindow,
    pub params: &'a ModelParams,
    pub schedule: &'a OrderSchedule,
    pub f_pipeline: f64,
    pub survival: &'a SurvivalCurveCache,
}

impl PbSlaModel<'_> {
    fn unit_freshness_slots(&self, units_per_lot: usize) -> Vec<f64> {
        let (f, _) = unit_state_from_f_belief(
            &self.lot_counts,
            &self.f_marginals,
            &self.f_grid,
            units_per_lot,
            6,
            "pb-belief",
            self.window.start_day,
        );
        f
    }

    fn day_no_stockout_prob(&self, q: u32, day_offset: u32) -> f64 {
        let sim_day = self.window.start_day + day_offset;
        let upl = self.params.units_per_lot.max(1);
        let mut spoil_probs: Vec<f64> = self
            .unit_freshness_slots(upl)
            .iter()
            .filter(|&&f| f > 0.0)
            .map(|&f| {
                let agings = day_offset + 1;
                1.0 - self.survival.survival_at(f, agings as usize)
            })
            .collect();
        let pipeline = self.pending_sum
            + if day_offset == self.window.lead_time {
                q
            } else {
                0
            };
        if pipeline > 0 {
            for _ in 0..pipeline {
                spoil_probs.push(1.0 - self.survival.survival_at(self.f_pipeline, 1));
            }
        }
        let supply_pmf = alive_count_pmf(&spoil_probs);
        let mu = self.params.demand_mu_for_day(sim_day);
        let vm = self.params.demand_vm;
        let mut prob = 0.0;
        for (s, ps) in supply_pmf.iter().enumerate() {
            if *ps <= 0.0 {
                continue;
            }
            prob += *ps * nb_cdf_le(s as u32, mu, vm);
        }
        prob.clamp(0.0, 1.0)
    }
}

impl SlaModel for PbSlaModel<'_> {
    fn p_no_stockout(&self, q: u32) -> f64 {
        let mut joint = 1.0;
        for d in 0..self.window.n_days {
            joint *= self.day_no_stockout_prob(q, d);
        }
        joint.clamp(0.0, 1.0)
    }
}

/// Upper q bound aligned with [`crate::tradeoff::full_tradeoff_q_candidates`].
fn sla_order_q_cap(case_size: u32) -> u32 {
    let cs = case_size.max(1);
    160.max(cs * 20)
}

/// Minimal feasible `q` meeting `alpha`, damped by `rho` and case-rounded.
pub fn sla_order(model: &dyn SlaModel, alpha: f64, rho: f64, case_size: u32, q_hi_hint: u32) -> u32 {
    if !(0.0 < alpha && alpha < 1.0) {
        panic!("alpha must be in (0,1)");
    }
    let cs = case_size.max(1);
    let max_q = sla_order_q_cap(cs);
    let max_cases = (max_q / cs).max(1) as i32;
    let mut hi_cases = (q_hi_hint / cs).max(1) as i32;
    while hi_cases < max_cases && model.p_no_stockout(hi_cases as u32 * cs) < alpha {
        hi_cases = (hi_cases * 2).min(max_cases);
    }
    let mut lo = 0i32;
    let mut hi = hi_cases;
    while lo < hi {
        let mid = (lo + hi) / 2;
        let q = mid as u32 * cs;
        if model.p_no_stockout(q) >= alpha {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    let mut q_min = lo as u32 * cs;
    while q_min >= cs {
        let q_try = q_min - cs;
        if model.p_no_stockout(q_try) >= alpha {
            q_min = q_try;
        } else {
            break;
        }
    }
    case_round(rho * q_min as f64, cs)
}

pub fn sla_mc_order_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    pending: &BTreeMap<u32, u32>,
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    schedule: &OrderSchedule,
    shipments: &[ShipmentTrace],
    alpha: f64,
    rho: f64,
    root_seed: u64,
    n_paths: u32,
    f_pipeline_default: f64,
) -> u32 {
    if !schedule.can_order(day) {
        return 0;
    }
    let n_days = schedule.protection_days(day);
    let window = ProtectionWindow {
        start_day: day,
        n_days,
        lead_time: schedule.lead_time_days,
    };
    let upl = params.units_per_lot.max(1);
    let run_id = format!("sla-mc-d{day}");
    let (freshness, lot_offsets) = unit_state_from_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        upl,
        root_seed,
        &run_id,
        day,
    );
    let model = McSlaModel {
        freshness,
        lot_offsets,
        pending: pending.clone(),
        window,
        params,
        shipments,
        root_seed,
        run_id,
        n_paths: n_paths.max(1),
    };
    let sw_hint = damped_sw_order_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        pending_sum,
        day,
        params,
        alpha,
        rho,
        Some(schedule),
        f_pipeline_default,
    );
    let q_hi = sw_hint.saturating_mul(2).max(params.case_size * 20);
    sla_order(&model, alpha, rho, params.case_size, q_hi)
}

pub fn sla_pb_order_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    pending: &BTreeMap<u32, u32>,
    pending_sum: u32,
    day: u32,
    params: &ModelParams,
    schedule: &OrderSchedule,
    alpha: f64,
    rho: f64,
    survival: &mut SurvivalCurveCache,
    f_pipeline_default: f64,
) -> u32 {
    if !schedule.can_order(day) {
        return 0;
    }
    let n_days = schedule.protection_days(day);
    let window = ProtectionWindow {
        start_day: day,
        n_days,
        lead_time: schedule.lead_time_days,
    };
    survival.rebuild_if_needed(params, n_days as usize + 1);
    let model = PbSlaModel {
        lot_counts: lot_counts.to_vec(),
        f_marginals: f_marginals.to_vec(),
        f_grid: f_grid.to_vec(),
        pending: pending.clone(),
        pending_sum,
        window,
        params,
        schedule,
        f_pipeline: f_pipeline_default,
        survival,
    };
    let sw_hint = damped_sw_order_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        pending_sum,
        day,
        params,
        alpha,
        rho,
        Some(schedule),
        f_pipeline_default,
    );
    let q_hi = sw_hint.saturating_mul(2).max(params.case_size * 20);
    sla_order(&model, alpha, rho, params.case_size, q_hi)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit_pf::UnitParticleBank;

    #[test]
    fn sla_mc_schedule_gate_zero() {
        let p = ModelParams::default();
        let s = OrderSchedule::default();
        let f_grid = vec![0.0, 1.0];
        let pending = BTreeMap::new();
        let q = sla_mc_order_f_belief(
            &[],
            &[],
            &f_grid,
            &pending,
            0,
            0,
            &p,
            &s,
            &[ShipmentTrace::smoke_cool()],
            0.9,
            0.8,
            42,
            8,
            1.0,
        );
        assert_eq!(q, 0, "Monday (day 0) is not an order day in default schedule");
    }

    #[test]
    fn sla_mc_empty_shelf_orders_more_than_full() {
        let p = ModelParams::default();
        let s = OrderSchedule::default();
        let f_grid = vec![0.0, 0.5, 1.0];
        // Four lots at peak freshness so stocked shelf orders below empty-shelf cap.
        let lot = vec![4.0, 4.0, 4.0, 4.0];
        let fm_full: Vec<f64> = (0..4).flat_map(|_| [0.0, 0.0, 1.0]).collect();
        let pending = BTreeMap::new();
        let ships = [ShipmentTrace::smoke_cool()];
        let empty = sla_mc_order_f_belief(
            &[],
            &[],
            &f_grid,
            &pending,
            6,
            6,
            &p,
            &s,
            &ships,
            0.9,
            0.8,
            42,
            8,
            1.0,
        );
        let full = sla_mc_order_f_belief(
            &lot,
            &fm_full,
            &f_grid,
            &pending,
            6,
            6,
            &p,
            &s,
            &ships,
            0.9,
            0.8,
            42,
            8,
            1.0,
        );
        assert!(
            empty > full,
            "empty ({empty}) should exceed well-stocked shelf order ({full})"
        );
    }

    #[test]
    fn sla_mc_higher_alpha_never_orders_less() {
        let p = ModelParams::default();
        let s = OrderSchedule::default();
        let f_grid = vec![0.0, 1.0];
        let pending = BTreeMap::new();
        let ships = [ShipmentTrace::smoke_cool()];
        let q_lo = sla_mc_order_f_belief(
            &[],
            &[],
            &f_grid,
            &pending,
            6,
            6,
            &p,
            &s,
            &ships,
            0.75,
            0.8,
            42,
            4,
            1.0,
        );
        let q_hi = sla_mc_order_f_belief(
            &[],
            &[],
            &f_grid,
            &pending,
            6,
            6,
            &p,
            &s,
            &ships,
            0.95,
            0.8,
            42,
            8,
            1.0,
        );
        assert!(q_hi >= q_lo);
    }

    #[test]
    fn survival_index_day_j_uses_j_plus_one_agings() {
        let params = ModelParams::default();
        let cache = SurvivalCurveCache::for_params(&params, 4);
        let s1 = cache.survival_at(0.8, 1);
        let s2 = cache.survival_at(0.8, 2);
        assert!(s2 <= s1, "more agings should not increase survival");
    }

    #[test]
    fn bank_start_state_uses_real_offsets() {
        let bank = UnitParticleBank::from_rows_uniform_lots(
            vec![0.5, 0.5],
            vec![vec![1.0, 0.9, 0.8, 0.7], vec![0.6, 0.5, 0.4, 0.3]],
            2,
        );
        let (_, offsets) = bank_start_state(&bank, 0);
        assert_eq!(offsets, bank.lot_offsets);
    }

    #[test]
    fn pb_supply_pmf_finite() {
        let probs = vec![0.1, 0.2, 0.3];
        let alive = alive_count_pmf(&probs);
        assert!(alive.iter().sum::<f64>() > 0.99);
    }
}
