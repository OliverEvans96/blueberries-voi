//! CTL-02/04 one-step rollout (Python controller.rollout).

use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::day_step::{day_step, DayStepIn, ModelParams};
use crate::physics::weibull_survival;

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

#[cfg(test)]
mod tests {
    use super::*;

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
    fn rollout_rejects_nonpositive_horizon() {
        let p = ModelParams::default();
        assert!(rollout_order(&[8], &[0.0], &[1], 8, &p, 1, 0, 1, 1).is_err());
    }

    #[test]
    fn rollout_order_returns_nonnegative_case_multiple() {
        let p = ModelParams::default();
        let q = rollout_order(&[10, 5], &[0.0, 2.0], &[1, 2], 8, &p, 3, 2, 1, 1).unwrap();
        assert_eq!(q % p.case_size, 0);
    }
}
