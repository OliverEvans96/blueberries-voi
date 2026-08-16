//! CTL-02/04 one-step rollout (Python controller.rollout).

use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::day_step::{day_step, unit_day_step, DayStepIn, ModelParams, UnitDayStepIn};
use crate::physics::weibull_survival;
use crate::policy::effective_inventory_f_belief;
use crate::shipments::ShipmentTrace;

pub fn candidate_orders(base_q: u32, case_size: u32, radius: i32) -> Vec<u32> {
    let cs = case_size.max(1);
    let base_cases = (base_q / cs) as i32;
    let mut out = Vec::new();
    for d in -radius..=radius {
        let c = (base_cases + d).max(0) as u32;
        out.push(c * cs);
    }
    out.sort_unstable();
    out.dedup();
    if out.is_empty() {
        out.push(0);
    }
    out
}

pub fn terminal_salvage_value(
    counts: &[u32],
    taus: &[f64],
    margin: f64,
    beta: f64,
    eta: f64,
) -> f64 {
    if counts.is_empty() {
        return 0.0;
    }
    let mut pairs: Vec<(f64, u32)> = taus.iter().copied().zip(counts.iter().copied()).collect();
    pairs.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    let mut total = 0.0;
    for (tau, n) in pairs {
        total += weibull_survival(tau, beta, eta) * f64::from(n);
    }
    margin * total
}

/// Terminal salvage from f-belief: margin × `effective_inventory_f_belief` with zero pipeline.
pub fn terminal_salvage_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    margin: f64,
) -> f64 {
    margin * effective_inventory_f_belief(lot_counts, f_marginals, f_grid, 0, 0.0)
}

pub fn day_profit(
    sales: u32,
    waste: u32,
    demand: u32,
    margin: f64,
    waste_cost: f64,
    stockout: f64,
) -> f64 {
    let lost = demand.saturating_sub(sales);
    margin * f64::from(sales) - waste_cost * f64::from(waste) - stockout * f64::from(lost)
}

fn unit_state_from_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    units_per_lot: usize,
) -> (Vec<f64>, Vec<usize>) {
    let l = lot_counts.len();
    let k = f_grid.len();
    let u = units_per_lot.max(1);
    let mut freshness = Vec::new();
    let mut lot_offsets = vec![0usize];
    for ell in 0..l {
        let mut e_f = 0.0;
        for bin in 0..k {
            let p = f_marginals.get(ell * k + bin).copied().unwrap_or(0.0);
            e_f += p * f_grid[bin];
        }
        let n = lot_counts[ell].round().max(0.0) as usize;
        let alive = n.min(u);
        let dead = u.saturating_sub(alive);
        freshness.extend(std::iter::repeat_n(e_f.max(0.0), alive));
        freshness.extend(std::iter::repeat_n(0.0, dead));
        lot_offsets.push(freshness.len());
    }
    (freshness, lot_offsets)
}

pub fn rollout_order(
    counts: &[u32],
    taus: &[f64],
    lot_ids: &[i64],
    base_q: u32,
    params: &ModelParams,
    seed: u64,
    h: u32,
    n_paths: u32,
    radius: i32,
) -> Result<u32, String> {
    if h == 0 {
        return Err(format!("H must be positive, got {h}"));
    }
    if n_paths == 0 {
        return Err(format!("n_rollout_paths must be positive, got {n_paths}"));
    }
    let mut cands = candidate_orders(base_q, params.case_size, radius);
    if cands.is_empty() {
        return Err("candidates must be non-empty".into());
    }
    let mut unique = vec![base_q];
    for q in cands.drain(..) {
        if !unique.contains(&q) {
            unique.push(q);
        }
    }
    let mut best_q = unique[0];
    let mut best_score = f64::NEG_INFINITY;
    for q in unique {
        let mut acc = 0.0;
        for path in 0..n_paths {
            acc += path_value(counts, taus, lot_ids, q, params, seed, path, h);
        }
        let score = acc / f64::from(n_paths);
        if score > best_score {
            best_score = score;
            best_q = q;
        }
    }
    Ok(best_q)
}

/// Rollout on f-belief using `unit_day_step` and f-native terminal salvage.
pub fn rollout_order_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    base_q: u32,
    params: &ModelParams,
    seed: u64,
    h: u32,
    n_paths: u32,
    radius: i32,
) -> Result<u32, String> {
    if h == 0 {
        return Err(format!("H must be positive, got {h}"));
    }
    if n_paths == 0 {
        return Err(format!("n_rollout_paths must be positive, got {n_paths}"));
    }
    let mut cands = candidate_orders(base_q, params.case_size, radius);
    if cands.is_empty() {
        return Err("candidates must be non-empty".into());
    }
    let mut unique = vec![base_q];
    for q in cands.drain(..) {
        if !unique.contains(&q) {
            unique.push(q);
        }
    }
    let mut best_q = unique[0];
    let mut best_score = f64::NEG_INFINITY;
    for q in unique {
        let mut acc = 0.0;
        for path in 0..n_paths {
            acc += path_value_f_belief(
                lot_counts,
                f_marginals,
                f_grid,
                q,
                params,
                seed,
                path,
                h,
            );
        }
        let score = acc / f64::from(n_paths);
        if score > best_score {
            best_score = score;
            best_q = q;
        }
    }
    Ok(best_q)
}

