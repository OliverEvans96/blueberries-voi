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

fn demo_shipments() -> Vec<voi_core::ShipmentTrace> {
    voi_core::shipments::mod21_demo_shipments("short_haul")
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
        "pb_log_pmf",
        "pb_loglik_by_lot",
        "pb_sample_deaths",
        "spoil_probs_from_freshness",
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

/// ADR 0143: aggregate and GSIN paths score independent per-unit Poisson-binomial spoilage.
#[test]
fn aggregate_router_scores_poisson_binomial_spoilage() {
    require_unit_pf();
    let body = read_src("unit_pf.rs");
    assert!(
        body.contains("pb_loglik_by_lot") || body.contains("pb_log_pmf"),
        "unit_pf must score Poisson-binomial spoilage"
    );
    assert!(
        body.contains("spoil_probs_from_freshness"),
        "unit_pf must derive per-unit spoil probabilities"
    );
    assert!(
        !body.contains("spoil_delta_interval") && !body.contains("delta_interval_loglik"),
        "unit_pf must not use superseded interval spoil primitives"
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
        arrival_lot_ids: vec![],
        shipment_trace: None,
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
        arrival_lot_ids: vec![],
        shipment_trace: None,
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

    let mut freshness = [0.8, 0.6, 0.4, 0.2];
    let params = ModelParams::default();
    let mut rng = Pcg64::seed_from_u64(7);
    let ll = sequential_kernel_path_logprob(&mut freshness, 2, &params, &mut rng);
    assert!(
        ll.is_finite(),
        "feasible path logprob must be finite, got {ll}"
    );
}

#[test]
fn sequential_kernel_path_logprob_mutates_freshness() {
    require_unit_ll();
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::{sequential_kernel_path_logprob, ModelParams};

    let mut freshness = [0.8, 0.6, 0.4, 0.2];
    let params = ModelParams::default();
    let mut rng = Pcg64::seed_from_u64(7);
    let _ = sequential_kernel_path_logprob(&mut freshness, 2, &params, &mut rng);
    assert!(
        freshness.iter().filter(|&&f| f <= 0.0).count() >= 2,
        "sequential_kernel_path_logprob must zero picked units in &mut freshness"
    );
}

/// ADR 0137: the aggregate (UPC) sales weight is a one-sided feasibility gate on the
/// post-aging state. A day that demands more units than any particle holds alive must
/// rule out every particle, not merely down-weight them.
#[test]
fn aggregate_totals_weight_rejects_infeasible_sales() {
    require_unit_pf();
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::{filter_step_unit, FilterObs, ModelParams, UnitParticleBank};

    let n = 4;
    // One lot of three slots, only one of them alive.
    let mut bank =
        UnitParticleBank::from_rows_uniform_lots(vec![0.25; n], vec![vec![0.1, 0.0, 0.0]; n], 3);
    let obs = FilterObs {
        sales_tot: Some(2),
        waste_tot: Some(0),
        arrivals: 0,
        ..Default::default()
    };
    let mut rng = Pcg64::seed_from_u64(11);
    let diag = filter_step_unit(&mut bank, &obs, &ModelParams::default(), &demo_shipments(), &mut rng);
    assert_eq!(
        diag.infeasible, n,
        "sales beyond the alive count must be infeasible for every particle"
    );
}

/// Extract the signature (up to the opening brace) and body of one `pub fn` in `unit_ll.rs`.
fn unit_ll_fn(name: &str) -> (String, String) {
    let body = read_src("unit_ll.rs");
    let tail = body
        .split(&format!("pub fn {name}"))
        .nth(1)
        .unwrap_or_else(|| panic!("unit_ll.rs must define `{name}`"))
        .to_string();
    let sig = tail.split('{').next().unwrap_or("").to_string();
    let fn_body = tail.split("pub fn ").next().unwrap_or("").to_string();
    (sig, fn_body)
}

/// ADR 0135/0137: every importance-weight term is deterministic given the particle state.
/// Randomness lives in the proposal (adapted aging, unscored WOR removal), never in the
/// weight — an rng in one of these signatures would put Monte Carlo noise into the filter.
#[test]
fn production_likelihood_terms_take_no_rng() {
    require_unit_ll();
    for name in [
        "pb_log_pmf",
        "pb_loglik_by_lot",
        "spoil_probs_from_freshness",
        "loglik_sales_by_units",
    ] {
        let (sig, _) = unit_ll_fn(name);
        assert!(
            !sig.contains("rng"),
            "{name} must not take rng (deterministic weight per ADR 0135)"
        );
    }
}

/// The scored terms must not reach for the sampled sales path either: that path is drawn
/// for state removal only, and its log-probability is a diagnostic (ADR 0135).
#[test]
fn production_likelihood_terms_have_no_path_mc_in_body() {
    require_unit_ll();
    for name in ["pb_loglik_by_lot", "loglik_sales_by_units"] {
        let (_, fn_body) = unit_ll_fn(name);
        assert!(
            !fn_body.contains("sequential_kernel_path_logprob"),
            "{name} must not call sequential_kernel_path_logprob (deterministic gates only)"
        );
    }
}

/// ADR 0143 removed ADR-0137 shared-decrement interval spoilage outright.
#[test]
fn superseded_interval_spoil_primitives_are_gone() {
    require_unit_ll();
    let body = read_src("unit_ll.rs");
    let lib = read_lib_rs();
    for sym in [
        "spoil_delta_interval",
        "delta_interval_loglik",
        "DeltaInterval",
        "DELTA_ANY",
        "contrast_spoilage_weight",
    ] {
        assert!(
            !body.contains(sym) && !lib.contains(sym),
            "`{sym}` was superseded by ADR 0143 and must not be reintroduced"
        );
    }
}

/// ADR 0137 removed the pre-0137 binomial waste primitives outright rather than leaving
/// them exported: an unused `Binomial(waste; rem, dead/units)` term is a live invitation
/// to rewire the filter back onto a model the physics does not support.
#[test]
fn superseded_binomial_waste_primitives_are_gone() {
    require_unit_ll();
    let body = read_src("unit_ll.rs");
    let lib = read_lib_rs();
    for sym in [
        "p1_totals_loglik",
        "loglik_waste_by_units",
        "loglik_waste_tot_after_sales_by",
        "binom_pmf",
    ] {
        assert!(
            !body.contains(sym) && !lib.contains(sym),
            "`{sym}` was superseded by ADR 0137 and must not be reintroduced"
        );
    }
}

#[test]
fn loglik_sales_by_units_uses_multinomial_cross_lot_term() {
    require_unit_ll();
    let body = read_src("unit_ll.rs");
    assert!(
        body.contains("multinomial") || body.contains("lot_share"),
        "F1 sales likelihood must score cross-lot split via multinomial lot_share"
    );
}

#[test]
fn unit_pf_l20_scripted_mean_f_mae_and_order_match() {
    require_unit_pf();
    require_unit_ll();

    use rand::Rng;
    use rand::SeedableRng;
    use rand_distr::{Distribution, Gamma};
    use rand_pcg::Pcg64;
    use voi_core::obs::FilterObs;
    use voi_core::policy::{damped_sw_order_f_belief, effective_inventory_f_belief};
    use voi_core::{
        belief_flat_from_unit_bank, filter_step_unit, picking_weights_f, ModelParams,
        UnitParticleBank,
    };

    const DAYS: usize = 14;
    const UNITS_PER_LOT: usize = 15;
    const N_PARTICLES: usize = 200;
    const N_LOTS: usize = 20;
    const K_WIRE: usize = 8;
    const MEAN_F_MAE_MAX: f64 = 0.02;
    // Post-ADR-0135 re-baseline (deterministic P1 sales weight + unscored WOR removal):
    // release run, SCRIPTED_SEED below — mean_f_mae typically ≪ 0.02; order match 100%.
    // Pre-0135 (MC path in importance weight, no state mutation): ADR 0130 cited ~0.0014 @ L=20.
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
        (0..k).map(|i| i as f64 / ((k - 1) as f64)).collect()
    }

    fn f_to_bin(f: f64, grid: &[f64]) -> usize {
        grid.iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| (*a - f).abs().partial_cmp(&(*b - f).abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
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
            let idx_alive: Vec<usize> = (0..n_units).filter(|&i| alive[i] && !sold[i]).collect();
            if idx_alive.is_empty() {
                break;
            }
            let alive_f: Vec<f64> = idx_alive.iter().map(|&i| units_f[i]).collect();
            let w = picking_weights_f(&alive_f, params.sigma, params.uniform_picking);
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
    let mut bank = UnitParticleBank::from_rows_uniform_lots(
        vec![1.0 / N_PARTICLES as f64; N_PARTICLES],
        (0..N_PARTICLES)
            .map(|_| {
                (0..total)
                    .map(|_| 0.45 + rng.random::<f64>() * 0.5)
                    .collect()
            })
            .collect(),
        UNITS_PER_LOT,
    );

    for _day in 0..DAYS {
        let (sales, waste) = simulate_truth_day(&mut units_f, &offsets, &params, &mut rng, &gamma);
        let obs = FilterObs {
            sales_tot: Some(sales),
            waste_tot: Some(waste),
            arrivals: 0,
            ..Default::default()
        };
        filter_step_unit(&mut bank, &obs, &params, &demo_shipments(), &mut rng);
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    // Retired lots are dead in truth too, so the aligned view compares element-wise.
    let pred_mf: Vec<f64> = bank
        .lot_summary_aligned(N_LOTS)
        .into_iter()
        .map(|(_, mean_f)| mean_f)
        .collect();

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
    let truth_eff =
        effective_inventory_f_belief(&truth_counts_f, &truth_f_marginals, &f_grid, 0, 1.0);

    // Read the belief through the production studio wire rather than a local copy of it,
    // so this gate also covers `belief_flat`'s lot alignment.
    let wire = belief_flat_from_unit_bank(&bank, N_LOTS, K_WIRE);
    let json_vec = |key: &str| -> Vec<f64> {
        wire[key]
            .as_array()
            .map(|a| a.iter().filter_map(serde_json::Value::as_f64).collect())
            .unwrap_or_default()
    };
    let (pred_lc, pred_fm, pred_grid) = (
        json_vec("lot_counts"),
        json_vec("f_marginals"),
        json_vec("f_grid"),
    );
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
        &pred_lc, &pred_fm, &pred_grid, 0, 7, &params, 0.9, 0.8, None, 1.0,
    );

    assert!(
        mean_f_mae < MEAN_F_MAE_MAX,
        "mean_f MAE {mean_f_mae} must be < {MEAN_F_MAE_MAX} (post-ADR-0135 re-baseline)"
    );
    assert_eq!(
        truth_order, pred_order,
        "damped-SW order must match f-truth controller"
    );
}

#[test]
fn unit_ll_promoted_to_production() {
    let lib = read_lib_rs();
    assert!(
        lib.contains("pub mod unit_ll"),
        "production lib must export unit_ll"
    );
}

// --- T-136: P1/F1 sales likelihood unification ---

fn lot_offsets(n_lots: usize, units_per_lot: usize) -> Vec<usize> {
    (0..=n_lots).map(|i| i * units_per_lot).collect()
}

fn lot_mean_f(units_f: &[f64], offsets: &[usize]) -> Vec<f64> {
    (0..offsets.len() - 1)
        .map(|ell| {
            let sl = &units_f[offsets[ell]..offsets[ell + 1]];
            sl.iter().sum::<f64>() / sl.len() as f64
        })
        .collect()
}

fn lot_mean_f_alive(units_f: &[f64], offsets: &[usize]) -> Vec<f64> {
    (0..offsets.len() - 1)
        .map(|ell| {
            let sl = &units_f[offsets[ell]..offsets[ell + 1]];
            let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
            if alive.is_empty() {
                0.0
            } else {
                alive.iter().sum::<f64>() / alive.len() as f64
            }
        })
        .collect()
}

fn mean_f_mae(truth: &[f64], pred: &[f64]) -> f64 {
    truth
        .iter()
        .zip(pred.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / truth.len() as f64
}

#[test]
fn score_particle_mutates_freshness_after_finite_p1_ll() {
    require_unit_pf();
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::obs::FilterObs;
    use voi_core::{filter_step_unit, ModelParams, UnitParticleBank};

    let upl = 5;
    let units = upl * 2;
    let n = 2;
    let mut rng = Pcg64::seed_from_u64(99);
    let mut bank = UnitParticleBank::from_rows_uniform_lots(
        vec![0.5; n],
        vec![vec![0.9; units], vec![0.8; units]],
        upl,
    );
    let alive_before: usize = bank.freshness[0].iter().filter(|&&f| f > 0.0).count();
    let obs = FilterObs {
        sales_tot: Some(3),
        waste_tot: Some(0),
        arrivals: 0,
        ..Default::default()
    };
    filter_step_unit(&mut bank, &obs, &ModelParams::default(), &demo_shipments(), &mut rng);
    let alive_after: usize = bank.freshness[0].iter().filter(|&&f| f > 0.0).count();
    assert!(
        alive_after < alive_before,
        "after finite P1 likelihood, sold units must be removed from particle freshness"
    );
}

#[test]
fn unit_pf_f1_p1_relative_mean_f_mae() {
    require_unit_pf();
    require_unit_ll();

    use rand::Rng;
    use rand::SeedableRng;
    use rand_distr::{Distribution, Gamma};
    use rand_pcg::Pcg64;
    use voi_core::obs::{mask_for, RichDay};
    use voi_core::{filter_step_unit, ModelParams, UnitParticleBank};

    const DAYS: usize = 10;
    const UPL: usize = 15;
    const N_LOTS: usize = 8;
    const N: usize = 100;
    const SEED: u64 = 77_001;

    let params = ModelParams::default();
    let gamma = Gamma::new(params.gamma_shape, params.gamma_scale).expect("gamma");
    let offsets = lot_offsets(N_LOTS, UPL);
    let total = N_LOTS * UPL;

    let mut truth_rng = Pcg64::seed_from_u64(SEED);
    let mut units_f: Vec<f64> = (0..total)
        .map(|_| 0.4 + truth_rng.random::<f64>() * 0.5)
        .collect();
    let init_f: Vec<f64> = units_f.clone();

    let mut script: Vec<RichDay> = Vec::with_capacity(DAYS);
    for _ in 0..DAYS {
        let (sales, waste, sales_by, waste_by) =
            simulate_truth_day_with_split(&mut units_f, &offsets, &params, &mut truth_rng, &gamma);
        script.push(RichDay {
            sales_total: sales as u32,
            waste_total: waste as u32,
            arrivals: 0,
            sales_by,
            waste_by,
            lot_ids: (0..N_LOTS).map(|i| i as i64).collect(),
            arrival_lot_ids: vec![],
            shipment_trace: None,
            f_at_receipt: None,
            age_at_receipt: None,
            pack_date_days: None,
        });
    }
    let final_truth = units_f.clone();

    fn run_filter_on_script(
        use_f1: bool,
        init: &[f64],
        final_truth: &[f64],
        script: &[RichDay],
        offsets: &[usize],
        params: &ModelParams,
        seed: u64,
        n: usize,
    ) -> f64 {
        let total = init.len();
        let mut bank_rng = Pcg64::seed_from_u64(seed);
        let mut bank = UnitParticleBank::from_rows_uniform_lots(
            vec![1.0 / n as f64; n],
            (0..n)
                .map(|p| {
                    init.iter()
                        .enumerate()
                        .map(|(i, &f)| {
                            let noise = ((p * 13 + i * 29) % 100) as f64 / 800.0 - 0.06;
                            (f + noise).clamp(0.01, 1.0)
                        })
                        .collect()
                })
                .collect(),
            UPL,
        );
        for rich in script {
            let obs = if use_f1 {
                mask_for("F1").unwrap().apply(rich)
            } else {
                mask_for("P1").unwrap().apply(rich)
            };
            filter_step_unit(&mut bank, &obs, params, &demo_shipments(), &mut bank_rng);
        }
        let truth_mf = lot_mean_f_alive(final_truth, offsets);
        let pred_mf: Vec<f64> = bank
            .lot_summary_aligned(offsets.len() - 1)
            .into_iter()
            .map(|(_, mean_f)| mean_f)
            .collect();
        let _ = n;
        mean_f_mae(&truth_mf, &pred_mf)
    }

    let p1_mae = run_filter_on_script(
        false,
        &init_f,
        &final_truth,
        &script,
        &offsets,
        &params,
        SEED + 1,
        N,
    );
    let f1_mae = run_filter_on_script(
        true,
        &init_f,
        &final_truth,
        &script,
        &offsets,
        &params,
        SEED + 1,
        N,
    );

    assert!(
        f1_mae <= p1_mae + 1e-9,
        "F1 mean_f MAE {f1_mae} must be <= P1 mean_f MAE {p1_mae}"
    );
}

fn simulate_truth_day_with_split(
    units_f: &mut [f64],
    offsets: &[usize],
    params: &voi_core::ModelParams,
    rng: &mut rand_pcg::Pcg64,
    gamma: &rand_distr::Gamma<f64>,
) -> (i32, i32, Vec<u32>, Vec<u32>) {
    use rand::Rng;
    use rand_distr::Distribution;
    use voi_core::picking_weights_f;
    // One shared decrement per store-day, exactly as `physics::apply_gamma_aging` does —
    // and the spoilage it causes must be *reported*, or the filter is fed an observation
    // its own physics says is impossible.
    let dec = gamma.sample(rng);
    let l = offsets.len() - 1;
    let mut waste_by = vec![0u32; l];
    for i in 0..units_f.len() {
        if units_f[i] > 0.0 {
            let after = (units_f[i] - dec).max(0.0);
            if after <= 0.0 {
                for ell in 0..l {
                    if i >= offsets[ell] && i < offsets[ell + 1] {
                        waste_by[ell] += 1;
                    }
                }
            }
            units_f[i] = after;
        }
    }
    let waste: i32 = waste_by.iter().sum::<u32>() as i32;
    let on_hand = units_f.iter().filter(|&&f| f > 0.0).count();
    if on_hand == 0 {
        return (0, waste, vec![0; l], waste_by);
    }
    let demand = rng.random_range(1..=(on_hand / 3 + 1).max(2)).min(on_hand);
    let mut sales_by = vec![0u32; offsets.len() - 1];
    let mut sold = vec![false; units_f.len()];
    for _ in 0..demand {
        let idx_alive: Vec<usize> = (0..units_f.len())
            .filter(|&i| units_f[i] > 0.0 && !sold[i])
            .collect();
        if idx_alive.is_empty() {
            break;
        }
        let alive_f: Vec<f64> = idx_alive.iter().map(|&i| units_f[i]).collect();
        let w = picking_weights_f(&alive_f, params.sigma, params.uniform_picking);
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
        for ell in 0..offsets.len() - 1 {
            if j >= offsets[ell] && j < offsets[ell + 1] {
                sales_by[ell] += 1;
            }
        }
    }
    for (u, &s) in units_f.iter_mut().zip(sold.iter()) {
        if s {
            *u = 0.0;
        }
    }
    let sales = sold.iter().filter(|&&s| s).count() as i32;
    (sales, waste, sales_by, waste_by)
}

#[test]
fn unit_pf_f1_strictly_beats_p1_heterogeneous_lots() {
    require_unit_pf();
    require_unit_ll();

    use voi_core::obs::{mask_for, RichDay};
    use voi_core::physics::GammaDecrementTable;
    use voi_core::unit_ll::{loglik_sales_by_units, pb_log_pmf, pb_loglik_by_lot, spoil_probs_from_freshness};
    use voi_core::ModelParams;

    const UPL: usize = 15;
    let params = ModelParams::default();
    let n_lots = 2;
    let offsets = lot_offsets(n_lots, UPL);
    let total = n_lots * UPL;
    let n = 64;

    fn hetero_init(swapped: bool, upl: usize, total: usize) -> Vec<f64> {
        let mut v = vec![0.0; total];
        for i in 0..total {
            let stale = i < upl;
            let on_stale_lot = stale == !swapped;
            v[i] = if on_stale_lot { 0.10 } else { 0.90 };
        }
        v
    }

    let truth = hetero_init(false, UPL, total);
    let truth_mf = lot_mean_f_alive(&truth, &offsets);

    // Skewed split: most sales from the fresh lot (lot 1) — only F1 sees this.
    let sales_by = vec![1u32, 6u32];
    let rich = RichDay {
        sales_total: 7,
        waste_total: 0,
        arrivals: 0,
        sales_by: sales_by.clone(),
        waste_by: vec![0; n_lots],
        lot_ids: vec![1, 2],
        arrival_lot_ids: vec![],
        shipment_trace: None,
        f_at_receipt: None,
        age_at_receipt: None,
        pack_date_days: None,
    };
    let obs_f1 = mask_for("F1").unwrap().apply(&rich);
    let _obs_p1 = mask_for("P1").unwrap().apply(&rich);

    let particles: Vec<Vec<f64>> = (0..n)
        .map(|p| hetero_init(p >= n / 2, UPL, total))
        .collect();

    fn weighted_mean_f_mae(
        particles: &[Vec<f64>],
        log_weights: &[f64],
        truth_mf: &[f64],
        offsets: &[usize],
        n_lots: usize,
    ) -> f64 {
        let mx = log_weights
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max);
        let mut w: Vec<f64> = log_weights.iter().map(|lw| (lw - mx).exp()).collect();
        let z: f64 = w.iter().sum();
        if z <= 0.0 {
            return f64::INFINITY;
        }
        w.iter_mut().for_each(|x| *x /= z);
        let mut pred_mf = vec![0.0; n_lots];
        for (p, row) in particles.iter().enumerate() {
            for ell in 0..n_lots {
                let sl = &row[offsets[ell]..offsets[ell + 1]];
                let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
                let mf = if alive.is_empty() {
                    0.0
                } else {
                    alive.iter().sum::<f64>() / alive.len() as f64
                };
                pred_mf[ell] += w[p] * mf;
            }
        }
        mean_f_mae(truth_mf, &pred_mf)
    }

    // Score exactly as production does (ADR 0143): Poisson-binomial spoilage at the
    // resolution the channel observes, plus the sales term that channel can support.
    let mut p1_log_w = Vec::with_capacity(n);
    let mut f1_log_w = Vec::with_capacity(n);
    let table = GammaDecrementTable::for_params(&params);
    for row in &particles {
        let probs = spoil_probs_from_freshness(row, &table);
        let waste_ll_p1 = pb_log_pmf(&probs, 0);
        let alive = row.iter().filter(|&&f| f > 0.0).count();
        p1_log_w.push(if alive < 7 {
            f64::NEG_INFINITY
        } else {
            waste_ll_p1
        });

        let waste_by = obs_f1.waste_by.as_ref().expect("F1 exposes waste_by");
        let waste_ll_f1 = pb_loglik_by_lot(row, &offsets, waste_by, &table);
        f1_log_w.push(waste_ll_f1 + loglik_sales_by_units(row, &sales_by, &offsets, &params));
    }

    let p1_mae = weighted_mean_f_mae(&particles, &p1_log_w, &truth_mf, &offsets, n_lots);
    let f1_mae = weighted_mean_f_mae(&particles, &f1_log_w, &truth_mf, &offsets, n_lots);

    assert!(
        p1_mae > 0.2,
        "P1 must not resolve swapped heterogeneity (p1_mae={p1_mae})"
    );
    assert!(
        f1_mae < p1_mae - 0.05,
        "F1 mean_f MAE must strictly beat P1 on heterogeneous lots: f1={f1_mae} p1={p1_mae}"
    );
}

fn multinomial_log_pmf(counts: &[u32], probs: &[f64]) -> f64 {
    let n: u32 = counts.iter().sum();
    if n == 0 {
        return 0.0;
    }
    let mut log_p = 0.0;
    let mut log_coef = 0.0f64;
    let mut nn = n as f64;
    for &k in counts {
        for i in 0..k {
            log_coef += (nn - i as f64).ln() - (i as f64 + 1.0).ln();
        }
        nn -= k as f64;
    }
    log_p += log_coef;
    for (&k, &p) in counts.iter().zip(probs.iter()) {
        if p <= 0.0 && k > 0 {
            return f64::NEG_INFINITY;
        }
        if p > 0.0 && k > 0 {
            log_p += k as f64 * p.ln();
        }
    }
    log_p
}

#[test]
fn multinomial_vs_exact_wor_split_small_l() {
    require_unit_ll();
    use voi_core::picking_weights_f;
    use voi_core::ModelParams;

    let params = ModelParams::default();
    let freshness = [0.9, 0.8, 0.2, 0.1, 0.05, 0.04];
    let offsets = [0usize, 3, 6];
    let sales_tot = 3usize;

    let pooled_w = picking_weights_f(&freshness, params.sigma, params.uniform_picking);
    let mut lot_share = vec![0.0; 2];
    for ell in 0..2 {
        lot_share[ell] = pooled_w[offsets[ell]..offsets[ell + 1]].iter().sum();
    }
    let z: f64 = lot_share.iter().sum();
    for s in &mut lot_share {
        *s /= z;
    }

    let mut exact = std::collections::HashMap::<Vec<u32>, f64>::new();
    fn enum_splits(
        step: usize,
        remaining: usize,
        counts: &mut [u32],
        weights: &[f64],
        alive: &mut [bool],
        log_path: f64,
        out: &mut std::collections::HashMap<Vec<u32>, f64>,
        offsets: &[usize],
        n_lots: usize,
    ) {
        if step == remaining {
            let key: Vec<u32> = counts.to_vec();
            *out.entry(key).or_insert(0.0) += log_path.exp();
            return;
        }
        let mut tot = 0.0;
        for i in 0..weights.len() {
            if alive[i] {
                tot += weights[i];
            }
        }
        if tot <= 0.0 {
            return;
        }
        for i in 0..weights.len() {
            if !alive[i] {
                continue;
            }
            let p = weights[i] / tot;
            alive[i] = false;
            for ell in 0..n_lots {
                if i >= offsets[ell] && i < offsets[ell + 1] {
                    counts[ell] += 1;
                }
            }
            enum_splits(
                step + 1,
                remaining,
                counts,
                weights,
                alive,
                log_path + p.ln(),
                out,
                offsets,
                n_lots,
            );
            for ell in 0..n_lots {
                if i >= offsets[ell] && i < offsets[ell + 1] {
                    counts[ell] -= 1;
                }
            }
            alive[i] = true;
        }
    }
    let mut counts = vec![0u32; 2];
    let mut alive = freshness.iter().map(|&f| f > 0.0).collect::<Vec<_>>();
    enum_splits(
        0,
        sales_tot,
        &mut counts,
        &pooled_w,
        &mut alive,
        0.0,
        &mut exact,
        &offsets,
        2,
    );
    let z_exact: f64 = exact.values().sum();
    for v in exact.values_mut() {
        *v /= z_exact;
    }

    let mut tv = 0.0;
    for (counts, p_exact) in &exact {
        let p_multi = multinomial_log_pmf(counts, &lot_share).exp();
        tv += (p_exact - p_multi).abs();
    }
    assert!(
        tv < 0.45,
        "multinomial vs exact WOR split TV={tv} must be < 0.45 at small L (low-pressure spot check)"
    );
}

#[test]
fn multinomial_vs_wor_mc_realistic_l() {
    require_unit_ll();
    use rand::Rng;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::picking_weights_f;
    use voi_core::ModelParams;

    const L: usize = 20;
    const UPL: usize = 15;
    const SALES: usize = 8;
    const TRIALS: usize = 5000;
    const TV_MAX: f64 = 0.15;

    let params = ModelParams::default();
    let total = L * UPL;
    let offsets = lot_offsets(L, UPL);
    let freshness: Vec<f64> = (0..total)
        .map(|i| 0.3 + (i as f64 / total as f64) * 0.6)
        .collect();
    let pooled_w = picking_weights_f(&freshness, params.sigma, params.uniform_picking);
    let mut lot_share = vec![0.0; L];
    for ell in 0..L {
        lot_share[ell] = pooled_w[offsets[ell]..offsets[ell + 1]].iter().sum();
    }
    let z: f64 = lot_share.iter().sum();
    for s in &mut lot_share {
        *s /= z;
    }

    let mut rng = Pcg64::seed_from_u64(12345);
    let mut emp = vec![0.0; L];
    for _ in 0..TRIALS {
        let mut alive = freshness.iter().map(|&f| f > 0.0).collect::<Vec<_>>();
        let mut counts = vec![0u32; L];
        for _ in 0..SALES {
            let mut tot = 0.0;
            for i in 0..total {
                if alive[i] {
                    tot += pooled_w[i];
                }
            }
            if tot <= 0.0 {
                break;
            }
            let draw = rng.random::<f64>() * tot;
            let mut acc = 0.0;
            let mut picked = 0usize;
            for i in 0..total {
                if !alive[i] {
                    continue;
                }
                acc += pooled_w[i];
                if draw < acc {
                    picked = i;
                    break;
                }
            }
            alive[picked] = false;
            for ell in 0..L {
                if picked >= offsets[ell] && picked < offsets[ell + 1] {
                    counts[ell] += 1;
                }
            }
        }
        for ell in 0..L {
            emp[ell] += counts[ell] as f64 / SALES as f64;
        }
    }
    for e in &mut emp {
        *e /= TRIALS as f64;
    }

    let tv: f64 = emp
        .iter()
        .zip(lot_share.iter())
        .map(|(e, p)| (e - p).abs())
        .sum::<f64>()
        / 2.0;
    assert!(
        tv < TV_MAX,
        "empirical WOR lot-share vs multinomial lot_share TV={tv} must be < {TV_MAX}"
    );
}

#[test]
fn engine_session_init_belief_mass_zero() {
    let mut s = voi_core::EngineSession::new(42);
    s.init(42);
    s.set_belief_dims(2, 4);
    s.configure(2, true, 7, 2, 1, vec![], 32, None, None);
    s.set_obs_scenario("P1").unwrap();
    let snap = s.snapshot_value();
    let lc: Vec<f64> = snap["belief"]["lot_counts"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|x| x.as_f64())
        .collect();
    let mass: f64 = lc.iter().sum();
    assert!(
        mass.abs() < 1e-9,
        "init belief mass must be zero, got {mass}"
    );
}

#[test]
fn p1_f1_zero_sales_belief_mass_parity() {
    use voi_core::EngineSession;

    fn mass_after_zero_days(scenario: &str, days: u32) -> f64 {
        let mut s = EngineSession::new(42);
        s.init(42);
        s.set_belief_dims(2, 4);
        s.configure(2, true, 7, 2, 1, vec![], 32, None, None);
        s.set_obs_scenario(scenario).unwrap();
        for _ in 0..days {
            s.step(0);
        }
        let snap = s.snapshot_value();
        snap["belief"]["lot_counts"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_f64())
            .sum()
    }
    let p1 = mass_after_zero_days("P1", 8);
    let f1 = mass_after_zero_days("F1", 8);
    assert!(p1 <= 0.5, "P1 mass after 8 zero days {p1}");
    assert!(f1 <= 0.5, "F1 mass after 8 zero days {f1}");
}

#[test]
fn filter_birth_matches_arrival_qty_not_upl() {
    use rand::SeedableRng;
    use rand_pcg::Pcg64;
    use voi_core::obs::FilterObs;
    use voi_core::unit_pf::{filter_step_unit, UnitParticleBank};
    use voi_core::ModelParams;

    let upl = 15usize;
    let n = 8usize;
    let mut bank = UnitParticleBank::empty(n);
    let obs = FilterObs {
        sales_tot: Some(0),
        waste_tot: Some(0),
        arrivals: 8,
        ..Default::default()
    };
    let params = ModelParams {
        units_per_lot: upl,
        ..ModelParams::default()
    };
    let mut rng = Pcg64::seed_from_u64(99);
    filter_step_unit(&mut bank, &obs, &params, &demo_shipments(), &mut rng);
    let alive: usize = bank
        .freshness
        .iter()
        .map(|row| row.iter().filter(|&&f| f > 0.0).count())
        .sum();
    assert_eq!(
        alive,
        n * 8,
        "each particle should birth 8 units, got {alive}"
    );
}
