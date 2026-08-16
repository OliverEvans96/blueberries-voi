//! Focused study: C2 Algorithm A + P1 totals-only (sales_total + waste_total).
//!
//! Measures timing at L ∈ {4,8,12,16,20}, accuracy vs unit truth, and whether
//! binned particle beliefs are usable for controller / studio visualization.
//!
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_a_totals_study -- --probe
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_a_totals_study

use std::env;
use std::fs;
use std::time::Instant;

use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma};
use rand_pcg::Pcg64;
use serde::Serialize;
use voi_core::exact_ll::binom_pmf;
use voi_core::policy::{damped_sw_order, damped_sw_order_belief, effective_inventory};
use voi_core::{picking_weights, ModelParams};

const DAYS: usize = 14;
const UNITS_PER_LOT: usize = 15;
const N_PARTICLES: usize = 200;
const L_VALUES: [usize; 5] = [4, 8, 12, 16, 20];
const K_WIRE: [usize; 4] = [4, 8, 16, 32];
const TIMING_REPS: usize = 20;
const TIMING_WARMUP: usize = 5;

#[derive(Clone, Debug, Serialize)]
struct RepMetrics {
    mean_f_mae: f64,
    /// TV on equal-weight mean of per-particle unit histograms (legacy metric).
    hist_tv_particle_mean: f64,
    /// TV on ESS-weighted belief wire (lot_counts + age_marginals @ K).
    hist_tv_belief_wire: f64,
    belief_wire_k: usize,
    tau_lot_mae: f64,
    eff_inv_rel_err: f64,
    order_qty_match: f64,
    order_qty_abs_diff: f64,
    lot_rank_spearman: f64,
    ess_final: f64,
    ess_min: f64,
    coverage90_mean_f: f64,
}

#[derive(Clone, Debug, Serialize)]
struct TimingRow {
    n_lots: usize,
    units_per_lot: usize,
    units_total: usize,
    mean_ms: f64,
    p95_ms: f64,
}

#[derive(Clone, Debug, Serialize)]
struct AccRow {
    n_lots: usize,
    n_reps: usize,
    belief_wire_k: usize,
    metrics: RepMetrics,
    mean_f_mae_se: f64,
    hist_tv_belief_wire_se: f64,
    eff_inv_rel_err_se: f64,
    order_qty_match_rate: f64,
}

#[derive(Clone, Debug, Serialize)]
struct StudyReport {
    study: &'static str,
    probe: bool,
    wall_seconds: f64,
    n_particles: usize,
    units_per_lot: usize,
    obs_mode: &'static str,
    timing: Vec<TimingRow>,
    accuracy: Vec<AccRow>,
    k_sensitivity_l20: Vec<AccRow>,
}

fn ess(weights: &[f64]) -> f64 {
    let z: f64 = weights.iter().sum();
    if z <= 0.0 {
        return 0.0;
    }
    let w: Vec<f64> = weights.iter().map(|x| x / z).collect();
    1.0 / w.iter().map(|x| x * x).sum::<f64>()
}

fn tv(p: &[f64], q: &[f64]) -> f64 {
    0.5 * p.iter().zip(q).map(|(a, b)| (a - b).abs()).sum::<f64>()
}

fn freshness_bins(k: usize) -> Vec<f64> {
    (0..=k).map(|i| i as f64 / k as f64).collect()
}

fn tau_grid_k(k: usize) -> Vec<f64> {
    if k == 0 {
        return Vec::new();
    }
    if k == 1 {
        return vec![0.0];
    }
    const LO: f64 = 0.0;
    const HI: f64 = 8.0;
    (0..k)
        .map(|i| LO + (HI - LO) * (i as f64) / ((k - 1) as f64))
        .collect()
}

