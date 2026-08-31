use std::time::Instant;
use voi_core::session::handle_rpc;

fn init_ms(q10: f64) -> (f64, bool) {
    let req = format!(
        r#"{{"id":"1","method":"init","params":{{"seed":42,"config":{{"q10":{},"eta_ref":14.0,"obs_scenario":"P1","arrival_product":"abdella_mix","n_particles":64,"H":5,"enable_filter":true}}}}}}"#,
        q10
    );
    let t0 = Instant::now();
    let out = handle_rpc(&req);
    let ms = t0.elapsed().as_secs_f64() * 1000.0;
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["ok"], true, "init failed: {}", out);
    let rebuilt = v["result"]["arrival_prior_rebuilt"].as_bool().unwrap_or(false);
    (ms, rebuilt)
}

#[test]
fn init_q10_two_uses_baked_fast_path() {
    let (ms, rebuilt) = init_ms(2.0);
    eprintln!("q10=2.0 init_ms={ms:.0} rebuilt={rebuilt}");
    assert!(!rebuilt, "expected baked prior fast path");
    assert!(ms < 2000.0, "q10=2 init took {ms}ms");
}

#[test]
#[ignore = "slow: live prior rebuild ~14s"]
fn init_q10_three_rebuilds_prior() {
    let (ms, rebuilt) = init_ms(3.0);
    eprintln!("q10=3.0 init_ms={ms:.0} rebuilt={rebuilt}");
    assert!(rebuilt);
}