fn path_value(
    counts: &[u32],
    taus: &[f64],
    lot_ids: &[i64],
    first_order: u32,
    params: &ModelParams,
    seed: u64,
    path: u32,
    h: u32,
) -> f64 {
    let mut rng = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path) * 1_000_003));
    let mut state = DayStepIn {
        counts: counts.to_vec(),
        taus: taus.to_vec(),
        lot_ids: lot_ids.to_vec(),
        demand: Some(params.demand_mu.max(0.0) as u32),
        spoil_by: None,
        delivery_n: first_order,
        delivery_tau: 0.0,
        delivery_lot_id: 100,
    };
    let mut profit = 0.0;
    let mut next_lot = 101i64;
    for d in 0..h {
        if d > 0 {
            state.delivery_n = first_order;
            state.delivery_lot_id = next_lot;
            next_lot += 1;
        }
        let mut rng_s = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path * 17 + d)));
        let out = day_step(&state, params, Some(&mut rng), Some(&mut rng_s));
        profit += day_profit(out.sales_total, out.waste_total, out.demand, 2.0, 1.5, 3.0);
        state.counts = out.counts;
        state.taus = out.taus;
        state.lot_ids = out.lot_ids;
        state.spoil_by = None;
        state.demand = Some(params.demand_mu.max(0.0) as u32);
    }
    profit + terminal_salvage_value(&state.counts, &state.taus, 2.0, params.beta, params.eta_ref)
}

fn path_value_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    first_order: u32,
    params: &ModelParams,
    seed: u64,
    path: u32,
    h: u32,
) -> f64 {
    let units_per_lot = params.units_per_lot.max(1);
    let (mut freshness, mut lot_offsets) =
        unit_state_from_f_belief(lot_counts, f_marginals, f_grid, units_per_lot);
    let shipments = [ShipmentTrace::smoke_cool()];
    let mut profit = 0.0;
    for d in 0..h {
        let mut rng_gamma = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path * 31 + d)));
        let mut rng_alloc = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path * 17 + d)));
        let mut rng_ship = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path * 19 + d)));
        let mut rng_sensor = Pcg64::seed_from_u64(seed.wrapping_add(u64::from(path * 23 + d)));
        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(params.demand_mu.max(0.0) as u32),
            gamma_decrement: Some(gamma_decrement_for_store(params)),
            deliver: d == 0 || first_order > 0,
            deliver_units: if d == 0 || first_order > 0 {
                Some(first_order)
            } else {
                None
            },
            delivery_f: Some(1.0),
            units_per_lot: Some(if d == 0 { first_order } else { first_order } as usize),
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let out = unit_day_step(
            &input,
            params,
            &shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            Some(&mut rng_ship),
            Some(&mut rng_sensor),
        );
        profit += day_profit(out.sales_total, out.waste_total, out.demand, 2.0, 1.5, 3.0);
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }
    let l = lot_counts.len();
    let k = f_grid.len();
    let alive_counts: Vec<f64> = (0..l)
        .map(|ell| {
            let start = lot_offsets[ell];
            let end = lot_offsets[ell + 1];
            freshness[start..end]
                .iter()
                .filter(|&&f| f > 0.0)
                .count() as f64
        })
        .collect();
    let terminal_marginals: Vec<f64> = if k > 0 {
        let mut m = vec![0.0; l * k];
        for ell in 0..l {
            let start = lot_offsets[ell];
            let end = lot_offsets[ell + 1];
            for &f in &freshness[start..end] {
                if f > 0.0 {
                    let bin = nearest_f_bin(f, f_grid);
                    m[ell * k + bin] += 1.0;
                }
            }
            let row = &mut m[ell * k..(ell + 1) * k];
            let z: f64 = row.iter().sum();
            if z > 0.0 {
                for x in row.iter_mut() {
                    *x /= z;
                }
            }
        }
        m
    } else {
        vec![]
    };
    profit + terminal_salvage_f_belief(&alive_counts, &terminal_marginals, f_grid, 2.0)
}

fn nearest_f_bin(f: f64, grid: &[f64]) -> usize {
    grid.iter()
        .enumerate()
        .min_by(|(_, a), (_, b)| (*a - f).abs().partial_cmp(&(*b - f).abs()).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0)
}

fn gamma_decrement_for_store(params: &ModelParams) -> f64 {
    crate::physics::gamma_decrement_for_store(params)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::belief_flat::f_grid_k;

    #[test]
    fn candidate_neighbourhood_plus_minus_radius() {
        let c = candidate_orders(16, 8, 2);
        assert!(c.contains(&0));
        assert!(c.contains(&16));
        assert!(c.contains(&32));
        assert!(c.iter().all(|q| q % 8 == 0));
    }

    #[test]
    fn terminal_salvage_empty_lots_is_zero() {
        assert_eq!(terminal_salvage_value(&[], &[], 2.0, 2.0, 14.0), 0.0);
    }

    #[test]
    fn terminal_salvage_f_belief_empty_is_zero() {
        assert_eq!(
            terminal_salvage_f_belief(&[], &[], &f_grid_k(3), 2.0),
            0.0
        );
    }

    #[test]
    fn rollout_rejects_nonpositive_horizon() {
        let p = ModelParams::default();
        assert!(rollout_order(&[8], &[0.0], &[1], 8, &p, 1, 0, 1, 1).is_err());
        assert!(rollout_order_f_belief(&[8.0], &[1.0], &f_grid_k(1), 8, &p, 1, 0, 1, 1).is_err());
    }

    #[test]
    fn rollout_order_returns_nonnegative_case_multiple() {
        let p = ModelParams::default();
        let q = rollout_order(&[10, 5], &[0.0, 2.0], &[1, 2], 8, &p, 3, 2, 1, 1).unwrap();
        assert_eq!(q % p.case_size, 0);
    }

    #[test]
    fn rollout_order_f_belief_returns_nonnegative_case_multiple() {
        let p = ModelParams::default();
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![10.0, 5.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let q = rollout_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            8,
            &p,
            3,
            2,
            1,
            1,
        )
        .unwrap();
        assert_eq!(q % p.case_size, 0);
    }
}
