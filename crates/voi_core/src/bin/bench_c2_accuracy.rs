//! C2 freshness inference **accuracy** study (Rust / voi_core).
//!
//! Mirrors `experiments/c2_accuracy_study.py` blocks using the same truth sim and
//! metrics (mean_f MAE, hist TV, ESS, 90% coverage). Algorithms A/B/C align with
//! `bench_c2_algorithms.rs` families; production baseline included at L≤4.
//!
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_accuracy -- --probe
//!   OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_c2_accuracy -- \
//!     --output outputs/c2_accuracy_study_rust.json

use std::env;
use std::fs;
use std::time::Instant;

use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Gamma};
use rand_pcg::Pcg64;
use serde::Serialize;
use voi_core::exact_ll::log_p_sales_waste_given_ages;
use voi_core::{
    filter_step, picking_weights, sequential_wor_composition_prob, FilterObs, ModelParams,
    ParticleBank,
};

const DAYS: usize = 14;
const UNITS_PER_LOT: usize = 15;
const LL_MAX_L: usize = 4;
const LL_COUNT: u32 = 4;
const MF_MAX_SWEEPS: usize = 5;
const MF_TV_STOP: f64 = 1e-4;
const SCORE_K: usize = 32;

#[derive(Clone, Debug, Serialize)]
struct Metrics {
    mean_f_mae: f64,
    hist_tv_mean: f64,
    ess_final: f64,
    ess_min: f64,
    coverage90_mean_f: f64,
}

#[derive(Clone, Debug, Serialize)]
struct CellResult {
    block: &'static str,
    algorithm: &'static str,
    label: String,
    n_particles: usize,
    n_lots: usize,
    k_bins: usize,
    obs_mode: &'static str,
    n_reps: usize,
    metrics: Metrics,
    mean_f_mae_se: f64,
    hist_tv_se: f64,
    ess_final_se: f64,
}

#[derive(Clone, Debug, Serialize)]
struct StudyReport {
    engine: &'static str,
    probe: bool,
    wall_seconds: f64,
    days_per_rep: usize,
    units_per_lot: usize,
    ll_max_l: usize,
    wor_states_l20_n4: u64,
    wor_states_l4_n4: u64,
    results: Vec<CellResult>,
}

