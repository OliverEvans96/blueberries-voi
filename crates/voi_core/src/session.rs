//! EngineSession JSON RPC — order schedule + unit PF + rollout (Python day_driver).

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::belief_flat::{belief_flat_from_unit_bank, f_grid_k};
use crate::day_step::{alive_by_lot, unit_day_step, UnitDayStepIn, ModelParams};
use crate::demand_profile::DemandProfile;
use crate::obs::{mask_for, RichDay};
use crate::params::{DEFAULT_L_DIM, DEFAULT_UNITS_PER_LOT};
use crate::physics::{draw_demand, draw_demand_spawn};
use crate::spawn_rng::SpawnRng;
use crate::policy::{case_round_ceil, constant_order, damped_sw_order_f_belief};
use crate::unit_pf::{filter_step_unit, UnitParticleBank};
use crate::rollout::rollout_order;
use crate::schedule::OrderSchedule;
use crate::shipments::{arrival_receipt_meta, ShipmentTrace};
use rand::SeedableRng;
use rand_pcg::Pcg64;

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

#[derive(Clone, Debug)]
pub struct EngineSession {
    params: ModelParams,
    freshness: Vec<f64>,
    lot_offsets: Vec<usize>,
    lot_ids: Vec<i64>,
    pending: std::collections::BTreeMap<u32, u32>,
    day: u32,
    seed: u64,
    crossings: u32,
    initialized: bool,
    _n_particles: usize,
    h: u32,
    n_paths: u32,
    radius: i32,
    lead_time: u32,
    enable_filter: bool,
    schedule: OrderSchedule,
    shipments: Vec<ShipmentTrace>,
    bank: UnitParticleBank,
    next_lot: i64,
    seq: u32,
    l_dim: usize,
    k_dim: usize,
    obs_scenario: String,
    richest_log: Vec<RichDay>,
    rungs: HashMap<String, (UnitParticleBank, i32)>,
    bank_init: UnitParticleBank,
    catchup_days_last: u32,
}

impl Default for EngineSession {
    fn default() -> Self {
        Self::new(1)
    }
}

impl EngineSession {
    pub fn new(seed: u64) -> Self {
        let n = 16usize;
        Self {
            params: ModelParams::default(),
            freshness: vec![],
            lot_offsets: vec![0],
            lot_ids: vec![],
            pending: std::collections::BTreeMap::new(),
            day: 0,
            seed,
            crossings: 0,
            initialized: false,
            _n_particles: n,
            h: 7,
            n_paths: 2,
            radius: 1,
            lead_time: 1,
            enable_filter: true,
            schedule: OrderSchedule::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            bank: UnitParticleBank {
                weights: vec![1.0 / n as f64; n],
                freshness: vec![vec![]; n],
            },
            next_lot: 1,
            seq: 0,
            l_dim: DEFAULT_L_DIM,
            k_dim: 4,
            obs_scenario: "P1".to_string(),
            richest_log: Vec::new(),
            rungs: HashMap::new(),
            bank_init: UnitParticleBank {
                weights: vec![1.0 / n as f64; n],
                freshness: vec![vec![]; n],
            },
            catchup_days_last: 0,
        }
    }

    pub fn init(&mut self, seed: u64) {
        *self = Self::new(seed);
        self.initialized = true;
        self.crossings += 1;
        if self.params.demand_profile.is_none() {
            apply_demand_profile(&mut self.params, committed_demand_profile());
        }
        if self.enable_filter {
            self.seed_particle_bank();
        }
    }

    pub fn set_demand_profile(&mut self, profile: DemandProfile) {
        apply_demand_profile(&mut self.params, profile);
    }

    pub fn configure(
        &mut self,
        lead_time: u32,
        enable_filter: bool,
        h: u32,
        n_paths: u32,
        radius: i32,
        shipments: Vec<ShipmentTrace>,
        n_particles: usize,
        demand_profile: Option<DemandProfile>,
        units_per_lot: Option<usize>,
    ) {
        self.lead_time = lead_time.max(1);
        self.enable_filter = enable_filter;
        self.h = h.max(1);
        self.n_paths = n_paths.max(1);
        self.radius = radius;
        let n = n_particles.max(1);
        self._n_particles = n;
        self.params.units_per_lot = units_per_lot.unwrap_or(DEFAULT_UNITS_PER_LOT).max(1);
        self.bank = UnitParticleBank {
            weights: vec![1.0 / n as f64; n],
            freshness: vec![vec![]; n],
        };
        if !shipments.is_empty() {
            self.shipments = shipments;
        }
        if let Some(profile) = demand_profile {
            apply_demand_profile(&mut self.params, profile);
        } else if self.params.demand_profile.is_none() {
            apply_demand_profile(&mut self.params, committed_demand_profile());
        }
        if self.enable_filter {
            self.seed_particle_bank();
        }
    }

    fn seed_particle_bank(&mut self) {
        use rand::Rng;

        let n = self._n_particles.max(1);
        let l = self.l_dim;
        let upl = self.params.units_per_lot.max(1);
        let units = l * upl;
        let grid = f_grid_k(self.k_dim.max(1));
        let mut rng = Pcg64::seed_from_u64(self.seed.wrapping_add(0xF117_0000));
        let freshness: Vec<Vec<f64>> = (0..n)
            .map(|_| {
                (0..units)
                    .map(|_| {
                        let bin = rng.random_range(0..grid.len());
                        grid[bin]
                    })
                    .collect()
            })
            .collect();
        self.bank = UnitParticleBank {
            weights: vec![1.0 / n as f64; n],
            freshness,
        };
        self.bank_init = self.bank.clone();
    }

    pub fn episode_day(&self) -> u32 {
        self.day
    }

    pub fn obs_scenario(&self) -> &str {
        &self.obs_scenario
    }

    fn require_init(&self) {
        if !self.initialized {
            panic!("EngineSession.init() must be called before step/act");
        }
    }