fn f_to_bin(f: f64, edges: &[f64]) -> usize {
    if f <= edges[0] {
        return 0;
    }
    if f >= edges[edges.len() - 1] {
        return edges.len() - 2;
    }
    let mut lo = 0usize;
    let mut hi = edges.len() - 1;
    while lo + 1 < hi {
        let mid = (lo + hi) / 2;
        if edges[mid] <= f {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    lo
}

fn tau_to_bin(tau: f64, grid: &[f64]) -> usize {
    grid.iter()
        .enumerate()
        .min_by(|(_, a), (_, b)| (*a - tau).abs().partial_cmp(&(*b - tau).abs()).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0)
}

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

fn truth_hist_per_lot(units_f: &[f64], offsets: &[usize], k: usize) -> Vec<Vec<f64>> {
    let edges = freshness_bins(k);
    let l = offsets.len() - 1;
    let mut h = vec![vec![0.0f64; k]; l];
    for ell in 0..l {
        for &f in &units_f[offsets[ell]..offsets[ell + 1]] {
            h[ell][f_to_bin(f, &edges)] += 1.0;
        }
        let s: f64 = h[ell].iter().sum();
        if s > 0.0 {
            for x in &mut h[ell] {
                *x /= s;
            }
        }
    }
    h
}

fn spearman(x: &[f64], y: &[f64]) -> f64 {
    if x.len() != y.len() || x.is_empty() {
        return f64::NAN;
    }
    let n = x.len();
    fn ranks(v: &[f64]) -> Vec<f64> {
        let mut idx: Vec<usize> = (0..v.len()).collect();
        idx.sort_by(|&a, &b| v[a].partial_cmp(&v[b]).unwrap());
        let mut r = vec![0.0; v.len()];
        let mut i = 0;
        while i < idx.len() {
            let mut j = i;
            while j + 1 < idx.len() && (v[idx[j + 1]] - v[idx[j]]).abs() < 1e-12 {
                j += 1;
            }
            let avg = (i + j) as f64 / 2.0 + 1.0;
            for k in i..=j {
                r[idx[k]] = avg;
            }
            i = j + 1;
        }
        r
    }
    let rx = ranks(x);
    let ry = ranks(y);
    let mx = rx.iter().sum::<f64>() / n as f64;
    let my = ry.iter().sum::<f64>() / n as f64;
    let mut num = 0.0;
    let mut dx = 0.0;
    let mut dy = 0.0;
    for i in 0..n {
        let a = rx[i] - mx;
        let b = ry[i] - my;
        num += a * b;
        dx += a * a;
        dy += b * b;
    }
    if dx <= 0.0 || dy <= 0.0 {
        return 0.0;
    }
    num / (dx * dy).sqrt()
}

fn percentile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let idx = ((p / 100.0) * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn belief_wire_from_particles(
    freshness: &[Vec<f64>],
    weights: &[f64],
    offsets: &[usize],
    k_wire: usize,
    eta: f64,
) -> (Vec<f64>, Vec<f64>) {
    let l = offsets.len() - 1;
    let grid = tau_grid_k(k_wire);
    let z: f64 = weights.iter().sum();
    let mut lot_counts = vec![0.0; l];
    let mut age_marginals = vec![0.0; l * k_wire];
    for (p, row) in freshness.iter().enumerate() {
        let w = if z > 0.0 { weights[p] / z } else { 0.0 };
        for ell in 0..l {
            let sl = &row[offsets[ell]..offsets[ell + 1]];
            let alive = sl.iter().filter(|&&f| f > 0.0).count() as f64;
            lot_counts[ell] += w * alive;
            if alive > 0.0 {
                for &f in sl {
                    if f > 0.0 {
                        let tau = unit_tau(f, eta);
                        let b = tau_to_bin(tau, &grid);
                        age_marginals[ell * k_wire + b] += w / alive;
                    }
                }
            }
        }
    }
  // normalize rows
    for ell in 0..l {
        let s: f64 = (0..k_wire).map(|b| age_marginals[ell * k_wire + b]).sum();
        if s > 0.0 {
            for b in 0..k_wire {
                age_marginals[ell * k_wire + b] /= s;
            }
        } else {
            for b in 0..k_wire {
                age_marginals[ell * k_wire + b] = 1.0 / k_wire as f64;
            }
        }
    }
    (lot_counts, age_marginals)
}

fn truth_belief_wire(
    units_f: &[f64],
    offsets: &[usize],
    k_wire: usize,
    eta: f64,
) -> (Vec<f64>, Vec<f64>) {
    let l = offsets.len() - 1;
    let grid = tau_grid_k(k_wire);
    let mut lot_counts = vec![0.0; l];
    let mut age_marginals = vec![0.0; l * k_wire];
    for ell in 0..l {
        let sl = &units_f[offsets[ell]..offsets[ell + 1]];
        let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
        lot_counts[ell] = alive.len() as f64;
        if alive.is_empty() {
            for b in 0..k_wire {
                age_marginals[ell * k_wire + b] = 1.0 / k_wire as f64;
            }
            continue;
        }
        for &f in &alive {
            let tau = unit_tau(f, eta);
            let b = tau_to_bin(tau, &grid);
            age_marginals[ell * k_wire + b] += 1.0 / alive.len() as f64;
        }
    }
    (lot_counts, age_marginals)
}

fn wire_hist_tv(
    truth_lc: &[f64],
    truth_am: &[f64],
    pred_lc: &[f64],
    pred_am: &[f64],
    k: usize,
) -> f64 {
    let l = truth_lc.len();
    let mut tvs = Vec::with_capacity(l);
    for ell in 0..l {
        if truth_lc[ell] <= 0.0 && pred_lc[ell] <= 0.0 {
            continue;
        }
        let t: Vec<f64> = (0..k).map(|b| truth_am[ell * k + b]).collect();
        let p: Vec<f64> = (0..k).map(|b| pred_am[ell * k + b]).collect();
        tvs.push(tv(&t, &p));
    }
    if tvs.is_empty() {
        return 0.0;
    }
    tvs.iter().sum::<f64>() / tvs.len() as f64
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
) -> (Vec<bool>, Vec<usize>) {
    let n_units = units_f.len();
    let l = offsets.len() - 1;
    let alive = vec![true; n_units];
    let mut sold = vec![false; n_units];
    let mut sales_by = vec![0usize; l];
    let to_sell = demand.min(alive.iter().filter(|&&a| a).count());
    for _ in 0..to_sell {
        let idx_alive: Vec<usize> = (0..n_units)
            .filter(|&i| alive[i] && !sold[i])
            .collect();
        if idx_alive.is_empty() {
            break;
        }
        let taus: Vec<f64> = idx_alive
            .iter()
            .map(|&i| unit_tau(units_f[i], params.eta_ref))
            .collect();
        let w = picking_weights(
            &taus,
            params.sigma,
            params.beta,
            params.eta_ref,
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
        for ell in 0..l {
            if offsets[ell] <= j && j < offsets[ell + 1] {
                sales_by[ell] += 1;
                break;
            }
        }
    }
    (sold, sales_by)
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
    let (sold_mask, _) = simulate_pick_units(units_f, offsets, demand, params, rng);
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

fn sequential_kernel_path_logprob(
    freshness: &[f64],
    sales: usize,
    params: &ModelParams,
    rng: &mut Pcg64,
) -> f64 {
    let taus: Vec<f64> = freshness
        .iter()
        .map(|&f| unit_tau(f, params.eta_ref))
        .collect();
    let base_w = picking_weights(
        &taus,
        params.sigma,
        params.beta,
        params.eta_ref,
        params.uniform_picking,
    );
    let mut alive = vec![true; freshness.len()];
    let mut log_p = 0.0;
    for _ in 0..sales {
        let mut tot = 0.0;
        for i in 0..freshness.len() {
            if alive[i] {
                tot += base_w[i];
            }
        }
        if tot <= 0.0 {
            return f64::NEG_INFINITY;
        }
        let draw = rng.random::<f64>() * tot;
        let mut acc = 0.0;
        let mut picked = 0usize;
        for i in 0..freshness.len() {
            if !alive[i] {
                continue;
            }
            acc += base_w[i];
            if draw < acc {
                picked = i;
                break;
            }
        }
        log_p += (base_w[picked] / tot).ln();
        alive[picked] = false;
    }
    log_p
}

fn p1_totals_loglik(
    freshness: &[f64],
    sales: i32,
    waste: i32,
    params: &ModelParams,
    rng: &mut Pcg64,
) -> f64 {
    let units = freshness.len();
    let alive = freshness.iter().filter(|&&f| f > 0.0).count();
    if alive < sales as usize {
        return f64::NEG_INFINITY;
    }
    let ll_sales = sequential_kernel_path_logprob(freshness, sales as usize, params, rng);
    if !ll_sales.is_finite() {
        return f64::NEG_INFINITY;
    }
    let dead = freshness.iter().filter(|&&f| f <= 0.0).count() as i32;
    let rem = alive as i32 - sales;
    let p_die = (dead as f64 / units as f64).clamp(0.0, 1.0);
    let pw = binom_pmf(waste, rem, p_die);
    if pw <= 0.0 {
        return f64::NEG_INFINITY;
    }
    ll_sales + pw.ln()
}

fn resample(rng: &mut Pcg64, n: usize, w: &[f64]) -> Vec<usize> {
    let mut idx = Vec::with_capacity(n);
    for _ in 0..n {
        let u = rng.random::<f64>();
        let mut cdf = 0.0;
        let mut chosen = w.len().saturating_sub(1);
        for (i, &wi) in w.iter().enumerate() {
            cdf += wi;
            if u <= cdf {
                chosen = i;
                break;
            }
        }
        idx.push(chosen);
    }
    idx
}

fn one_day_update(
    freshness: &mut Vec<Vec<f64>>,
    sales: i32,
    waste: i32,
    params: &ModelParams,
    gamma: &Gamma<f64>,
    rng: &mut Pcg64,
    seed: u64,
    day: usize,
) -> Vec<f64> {
    let n = freshness.len();
    let mut log_w = vec![0.0f64; n];
    for p in 0..n {
        for f in &mut freshness[p] {
            if *f > 0.0 {
                *f = (*f - gamma_decrement(rng, gamma)).max(0.0);
            }
        }
        let mut path_rng =
            Pcg64::seed_from_u64(seed.wrapping_add(p as u64).wrapping_add(day as u64));
        log_w[p] = p1_totals_loglik(&freshness[p], sales, waste, params, &mut path_rng);
    }
    let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - mx).exp()).collect();
    let z: f64 = w.iter().sum();
    for x in &mut w {
        *x /= z.max(1e-300);
    }
    let idx = resample(rng, n, &w);
    *freshness = idx.into_iter().map(|i| freshness[i].clone()).collect();
    w
}

fn time_one_day(n_lots: usize, upl: usize, params: &ModelParams, gamma: &Gamma<f64>) -> f64 {
    let units = n_lots * upl;
    let mut rng = Pcg64::seed_from_u64(99);
    let mut freshness: Vec<Vec<f64>> = (0..N_PARTICLES)
        .map(|_| (0..units).map(|_| 0.5 + rng.random::<f64>() * 0.4).collect())
        .collect();
    let sales = 12i32;
    let waste = 2i32;
    let t0 = Instant::now();
    one_day_update(
        &mut freshness,
        sales,
        waste,
        params,
        gamma,
        &mut rng,
        99,
        0,
    );
    t0.elapsed().as_secs_f64() * 1000.0
}

fn run_rep(
    n_lots: usize,
    seed: u64,
    k_wire: usize,
    params: &ModelParams,
    gamma: &Gamma<f64>,
) -> RepMetrics {
    let upl = UNITS_PER_LOT;
    let total = n_lots * upl;
    let offsets: Vec<usize> = (0..=n_lots).map(|i| i * upl).collect();
    let score_k = 32usize;

    let mut rng = Pcg64::seed_from_u64(seed);
    let mut units_f: Vec<f64> = (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect();
    let mut freshness: Vec<Vec<f64>> = (0..N_PARTICLES)
        .map(|_| (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect())
        .collect();
    let mut ess_trace = Vec::new();

    for day in 0..DAYS {
        let (sales, waste) = simulate_truth_day(&mut units_f, &offsets, params, &mut rng, gamma);
        let w = one_day_update(
            &mut freshness,
            sales,
            waste,
            params,
            gamma,
            &mut rng,
            seed,
            day,
        );
        ess_trace.push(ess(&w));
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    let truth_h = truth_hist_per_lot(&units_f, &offsets, score_k);
    let truth_tau = lot_tau_from_units(&units_f, &offsets, params.eta_ref);
    let truth_counts: Vec<u32> = (0..n_lots)
        .map(|ell| units_f[offsets[ell]..offsets[ell + 1]].iter().filter(|&&f| f > 0.0).count() as u32)
        .collect();
    let truth_eff = effective_inventory(&truth_counts, &truth_tau, 0, params);

    let uniform_w = vec![1.0 / N_PARTICLES as f64; N_PARTICLES];
    let (pred_lc, pred_am) =
        belief_wire_from_particles(&freshness, &uniform_w, &offsets, k_wire, params.eta_ref);
    let (truth_lc, truth_am) = truth_belief_wire(&units_f, &offsets, k_wire, params.eta_ref);

    let mut pred_mf = vec![0.0; n_lots];
    let mut pred_h = vec![vec![0.0; score_k]; n_lots];
    let mut pred_tau_acc = vec![0.0; n_lots];
    let mut particle_mf = vec![vec![0.0; n_lots]; N_PARTICLES];
    for p in 0..N_PARTICLES {
        let ptau = lot_tau_from_units(&freshness[p], &offsets, params.eta_ref);
        for ell in 0..n_lots {
            let sl = &freshness[p][offsets[ell]..offsets[ell + 1]];
            let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
            let mf = if alive.is_empty() {
                0.0
            } else {
                alive.iter().sum::<f64>() / alive.len() as f64
            };
            particle_mf[p][ell] = mf;
            pred_mf[ell] += mf / N_PARTICLES as f64;
            pred_tau_acc[ell] += ptau[ell] / N_PARTICLES as f64;
            for &f in &alive {
                pred_h[ell][f_to_bin(f, &freshness_bins(score_k))] += 1.0 / N_PARTICLES as f64;
            }
        }
    }
    for ell in 0..n_lots {
        let s: f64 = pred_h[ell].iter().sum();
        if s > 0.0 {
            for x in &mut pred_h[ell] {
                *x /= s;
            }
        }
    }

    let mean_f_mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;

    let hist_tv_particle_mean = (0..n_lots)
        .map(|ell| tv(&pred_h[ell], &truth_h[ell]))
        .sum::<f64>()
        / n_lots as f64;

    let wire_tv = wire_hist_tv(&truth_lc, &truth_am, &pred_lc, &pred_am, k_wire);

    let pred_tau = pred_tau_acc;
    let tau_lot_mae = pred_tau
        .iter()
        .zip(truth_tau.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;

    let grid = tau_grid_k(k_wire);
    let belief_eff = voi_core::policy::effective_inventory_belief(
        &pred_lc,
        &pred_am,
        &grid,
        0,
        params,
    );
    let eff_inv_rel_err = if truth_eff.abs() > 1e-6 {
        ((belief_eff - truth_eff) / truth_eff).abs()
    } else {
        (belief_eff - truth_eff).abs()
    };

    let truth_order = damped_sw_order(&truth_counts, &truth_tau, 0, 7, params, 0.9, 0.8, None);
    let pred_order = damped_sw_order_belief(
        &pred_lc,
        &pred_am,
        &grid,
        0,
        7,
        params,
        0.9,
        0.8,
        None,
    );
    let order_qty_match = if truth_order == pred_order { 1.0 } else { 0.0 };
    let order_qty_abs_diff = (truth_order as i32 - pred_order as i32).unsigned_abs() as f64;

    let lot_rank_spearman = spearman(&pred_mf, &truth_mf);

    let mut cov = 0.0;
    for ell in 0..n_lots {
        let col: Vec<f64> = particle_mf.iter().map(|row| row[ell]).collect();
        let mut sorted = col.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let lo = percentile(&sorted, 5.0);
        let hi = percentile(&sorted, 95.0);
        if truth_mf[ell] >= lo && truth_mf[ell] <= hi {
            cov += 1.0;
        }
    }

    RepMetrics {
        mean_f_mae,
        hist_tv_particle_mean,
        hist_tv_belief_wire: wire_tv,
        belief_wire_k: k_wire,
        tau_lot_mae,
        eff_inv_rel_err,
        order_qty_match,
        order_qty_abs_diff,
        lot_rank_spearman,
        ess_final: *ess_trace.last().unwrap_or(&f64::NAN),
        ess_min: ess_trace.iter().copied().fold(f64::INFINITY, f64::min),
        coverage90_mean_f: cov / n_lots as f64,
    }
}

fn aggregate(reps: &[RepMetrics], n_lots: usize, k_wire: usize) -> AccRow {
    let mean = |f: fn(&RepMetrics) -> f64| -> f64 {
        reps.iter().map(f).sum::<f64>() / reps.len().max(1) as f64
    };
    let se = |f: fn(&RepMetrics) -> f64| -> f64 {
        if reps.len() <= 1 {
            return 0.0;
        }
        let m = mean(f);
        let v = reps.iter().map(|r| (f(r) - m).powi(2)).sum::<f64>() / (reps.len() - 1) as f64;
        (v / reps.len() as f64).sqrt()
    };
    let mut m = reps[0].clone();
    m.mean_f_mae = mean(|r| r.mean_f_mae);
    m.hist_tv_particle_mean = mean(|r| r.hist_tv_particle_mean);
    m.hist_tv_belief_wire = mean(|r| r.hist_tv_belief_wire);
    m.tau_lot_mae = mean(|r| r.tau_lot_mae);
    m.eff_inv_rel_err = mean(|r| r.eff_inv_rel_err);
    m.order_qty_abs_diff = mean(|r| r.order_qty_abs_diff);
    m.lot_rank_spearman = mean(|r| r.lot_rank_spearman);
    m.ess_final = mean(|r| r.ess_final);
    m.ess_min = mean(|r| r.ess_min);
    m.coverage90_mean_f = mean(|r| r.coverage90_mean_f);
    AccRow {
        n_lots,
        n_reps: reps.len(),
        belief_wire_k: k_wire,
        order_qty_match_rate: mean(|r| r.order_qty_match),
        mean_f_mae_se: se(|r| r.mean_f_mae),
        hist_tv_belief_wire_se: se(|r| r.hist_tv_belief_wire),
        eff_inv_rel_err_se: se(|r| r.eff_inv_rel_err),
        metrics: m,
    }
}

fn main() {
    let probe = env::args().any(|a| a == "--probe");
    let acc_reps = if probe { 1 } else { 12 };
    let t0 = Instant::now();
    let params = ModelParams::default();
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");

    eprintln!("timing L sweep (P1 totals, N={N_PARTICLES}) …");
    let mut timing = Vec::new();
    for &l in &L_VALUES {
        let mut samples = Vec::new();
        for _ in 0..TIMING_WARMUP {
            let _ = time_one_day(l, UNITS_PER_LOT, &params, &gamma);
        }
        for _ in 0..TIMING_REPS {
            samples.push(time_one_day(l, UNITS_PER_LOT, &params, &gamma));
        }
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let mean = samples.iter().sum::<f64>() / samples.len() as f64;
        let p95 = percentile(&samples, 95.0);
        timing.push(TimingRow {
            n_lots: l,
            units_per_lot: UNITS_PER_LOT,
            units_total: l * UNITS_PER_LOT,
            mean_ms: mean,
            p95_ms: p95,
        });
        eprintln!("  L={l}: mean={mean:.2} ms p95={p95:.2} ms");
    }

    eprintln!("accuracy L sweep (K_wire=8, studio default) …");
    let k_studio = 8usize;
    let mut accuracy = Vec::new();
    for &l in &L_VALUES {
        let mut reps = Vec::new();
        for i in 0..acc_reps {
            reps.push(run_rep(l, 50_000 + l as u64 * 1000 + i as u64, k_studio, &params, &gamma));
        }
        accuracy.push(aggregate(&reps, l, k_studio));
    }

    eprintln!("K sensitivity @ L=20 …");
    let mut k_sensitivity_l20 = Vec::new();
    for &k in &K_WIRE {
        let mut reps = Vec::new();
        for i in 0..acc_reps {
            reps.push(run_rep(
                20,
                80_000 + k as u64 * 100 + i as u64,
                k,
                &params,
                &gamma,
            ));
        }
        k_sensitivity_l20.push(aggregate(&reps, 20, k));
    }

    let report = StudyReport {
        study: "c2_a_p1_totals",
        probe,
        wall_seconds: t0.elapsed().as_secs_f64(),
        n_particles: N_PARTICLES,
        units_per_lot: UNITS_PER_LOT,
        obs_mode: "totals",
        timing,
        accuracy,
        k_sensitivity_l20,
    };

    let out = "outputs/c2_a_totals_study.json";
    if let Some(parent) = std::path::Path::new(out).parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::write(out, serde_json::to_string_pretty(&report).expect("json")).expect("write");
    eprintln!("wrote {out} in {:.1}s", report.wall_seconds);
}