fn wor_state_count(l: usize, count_per_lot: u32) -> u64 {
    (count_per_lot as u64 + 1).pow(l as u32)
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

fn unit_tau(f: f64, eta: f64) -> f64 {
    (1.0 - f).max(0.0) * eta
}

fn tau_to_mean_f(tau: f64, eta: f64) -> f64 {
    (1.0 - tau / eta).clamp(0.0, 1.0)
}

fn lot_mean_f(units_f: &[f64], offsets: &[usize]) -> Vec<f64> {
    (0..offsets.len() - 1)
        .map(|ell| {
            let sl = &units_f[offsets[ell]..offsets[ell + 1]];
            sl.iter().sum::<f64>() / sl.len() as f64
        })
        .collect()
}

fn truth_hist_per_lot(units_f: &[f64], offsets: &[usize], edges: &[f64]) -> Vec<Vec<f64>> {
    let k = edges.len() - 1;
    let l = offsets.len() - 1;
    let mut h = vec![vec![0.0f64; k]; l];
    for ell in 0..l {
        for &f in &units_f[offsets[ell]..offsets[ell + 1]] {
            h[ell][f_to_bin(f, edges)] += 1.0;
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
) -> (i32, i32, Vec<usize>) {
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
    let (sold_mask, sales_by) = simulate_pick_units(units_f, offsets, demand, params, rng);
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
    (sales, waste, sales_by)
}

fn hist_predict(h: &[Vec<f64>], k: usize, rng: &mut Pcg64, gamma: &Gamma<f64>) -> Vec<Vec<f64>> {
    let edges = freshness_bins(k);
    let l = h.len();
    let mut out = vec![vec![0.0f64; k]; l];
    for ell in 0..l {
        for b in 0..k {
            let mass = h[ell][b];
            if mass <= 0.0 {
                continue;
            }
            let center = 0.5 * (edges[b] + edges[b + 1]);
            let d = gamma_decrement(rng, gamma);
            let new_f = (center - d).max(0.0);
            let nb = f_to_bin(new_f, &edges);
            out[ell][nb] += mass;
        }
        let s: f64 = out[ell].iter().sum();
        if s > 0.0 {
            for x in &mut out[ell] {
                *x /= s;
            }
        }
    }
    out
}

fn tau_from_hist(h_row: &[f64], edges: &[f64], eta: f64) -> f64 {
    let centers: Vec<f64> = edges.windows(2).map(|w| 0.5 * (w[0] + w[1])).collect();
    let mean_f: f64 = h_row.iter().zip(centers.iter()).map(|(p, c)| p * c).sum();
    unit_tau(mean_f, eta)
}

fn loglik_totals(
    lot_counts: &[u32],
    taus: &[f64],
    sales: i32,
    waste: i32,
    params: &ModelParams,
) -> f64 {
    if lot_counts.len() > LL_MAX_L {
        return 0.0;
    }
    log_p_sales_waste_given_ages(lot_counts, taus, sales, waste, params)
}

fn loglik_sales_by(
    lot_counts: &[u32],
    taus: &[f64],
    sales_by: &[usize],
    params: &ModelParams,
) -> f64 {
    let mut ll = 0.0;
    for ell in 0..lot_counts.len() {
        let n = lot_counts[ell];
        let s = sales_by[ell] as i32;
        if s < 0 || s > n as i32 {
            return f64::NEG_INFINITY;
        }
        let w = picking_weights(
            &[taus[ell]],
            params.sigma,
            params.beta,
            params.eta_ref,
            params.uniform_picking,
        );
        let p = sequential_wor_composition_prob(&[n], &[s as u32], &w);
        if p <= 0.0 {
            return f64::NEG_INFINITY;
        }
        ll += p.ln();
    }
    ll
}

fn loglik_for_obs(
    lot_counts: &[u32],
    taus: &[f64],
    sales: i32,
    waste: i32,
    sales_by: Option<&[usize]>,
    obs_mode: &str,
    params: &ModelParams,
) -> f64 {
    if obs_mode == "sales_by" {
        if let Some(sb) = sales_by {
            return loglik_sales_by(lot_counts, taus, sb, params);
        }
    }
    if lot_counts.len() <= LL_MAX_L {
        return loglik_totals(lot_counts, taus, sales, waste, params);
    }
    let on_hand: i32 = lot_counts.iter().map(|&c| c as i32).sum();
    if sales < 0 || sales > on_hand {
        return f64::NEG_INFINITY;
    }
    if waste >= 0 {
        0.0
    } else {
        f64::NEG_INFINITY
    }
}

fn effective_obs_mode(n_lots: usize, obs_mode: &str) -> &'static str {
    if n_lots > LL_MAX_L {
        "sales_by"
    } else if obs_mode == "sales_by" {
        "sales_by"
    } else {
        "totals"
    }
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

fn percentile(vals: &[f64], p: f64) -> f64 {
    let mut v = vals.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    if v.is_empty() {
        return f64::NAN;
    }
    let idx = ((p / 100.0) * (v.len() - 1) as f64).round() as usize;
    v[idx.min(v.len() - 1)]
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

fn marginal_tv(a: &[f64], b: &[f64]) -> f64 {
    0.5 * a.iter().zip(b).map(|(x, y)| (x - y).abs()).sum::<f64>()
}

fn mean_field_step(
    n_lots: &[u32],
    q: &mut [Vec<f64>],
    tau_grid: &[f64],
    sales: i32,
    waste: i32,
    params: &ModelParams,
) {
    let l = n_lots.len();
    let k = tau_grid.len();
    for _ in 0..MF_MAX_SWEEPS {
        let q_old: Vec<Vec<f64>> = q.to_vec();
        for ell in 0..l {
            let mut mean_tau = vec![0.0f64; l];
            for j in 0..l {
                if j != ell {
                    mean_tau[j] = q[j]
                        .iter()
                        .zip(tau_grid.iter())
                        .map(|(&p, &t)| p * t)
                        .sum();
                }
            }
            let mut log_unnorm = vec![f64::NEG_INFINITY; k];
            for ki in 0..k {
                let p0 = q[ell][ki];
                if p0 <= 0.0 {
                    continue;
                }
                let mut tau = mean_tau.clone();
                tau[ell] = tau_grid[ki];
                let ll = log_p_sales_waste_given_ages(n_lots, &tau, sales, waste, params);
                if ll.is_finite() {
                    log_unnorm[ki] = p0.ln() + ll;
                }
            }
            let m = log_unnorm.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            if !m.is_finite() {
                q[ell].fill(1.0 / k as f64);
            } else {
                let mut w: Vec<f64> = log_unnorm.iter().map(|&x| (x - m).exp()).collect();
                let s: f64 = w.iter().sum();
                for x in &mut w {
                    *x /= s.max(1e-300);
                }
                q[ell] = w;
            }
        }
        let max_change = (0..l)
            .map(|ell| marginal_tv(&q[ell], &q_old[ell]))
            .fold(0.0f64, f64::max);
        if max_change < MF_TV_STOP {
            break;
        }
    }
}

fn tau_grid_bins(k: usize) -> Vec<f64> {
    (0..k).map(|i| 0.5 + i as f64 * 0.75).collect()
}

fn run_histogram_pf(
    n_particles: usize,
    n_lots: usize,
    k: usize,
    obs_mode: &str,
    seed: u64,
    params: &ModelParams,
    gamma: &Gamma<f64>,
) -> Metrics {
    let obs_mode = effective_obs_mode(n_lots, obs_mode);
    let mut rng = Pcg64::seed_from_u64(seed);
    let upl = UNITS_PER_LOT;
    let total = n_lots * upl;
    let offsets: Vec<usize> = (0..=n_lots).map(|i| i * upl).collect();
    let edges = freshness_bins(k);
    let lot_counts = vec![upl as u32; n_lots];

    let mut units_f: Vec<f64> = (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect();
    let mut hists: Vec<Vec<Vec<f64>>> = (0..n_particles)
        .map(|_| {
            (0..n_lots)
                .map(|_| {
                    let mut row = vec![0.0; k];
                    row[k / 2] = 1.0;
                    row
                })
                .collect()
        })
        .collect();
    let mut log_w = vec![0.0f64; n_particles];
    let mut ess_trace = Vec::new();

    for day in 0..DAYS {
        let (sales, waste, sales_by) =
            simulate_truth_day(&mut units_f, &offsets, params, &mut rng, gamma);
        let obs_by = if obs_mode == "sales_by" {
            Some(sales_by.as_slice())
        } else {
            None
        };
        for p in 0..n_particles {
            hists[p] = hist_predict(&hists[p], k, &mut rng, gamma);
            let taus: Vec<f64> = hists[p]
                .iter()
                .map(|h| tau_from_hist(h, &edges, params.eta_ref))
                .collect();
            let ll = loglik_for_obs(
                &lot_counts,
                &taus,
                sales,
                waste,
                obs_by,
                obs_mode,
                params,
            );
            log_w[p] = if ll.is_finite() { ll } else { -1e9 };
            let _ = day;
        }
        let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - mx).exp()).collect();
        let z: f64 = w.iter().sum();
        for x in &mut w {
            *x /= z.max(1e-300);
        }
        ess_trace.push(ess(&w));
        let idx = resample(&mut rng, n_particles, &w);
        hists = idx.into_iter().map(|i| hists[i].clone()).collect();
        log_w.fill(0.0);
    }

    score_histogram_pf(&hists, &units_f, &offsets, &edges, n_lots, &ess_trace)
}

fn score_histogram_pf(
    hists: &[Vec<Vec<f64>>],
    units_f: &[f64],
    offsets: &[usize],
    edges: &[f64],
    n_lots: usize,
    ess_trace: &[f64],
) -> Metrics {
    let n_particles = hists.len();
    let truth_mf = lot_mean_f(units_f, offsets);
    let truth_h = truth_hist_per_lot(units_f, offsets, edges);
    let centers: Vec<f64> = edges.windows(2).map(|w| 0.5 * (w[0] + w[1])).collect();
    let mut pred_mf = vec![0.0; n_lots];
    let mut pred_h = vec![vec![0.0; edges.len() - 1]; n_lots];
    for p in 0..n_particles {
        for ell in 0..n_lots {
            pred_mf[ell] += (hists[p][ell]
                .iter()
                .zip(centers.iter())
                .map(|(h, c)| h * c)
                .sum::<f64>())
                / n_particles as f64;
            for (j, &hj) in hists[p][ell].iter().enumerate() {
                pred_h[ell][j] += hj / n_particles as f64;
            }
        }
    }
    let mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;
    let tv_mean = (0..n_lots)
        .map(|ell| tv(&pred_h[ell], &truth_h[ell]))
        .sum::<f64>()
        / n_lots as f64;
    let particle_mf: Vec<Vec<f64>> = (0..n_particles)
        .map(|p| {
            (0..n_lots)
                .map(|ell| {
                    hists[p][ell]
                        .iter()
                        .zip(centers.iter())
                        .map(|(h, c)| h * c)
                        .sum()
                })
                .collect()
        })
        .collect();
    let mut cov = 0.0;
    for ell in 0..n_lots {
        let col: Vec<f64> = particle_mf.iter().map(|row| row[ell]).collect();
        let lo = percentile(&col, 5.0);
        let hi = percentile(&col, 95.0);
        if truth_mf[ell] >= lo && truth_mf[ell] <= hi {
            cov += 1.0;
        }
    }
    cov /= n_lots as f64;
    Metrics {
        mean_f_mae: mae,
        hist_tv_mean: tv_mean,
        ess_final: *ess_trace.last().unwrap_or(&f64::NAN),
        ess_min: ess_trace.iter().copied().fold(f64::INFINITY, f64::min),
        coverage90_mean_f: cov,
    }
}

fn run_unit_pf(
    n_particles: usize,
    n_lots: usize,
    obs_mode: &str,
    seed: u64,
    params: &ModelParams,
    gamma: &Gamma<f64>,
) -> Metrics {
    let mut rng = Pcg64::seed_from_u64(seed);
    let upl = UNITS_PER_LOT;
    let total = n_lots * upl;
    let offsets: Vec<usize> = (0..=n_lots).map(|i| i * upl).collect();
    let edges = freshness_bins(SCORE_K);

    let mut units_f: Vec<f64> = (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect();
    let mut freshness: Vec<Vec<f64>> = (0..n_particles)
        .map(|_| (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect())
        .collect();
    let mut log_w = vec![0.0f64; n_particles];
    let mut ess_trace = Vec::new();

    for day in 0..DAYS {
        let (sales, _waste, sales_by) =
            simulate_truth_day(&mut units_f, &offsets, params, &mut rng, gamma);
        for p in 0..n_particles {
            for f in &mut freshness[p] {
                if *f > 0.0 {
                    *f = (*f - gamma_decrement(&mut rng, gamma)).max(0.0);
                }
            }
            let alive = freshness[p].iter().filter(|&&f| f > 0.0).count();
            let ll = if obs_mode == "totals" && alive >= sales as usize {
                let mut sub =
                    Pcg64::seed_from_u64(seed.wrapping_add(p as u64).wrapping_add(day as u64));
                sequential_kernel_path_logprob(&freshness[p], sales as usize, params, &mut sub)
            } else if obs_mode == "sales_by" {
                let mut s = 0.0;
                for ell in 0..n_lots {
                    let sl = &freshness[p][offsets[ell]..offsets[ell + 1]];
                    let alive_f: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
                    let mean_f = if alive_f.is_empty() {
                        0.0
                    } else {
                        alive_f.iter().sum::<f64>() / alive_f.len() as f64
                    };
                    s += -(mean_f - sales_by[ell] as f64 / upl as f64).abs();
                }
                s
            } else {
                -1e9
            };
            log_w[p] = ll;
        }
        let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - mx).exp()).collect();
        let z: f64 = w.iter().sum();
        for x in &mut w {
            *x /= z.max(1e-300);
        }
        ess_trace.push(ess(&w));
        let idx = resample(&mut rng, n_particles, &w);
        freshness = idx.into_iter().map(|i| freshness[i].clone()).collect();
        log_w.fill(0.0);
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    let truth_h = truth_hist_per_lot(&units_f, &offsets, &edges);
    let n_particles = freshness.len();
    let mut pred_mf = vec![0.0; n_lots];
    let mut pred_h = vec![vec![0.0; SCORE_K]; n_lots];
    for p in 0..n_particles {
        for ell in 0..n_lots {
            let sl = &freshness[p][offsets[ell]..offsets[ell + 1]];
            let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
            let mf = if alive.is_empty() {
                0.0
            } else {
                alive.iter().sum::<f64>() / alive.len() as f64
            };
            pred_mf[ell] += mf / n_particles as f64;
            for &f in &alive {
                pred_h[ell][f_to_bin(f, &edges)] += 1.0 / n_particles as f64;
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
    let mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;
    let tv_mean = (0..n_lots)
        .map(|ell| tv(&pred_h[ell], &truth_h[ell]))
        .sum::<f64>()
        / n_lots as f64;
    let particle_mf: Vec<Vec<f64>> = (0..n_particles)
        .map(|p| {
            (0..n_lots)
                .map(|ell| {
                    let sl = &freshness[p][offsets[ell]..offsets[ell + 1]];
                    let alive: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
                    if alive.is_empty() {
                        0.0
                    } else {
                        alive.iter().sum::<f64>() / alive.len() as f64
                    }
                })
                .collect()
        })
        .collect();
    let mut cov = 0.0;
    for ell in 0..n_lots {
        let col: Vec<f64> = particle_mf.iter().map(|row| row[ell]).collect();
        let lo = percentile(&col, 5.0);
        let hi = percentile(&col, 95.0);
        if truth_mf[ell] >= lo && truth_mf[ell] <= hi {
            cov += 1.0;
        }
    }
    cov /= n_lots as f64;
    Metrics {
        mean_f_mae: mae,
        hist_tv_mean: tv_mean,
        ess_final: *ess_trace.last().unwrap_or(&f64::NAN),
        ess_min: ess_trace.iter().copied().fold(f64::INFINITY, f64::min),
        coverage90_mean_f: cov,
    }
}

fn run_mf(n_lots: usize, k: usize, seed: u64, params: &ModelParams, gamma: &Gamma<f64>) -> Metrics {
    assert!(n_lots <= LL_MAX_L);
    let mut rng = Pcg64::seed_from_u64(seed);
    let upl = UNITS_PER_LOT;
    let total = n_lots * upl;
    let offsets: Vec<usize> = (0..=n_lots).map(|i| i * upl).collect();
    let edges = freshness_bins(k);
    let tau_grid = tau_grid_bins(k);
    let n_lots_v = vec![LL_COUNT; n_lots];

    let mut units_f: Vec<f64> = (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect();
    let mut q: Vec<Vec<f64>> = (0..n_lots).map(|_| vec![1.0 / k as f64; k]).collect();

    for _ in 0..DAYS {
        let (sales, waste, _) = simulate_truth_day(&mut units_f, &offsets, params, &mut rng, gamma);
        mean_field_step(&n_lots_v, &mut q, &tau_grid, sales, waste, params);
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    let centers: Vec<f64> = (0..k).map(|i| i as f64 / k as f64 + 0.5 / k as f64).collect();
    let pred_mf: Vec<f64> = q
        .iter()
        .map(|row| row.iter().zip(centers.iter()).map(|(p, c)| p * c).sum())
        .collect();
    let mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;
    let truth_h = truth_hist_per_lot(&units_f, &offsets, &edges);
    let tv_mean = (0..n_lots)
        .map(|ell| tv(&q[ell], &truth_h[ell]))
        .sum::<f64>()
        / n_lots as f64;
    Metrics {
        mean_f_mae: mae,
        hist_tv_mean: tv_mean,
        ess_final: f64::NAN,
        ess_min: f64::NAN,
        coverage90_mean_f: f64::NAN,
    }
}

fn run_baseline(
    n_particles: usize,
    n_lots: usize,
    k: usize,
    obs_mode: &str,
    seed: u64,
    params: &ModelParams,
    gamma: &Gamma<f64>,
) -> Metrics {
    let obs_mode = effective_obs_mode(n_lots, obs_mode);
    let mut rng = Pcg64::seed_from_u64(seed);
    let upl = UNITS_PER_LOT;
    let total = n_lots * upl;
    let offsets: Vec<usize> = (0..=n_lots).map(|i| i * upl).collect();
    let edges = freshness_bins(k);

    let mut units_f: Vec<f64> = (0..total).map(|_| 0.45 + rng.random::<f64>() * 0.5).collect();
    let mut bank = ParticleBank {
        weights: vec![1.0 / n_particles as f64; n_particles],
        counts: vec![vec![upl as u32; n_lots]; n_particles],
        taus: vec![vec![1.2f64; n_lots]; n_particles],
    };
    let mut ess_trace = Vec::new();

    for day in 0..DAYS {
        let (sales, waste, sales_by) =
            simulate_truth_day(&mut units_f, &offsets, params, &mut rng, gamma);
        let obs = if obs_mode == "sales_by" {
            FilterObs {
                sales_tot: Some(sales),
                waste_tot: Some(waste),
                arrivals: 0,
                sales_by: Some(sales_by.iter().map(|&x| x as u32).collect()),
                waste_by: None,
                lot_ids_live: None,
                pack_date_days: None,
                age_at_receipt: None,
            }
        } else {
            FilterObs {
                sales_tot: Some(sales),
                waste_tot: Some(waste),
                arrivals: 0,
                sales_by: None,
                waste_by: None,
                lot_ids_live: None,
                pack_date_days: None,
                age_at_receipt: None,
            }
        };
        let mut fr = Pcg64::seed_from_u64(seed.wrapping_add(day as u64).wrapping_add(99));
        bank = filter_step(&bank, &obs, params, &mut fr);
        ess_trace.push(ess(&bank.weights));
    }

    let truth_mf = lot_mean_f(&units_f, &offsets);
    let truth_h = truth_hist_per_lot(&units_f, &offsets, &edges);
    let n_particles = bank.taus.len();
    let mut pred_mf = vec![0.0; n_lots];
    for p in 0..n_particles {
        for ell in 0..n_lots {
            pred_mf[ell] += tau_to_mean_f(bank.taus[p][ell], params.eta_ref) * bank.weights[p];
        }
    }
    let mae = pred_mf
        .iter()
        .zip(truth_mf.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f64>()
        / n_lots as f64;
    // coarse hist from tau marginals mapped to single bin
    let tv_mean = (0..n_lots)
        .map(|ell| {
            let mf = pred_mf[ell];
            let mut approx = vec![0.0; edges.len() - 1];
            approx[f_to_bin(mf, &edges)] = 1.0;
            tv(&approx, &truth_h[ell])
        })
        .sum::<f64>()
        / n_lots as f64;
    let particle_mf: Vec<Vec<f64>> = bank
        .taus
        .iter()
        .map(|tau_row| {
            tau_row
                .iter()
                .map(|&t| tau_to_mean_f(t, params.eta_ref))
                .collect()
        })
        .collect();
    let mut cov = 0.0;
    for ell in 0..n_lots {
        let col: Vec<f64> = particle_mf.iter().map(|row| row[ell]).collect();
        let lo = percentile(&col, 5.0);
        let hi = percentile(&col, 95.0);
        if truth_mf[ell] >= lo && truth_mf[ell] <= hi {
            cov += 1.0;
        }
    }
    cov /= n_lots as f64;
    Metrics {
        mean_f_mae: mae,
        hist_tv_mean: tv_mean,
        ess_final: *ess_trace.last().unwrap_or(&f64::NAN),
        ess_min: ess_trace.iter().copied().fold(f64::INFINITY, f64::min),
        coverage90_mean_f: cov,
    }
}

fn aggregate(
    block: &'static str,
    algo: &'static str,
    label: String,
    rows: &[Metrics],
    n_particles: usize,
    n_lots: usize,
    k_bins: usize,
    obs_mode: &'static str,
) -> CellResult {
    let mae: Vec<f64> = rows.iter().map(|r| r.mean_f_mae).collect();
    let tvv: Vec<f64> = rows.iter().map(|r| r.hist_tv_mean).collect();
    let ef: Vec<f64> = rows
        .iter()
        .filter_map(|r| {
            if r.ess_final.is_finite() {
                Some(r.ess_final)
            } else {
                None
            }
        })
        .collect();
    let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len().max(1) as f64;
    let se = |v: &[f64]| {
        if v.len() <= 1 {
            return 0.0;
        }
        let m = mean(v);
        let var = v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (v.len() - 1) as f64;
        (var / v.len() as f64).sqrt()
    };
    CellResult {
        block,
        algorithm: algo,
        label,
        n_particles,
        n_lots,
        k_bins,
        obs_mode,
        n_reps: rows.len(),
        metrics: Metrics {
            mean_f_mae: mean(&mae),
            hist_tv_mean: mean(&tvv),
            ess_final: if ef.is_empty() {
                f64::NAN
            } else {
                mean(&ef)
            },
            ess_min: rows
                .iter()
                .filter_map(|r| {
                    if r.ess_min.is_finite() {
                        Some(r.ess_min)
                    } else {
                        None
                    }
                })
                .sum::<f64>()
                / rows
                    .iter()
                    .filter(|r| r.ess_min.is_finite())
                    .count()
                    .max(1) as f64,
            coverage90_mean_f: mean(&rows.iter().map(|r| r.coverage90_mean_f).collect::<Vec<_>>()),
        },
        mean_f_mae_se: se(&mae),
        hist_tv_se: se(&tvv),
        ess_final_se: se(&ef),
    }
}

fn main() {
    let mut args = env::args().skip(1);
    let mut probe = false;
    let mut out_path = "outputs/c2_accuracy_study_rust.json".to_string();
    while let Some(a) = args.next() {
        match a.as_str() {
            "--probe" => probe = true,
            "--output" => {
                out_path = args.next().expect("--output needs path");
            }
            _ => {}
        }
    }

    let reps_k = if probe { 1 } else { 20 };
    let reps_l = if probe { 1 } else { 15 };
    let reps_l_big = if probe { 1 } else { 8 };
    let reps_n = if probe { 1 } else { 15 };
    let reps_n2k = if probe { 1 } else { 10 };
    let reps_obs = if probe { 1 } else { 15 };

    let t0 = Instant::now();
    let params = ModelParams::default();
    let gamma = Gamma::new(2.0, 0.05).expect("gamma");
    let mut results = Vec::new();

    eprintln!("block 1: K sensitivity …");
    for k in [8usize, 16, 32] {
        let mut rows = Vec::new();
        for i in 0..reps_k {
            rows.push(run_histogram_pf(
                200,
                4,
                k,
                "totals",
                10_000 + k as u64 * 100 + i as u64,
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "k_sensitivity",
            "c2_b",
            format!("K={k}"),
            &rows,
            200,
            4,
            k,
            "totals",
        ));
    }

    eprintln!("block 2: L sweep …");
    for l in [2usize, 4, 8, 20] {
        let obs_l = if l > LL_MAX_L { "sales_by" } else { "totals" };
        let n_rep_a = if l >= 8 { reps_l_big } else { reps_l };
        let mut rows_b = Vec::new();
        for i in 0..reps_l {
            rows_b.push(run_histogram_pf(
                200,
                l,
                16,
                obs_l,
                20_000 + l as u64 * 100 + i as u64,
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "l_sweep",
            "c2_b",
            format!("L={l}"),
            &rows_b,
            200,
            l,
            16,
            obs_l,
        ));
        let mut rows_a = Vec::new();
        for i in 0..n_rep_a {
            rows_a.push(run_unit_pf(
                200,
                l,
                "totals",
                30_000 + l as u64 * 100 + i as u64,
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "l_sweep",
            "c2_a",
            format!("L={l}"),
            &rows_a,
            200,
            l,
            0,
            "totals",
        ));
        if l <= LL_MAX_L {
            let mut rows_c = Vec::new();
            for i in 0..reps_l {
                rows_c.push(run_mf(
                    l,
                    16,
                    40_000 + l as u64 * 100 + i as u64,
                    &params,
                    &gamma,
                ));
            }
            results.push(aggregate(
                "l_sweep",
                "c2_c",
                format!("L={l}"),
                &rows_c,
                1,
                l,
                16,
                "totals",
            ));
            let mut rows_bl = Vec::new();
            for i in 0..reps_l {
                rows_bl.push(run_baseline(
                    200,
                    l,
                    16,
                    "totals",
                    80_000 + l as u64 * 100 + i as u64,
                    &params,
                    &gamma,
                ));
            }
            results.push(aggregate(
                "l_sweep",
                "baseline",
                format!("L={l}"),
                &rows_bl,
                200,
                l,
                16,
                "totals",
            ));
        }
    }

    eprintln!("block 3: N sweep …");
    for n in [200usize, 2000] {
        let n_rep = if n == 2000 { reps_n2k } else { reps_n };
        let mut rows = Vec::new();
        for i in 0..n_rep {
            rows.push(run_histogram_pf(
                n,
                4,
                16,
                "totals",
                50_000 + n as u64 + i as u64,
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "n_sweep",
            "c2_b",
            format!("N={n}"),
            &rows,
            n,
            4,
            16,
            "totals",
        ));
    }

    eprintln!("block 4: obs channel …");
    for mode in ["totals", "sales_by"] {
        let mut rows_b = Vec::new();
        for i in 0..reps_obs {
            rows_b.push(run_histogram_pf(
                200,
                4,
                16,
                mode,
                60_000 + i as u64 + if mode == "totals" { 0 } else { 1000 },
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "obs_channel",
            "c2_b",
            mode.to_string(),
            &rows_b,
            200,
            4,
            16,
            mode,
        ));
        let mut rows_a = Vec::new();
        for i in 0..reps_obs {
            rows_a.push(run_unit_pf(
                200,
                4,
                mode,
                70_000 + i as u64 + if mode == "totals" { 0 } else { 1000 },
                &params,
                &gamma,
            ));
        }
        results.push(aggregate(
            "obs_channel",
            "c2_a",
            mode.to_string(),
            &rows_a,
            200,
            4,
            0,
            mode,
        ));
    }

    let report = StudyReport {
        engine: "rust",
        probe,
        wall_seconds: t0.elapsed().as_secs_f64(),
        days_per_rep: DAYS,
        units_per_lot: UNITS_PER_LOT,
        ll_max_l: LL_MAX_L,
        wor_states_l20_n4: wor_state_count(20, 4),
        wor_states_l4_n4: wor_state_count(4, 4),
        results,
    };
    if let Some(parent) = std::path::Path::new(&out_path).parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::write(&out_path, serde_json::to_string_pretty(&report).expect("json")).expect("write");
    eprintln!("wrote {out_path} in {:.1}s", report.wall_seconds);
}
