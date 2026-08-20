//! T-C2-A AC-unit-pf: unit_ll / unit_pf wiring and observation router (RED until implemented).

use std::fs;
use std::path::PathBuf;

use voi_core::obs::{mask_for, RichDay};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_src(name: &str) -> String {
    fs::read_to_string(manifest_dir().join("src").join(name))
        .unwrap_or_else(|err| panic!("failed to read src/{name}: {err}"))
}

fn read_lib_rs() -> String {
    read_src("lib.rs")
}

fn unit_ll_wired() -> bool {
    manifest_dir().join("src/unit_ll.rs").is_file() && read_lib_rs().contains("pub mod unit_ll")
}

fn unit_pf_wired() -> bool {
    manifest_dir().join("src/unit_pf.rs").is_file() && read_lib_rs().contains("pub mod unit_pf")
}

fn require_unit_ll() {
    if !manifest_dir().join("src/unit_ll.rs").is_file() {
        panic!("AC-unit-pf: missing crates/voi_core/src/unit_ll.rs");
    }
    let lib = read_lib_rs();
    if !lib.contains("pub mod unit_ll") {
        panic!("AC-unit-pf: lib.rs must declare `pub mod unit_ll`");
    }
    let body = read_src("unit_ll.rs");
    for sym in [
        "sequential_kernel_path_logprob",
        "p1_totals_loglik",
        "loglik_sales_by_units",
    ] {
        if !body.contains(sym) && !lib.contains(sym) {
            panic!("AC-unit-pf: unit_ll must export `{sym}`");
        }
    }
}

fn require_unit_pf() {
    if !manifest_dir().join("src/unit_pf.rs").is_file() {
        panic!("AC-unit-pf: missing crates/voi_core/src/unit_pf.rs");
    }
    let lib = read_lib_rs();
    if !lib.contains("pub mod unit_pf") {
        panic!("AC-unit-pf: lib.rs must declare `pub mod unit_pf`");
    }
    let body = read_src("unit_pf.rs");
    for sym in ["UnitParticleBank", "filter_step_unit"] {
        if !body.contains(sym) && !lib.contains(sym) {
            panic!("AC-unit-pf: unit_pf must export `{sym}`");
        }
    }
}

#[test]
fn unit_ll_module_file_present() {
    require_unit_ll();
}

#[test]
fn unit_pf_module_file_present() {
    require_unit_pf();
}

#[test]
fn filter_step_unit_uses_systematic_resample_not_multinomial() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("systematic_resample"),
        "filter_step_unit must resample via production systematic_resample"
    );
    assert!(
        !body.contains("fn resample(") || body.contains("systematic_resample"),
        "unit_pf must not use bench-style multinomial resample helper"
    );
}

#[test]
fn p1_router_scores_via_p1_totals_loglik() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("p1_totals_loglik"),
        "P1 totals path must call unit_ll::p1_totals_loglik"
    );
}

#[test]
fn f1_router_scores_via_loglik_sales_by_units() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("loglik_sales_by_units"),
        "sales_by path must call unit_ll::loglik_sales_by_units"
    );
}

#[test]
fn filter_never_synthesizes_sales_by_from_totals() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    let lowered = body.to_lowercase();
    assert!(
        !lowered.contains("sales_by = some") && !lowered.contains("sales_by=some"),
        "filter_step_unit must not invent sales_by from totals"
    );
}

#[test]
fn p1_mask_obs_sales_by_stays_none() {
    let rich = RichDay {
        sales_total: 5,
        waste_total: 2,
        arrivals: 0,
        sales_by: vec![3, 2],
        waste_by: vec![1, 1],
        lot_ids: vec![1, 2],
        f_at_receipt: None,
        age_at_receipt: None,
        pack_date_days: None,
    };
    let obs = mask_for("P1").expect("P1").apply(&rich);
    assert_eq!(obs.sales_tot, Some(5));
    assert_eq!(obs.waste_tot, Some(2));
    assert!(obs.sales_by.is_none(), "P1 mask must not expose sales_by");
}

