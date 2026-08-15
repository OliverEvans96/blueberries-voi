//! EngineSession JSON RPC — order schedule + RBPF + rollout (Python day_driver).

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::day_step::{day_step, DayStepIn, ModelParams};
use crate::obs::{mask_for, RichDay};
use crate::physics::draw_demand;
use crate::policy::{case_round_ceil, damped_sw_order};
use crate::rbpf::{filter_step, ParticleBank};
use crate::rollout::rollout_order;
use crate::schedule::OrderSchedule;
use crate::shipments::{generate_arrival_age, ShipmentTrace};
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
    state: DayStepIn,
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
    bank: ParticleBank,
    next_lot: i64,
    seq: u32,
    l_dim: usize,
    k_dim: usize,
    obs_scenario: String,
    richest_log: Vec<RichDay>,
    rungs: HashMap<String, (ParticleBank, i32)>,
    bank_init: ParticleBank,
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
            state: DayStepIn {
                counts: vec![],
                taus: vec![],
                lot_ids: vec![],
                demand: None,
                spoil_by: Some(vec![]),
                delivery_n: 0,
                delivery_tau: 0.0,
                delivery_lot_id: 0,
            },
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
            bank: ParticleBank {
                weights: vec![1.0 / n as f64; n],
                counts: vec![vec![]; n],
                taus: vec![vec![]; n],
            },
            next_lot: 1,
            seq: 0,
            l_dim: 2,
            k_dim: 4,
            obs_scenario: "P1".to_string(),
            richest_log: Vec::new(),
            rungs: HashMap::new(),
            bank_init: ParticleBank {
                weights: vec![1.0 / n as f64; n],
                counts: vec![vec![]; n],
                taus: vec![vec![]; n],
            },
            catchup_days_last: 0,
        }
    }

    pub fn init(&mut self, seed: u64) {
        *self = Self::new(seed);
        self.initialized = true;
        self.crossings += 1;
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
    ) {
        self.lead_time = lead_time.max(1);
        self.enable_filter = enable_filter;
        self.h = h.max(1);
        self.n_paths = n_paths.max(1);
        self.radius = radius;
        let n = n_particles.max(1);
        self._n_particles = n;
        self.bank = ParticleBank {
            weights: vec![1.0 / n as f64; n],
            counts: vec![vec![]; n],
            taus: vec![vec![]; n],
        };
        if !shipments.is_empty() {
            self.shipments = shipments;
        }
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
        if arrival > 0 {
            let mut rs = stream_rng(self.seed, self.day, 4);
            let mut rn = stream_rng(self.seed, self.day, 5);
            let tau = generate_arrival_age(
                &mut rs,
                &mut rn,
                &self.shipments,
                self.params.q10,
                self.params.t_ref_c,
                1.0,
            );
            self.state.delivery_n = arrival;
            self.state.delivery_tau = tau;
            self.state.delivery_lot_id = self.next_lot;
            self.next_lot += 1;
        } else {
            self.state.delivery_n = 0;
        }
        let mut rng_d = stream_rng(self.seed, self.day, 1);
        self.state.demand = Some(draw_demand(
            &mut rng_d,
            self.params.demand_mu,
            self.params.demand_vm,
        ));
        self.state.spoil_by = None;
        let mut rng_a = stream_rng(self.seed, self.day, 2);
        let mut rng_s = stream_rng(self.seed, self.day, 3);
        let out = day_step(
            &self.state,
            &self.params,
            Some(&mut rng_a),
            Some(&mut rng_s),
        );
        let rich = RichDay {
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            arrivals: arrival,
            sales_by: out.sales_by.clone(),
            waste_by: out.waste_by.clone(),
            lot_ids: out.lot_ids.clone(),
            age_at_receipt: if arrival > 0 {
                Some(self.state.delivery_tau)
            } else {
                None
            },
            // I1 Gaussian mean = pack_date_days (calendar transit)
            pack_date_days: if arrival > 0 {
                Some(self.state.delivery_tau.round() as i32)
            } else {
                None
            },
        };
        if self.enable_filter {
            let obs = mask_for(&self.obs_scenario).unwrap().apply(&rich);
            let mut fr = stream_rng(self.seed, self.day, 6);
            self.bank = filter_step(&self.bank, &obs, &self.params, &mut fr);
        }
        self.state.counts = out.counts.clone();
        self.state.taus = out.taus.clone();
        self.state.lot_ids = out.lot_ids.clone();
        let on_hand: u32 = out.counts.iter().sum();
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
            "demand_summary": demand_summary_wire(),
        })
    }

    fn day_delta_value(&self, d: &DayDelta) -> serde_json::Value {
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
        crate::belief_flat::particle_bank_to_flat(&self.bank, self.l_dim, self.k_dim)
    }

    fn live_lots_value(&self) -> serde_json::Value {
        let lots: Vec<serde_json::Value> = self
            .state
            .counts
            .iter()
            .zip(self.state.taus.iter())
            .zip(self.state.lot_ids.iter())
            .filter(|((&n, _), _)| n > 0)
            .map(|((&n, &tau), &lot_id)| serde_json::json!({"lot_id": lot_id, "n": n, "tau": tau}))
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

    pub fn act_rollout(&mut self) -> DayDelta {
        self.require_init();
        let pending_sum: u32 = self.pending.values().copied().sum();
        let base = damped_sw_order(
            &self.state.counts,
            &self.state.taus,
            pending_sum,
            self.day,
            &self.params,
            0.9,
            0.8,
            Some(&self.schedule),
        );
        let ids = self.state.lot_ids.clone();
        let q = if self.state.counts.iter().any(|&n| n > 0) {
            rollout_order(
                &self.state.counts,
                &self.state.taus,
                &ids,
                base,
                &self.params,
                self.seed,
                self.h,
                self.n_paths,
                self.radius,
            )
            .unwrap_or(base)
        } else {
            base
        };
        self.crossings += 1;
        self.advance_one(q)
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
                bank = filter_step(&bank, &obs, &self.params, &mut fr);
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

const AGE_GRID_LO: f64 = 0.0;
const AGE_GRID_HI: f64 = 8.0;
const SCHEDULE_EPOCH: &str = "2024-01-01";

fn tau_grid(k: usize) -> Vec<f64> {
    if k == 0 {
        return Vec::new();
    }
    if k == 1 {
        return vec![0.0];
    }
    (0..k)
        .map(|i| AGE_GRID_LO + (AGE_GRID_HI - AGE_GRID_LO) * (i as f64) / ((k - 1) as f64))
        .collect()
}

#[allow(dead_code)] // kept for empty-physics overlay comments; live belief uses particle_bank_to_flat
fn empty_flat_belief(l: usize, k: usize) -> serde_json::Value {
    let grid = tau_grid(k);
    if l == 0 {
        return serde_json::json!({
            "lot_counts": [],
            "age_marginals": [],
            "tau_grid": grid,
            "L": 0,
            "K": k,
        });
    }
    let uniform = vec![1.0 / k as f64; k];
    let mut age = Vec::with_capacity(l * k);
    for _ in 0..l {
        age.extend_from_slice(&uniform);
    }
    serde_json::json!({
        "lot_counts": vec![0.0; l],
        "age_marginals": age,
        "tau_grid": grid,
        "L": l,
        "K": k,
    })
}

fn nearest_bin(tau: f64, grid: &[f64]) -> usize {
    let mut best = 0usize;
    let mut best_d = f64::INFINITY;
    for (i, &g) in grid.iter().enumerate() {
        let d = (tau - g).abs();
        if d < best_d {
            best_d = d;
            best = i;
        }
    }
    best
}

#[allow(dead_code)] // unused: Snapshot.belief is particle_bank_to_flat; live_lots is physics overlay
fn oracle_flat_belief(counts: &[u32], taus: &[f64], k: usize) -> serde_json::Value {
    let l = counts.len();
    let k = k.max(1);
    let grid = tau_grid(k);
    let lot_counts: Vec<f64> = counts.iter().map(|&n| n as f64).collect();
    let mut age = vec![0.0; l * k];
    for (i, &tau) in taus.iter().enumerate().take(l) {
        let bin = nearest_bin(tau, &grid);
        age[i * k + bin] = 1.0;
    }
    serde_json::json!({
        "lot_counts": lot_counts,
        "age_marginals": age,
        "tau_grid": grid,
        "L": l,
        "K": k,
    })
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

fn demand_summary_wire() -> serde_json::Value {
    let scale = 30.0;
    let factors = [
        0.97076, 1.00837, 0.928811, 0.860509, 0.925391, 1.12922, 1.176938,
    ];
    serde_json::json!({
        "scale_mu": scale,
        "dow_means": factors.map(|f| scale * f),
    })
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

fn rpc_u64(params: &serde_json::Value, key: &str) -> Option<u64> {
    params.get(key).and_then(|v| v.as_u64()).or_else(|| {
        params
            .get("config")
            .and_then(|c| c.get(key))
            .and_then(|v| v.as_u64())
    })
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
                let l = rpc_u64(&req.params, "L").unwrap_or(2) as usize;
                let k = rpc_u64(&req.params, "K").unwrap_or(4) as usize;
                sess.reset(seed);
                sess.set_belief_dims(l, k.max(1));
                if let Some(sc) = req
                    .params
                    .get("obs_scenario")
                    .or_else(|| req.params.get("config").and_then(|c| c.get("obs_scenario")))
                    .and_then(|v| v.as_str())
                {
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
                let d = sess.act_rollout();
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
        assert!(belief["age_marginals"].is_array());
        assert!(belief["tau_grid"].is_array());
        assert_eq!(belief["L"], 2);
        assert_eq!(belief["K"], 4);
        assert_eq!(v["result"]["episode_day"], 0);
        assert_eq!(v["result"]["seq"], 0);
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
        s.configure(1, true, 7, 2, 1, vec![], 200);
        assert_eq!(s.n_particles(), 200);
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

    fn merged_age_mass(belief: &serde_json::Value) -> Vec<f64> {
        let k = belief["K"].as_u64().unwrap_or(0) as usize;
        let l = belief["L"].as_u64().unwrap_or(0) as usize;
        let counts = json_f64s(belief, "lot_counts");
        let ages = json_f64s(belief, "age_marginals");
        let mut m = vec![0.0; k];
        for i in 0..l {
            let c = counts.get(i).copied().unwrap_or(0.0);
            for j in 0..k {
                m[j] += c * ages.get(i * k + j).copied().unwrap_or(0.0);
            }
        }
        m
    }

    fn step_until_arrivals(s: &mut EngineSession, orders: &[u32]) -> u32 {
        let mut arrived = 0u32;
        for &q in orders {
            let d = s.step(q);
            arrived += d.arrivals;
        }
        arrived
    }

    /// AC: F2 vs P0 Snapshot.belief.age_marginals differ; live_lots identical.
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
            json_f64s(&snap_f2["belief"], "age_marginals"),
            json_f64s(&snap_p0["belief"], "age_marginals"),
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
        let h_f2a = shannon(&merged_age_mass(&f2a.snapshot_value()["belief"]));
        let h_p1 = shannon(&merged_age_mass(&p1.snapshot_value()["belief"]));
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
        let same_ages = json_f64s(&b0, "age_marginals") == json_f64s(&b1, "age_marginals");
        assert!(
            !same_counts || !same_ages,
            "P0 omits waste LL so posterior must differ from P1"
        );
    }

    /// AC: uneven sales_by → F1 posterior differs from P1.
    #[test]
    fn f1_vs_p1_belief_differs_after_uneven_sales() {
        let orders = [8u32, 8, 0, 8, 0, 8, 0, 8, 0, 8];
        let mut f1 = EngineSession::new(5);
        f1.init(5);
        f1.set_obs_scenario("F1").unwrap();
        let _ = f1.step_n(&orders);
        let mut p1 = EngineSession::new(5);
        p1.init(5);
        p1.set_obs_scenario("P1").unwrap();
        let _ = p1.step_n(&orders);
        assert_ne!(
            json_f64s(&f1.snapshot_value()["belief"], "age_marginals"),
            json_f64s(&p1.snapshot_value()["belief"], "age_marginals"),
            "F1 lot-resolved sales must move the posterior vs P1"
        );
        assert_eq!(
            f1.snapshot_value()["live_lots"],
            p1.snapshot_value()["live_lots"]
        );
    }

    /// AC: catch-up to F2 matches never-switched F2 (CRN); belief is not oracle-only.
    #[test]
    fn catch_up_f2_matches_never_switched_and_not_oracle() {
        let orders = [8u32, 0, 8, 0, 8, 0];
        let mut always = EngineSession::new(11);
        always.init(11);
        always.set_obs_scenario("F2").unwrap();
        let _ = always.step_n(&orders);
        let b_always = always.snapshot_value()["belief"].clone();

        let mut switched = EngineSession::new(11);
        switched.init(11);
        let _ = switched.step_n(&orders);
        switched.set_obs_scenario("F2").unwrap();
        let b_switched = switched.snapshot_value()["belief"].clone();
        assert_eq!(
            json_f64s(&b_always, "age_marginals"),
            json_f64s(&b_switched, "age_marginals"),
            "day-keyed catch-up must match a never-switched F2 session"
        );
        assert_eq!(always.bank_weights(), switched.bank_weights());

        let mut p0 = EngineSession::new(11);
        p0.init(11);
        p0.set_obs_scenario("P0").unwrap();
        let _ = p0.step_n(&orders);
        assert_ne!(
            json_f64s(&b_always, "age_marginals"),
            json_f64s(&p0.snapshot_value()["belief"], "age_marginals"),
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
}
