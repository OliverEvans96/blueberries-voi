//! Per-trial JSON evaluator for T-163 joint arrival calibration (Ax subprocess).
//!
//! ```bash
//! cargo build -p voi_core --release --example t163_eval_trial
//! echo '{"p_short":0.7,"q10":2.8,"delta_c":0.0}' | ./target/release/examples/t163_eval_trial
//! ./target/release/examples/t163_eval_trial --benchmark
//! ```

use std::io::{self, Read};

use serde::Deserialize;
use serde_json::json;
use voi_core::{
    benchmark_fast_trial, benchmark_fast_vs_slow, evaluate_fast_trial, JointCalibFastResult,
};

#[derive(Debug, Clone, Deserialize)]
struct TrialInput {
    p_short: f64,
    q10: f64,
    delta_c: f64,
    #[serde(default)]
    include_ac2_11a: bool,
    #[serde(default = "default_ac2_11a_seed")]
    ac2_11a_seed: u64,
}

fn default_ac2_11a_seed() -> u64 {
    150_211
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--benchmark") {
        let fast_s = benchmark_fast_trial();
        let (fast_only, with_slow) = benchmark_fast_vs_slow();
        println!(
            "{}",
            json!({
                "benchmark": true,
                "fast_metrics_s": fast_only,
                "with_ac2_11a_s": with_slow,
                "representative_fast_s": fast_s,
            })
        );
        return;
    }

    let mut payload = String::new();
    io::stdin()
        .read_to_string(&mut payload)
        .expect("read stdin");
    if payload.trim().is_empty() {
        eprintln!("usage: t163_eval_trial [--benchmark]  (JSON trial on stdin)");
        std::process::exit(1);
    }
    let input: TrialInput = serde_json::from_str(&payload).expect("parse stdin JSON");
    let result: JointCalibFastResult = evaluate_fast_trial(
        input.p_short,
        input.q10,
        input.delta_c,
        input.include_ac2_11a,
        input.ac2_11a_seed,
    );
    println!("{}", serde_json::to_string(&result).expect("serialize result"));
}
