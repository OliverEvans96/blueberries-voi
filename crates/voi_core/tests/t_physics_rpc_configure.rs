//! RPC configure must apply store-temperature physics knobs and echo them in applied_config.

use serde_json::Value;
use voi_core::handle_rpc;

fn applied_config(method: &str, config: &str) -> Value {
    let req = format!(
        r#"{{"id":"1","method":"{method}","params":{{"seed":1,"config":{config}}}}}"#
    );
    let out = handle_rpc(&req);
    let v: Value = serde_json::from_str(&out).unwrap_or_else(|_| panic!("bad json: {out}"));
    assert_eq!(v["ok"], true, "{method}: {out}");
    v["result"]["applied_config"].clone()
}

#[test]
fn rpc_configure_applies_q10_t_ref_t_store_and_echoes_physics() {
    let cfg = r#"{"q10":2.5,"t_ref_c":2.0,"t_store_c":6.0,"eta_ref":21.0,"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}"#;
    for method in ["init", "reset"] {
        let applied = applied_config(method, cfg);
        assert_eq!(applied["q10"].as_f64().unwrap(), 2.5);
        assert_eq!(applied["t_ref_c"].as_f64().unwrap(), 2.0);
        assert_eq!(applied["t_store_c"].as_f64().unwrap(), 6.0);
        assert_eq!(applied["eta_ref"].as_f64().unwrap(), 21.0);
    }
}

#[test]
fn rpc_configure_q10_changes_gamma_decrement_rate() {
    let cool = applied_config(
        "init",
        r#"{"q10":2.0,"t_ref_c":0.0,"t_store_c":4.0,"eta_ref":14.0,"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}"#,
    );
    let warm = applied_config(
        "reset",
        r#"{"q10":4.0,"t_ref_c":0.0,"t_store_c":4.0,"eta_ref":14.0,"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}"#,
    );
    assert!(warm["q10"].as_f64().unwrap() > cool["q10"].as_f64().unwrap());
}