#[test]
fn f1_mask_exposes_sales_by_for_router() {
    let rich = RichDay {
        sales_total: 5,
        waste_total: 2,
        arrivals: 0,
        sales_by: vec![3, 2],
        waste_by: vec![1, 1],
        lot_ids: vec![10, 11],
        f_at_receipt: None,
        age_at_receipt: None,
        pack_date_days: None,
    };
    let obs = mask_for("F1").expect("F1").apply(&rich);
    assert_eq!(obs.sales_by.as_deref(), Some(&[3u32, 2][..]));
    assert!(obs.sales_tot.is_some());
}

#[test]
fn sequential_kernel_path_logprob_feasible_finite() {
    require_unit_ll();
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::{sequential_kernel_path_logprob, ModelParams};

    let freshness = [0.8, 0.6, 0.4, 0.2];
    let params = ModelParams::default();
    let mut rng = Pcg64::seed_from_u64(7);
    let ll = sequential_kernel_path_logprob(&freshness, 2, &params, &mut rng);
    assert!(ll.is_finite(), "feasible path logprob must be finite, got {ll}");
}

#[test]
fn p1_totals_loglik_impossible_sales_neg_inf() {
    require_unit_ll();
    use voi_core::{p1_totals_loglik, ModelParams};

    let freshness = [0.1, 0.0, 0.0];
    let params = ModelParams::default();
    let ll = p1_totals_loglik(&freshness, 2, 0, &params);
    assert!(
        !ll.is_finite() || ll < -1e100,
        "infeasible sales must yield -inf, got {ll}"
    );
}