    fn advance_one(&mut self, order_qty: u32) -> DayDelta {
        self.require_init();
        if self.day >= 90 {
            panic!("episode ended at day 90; Reset to start a new episode");
        }
        let mut order = case_round_ceil(order_qty, self.params.case_size);
        if !self.schedule.can_order(self.day) {
            order = 0;
        }
        *self.pending.entry(self.day + self.lead_time).or_insert(0) += order;
        let arrival = self.pending.remove(&self.day).unwrap_or(0);
        let pre_lot_ids = self.lot_ids.clone();
        let (f_at_receipt, age_at_receipt, pack_date_days) = if arrival > 0 {
            let mut rs = stream_rng(self.seed, self.day, 4);
            let mut rn = stream_rng(self.seed, self.day, 5);
            let (f, tau, pack) = arrival_receipt_meta(
                &mut rs,
                &mut rn,
                &self.shipments,
                &self.params,
                1.0,
            );
            (Some(f), Some(tau), Some(pack))
        } else {
            (None, None, None)
        };
        let demand = if self.params.demand_profile.is_some() {
            let mut rng_d = SpawnRng::spawn_rng(self.seed, "session", self.day, ":demand");
            draw_demand_spawn(&mut rng_d, &self.params, Some(self.day))
        } else {
            let mut rng_d = stream_rng(self.seed, self.day, 1);
            draw_demand(&mut rng_d, &self.params, None)
        };
        let mut rng_gamma = stream_rng(self.seed, self.day, 3);
        let mut rng_alloc = stream_rng(self.seed, self.day, 2);
        let mut rng_ship = if arrival > 0 {
            Some(stream_rng(self.seed, self.day, 4))
        } else {
            None
        };
        let mut rng_sensor = if arrival > 0 {
            Some(stream_rng(self.seed, self.day, 5))
        } else {
            None
        };
        let input = UnitDayStepIn {
            freshness: self.freshness.clone(),
            lot_offsets: self.lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_f: None,
            units_per_lot: Some(self.params.units_per_lot),
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let out = unit_day_step(
            &input,
            &self.params,
            &self.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            rng_ship.as_mut(),
            rng_sensor.as_mut(),
        );
        self.freshness = out.freshness;
        self.lot_offsets = out.lot_offsets;
        if arrival > 0 {
            self.lot_ids.push(self.next_lot);
            self.next_lot += 1;
        }
        let rich = RichDay {
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            arrivals: arrival,
            sales_by: out.sales_by.clone(),
            waste_by: out.waste_by.clone(),
            lot_ids: pre_lot_ids,
            f_at_receipt,
            age_at_receipt,
            pack_date_days,
        };
        if self.enable_filter {
            let obs = mask_for(&self.obs_scenario).unwrap().apply(&rich);
            let mut fr = stream_rng(self.seed, self.day, 6);
            filter_step_unit(&mut self.bank, &obs, &self.params, &mut fr);
        }
        let on_hand: u32 = alive_by_lot(&self.freshness, &self.lot_offsets).iter().sum();
        let delta = DayDelta {
            demand: out.demand,
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            on_hand,
            order_qty: order,
            arrivals: arrival,
            episode_day: self.day,
        };
        self.day += 1;
        self.seq += 1;
        self.richest_log.push(rich);
        if self.enable_filter {
            self.rungs.insert(
                self.obs_scenario.clone(),
                (self.bank.clone(), self.day as i32 - 1),
            );
        }
        delta
    }

    pub fn snapshot_value(&self) -> serde_json::Value {
        serde_json::json!({
            "seq": self.seq,
            "episode_day": self.day,
            "belief": self.belief_value(),
            "history": [],
            "live_lots": self.live_lots_value(),
            "pipeline": self.pipeline_value(),
            "applied_config": {
                "n_particles": self._n_particles,
                "H": self.h,
                "n_rollout_paths": self.n_paths,
                "candidate_case_radius": self.radius,
                "L": self.l_dim,
                "K": self.k_dim,
                "enable_filter": self.enable_filter,
                "lead_time": self.lead_time,
                "obs_scenario": self.obs_scenario,
                "seed": self.seed,
            },
            "schedule": schedule_wire(&self.schedule),
            "demand_summary": demand_summary_wire(&self.params),
        })
    }

    pub fn day_delta_value(&self, d: &DayDelta) -> serde_json::Value {
        serde_json::json!({
            "seq": self.seq,
            "episode_day": d.episode_day,
            "day": {
                "day": d.episode_day,
                "order_qty": d.order_qty,
                "arrivals": d.arrivals,
                "sales_total": d.sales_total,
                "waste_total": d.waste_total,
                "demand": d.demand,
                "L": d.on_hand,
            },
            "live_lots": self.live_lots_value(),
            "pipeline": self.pipeline_value(),
            "drop_oldest": self.seq > 14,
            "belief": self.belief_value(),
        })
    }

    fn belief_value(&self) -> serde_json::Value {
        belief_flat_from_unit_bank(&self.bank, self.l_dim, self.k_dim)
    }

    fn live_lots_value(&self) -> serde_json::Value {
        let l = self.lot_offsets.len().saturating_sub(1);
        let alive = alive_by_lot(&self.freshness, &self.lot_offsets);
        let lots: Vec<serde_json::Value> = (0..l)
            .filter(|&ell| alive.get(ell).copied().unwrap_or(0) > 0)
            .map(|ell| {
                let n = alive[ell];
                let start = self.lot_offsets[ell];
                let end = self.lot_offsets.get(ell + 1).copied().unwrap_or(start);
                let mean_f = if n > 0 {
                    self.freshness[start..end]
                        .iter()
                        .filter(|&&f| f > 0.0)
                        .sum::<f64>()
                        / f64::from(n)
                } else {
                    0.0
                };
                let lot_id = self.lot_ids.get(ell).copied().unwrap_or(ell as i64 + 1);
                serde_json::json!({"lot_id": lot_id, "n": n, "mean_f": mean_f})
            })
            .collect();
        serde_json::Value::Array(lots)
    }

    fn pipeline_value(&self) -> serde_json::Value {
        let pipe: Vec<serde_json::Value> = self
            .pending
            .iter()
            .filter(|(_, &qty)| qty != 0)
            .map(|(&arrival_day, &qty)| serde_json::json!({"arrival_day": arrival_day, "qty": qty}))
            .collect();
        serde_json::Value::Array(pipe)
    }

    pub fn set_belief_dims(&mut self, l: usize, k: usize) {
        self.l_dim = l;
        self.k_dim = k.max(1);
    }

    pub fn step(&mut self, order: u32) -> DayDelta {
        self.crossings += 1;
        self.advance_one(order)
    }

    pub fn step_n(&mut self, orders: &[u32]) -> Vec<DayDelta> {
        self.crossings += 1;
        orders.iter().map(|&q| self.advance_one(q)).collect()
    }

    fn f_belief_for_policy(&self) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        if self.enable_filter {
            let v = belief_flat_from_unit_bank(&self.bank, self.l_dim, self.k_dim);
            (
                json_f64_vec(&v["lot_counts"]),
                json_f64_vec(&v["f_marginals"]),
                json_f64_vec(&v["f_grid"]),
            )
        } else {
            let k = self.k_dim.max(1);
            let grid = f_grid_k(k);
            let uniform = 1.0 / k as f64;
            (
                vec![0.0; self.l_dim],
                vec![uniform; self.l_dim * k],
                grid,
            )
        }
    }

