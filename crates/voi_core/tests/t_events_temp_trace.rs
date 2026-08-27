//! F3 events wire must expose non-constant shipment temperature histories.

use serde_json::Value;
use voi_core::handle_rpc;

const LOTS_PER_DELIVERY: usize = 3;

fn rpc(method: &str, params: &str) -> Value {
    let req = format!(r#"{{"id":"1","method":"{method}","params":{params}}}"#);
    let out = handle_rpc(&req);
    let v: Value = serde_json::from_str(&out).unwrap_or_else(|_| panic!("bad json: {out}"));
    assert_eq!(v["ok"], true, "rpc {method} failed: {out}");
    v["result"].clone()
}

#[test]
fn events_f3_temp_trace_is_non_constant() {
    rpc(
        "init",
        r#"{"seed":42,"config":{"arrival_product":"abdella_all","obs_scenario":"F3"}}"#,
    );
    rpc(
        "step_n",
        r#"{"orders":[48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48]}"#,
    );
    let events = rpc("events", r#"{"since_day":0}"#);
    let days = events["days"]
        .as_array()
        .expect("events.days array must exist");
    let delivery_days: Vec<&Value> = days
        .iter()
        .filter(|d| d["arrivals"].as_u64().unwrap_or(0) > 0)
        .collect();
    assert!(
        !delivery_days.is_empty(),
        "expected at least one delivery day in events wire"
    );
    for day in delivery_days {
        let traces = day["temp_traces_by_lot"]
            .as_array()
            .expect("F3 mask must expose temp_traces_by_lot on delivery days");
        assert_eq!(
            traces.len(),
            LOTS_PER_DELIVERY,
            "expected {LOTS_PER_DELIVERY} per-lot traces on day {:?}, got {:?}",
            day["day"],
            traces.len()
        );
        for (ell, tr) in traces.iter().enumerate() {
            let temps = tr["temps_c"]
                .as_array()
                .expect("per-lot trace temps_c");
            assert!(
                temps.len() >= 3,
                "expected multi-point trace for lot {ell} on day {:?}, got {:?}",
                day["day"],
                temps
            );
            let values: Vec<f64> = temps.iter().filter_map(|t| t.as_f64()).collect();
            let min_t = values.iter().cloned().fold(f64::INFINITY, f64::min);
            let max_t = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            assert!(
                (max_t - min_t).abs() > 0.05,
                "constant temp trace {:?} for lot {ell} on day {:?}",
                values,
                day["day"]
            );
        }
    }
}