#[test]
fn unit_pf_l20_scripted_mean_f_mae_and_order_match() {
    require_unit_pf();
    require_unit_ll();

    use rand::Rng;
    use rand_distr::{Distribution, Gamma};
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::obs::FilterObs;
    use voi_core::policy::{
        damped_sw_order_f_belief, effective_inventory_f_belief,
    };
    use voi_core::{filter_step_unit, picking_weights_f, ModelParams, UnitParticleBank};

    const DAYS: usize = 14;
    const UNITS_PER_LOT: usize = 15;
    const N_PARTICLES: usize = 200;
    const N_LOTS: usize = 20;
    const K_WIRE: usize = 8;
    const MEAN_F_MAE_MAX: f64 = 0.02;
    const SCRIPTED_SEED: u64 = 50_000 + N_LOTS as u64 * 1_000;

    fn unit_tau(f: f64, eta: f64) -> f64 {
        (1.0 - f).max(0.0) * eta
    }

    fn lot_mean_f(units_f: &[f64], offsets: &[usize]) -> Vec<f64> {
        (0..offsets.len() - 1)
            .map(|ell| {
                let sl = &units_f[offsets[ell]..offsets[ell + 1]];
                sl.iter().sum::<f64>() / sl.len() as f64
            })
            .collect()
    }

    fn lot_tau_from_units(units_f: &[f64], offsets: &[usize], eta: f64) -> Vec<f64> {
        (0..offsets.len() - 1)
            .map(|ell| {
                let sl = &units_f[offsets[ell]..offsets[ell + 1]];
                let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
                if alive.is_empty() {
                    return 0.0;
                }
                let mean_f = alive.iter().sum::<f64>() / alive.len() as f64;
                unit_tau(mean_f, eta)
            })
            .collect()
    }

    fn f_grid_k(k: usize) -> Vec<f64> {
        if k <= 1 {
            return vec![0.0];
        }
        (0..k)
            .map(|i| i as f64 / ((k - 1) as f64))
            .collect()
    }

    fn f_to_bin(f: f64, grid: &[f64]) -> usize {
        grid.iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| (*a - f).abs().partial_cmp(&(*b - f).abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }

    fn belief_wire_from_particles(
        freshness: &[Vec<f64>],
        weights: &[f64],
        offsets: &[usize],
        k_wire: usize,
    ) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let l = offsets.len() - 1;
        let grid = f_grid_k(k_wire);
        let z: f64 = weights.iter().sum();
        let mut lot_counts = vec![0.0; l];
        let mut f_marginals = vec![0.0; l * k_wire];
        for (p, row) in freshness.iter().enumerate() {
            let w = if z > 0.0 { weights[p] / z } else { 0.0 };
            for ell in 0..l {
                let sl = &row[offsets[ell]..offsets[ell + 1]];
                let alive = sl.iter().filter(|&&f| f > 0.0).count() as f64;
                lot_counts[ell] += w * alive;
                if alive > 0.0 {
                    for &f in sl {
                        if f > 0.0 {
                            let b = f_to_bin(f, &grid);
                            f_marginals[ell * k_wire + b] += w / alive;
                        }
                    }
                }
            }
        }
        for ell in 0..l {
            let s: f64 = (0..k_wire).map(|b| f_marginals[ell * k_wire + b]).sum();
            if s > 0.0 {
                for b in 0..k_wire {
                    f_marginals[ell * k_wire + b] /= s;
                }
            }
        }
        (lot_counts, f_marginals, grid)
    }

    fn gamma_decrement(rng: &mut Pcg64, gamma: &Gamma<f64>) -> f64 {
        gamma.sample(rng)
    }

    fn simulate_pick_units(
        units_f: &[f64],
        offsets: &[usize],
        demand: usize,
        params: &ModelParams,
        rng: &mut Pcg64,
    ) -> Vec<bool> {
        let n_units = units_f.len();
        let l = offsets.len() - 1;
        let alive = vec![true; n_units];
        let mut sold = vec![false; n_units];
        let to_sell = demand.min(alive.iter().filter(|&&a| a).count());
        for _ in 0..to_sell {
            let idx_alive: Vec<usize> = (0..n_units)
                .filter(|&i| alive[i] && !sold[i])
                .collect();
            if idx_alive.is_empty() {
                break;
            }
            let alive_f: Vec<f64> = idx_alive.iter().map(|&i| units_f[i]).collect();
            let w = picking_weights_f(
                &alive_f,
                params.sigma,
                params.uniform_picking,
            );
            let tot: f64 = w.iter().sum();
            let j = if tot <= 0.0 {
                idx_alive[rng.random_range(0..idx_alive.len())]
            } else {
                let draw = rng.random::<f64>() * tot;
                let mut acc = 0.0;
                let mut picked = idx_alive[0];
                for (i, &wi) in w.iter().enumerate() {
                    acc += wi;
                    if draw < acc {
                        picked = idx_alive[i];
                        break;
                    }
                }
                picked
            };
            sold[j] = true;
        }
        sold
    }

    fn simulate_truth_day(
        units_f: &mut [f64],
        offsets: &[usize],
        params: &ModelParams,
        rng: &mut Pcg64,
        gamma: &Gamma<f64>,
    ) -> (i32, i32) {
        let before: Vec<f64> = units_f.to_vec();
        for f in units_f.iter_mut() {
            if *f > 0.0 {
                *f = (*f - gamma_decrement(rng, gamma)).max(0.0);
            }
        }
        let on_hand = units_f.iter().filter(|&&f| f > 0.0).count();
        let lo = (on_hand / 5).max(1);
        let hi = (on_hand / 3 + 1).max(2);
        let demand = rng.random_range(lo..hi).min(on_hand);
        let sold_mask = simulate_pick_units(units_f, offsets, demand, params, rng);
        let spoiled_before = before
            .iter()
            .zip(units_f.iter())
            .filter(|(&b, &u)| b > 0.0 && u <= 0.0)
            .count() as i32;
        for (u, &s) in units_f.iter_mut().zip(sold_mask.iter()) {
            if s {
                *u = 0.0;
            }
        }
        let spoiled_after = units_f
            .iter()
            .zip(sold_mask.iter())
            .zip(before.iter())
            .filter(|((&u, &s), &b)| u <= 0.0 && !s && b > 0.0)
            .count() as i32;
        let sales = sold_mask.iter().filter(|&&s| s).count() as i32;
        let waste = spoiled_before.max(spoiled_after);
        (sales, waste)
    }

    let params = ModelParams::default();
    let gamma = Gamma::new(params.gamma_shape, params.gamma_scale).expect("gamma");
    let offsets: Vec<usize> = (0..=N_LOTS).map(|i| i * UNITS_PER_LOT).collect();
    let total = N_LOTS * UNITS_PER_LOT;

    let mut rng = Pcg64::seed_from_u64(SCRIPTED_SEED);
    let mut units_f: Vec<f64> = (0..total)
        .map(|_| 0.45 + rng.random::<f64>() * 0.5)
        .collect();
    let mut bank = UnitParticleBank {
        weights: vec![1.0 / N_PARTICLES as f64; N_PARTICLES],
        freshness: (0..N_PARTICLES)
            .map(|_| (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect())
            .collect(),
    };

    for _day in 0..DAYS {
        let (sales, waste) = simulate_truth_day(&mut units_f, &offsets, &params, &mut rng, &gamma);
        let obs = FilterObs {
            sales_tot: Some(sales),
            waste_tot: Some(waste),
            arrivals: 0,
            ..Default::default()
        };
        filter_step_unit(&mut bank, &obs, &params, &mut rng);
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    let mut pred_mf = vec![0.0; N_LOTS];
    for p in 0..N_PARTICLES {
        for ell in 0..N_LOTS {
            let sl = &bank.freshness[p][offsets[ell]..offsets[ell + 1]];
            let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
            let mf = if alive.is_empty() {
                0.0
            } else {
                alive.iter().sum::<f64>() / alive.len() as f64
            };
            pred_mf[ell] += mf / N_PARTICLES as f64;
        }
    }

    let mean_f_mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / N_LOTS as f64;

    let truth_counts: Vec<u32> = (0..N_LOTS)
        .map(|ell| {
            units_f[offsets[ell]..offsets[ell + 1]]
                .iter()
                .filter(|&&f| f > 0.0)
                .count() as u32
        })
        .collect();
    let truth_counts_f: Vec<f64> = truth_counts.iter().map(|&n| f64::from(n)).collect();
    let mut truth_f_marginals = vec![0.0; N_LOTS * K_WIRE];
    let f_grid = f_grid_k(K_WIRE);
    for ell in 0..N_LOTS {
        if truth_counts[ell] == 0 {
            continue;
        }
        let sl = &units_f[offsets[ell]..offsets[ell + 1]];
        for &f in sl {
            if f > 0.0 {
                let b = f_to_bin(f, &f_grid);
                truth_f_marginals[ell * K_WIRE + b] += 1.0;
            }
        }
        let row = &mut truth_f_marginals[ell * K_WIRE..(ell + 1) * K_WIRE];
        let z: f64 = row.iter().sum();
        if z > 0.0 {
            for x in row.iter_mut() {
                *x /= z;
            }
        }
    }
    let truth_eff = effective_inventory_f_belief(
        &truth_counts_f,
        &truth_f_marginals,
        &f_grid,
        0,
        1.0,
    );

    let uniform_w = vec![1.0 / N_PARTICLES as f64; N_PARTICLES];
    let (pred_lc, pred_fm, pred_grid) =
        belief_wire_from_particles(&bank.freshness, &uniform_w, &offsets, K_WIRE);
    let belief_eff = effective_inventory_f_belief(&pred_lc, &pred_fm, &pred_grid, 0, 1.0);
    let _ = (truth_eff, belief_eff);

    let truth_order = damped_sw_order_f_belief(
        &truth_counts_f,
        &truth_f_marginals,
        &f_grid,
        0,
        7,
        &params,
        0.9,
        0.8,
        None,
        1.0,
    );
    let pred_order = damped_sw_order_f_belief(
        &pred_lc,
        &pred_fm,
        &pred_grid,
        0,
        7,
        &params,
        0.9,
        0.8,
        None,
        1.0,
    );

    assert!(
        mean_f_mae < MEAN_F_MAE_MAX,
        "mean_f MAE {mean_f_mae} must be < {MEAN_F_MAE_MAX}"
    );
    assert_eq!(
        truth_order,
        pred_order,
        "damped-SW order must match f-truth controller"
    );
}

#[test]
fn unit_ll_promoted_to_production() {
    let lib = read_lib_rs();
    assert!(lib.contains("pub mod unit_ll"), "production lib must export unit_ll");
}
