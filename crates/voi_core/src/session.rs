//! EngineSession JSON RPC — order schedule + RBPF + rollout (Python day_driver).

use serde::{Deserialize, Serialize};

use crate::day_step::{day_step, DayStepIn, ModelParams};
use crate::physics::draw_demand;
use crate::policy::{case_round_ceil, damped_sw_order};
use crate::rbpf::{filter_step, FilterObs, ParticleBank};
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
    ) {
        self.lead_time = lead_time.max(1);
        self.enable_filter = enable_filter;
        self.h = h.max(1);
        self.n_paths = n_paths.max(1);
        self.radius = radius;
        if !shipments.is_empty() {
            self.shipments = shipments;
        }
    }

    pub fn episode_day(&self) -> u32 {
        self.day
    }

    fn require_init(&self) {
        if !self.initialized {
            panic!("EngineSession.init() must be called before step/act");
        }
    }

    fn advance_one(&mut self, order_qty: u32) -> DayDelta {
        self.require_init();
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
        if self.enable_filter {
            let obs = FilterObs {
                sales_tot: Some(out.sales_total as i32),
                waste_tot: Some(out.waste_total as i32),
                arrivals: arrival,
            };
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
        delta
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

    pub fn host_crossings(&self) -> u32 {
        self.crossings
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
                let seed = req.params.get("seed").and_then(|v| v.as_u64()).unwrap_or(0);
                sess.reset(seed);
                serde_json::json!({"ok": true, "seq": 0, "episode_day": 0})
            }
            "step" => {
                let order = req
                    .params
                    .get("order")
                    .or_else(|| req.params.get("order_qty"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u32;
                serde_json::to_value(sess.step(order)).unwrap()
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
                serde_json::to_value(sess.step_n(&orders)).unwrap()
            }
            "act" => serde_json::to_value(sess.act_rollout()).unwrap(),
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
}