    /// Select an order via policy dispatch on belief mean (filter on) or empty shelf.
    pub fn act(
        &mut self,
        policy: Option<&str>,
        order_qty: Option<u32>,
        alpha: Option<f64>,
        rho: Option<f64>,
        h: Option<u32>,
        n_rollout_paths: Option<u32>,
        candidate_case_radius: Option<i32>,
    ) -> DayDelta {
        self.require_init();
        let pending_sum: u32 = self.pending.values().copied().sum();
        let (lot_counts, f_marginals, f_grid) = self.f_belief_for_policy();
        let f_pipe = 1.0;
        let alpha = alpha.unwrap_or(0.9);
        let rho = rho.unwrap_or(0.8);
        let h = h.unwrap_or(self.h);
        let n_paths = n_rollout_paths.unwrap_or(self.n_paths);
        let radius = candidate_case_radius.unwrap_or(self.radius);
        let name = policy.unwrap_or("rollout").to_ascii_lowercase();
        let q = match name.as_str() {
            "constant" | "const" | "fixed" => {
                constant_order(order_qty.unwrap_or(0), self.params.case_size)
            }
            "damped_sw" | "sw" => damped_sw_order_f_belief(
                &lot_counts,
                &f_marginals,
                &f_grid,
                pending_sum,
                self.day,
                &self.params,
                alpha,
                rho,
                Some(&self.schedule),
                f_pipe,
            ),
            "rollout" | "ctl" | "rollout_order" => {
                let base = damped_sw_order_f_belief(
                    &lot_counts,
                    &f_marginals,
                    &f_grid,
                    pending_sum,
                    self.day,
                    &self.params,
                    alpha,
                    rho,
                    Some(&self.schedule),
                    f_pipe,
                );
                rollout_order(
                    &lot_counts,
                    &f_marginals,
                    &f_grid,
                    base,
                    &self.params,
                    self.seed,
                    h,
                    n_paths,
                    radius,
                )
                .unwrap_or(base)
            }
            other => panic!("unknown policy {other:?}; use 'constant', 'damped_sw', or 'rollout'"),
        };
        self.crossings += 1;
        self.advance_one(q)
    }

    pub fn act_rollout(&mut self) -> DayDelta {
        self.act(Some("rollout"), None, None, None, None, None, None)
    }

    pub fn reset(&mut self, seed: u64) {
        self.init(seed);
    }

    pub fn set_obs_scenario(&mut self, obs_scenario: &str) -> Result<serde_json::Value, String> {
        self.require_init();
        validate_scenario(obs_scenario)?;
        self.catchup_days_last = 0;
        if obs_scenario == self.obs_scenario && self.rungs.contains_key(obs_scenario) {
            return Ok(self.snapshot_value());
        }
        if self.enable_filter {
            self.rungs.insert(
                self.obs_scenario.clone(),
                (self.bank.clone(), self.day as i32 - 1),
            );
        }
        self.obs_scenario = obs_scenario.to_string();
        if self.enable_filter {
            let (mut bank, last) = self
                .rungs
                .get(obs_scenario)
                .cloned()
                .unwrap_or_else(|| (self.bank_init.clone(), -1));
            let now = self.day as i32 - 1;
            let mut n = 0u32;
            for day_idx in (last + 1)..=now {
                let log = &self.richest_log[day_idx as usize];
                let obs = mask_for(obs_scenario).unwrap().apply(log);
                let mut fr = stream_rng(self.seed, day_idx as u32, 6);
                filter_step_unit(&mut bank, &obs, &self.params, &mut fr);
                n += 1;
            }
            self.catchup_days_last = n;
            self.bank = bank;
            self.rungs
                .insert(obs_scenario.to_string(), (self.bank.clone(), now));
        }
        Ok(self.snapshot_value())
    }

    pub fn bank_weights(&self) -> Vec<f64> {
        self.bank.weights.clone()
    }

    pub fn catchup_days_last_call(&self) -> u32 {
        self.catchup_days_last
    }

    pub fn host_crossings(&self) -> u32 {
        self.crossings
    }

    pub fn n_particles(&self) -> usize {
        self._n_particles
    }
}

const SCHEDULE_EPOCH: &str = "2024-01-01";
const EMBEDDED_DEMAND_PROFILE: &str =
    include_str!("../../../data/freshnet/demand_profile.json");

fn committed_demand_profile() -> DemandProfile {
    DemandProfile::from_json(EMBEDDED_DEMAND_PROFILE).expect("embedded demand profile")
}

fn apply_demand_profile(params: &mut ModelParams, profile: DemandProfile) {
    params.demand_vm = profile.demand_vm();
    params.demand_profile = Some(profile);
}

fn json_f64_vec(value: &serde_json::Value) -> Vec<f64> {
    value
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default()
}

fn schedule_wire(sched: &OrderSchedule) -> serde_json::Value {
    let delivery: Vec<u32> = sched
        .delivery_weekdays
        .iter()
        .enumerate()
        .filter(|(_, &on)| on)
        .map(|(i, _)| i as u32)
        .collect();
    let order: Vec<u32> = sched
        .order_weekdays
        .iter()
        .enumerate()
        .filter(|(_, &on)| on)
        .map(|(i, _)| i as u32)
        .collect();
    serde_json::json!({
        "delivery_weekdays": delivery,
        "order_weekdays": order,
        "lead_time_days": sched.lead_time_days,
        "epoch": SCHEDULE_EPOCH,
    })
}

