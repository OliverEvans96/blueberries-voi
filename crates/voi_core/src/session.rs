//! EngineSession JSON RPC (studio worker + tests).

use serde::{Deserialize, Serialize};

use crate::day_step::{advance_days, day_step, DayStepIn, ModelParams};
use rand::SeedableRng;
use rand_pcg::Pcg64;

#[derive(Clone, Debug)]
pub struct EngineSession {
    params: ModelParams,
    state: DayStepIn,
    rng_alloc: Pcg64,
    rng_spoil: Pcg64,
    crossings: u32,
}

impl Default for EngineSession {
    fn default() -> Self {
        Self::new(1)
    }
}

impl EngineSession {
    pub fn new(seed: u64) -> Self {
        Self {
            params: ModelParams::default(),
            state: DayStepIn {
                counts: vec![],
                taus: vec![],
                lot_ids: vec![],
                demand: Some(0),
                spoil_by: Some(vec![]),
                delivery_n: 0,
                delivery_tau: 0.0,
                delivery_lot_id: 0,
            },
            rng_alloc: Pcg64::seed_from_u64(seed),
            rng_spoil: Pcg64::seed_from_u64(seed.wrapping_add(1)),
            crossings: 0,
        }
    }

    pub fn step(&mut self, order: u32, demand: u32) -> DayDelta {
        self.crossings += 1;
        self.state.demand = Some(demand);
        self.state.delivery_n = order;
        self.state.spoil_by = None;
        let out = day_step(
            &self.state,
            &self.params,
            Some(&mut self.rng_alloc),
            Some(&mut self.rng_spoil),
        );
        self.state.counts = out.counts.clone();
        self.state.taus = out.taus.clone();
        self.state.lot_ids = out.lot_ids.clone();
        DayDelta {
            demand: out.demand,
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            on_hand: out.counts.iter().sum(),
        }
    }

    pub fn step_n(&mut self, orders: &[u32], demand: u32) -> Vec<DayDelta> {
        self.crossings += 1;
        self.state.demand = Some(demand);
        self.state.spoil_by = None;
        let outs = advance_days(
            self.state.clone(),
            orders,
            &self.params,
            &mut self.rng_alloc,
            &mut self.rng_spoil,
        );
        if let Some(last) = outs.last() {
            self.state.counts = last.counts.clone();
            self.state.taus = last.taus.clone();
            self.state.lot_ids = last.lot_ids.clone();
        }
        outs.into_iter()
            .map(|o| DayDelta {
                demand: o.demand,
                sales_total: o.sales_total,
                waste_total: o.waste_total,
                on_hand: o.counts.iter().sum(),
            })
            .collect()
    }

    pub fn reset(&mut self, seed: u64) {
        *self = Self::new(seed);
        self.crossings += 1;
    }

    pub fn host_crossings(&self) -> u32 {
        self.crossings
    }
}

#[cfg(test)]
mod python_session_mirrors {
    use super::*;

    #[test]
    fn step_n_returns_exactly_k_day_deltas() {
        let mut s = EngineSession::new(2);
        let orders = [0u32, 8, 0, 16];
        let deltas = s.step_n(&orders, 0);
        assert_eq!(deltas.len(), orders.len());
    }

    #[test]
    fn step_n_empty_orders_returns_empty_sequence() {
        let mut s = EngineSession::new(4);
        let deltas = s.step_n(&[], 0);
        assert!(deltas.is_empty());
        assert_eq!(s.host_crossings(), 1);
    }

    #[test]
    fn rpc_methods_init_step_step_n_reset_act() {
        for method in ["init", "step", "step_n", "reset", "act"] {
            let req = format!(
                r#"{{"id":"1","method":"{method}","params":{{"seed":1,"orders":[0],"order":0,"demand":0}}}}"#
            );
            let out = handle_rpc(&req);
            assert!(out.contains("\"ok\":true"), "{method}: {out}");
        }
    }

    #[test]
    fn rpc_unknown_method_errors() {
        let out = handle_rpc(r#"{"id":"x","method":"nope","params":{}}"#);
        assert!(out.contains("\"ok\":false"));
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DayDelta {
    pub demand: u32,
    pub sales_total: u32,
    pub waste_total: u32,
    pub on_hand: u32,
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
    // Process-global session for the wasm worker (one bind, like Pyodide).
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
                serde_json::json!({"ok": true})
            }
            "step" => {
                let order = req.params.get("order").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                let demand = req.params.get("demand").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                serde_json::to_value(sess.step(order, demand)).unwrap()
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
                let demand = req.params.get("demand").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                serde_json::to_value(sess.step_n(&orders, demand)).unwrap()
            }
            "act" => serde_json::json!({"order": 0, "policy": "stub"}),
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
        let _ = s.step_n(&[8, 0, 8], 5);
        assert_eq!(s.host_crossings(), 1);
    }

    #[test]
    fn rpc_step_n_json() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let out = handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[8,0],"demand":0}}"#);
        assert!(out.contains("\"ok\":true"), "{out}");
    }
}
