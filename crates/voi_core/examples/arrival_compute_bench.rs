//! One-shot timing bench: preview-tier Λ approximations vs full arrival integration.
//!
//! Run: cargo run --release --locked -p voi_core --example arrival_compute_bench

use std::time::Instant;

use voi_core::arrival::{embedded_arrival_model, export_baked_prior, ArrivalCondition, ArrivalModel};
use voi_core::physics::store_temp_factor;
use voi_core::ModelParams;

fn median_ms(samples: &[f64]) -> f64 {
    let mut v = samples.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v[v.len() / 2]
}

fn bench<F: FnMut()>(label: &str, warmup: u32, iters: u32, mut f: F) -> f64 {
    for _ in 0..warmup {
        f();
    }
    let mut ms = Vec::with_capacity(iters as usize);
    for _ in 0..iters {
        let t0 = Instant::now();
        f();
        ms.push(t0.elapsed().as_secs_f64() * 1000.0);
    }
    let med = median_ms(&ms);
    eprintln!("{label:48} median {med:8.3} ms  (n={iters})");
    med
}

fn preview_lambda_clean(d: f64, phi_set: f64) -> f64 {
    (d * phi_set).max(1e-6)
}

fn preview_lambda_break_delta(n: u32, tau_bar: f64, ber: f64) -> f64 {
    n as f64 * tau_bar * ber
}

fn main() {
    let json = embedded_arrival_model();
    let model = ArrivalModel::from_json(json).expect("from_json");
    let model_live = ArrivalModel::from_json_live(json).expect("from_json_live");
    let corridor = "abdella_all";
    let d_med = 5.5_f64;
    let phi_set = model.phi_set();
    let ber = model.break_exposure_rate();

    eprintln!("=== Preview-tier closed-form Λ (notebook lottery charts) ===");
    bench("preview: d·φ_set scalar", 1000, 10_000, || {
        let _ = preview_lambda_clean(d_med, phi_set);
    });
    bench("preview: ΔΛ break overlay (N=2)", 1000, 10_000, || {
        let _ = preview_lambda_break_delta(2, model.tau_bar, ber);
    });
    bench("preview: φ_set from legs (3 legs)", 1000, 10_000, || {
        let _ = model.phi_set();
    });
    bench("preview: φ(T) per thermal mode (×3)", 1000, 10_000, || {
        let mut s = 0.0;
        for mode in [&model.thermal_modes.cool, &model.thermal_modes.nominal, &model.thermal_modes.warm] {
            for leg in &model.legs {
                s += leg.weight
                    * store_temp_factor(leg.setpoint_c + mode.offset_c, model.t_ref, model.q10);
            }
        }
        std::hint::black_box(s);
    });

    eprintln!();
    eprintln!("=== Rust arrival model — Λ / channel laws (release, default artifact) ===");
    bench("rust: lambda_from_breaks(d=5.5, N=2 breaks)", 1000, 10_000, || {
        let _ = model.lambda_from_breaks(d_med, &[0.4, 0.3]);
    });
    bench(
        "rust: rung_law Prior grid=81 (studio chart wire)",
        3,
        20,
        || {
            let _ = model_live.rung_law_on_grid(ArrivalCondition::Prior, corridor, 81);
        },
    );
    bench(
        "rust: rung_law Duration(d=5) grid=81 (F2 chart wire)",
        3,
        20,
        || {
            let _ = model_live.rung_law_on_grid(ArrivalCondition::Duration(5), corridor, 81);
        },
    );
    bench(
        "rust: rung_law Exposure(Λ=7) grid=512 (F3 law)",
        3,
        20,
        || {
            let _ =
                model_live.rung_law_on_grid(ArrivalCondition::Exposure(7.0), corridor, 512);
        },
    );
    bench(
        "rust: rung_law Prior grid=512 (full arrival f dist)",
        1,
        5,
        || {
            let _ = model_live.rung_law_on_grid(ArrivalCondition::Prior, corridor, 512);
        },
    );
    bench(
        "rust: rung_law Prior grid=2 (lambda enum only, 1 f-point)",
        3,
        20,
        || {
            let _ = model_live.rung_law_on_grid(ArrivalCondition::Prior, corridor, 2);
        },
    );

    eprintln!();
    eprintln!("=== Rust prior rebuild paths (studio Reset / sync_params) ===");
    bench("rust: embedded() baked prior load", 3, 20, || {
        let _ = ArrivalModel::embedded();
    });
    bench("rust: from_json_live() + implicit prior build", 0, 3, || {
        let _ = ArrivalModel::from_json_live(json).expect("live");
    });
    bench("rust: export_baked_prior (full live integration)", 0, 3, || {
        let _ = export_baked_prior(json).expect("export");
    });
    let mut sync_model = ArrivalModel::embedded();
    let mut toggle = false;
    bench("rust: sync_params q10 change (prior rebuild)", 1, 5, || {
        toggle = !toggle;
        let mut p = ModelParams::default();
        p.q10 = if toggle { 3.1 } else { 3.0 };
        sync_model.sync_params(&p);
    });
    let mut break_model = ArrivalModel::embedded();
    bench("rust: set_break_rate rho toggle (prior rebuild)", 1, 5, || {
        let rho = if (break_model.rho - 0.08).abs() < 1e-6 {
            0.09
        } else {
            0.08
        };
        break_model.set_break_rate(rho);
    });

    eprintln!();
    eprintln!("=== Telemetry from last embedded sync (if any) ===");
    let mut m = ArrivalModel::embedded();
    m.clear_prior_rebuild_telemetry();
    let mut p = ModelParams::default();
    p.q10 = 3.25;
    m.sync_params(&p);
    eprintln!(
        "arrival_prior_rebuild_ms (sync_params q10): {}",
        m.prior_rebuild_ms_since_clear()
    );

    eprintln!();
    eprintln!("=== handle_rpc paths (native = WASM core) ===");
    use voi_core::handle_rpc;
    let init_base = serde_json::json!({
        "id": 1,
        "method": "init",
        "params": {
            "seed": 42,
            "n_particles": 16,
            "arrival_product": "abdella_all",
        }
    });
    let req_base = init_base.to_string();
    handle_rpc(&req_base);
    bench("handle_rpc init (baked prior, 2nd call)", 2, 10, || {
        let out = handle_rpc(&req_base);
        std::hint::black_box(out);
    });
    for (i, q10) in [(3.15_f64), (3.25), (3.35)].iter().enumerate() {
        let req = serde_json::json!({
            "id": 100 + i,
            "method": "init",
            "params": {
                "seed": 42,
                "n_particles": 16,
                "arrival_product": "abdella_all",
                "q10": q10,
            }
        });
        let t0 = Instant::now();
        let out = handle_rpc(&req.to_string());
        let ms = t0.elapsed().as_secs_f64() * 1000.0;
        let v: serde_json::Value = serde_json::from_str(&out).expect("json");
        let rebuilt = v["result"]["arrival_prior_rebuilt"].as_bool().unwrap_or(false);
        let rebuild_ms = v["result"]["arrival_prior_rebuild_ms"].as_u64().unwrap_or(0);
        eprintln!(
            "handle_rpc init q10={q10:.2} wall={ms:.1} ms  prior_rebuilt={rebuilt}  telemetry={rebuild_ms} ms"
        );
    }
}