fn demand_summary_wire(params: &ModelParams) -> serde_json::Value {
    let profile = params
        .demand_profile
        .as_ref()
        .cloned()
        .unwrap_or_else(committed_demand_profile);
    let scale = profile.scale_target_mu();
    serde_json::json!({
        "scale_mu": scale,
        "dow_means": profile.dow_means(),
    })
}

fn parse_demand_profile_from_rpc(params: &serde_json::Value) -> Option<DemandProfile> {
    if let Some(json) = rpc_str(params, "demand_profile_json") {
        return DemandProfile::from_json(json).ok();
    }
    if let Some(value) = rpc_field(params, "demand_profile") {
        if let Some(json) = value.as_str() {
            return DemandProfile::from_json(json).ok();
        }
        if value.is_object() {
            return DemandProfile::from_json(&value.to_string()).ok();
        }
    }
    None
}

fn validate_scenario(id: &str) -> Result<(), String> {
    if id == "B-state" {
        return Err(
            "SCN-B-state is a verification bypass, not an ObsMask; do not fabricate observations via mask_for"
                .to_string(),
        );
    }
    match id {
        "P0" | "P1" | "F1" | "F1s" | "F2a" | "F2" => Ok(()),
        _ => Err(format!("Unknown scenario for ObsMask: {id:?}")),
    }
}

fn rpc_field<'a>(params: &'a serde_json::Value, key: &str) -> Option<&'a serde_json::Value> {
    params
        .get(key)
        .or_else(|| params.get("config").and_then(|c| c.get(key)))
}

fn rpc_u64(params: &serde_json::Value, key: &str) -> Option<u64> {
    rpc_field(params, key).and_then(|v| v.as_u64())
}

fn rpc_i64(params: &serde_json::Value, key: &str) -> Option<i64> {
    rpc_field(params, key).and_then(|v| v.as_i64())
}

fn rpc_bool(params: &serde_json::Value, key: &str) -> Option<bool> {
    rpc_field(params, key).and_then(|v| v.as_bool())
}

fn rpc_str<'a>(params: &'a serde_json::Value, key: &str) -> Option<&'a str> {
    rpc_field(params, key).and_then(|v| v.as_str())
}

fn f64_array(value: &serde_json::Value) -> Vec<f64> {
    value
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default()
}

fn parse_shipments_from_rpc(params: &serde_json::Value) -> Vec<ShipmentTrace> {
    if let Some(arr) = rpc_field(params, "shipments").and_then(|v| v.as_array()) {
        let ships: Vec<ShipmentTrace> = arr
            .iter()
            .filter_map(|item| {
                let times = item.get("times_d")?;
                let temps = item.get("temps_c")?;
                Some(ShipmentTrace {
                    times_d: f64_array(times),
                    temps_c: f64_array(temps),
                })
            })
            .collect();
        if !ships.is_empty() {
            return ships;
        }
    }
    let times_outer = rpc_field(params, "times").and_then(|v| v.as_array());
    let temps_outer = rpc_field(params, "temps").and_then(|v| v.as_array());
    if let (Some(times), Some(temps)) = (times_outer, temps_outer) {
        let ships: Vec<ShipmentTrace> = times
            .iter()
            .zip(temps.iter())
            .map(|(t, m)| ShipmentTrace {
                times_d: f64_array(t),
                temps_c: f64_array(m),
            })
            .filter(|s| s.times_d.len() >= 2 && s.temps_c.len() >= 2)
            .collect();
        if !ships.is_empty() {
            return ships;
        }
    }
    Vec::new()
}

