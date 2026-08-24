//! Obs-channel switch must move f_marginals on the wire (studio freshness chart).

use serde_json::Value;
use voi_core::handle_rpc;

fn rpc(method: &str, params: &str) -> Value {
    let req = format!(r#"{{"id":"1","method":"{method}","params":{params}}}"#);
    let out = handle_rpc(&req);
    let v: Value = serde_json::from_str(&out).unwrap_or_else(|_| panic!("bad json: {out}"));
    assert_eq!(v["ok"], true, "rpc {method} failed: {out}");
    v["result"].clone()
}

fn max_marginal_diff(a: &Value, b: &Value) -> f64 {
    let ma = a["belief"]["f_marginals"].as_array().unwrap();
    let mb = b["belief"]["f_marginals"].as_array().unwrap();
    ma.iter()
        .zip(mb.iter())
        .map(|(x, y)| (x.as_f64().unwrap_or(0.0) - y.as_f64().unwrap_or(0.0)).abs())
        .fold(0.0, f64::max)
}

fn max_history_diff(a: &Value, b: &Value) -> f64 {
    let ha = a["belief_history"].as_array().expect("belief_history array");
    let hb = b["belief_history"].as_array().expect("belief_history array");
    let mut max: f64 = 0.0;
    for ea in ha {
        let day = ea["day"].as_u64().unwrap();
        let eb = hb.iter().find(|e| e["day"].as_u64() == Some(day));
        if let Some(eb) = eb {
            max = max.max(max_marginal_diff(ea, eb));
        }
    }
    max
}

#[test]
fn set_obs_channels_moves_belief_history_p1_vs_f2() {
    rpc(
        "init",
        r#"{"seed":42,"config":{"arrival_product":"abdella_all","obs_scenario":"P1"}}"#,
    );
    rpc("step_n", r#"{"orders":[48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48,48]}"#);

    let p1 = rpc(
        "set_obs_channels",
        r#"{"code_type":"upc","scan_waste":true,"delivery_history":"none"}"#,
    );
    let f2 = rpc(
        "set_obs_channels",
        r#"{"code_type":"upc","scan_waste":true,"delivery_history":"pack_date"}"#,
    );

    assert!(
        p1["belief_history"].as_array().map(|a| a.len()).unwrap_or(0) >= 2,
        "expected belief_history replay, got {:?}",
        p1["belief_history"]
    );
    let term = max_marginal_diff(&p1, &f2);
    let hist = max_history_diff(&p1, &f2);
    assert!(
        term > 1e-6 || hist > 1e-6,
        "P1 vs F2 beliefs identical (term={term:.6} hist={hist:.6})"
    );
}