impl EngineSession {
    fn apply_rpc_configure(&mut self, params: &serde_json::Value) {
        let lead_time = rpc_u64(params, "lead_time").unwrap_or(1) as u32;
        let enable_filter = rpc_bool(params, "enable_filter").unwrap_or(true);
        let h = rpc_u64(params, "H").unwrap_or(7) as u32;
        let n_paths = rpc_u64(params, "n_rollout_paths").unwrap_or(2) as u32;
        let radius = rpc_i64(params, "candidate_case_radius").unwrap_or(1) as i32;
        let n_particles = rpc_u64(params, "n_particles").unwrap_or(200) as usize;
        let shipments = parse_shipments_from_rpc(params);
        let demand_profile = parse_demand_profile_from_rpc(params);
        let units_per_lot = rpc_u64(params, "units_per_lot").map(|n| n as usize);
        self.configure(
            lead_time,
            enable_filter,
            h,
            n_paths,
            radius,
            shipments,
            n_particles,
            demand_profile,
            units_per_lot,
        );
        self.schedule.lead_time_days = self.lead_time;
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DayDelta {
    pub demand: u32,
    pub sales_total: u32,
    pub waste_total: u32,
    pub on_hand: u32,
    pub order_qty: u32,
    pub arrivals: u32,
    pub episode_day: u32,
}

#[derive(Deserialize)]
struct RpcRequest {
    id: serde_json::Value,
    method: String,
    #[serde(default)]
    params: serde_json::Value,
}

pub fn handle_rpc(request_json: &str) -> String {
    let req: RpcRequest = match serde_json::from_str(request_json) {
        Ok(r) => r,
        Err(e) => {
            return format!(
                "{{\"id\":null,\"ok\":false,\"error\":{{\"type\":\"ParseError\",\"message\":{}}}}}",
                serde_json::to_string(&e.to_string()).unwrap()
            );
        }
    };
    use std::cell::RefCell;
    thread_local! {
        static SESSION: RefCell<EngineSession> = RefCell::new(EngineSession::new(0));
    }
    SESSION.with(|s| {
        let mut sess = s.borrow_mut();
        let result = match req.method.as_str() {
            "init" | "reset" => {
                let seed = rpc_u64(&req.params, "seed").unwrap_or(0);
                let l = rpc_u64(&req.params, "L").unwrap_or(DEFAULT_L_DIM as u64) as usize;
                let k = rpc_u64(&req.params, "K").unwrap_or(4) as usize;
                sess.reset(seed);
                sess.set_belief_dims(l, k.max(1));
                sess.apply_rpc_configure(&req.params);
                if let Some(sc) = rpc_str(&req.params, "obs_scenario") {
                    let _ = sess.set_obs_scenario(sc);
                }
                sess.snapshot_value()
            }
            "step" => {
                let order = req
                    .params
                    .get("order")
                    .or_else(|| req.params.get("order_qty"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u32;
                let d = sess.step(order);
                sess.day_delta_value(&d)
            }
            "step_n" => {
                let orders: Vec<u32> = req
                    .params
                    .get("orders")
                    .and_then(|v| v.as_array())
                    .map(|a| {
                        a.iter()
                            .filter_map(|x| x.as_u64().map(|n| n as u32))
                            .collect()
                    })
                    .unwrap_or_default();
                sess.crossings += 1;
                let deltas: Vec<serde_json::Value> = orders
                    .iter()
                    .map(|&q| {
                        let d = sess.advance_one(q);
                        sess.day_delta_value(&d)
                    })
                    .collect();
                serde_json::Value::Array(deltas)
            }
            "act" => {
                let policy = req.params.get("policy").and_then(|v| v.as_str());
                let order_qty = req
                    .params
                    .get("order_qty")
                    .or_else(|| req.params.get("q"))
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let alpha = req.params.get("alpha").and_then(|v| v.as_f64());
                let rho = req.params.get("rho").and_then(|v| v.as_f64());
                let h = req
                    .params
                    .get("H")
                    .or_else(|| req.params.get("h"))
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let n_paths = req
                    .params
                    .get("n_rollout_paths")
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let radius = req
                    .params
                    .get("candidate_case_radius")
                    .and_then(|v| v.as_i64())
                    .map(|n| n as i32);
                let d = sess.act(
                    policy,
                    order_qty,
                    alpha,
                    rho,
                    h,
                    n_paths,
                    radius,
                );
                sess.day_delta_value(&d)
            }
            "set_obs_scenario" => {
                let id = req
                    .params
                    .get("obs_scenario")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                match sess.set_obs_scenario(id) {
                    Ok(v) => v,
                    Err(e) => {
                        return format!(
                            "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"ValidationError\",\"message\":{}}}}}",
                            req.id,
                            serde_json::to_string(&e).unwrap()
                        );
                    }
                }
            }
            other => {
                return format!(
                    "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"UnknownMethod\",\"message\":{}}}}}",
                    req.id,
                    serde_json::to_string(other).unwrap()
                );
            }
        };
        serde_json::json!({"id": req.id, "ok": true, "result": result}).to_string()
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy::damped_sw_order_f_belief;

    fn t121b_shipment() -> ShipmentTrace {
        ShipmentTrace {
            times_d: vec![0.0, 1.0, 2.0],
            temps_c: vec![1.0, 1.0, 1.0],
        }
    }

    fn warm_t121b_session(seed: u64) -> EngineSession {
        let mut s = EngineSession::new(seed);
        s.init(seed);
        s.set_belief_dims(2, 4);
        s.configure(1, false, 7, 2, 1, vec![t121b_shipment()], 32, None, None);
        s.step(8);
        for _ in 0..5 {
            s.step(0);
        }
        s.configure(1, true, 7, 2, 1, vec![t121b_shipment()], 32, None, None);
        s
    }

    #[test]
    fn step_n_is_one_crossing() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let before = s.host_crossings();
        let _ = s.step_n(&[8, 0, 8]);
        assert_eq!(s.host_crossings(), before + 1);
    }

    #[test]
    fn step_before_init_panics() {
        let mut s = EngineSession::new(1);
        let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            s.step(0);
        }));
        assert!(panicked.is_err());
    }

    #[test]
    fn step_n_empty_orders_returns_empty_sequence() {
        let mut s = EngineSession::new(4);
        s.init(4);
        let deltas = s.step_n(&[]);
        assert!(deltas.is_empty());
    }

    #[test]
    fn step_n_returns_exactly_k() {
        let mut s = EngineSession::new(2);
        s.init(2);
        let orders = [0u32, 8, 0, 16];
        assert_eq!(s.step_n(&orders).len(), 4);
    }

    #[test]
    fn rpc_methods_ok() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        for method in ["step", "step_n", "reset", "act"] {
            let req = format!(
                r#"{{"id":"1","method":"{method}","params":{{"seed":1,"orders":[0,8,0,8,0,8,0],"order":0,"order_qty":0}}}}"#
            );
            let out = handle_rpc(&req);
            assert!(out.contains("\"ok\":true"), "{method}: {out}");
        }
    }

    #[test]
    fn act_rollout_advances_day() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let d = s.act_rollout();
        assert_eq!(d.episode_day, 0);
    }

    #[test]
    fn rpc_init_result_has_flat_belief() {
        let out = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true);
        let belief = &v["result"]["belief"];
        assert!(belief["lot_counts"].is_array(), "{out}");
        assert!(belief["f_marginals"].is_array());
        assert!(belief["f_grid"].is_array());
        assert_eq!(belief["L"], DEFAULT_L_DIM);
        assert_eq!(belief["K"], 4);
        assert_eq!(v["result"]["episode_day"], 0);
        assert_eq!(v["result"]["seq"], 0);
    }

    #[test]
    fn rpc_init_includes_schedule_and_demand_summary() {
        let out = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let schedule = &v["result"]["schedule"];
        assert!(schedule["delivery_weekdays"].as_array().is_some_and(|a| !a.is_empty()));
        assert!(schedule["order_weekdays"].as_array().is_some_and(|a| !a.is_empty()));
        assert_eq!(schedule["epoch"], SCHEDULE_EPOCH);
        let summary = &v["result"]["demand_summary"];
        assert!(summary["scale_mu"].as_f64().is_some_and(|x| x > 0.0));
        assert_eq!(summary["dow_means"].as_array().map(Vec::len), Some(7));
    }

    #[test]
    fn rpc_init_belief_lot_counts_positive_mass() {
        let out = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":1,"config":{"enable_filter":true}}}"#,
        );
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let f_mass: f64 = v["result"]["belief"]["f_marginals"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_f64())
            .sum();
        assert!(
            f_mass > 0.0,
            "filter-enabled init must expose non-zero f marginal mass"
        );
    }

    #[test]
    fn rpc_init_accepts_nested_config_shipments() {
        let out = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":42,"config":{"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[5.0,5.0,5.0]}],"n_particles":64,"H":5,"lead_time":2,"L":2,"K":4,"enable_filter":true,"n_rollout_paths":3,"candidate_case_radius":2,"obs_scenario":"P1"}}}"#,
        );
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let cfg = &v["result"]["applied_config"];
        assert_eq!(cfg["n_particles"], 64);
        assert_eq!(cfg["H"], 5);
        assert_eq!(cfg["lead_time"], 2);
        assert_eq!(cfg["n_rollout_paths"], 3);
        assert_eq!(cfg["candidate_case_radius"], 2);
        assert_eq!(v["result"]["schedule"]["lead_time_days"], 2);
        let warm = handle_rpc(
            r#"{"id":"2","method":"step_n","params":{"orders":[0,0,0,0,0,0,8,0,0]}}"#,
        );
        let warm_v: serde_json::Value = serde_json::from_str(&warm).unwrap();
        let warm_last = warm_v["result"].as_array().unwrap().last().unwrap();
        let f_warm = warm_last["live_lots"][0]["mean_f"]
            .as_f64()
            .expect("warm shipment arrival must populate live_lots");
        let smoke = handle_rpc(
            r#"{"id":"3","method":"init","params":{"seed":42,"config":{"lead_time":2,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#,
        );
        assert_eq!(smoke.contains("\"ok\":true"), true);
        let cool = handle_rpc(
            r#"{"id":"4","method":"step_n","params":{"orders":[0,0,0,0,0,0,8,0,0]}}"#,
        );
        let cool_v: serde_json::Value = serde_json::from_str(&cool).unwrap();
        let cool_last = cool_v["result"].as_array().unwrap().last().unwrap();
        let f_cool = cool_last["live_lots"][0]["mean_f"]
            .as_f64()
            .expect("smoke shipment arrival must populate live_lots");
        assert!(
            f_warm < f_cool - 1e-6,
            "configured warm shipments must lower arrival freshness vs cool default ({f_warm} vs {f_cool})"
        );
    }

    #[test]
    fn rpc_init_reset_sync_schedule_lead_time() {
        for method in ["init", "reset"] {
            let req = format!(
                r#"{{"id":"1","method":"{method}","params":{{"seed":9,"config":{{"lead_time":4,"shipments":[{{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}}]}}}}}}"#
            );
            let out = handle_rpc(&req);
            let v: serde_json::Value = serde_json::from_str(&out).unwrap();
            assert_eq!(v["ok"], true, "{method}: {out}");
            assert_eq!(v["result"]["applied_config"]["lead_time"], 4);
            assert_eq!(
                v["result"]["schedule"]["lead_time_days"], 4,
                "{method} must sync schedule lead time"
            );
        }
    }

    #[test]
    fn rpc_step_live_lots_nonempty_after_arrival() {
        let _ = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":42,"config":{"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#,
        );
        let out = handle_rpc(
            r#"{"id":"2","method":"step_n","params":{"orders":[0,0,0,0,0,0,8,0]}}"#,
        );
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let last = v["result"].as_array().unwrap().last().unwrap();
        let lots = last["live_lots"].as_array().expect("live_lots array");
        assert!(!lots.is_empty(), "arrival after lead_time must surface live_lots");
        assert!(lots[0]["lot_id"].is_number());
        assert!(lots[0]["n"].as_u64().is_some_and(|n| n > 0));
        assert!(lots[0]["mean_f"].is_number());
    }

    #[test]
    fn rpc_step_includes_belief() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let out = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true);
        assert!(v["result"]["belief"]["lot_counts"].is_array(), "{out}");
        assert!(v["result"]["day"]["day"].is_number(), "{out}");
        assert!(v["result"]["drop_oldest"].is_boolean());
    }

    #[test]
    fn rpc_step_n_empty_and_k_match() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let empty = handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[]}}"#);
        let v: serde_json::Value = serde_json::from_str(&empty).unwrap();
        assert_eq!(v["ok"], true);
        assert_eq!(v["result"].as_array().map(Vec::len), Some(0));
        let many = handle_rpc(r#"{"id":"3","method":"step_n","params":{"orders":[0,8,0]}}"#);
        let w: serde_json::Value = serde_json::from_str(&many).unwrap();
        assert_eq!(w["result"].as_array().map(Vec::len), Some(3));
        assert!(w["result"][0]["belief"]["lot_counts"].is_array());
    }

    #[test]
    fn rpc_unknown_and_malformed_are_envelopes() {
        let unknown = handle_rpc(r#"{"id":"9","method":"nope","params":{}}"#);
        let u: serde_json::Value = serde_json::from_str(&unknown).unwrap();
        assert_eq!(u["ok"], false);
        assert_eq!(u["error"]["type"], "UnknownMethod");
        let bad = handle_rpc("{not-json");
        let b: serde_json::Value = serde_json::from_str(&bad).unwrap();
        assert_eq!(b["ok"], false);
        assert_eq!(b["error"]["type"], "ParseError");
    }

    #[test]
    fn set_obs_scenario_updates_applied_config_without_reset() {
        let mut live = EngineSession::new(7);
        live.init(7);
        let _ = live.step_n(&[8, 0, 8]);
        let day_before = live.episode_day();
        let snap = live.set_obs_scenario("P0").expect("P0");
        assert_eq!(snap["applied_config"]["obs_scenario"], "P0");
        assert_eq!(live.episode_day(), day_before);
        assert_eq!(snap["episode_day"], day_before);
    }

    #[test]
    fn set_obs_scenario_invalid_id_errors() {
        let mut s = EngineSession::new(1);
        s.init(1);
        assert!(s.set_obs_scenario("P2").is_err());
        assert!(s.set_obs_scenario("B-state").is_err());
    }

    #[test]
    fn catch_up_matches_never_switched_weights() {
        let mut always = EngineSession::new(11);
        always.init(11);
        always.set_obs_scenario("P0").unwrap();
        let _ = always.step_n(&[8, 0, 8, 0]);
        let w_always = always.bank_weights();

        let mut switched = EngineSession::new(11);
        switched.init(11);
        let _ = switched.step_n(&[8, 0, 8, 0]);
        switched.set_obs_scenario("P0").unwrap();
        let w_switched = switched.bank_weights();
        assert_eq!(w_always, w_switched);
    }

    #[test]
    fn switch_back_is_gap_only() {
        let mut s = EngineSession::new(3);
        s.init(3);
        let _ = s.step_n(&[8, 0, 8]);
        s.set_obs_scenario("F2").unwrap();
        let first = s.catchup_days_last_call();
        assert_eq!(first, 3);
        let _ = s.step(0);
        s.set_obs_scenario("P1").unwrap();
        let back = s.catchup_days_last_call();
        assert_eq!(back, 1, "switch-back should replay only the unsynced day");
    }

    #[test]
    fn rpc_set_obs_scenario_ok() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let _ = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        let out =
            handle_rpc(r#"{"id":"3","method":"set_obs_scenario","params":{"obs_scenario":"F1"}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        assert_eq!(v["result"]["applied_config"]["obs_scenario"], "F1");
    }

    #[test]
    fn step_refuses_at_day_90() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let _ = s.step_n(&[0u32; 90]);
        let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            s.step(0);
        }));
        assert!(panicked.is_err());
    }

    #[test]
    fn configure_sets_particle_count() {
        let mut s = EngineSession::new(1);
        s.init(1);
        s.configure(1, true, 7, 2, 1, vec![], 200, None, None);
        assert_eq!(s.n_particles(), 200);
    }

    #[test]
    fn demand_summary_wire_matches_committed_profile() {
        let profile = committed_demand_profile();
        let mut params = ModelParams::default();
        apply_demand_profile(&mut params, profile.clone());
        let wire = demand_summary_wire(&params);
        assert!((wire["scale_mu"].as_f64().unwrap() - profile.scale_target_mu()).abs() <= 1e-9);
        let dow: Vec<f64> = wire["dow_means"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_f64())
            .collect();
        assert_eq!(dow.len(), 7);
        for (got, want) in dow.iter().zip(profile.dow_means()) {
            assert!((got - want).abs() <= 1e-9, "{got} vs {want}");
        }
    }

    #[test]
    fn session_configure_loads_calendar_profile_and_uses_day_in_demand() {
        let mut s = EngineSession::new(0);
        s.init(0);
        s.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let d0 = s.step(0);
        let mut s_dup = EngineSession::new(0);
        s_dup.init(0);
        s_dup.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let d0_dup = s_dup.step(0);
        assert_eq!(
            d0.demand, d0_dup.demand,
            "day-0 demand must be deterministic for fixed seed/config"
        );
        let mut s2 = EngineSession::new(0);
        s2.init(0);
        s2.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let mut demands = Vec::new();
        for _ in 0..90 {
            let d = s2.step(0);
            demands.push(d.demand);
        }
        let mean: f64 = demands.iter().map(|&d| f64::from(d)).sum::<f64>() / 90.0;
        assert!(
            mean > 20.0 && mean < 40.0,
            "90-day session mean {mean} must fall in [20, 40]"
        );
    }

    fn shannon(p: &[f64]) -> f64 {
        let z: f64 = p.iter().sum();
        if z <= 0.0 {
            return 0.0;
        }
        p.iter()
            .map(|x| {
                let q = *x / z;
                if q > 0.0 {
                    -q * q.ln()
                } else {
                    0.0
                }
            })
            .sum()
    }

    fn json_f64s(v: &serde_json::Value, key: &str) -> Vec<f64> {
        v[key]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .filter_map(|x| x.as_f64())
            .collect()
    }

    fn max_row_entropy(belief: &serde_json::Value) -> f64 {
        let k = belief["K"].as_u64().unwrap_or(0) as usize;
        let l = belief["L"].as_u64().unwrap_or(0) as usize;
        let f_margs = json_f64s(belief, "f_marginals");
        let lot_counts = json_f64s(belief, "lot_counts");
        (0..l)
            .filter(|&i| lot_counts.get(i).copied().unwrap_or(0.0) > 0.0)
            .map(|i| shannon(&f_margs[i * k..(i + 1) * k]))
            .fold(0.0, f64::max)
    }

    fn step_until_arrivals(s: &mut EngineSession, orders: &[u32]) -> u32 {
        let mut arrived = 0u32;
        for &q in orders {
            let d = s.step(q);
            arrived += d.arrivals;
        }
        arrived
    }

    /// AC: F2 vs P0 Snapshot.belief.f_marginals differ; live_lots identical.
    #[test]
    fn f2_belief_differs_from_p0_live_lots_unchanged() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
        let mut f2 = EngineSession::new(42);
        f2.init(42);
        f2.set_obs_scenario("F2").unwrap();
        assert!(step_until_arrivals(&mut f2, &orders) > 0);
        let snap_f2 = f2.snapshot_value();

        let mut p0 = EngineSession::new(42);
        p0.init(42);
        p0.set_obs_scenario("P0").unwrap();
        let _ = p0.step_n(&orders);
        let snap_p0 = p0.snapshot_value();

        assert_eq!(
            snap_f2["live_lots"], snap_p0["live_lots"],
            "physics live_lots must match across rungs"
        );
        assert_ne!(
            json_f64s(&snap_f2["belief"], "f_marginals"),
            json_f64s(&snap_p0["belief"], "f_marginals"),
            "F2 particle posterior must differ from P0"
        );
    }

    /// AC: F2a age mass narrower than P1 (lower entropy).
    #[test]
    fn f2a_age_mass_narrower_than_p1() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0, 8, 0];
        let mut f2a = EngineSession::new(17);
        f2a.init(17);
        f2a.set_obs_scenario("F2a").unwrap();
        let _ = f2a.step_n(&orders);
        let mut p1 = EngineSession::new(17);
        p1.init(17);
        p1.set_obs_scenario("P1").unwrap();
        let _ = p1.step_n(&orders);
        let h_f2a = max_row_entropy(&f2a.snapshot_value()["belief"]);
        let h_p1 = max_row_entropy(&p1.snapshot_value()["belief"]);
        assert!(
            h_f2a < h_p1 - 1e-9,
            "F2a entropy {h_f2a} should be < P1 {h_p1}"
        );
    }

    /// AC: after positive waste, P0 vs P1 Snapshot belief (lot_counts or ages) differ.
    #[test]
    fn p0_vs_p1_belief_differs_after_waste() {
        let mut p0 = EngineSession::new(99);
        p0.init(99);
        p0.set_obs_scenario("P0").unwrap();
        let mut p1 = EngineSession::new(99);
        p1.init(99);
        p1.set_obs_scenario("P1").unwrap();
        let mut saw_waste = false;
        for _ in 0..89 {
            let d0 = p0.step(32);
            let d1 = p1.step(32);
            assert_eq!(d0.waste_total, d1.waste_total);
            if d0.waste_total > 0 {
                saw_waste = true;
                break;
            }
        }
        assert!(saw_waste, "fixture must produce waste");
        let b0 = p0.snapshot_value()["belief"].clone();
        let b1 = p1.snapshot_value()["belief"].clone();
        let same_counts = json_f64s(&b0, "lot_counts") == json_f64s(&b1, "lot_counts");
        let same_ages = json_f64s(&b0, "f_marginals") == json_f64s(&b1, "f_marginals");
        assert!(
            !same_counts || !same_ages,
            "P0 omits waste LL so posterior must differ from P1"
        );
    }

    /// AC: uneven sales_by → F1 posterior differs from P1.
    #[test]
    fn f1_vs_p1_belief_differs_after_uneven_sales() {
        let mut f1 = EngineSession::new(42);
        f1.init(42);
        f1.set_belief_dims(2, 8);
        f1.set_obs_scenario("F1").unwrap();
        let mut p1 = EngineSession::new(42);
        p1.init(42);
        p1.set_belief_dims(2, 8);
        p1.set_obs_scenario("P1").unwrap();
        let mut two_lots = false;
        for _ in 0..40 {
            let d0 = f1.step(64);
            let d1 = p1.step(64);
            assert_eq!(d0.sales_total, d1.sales_total);
            let n_live = f1
                .snapshot_value()["live_lots"]
                .as_array()
                .map(Vec::len)
                .unwrap_or(0);
            if n_live >= 2 {
                two_lots = true;
                if d0.sales_total > 0 {
                    break;
                }
            }
        }
        assert!(two_lots, "fixture must reach two live lots with sales");
        let b_f1 = f1.snapshot_value()["belief"].clone();
        let b_p1 = p1.snapshot_value()["belief"].clone();
        assert!(
            json_f64s(&b_f1, "f_marginals") != json_f64s(&b_p1, "f_marginals")
                || json_f64s(&b_f1, "lot_counts") != json_f64s(&b_p1, "lot_counts"),
            "F1 lot-resolved sales must move the posterior vs P1; F1={b_f1} P1={b_p1}"
        );
        assert_eq!(
            f1.snapshot_value()["live_lots"],
            p1.snapshot_value()["live_lots"]
        );
    }

    /// AC: catch-up to F2 matches never-switched F2 (CRN); belief is not oracle-only.
    #[test]
    fn catch_up_f2_matches_never_switched_and_not_oracle() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
        let mut always = EngineSession::new(42);
        always.init(42);
        always.set_belief_dims(4, 8);
        always.set_obs_scenario("F2").unwrap();
        let _ = always.step_n(&orders);
        let b_always = always.snapshot_value()["belief"].clone();

        let mut switched = EngineSession::new(42);
        switched.init(42);
        switched.set_belief_dims(4, 8);
        let _ = switched.step_n(&orders);
        switched.set_obs_scenario("F2").unwrap();
        let b_switched = switched.snapshot_value()["belief"].clone();
        assert_eq!(
            json_f64s(&b_always, "f_marginals"),
            json_f64s(&b_switched, "f_marginals"),
            "day-keyed catch-up must match a never-switched F2 session"
        );
        assert_eq!(always.bank_weights(), switched.bank_weights());

        let mut p0 = EngineSession::new(42);
        p0.init(42);
        p0.set_belief_dims(4, 8);
        p0.set_obs_scenario("P0").unwrap();
        let _ = p0.step_n(&orders);
        assert_ne!(
            json_f64s(&b_always, "f_marginals"),
            json_f64s(&p0.snapshot_value()["belief"], "f_marginals"),
            "caught-up F2 posterior must not collapse to P0/oracle"
        );
    }

    #[test]
    fn set_obs_scenario_rejects_p2_and_b_state() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let p2 = s.set_obs_scenario("P2").unwrap_err();
        assert!(p2.contains("Unknown scenario"), "{p2}");
        let b = s.set_obs_scenario("B-state").unwrap_err();
        assert!(b.contains("bypass") || b.contains("B-state"), "{b}");
    }

    #[test]
    fn act_rollout_uses_belief_not_truth_counts() {
        let s = warm_t121b_session(_SEED);
        let belief = belief_flat_from_unit_bank(&s.bank, s.l_dim, s.k_dim);
        let lot_counts = json_f64s(&belief, "lot_counts");
        let f_marginals = json_f64s(&belief, "f_marginals");
        let f_grid = json_f64s(&belief, "f_grid");
        assert!(
            lot_counts.iter().any(|&x| x > 0.0),
            "fixture must seed nontrivial belief mean"
        );
        let pending_sum: u32 = s.pending.values().copied().sum();
        let f_pipe = 1.0;
        let belief_rollout = {
            let base = damped_sw_order_f_belief(
                &lot_counts,
                &f_marginals,
                &f_grid,
                pending_sum,
                s.day,
                &s.params,
                0.9,
                0.8,
                Some(&s.schedule),
                f_pipe,
            );
            rollout_order(
                &lot_counts,
                &f_marginals,
                &f_grid,
                base,
                &s.params,
                s.seed,
                s.h,
                s.n_paths,
                s.radius,
            )
            .unwrap_or(base)
        };
        let mut live = warm_t121b_session(_SEED);
        let d = live.act(Some("rollout"), None, None, None, None, None, None);
        assert_eq!(d.order_qty, belief_rollout);
    }

    #[test]
    fn act_damped_sw_differs_from_rollout_when_belief_nontrivial() {
        let sw = warm_t121b_session(_SEED)
            .act(Some("damped_sw"), None, None, None, None, None, None)
            .order_qty;
        let roll = warm_t121b_session(_SEED)
            .act(Some("rollout"), None, None, None, None, None, None)
            .order_qty;
        assert_ne!(sw, roll, "damped_sw and rollout must dispatch separately");
    }

    #[test]
    fn act_alpha_budget_changes_damped_sw_order() {
        let mut low = warm_t121b_session(17);
        let q_low = low
            .act(Some("damped_sw"), None, Some(0.5), None, None, None, None)
            .order_qty;

        let mut high = warm_t121b_session(17);
        let q_high = high
            .act(Some("damped_sw"), None, Some(0.99), None, None, None, None)
            .order_qty;

        assert!(q_high >= q_low, "higher alpha should not reduce damped_sw order");
    }

    const _SEED: u64 = 99;
}
