//! CTL-02/04 one-step rollout (Python `bakeoff_rollout`).

use std::collections::BTreeMap;

use crate::arrival::{
    ArrivalModel, STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS,
    STREAM_ARRIVAL_TEMP,
};
use crate::day_step::{unit_day_step_with_birth, UnitDayStepIn};
use crate::params::ModelParams;
use crate::physics::{draw_demand_spawn, f_to_age, weibull_survival};
use crate::policy::{damped_sw_order_f_belief, effective_inventory_f_belief};
use crate::schedule::OrderSchedule;
use crate::shipments::ShipmentTrace;
use crate::spawn_rng::SpawnRng;
use crate::voi::truth_f_belief;

const STREAM_DEMAND: &str = ":demand";
const STREAM_ALLOC: &str = ":alloc";
const STREAM_SPOIL: &str = ":spoil";
const STREAM_BIRTH: &str = ":birth";
const ORACLE_K: usize = 5;

/// SIM-01=B profit coefficients for rollout path scoring.
#[derive(Clone, Debug)]
pub struct RolloutCosts {
    pub unit_margin: f64,
    pub waste_cost: f64,
    pub stockout_penalty: f64,
}

impl Default for RolloutCosts {
    /// The same uncalibrated scaffold margin/waste/stockout costs as the top-level profit
    /// accounting (`DEFAULT_PROFIT_COSTS`), used here as the objective the rollout
    /// controller's own forward search optimizes against.
    fn default() -> Self {
        Self {
            unit_margin: 2.0,
            waste_cost: 1.5,
            stockout_penalty: 3.0,
        }
    }
}

/// How rollout enumerates candidate order quantities around the base policy.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CandidateSearchMode {
    /// Dense ±`radius` case neighbourhood (legacy default).
    Neighborhood,
    /// Fixed-count stratified lattice over a wide ±span in cases (ADR 0146).
    StratifiedWide,
}

/// Knobs for [`candidate_orders_v2`] and rollout candidate enumeration.
#[derive(Clone, Debug, PartialEq)]
pub struct CandidateSearchConfig {
    pub mode: CandidateSearchMode,
    /// Target candidate count (including `base_q` after merge/dedupe/backfill).
    pub n_candidates: u32,
    /// Half-width in cases for [`CandidateSearchMode::Neighborhood`].
    pub radius: i32,
    /// Fixed span in cases for wide mode; `0` selects adaptive span from `span_fraction`.
    pub span_cases: i32,
    pub span_fraction: f64,
    pub min_span_cases: i32,
    pub max_span_cases: i32,
}

impl Default for CandidateSearchConfig {
    fn default() -> Self {
        Self {
            mode: CandidateSearchMode::Neighborhood,
            n_candidates: 5,
            radius: 2,
            span_cases: 0,
            span_fraction: 0.25,
            min_span_cases: 4,
            max_span_cases: 10,
        }
    }
}

impl CandidateSearchConfig {
    /// Legacy surface: `candidate_case_radius` alone maps to neighbourhood search.
    pub fn neighborhood(radius: i32) -> Self {
        Self {
            mode: CandidateSearchMode::Neighborhood,
            radius,
            ..Self::default()
        }
    }

    pub fn stratified_wide(n_candidates: u32) -> Self {
        Self {
            mode: CandidateSearchMode::StratifiedWide,
            n_candidates: n_candidates.max(1),
            ..Self::default()
        }
    }

    /// Merge session defaults with optional per-act / RPC overrides.
    pub fn with_overrides(
        base: &Self,
        candidate_case_radius: Option<i32>,
        candidate_search_mode: Option<&str>,
        candidate_span_cases: Option<i32>,
        n_candidates: Option<u32>,
    ) -> Self {
        let mut cfg = base.clone();
        if let Some(mode) = candidate_search_mode {
            cfg.mode = match mode.to_ascii_lowercase().as_str() {
                "stratified_wide" | "wide" | "stratified" => {
                    CandidateSearchMode::StratifiedWide
                }
                _ => CandidateSearchMode::Neighborhood,
            };
        }
        if let Some(span) = candidate_span_cases {
            cfg.span_cases = span;
        }
        if let Some(k) = n_candidates {
            cfg.n_candidates = k.max(1);
        }
        if let Some(r) = candidate_case_radius {
            cfg.radius = r;
            if candidate_search_mode.is_none() {
                cfg.mode = CandidateSearchMode::Neighborhood;
            }
        }
        cfg
    }
}

/// Parse candidate-search knobs from a JSON configure / act payload.
pub fn candidate_search_from_rpc(params: &serde_json::Value) -> CandidateSearchConfig {
    let radius = params
        .get("candidate_case_radius")
        .and_then(|v| v.as_i64())
        .map(|n| n as i32)
        .unwrap_or(1);
    let mut cfg = CandidateSearchConfig::neighborhood(radius);
    if let Some(mode) = params.get("candidate_search_mode").and_then(|v| v.as_str()) {
        cfg.mode = match mode.to_ascii_lowercase().as_str() {
            "stratified_wide" | "wide" | "stratified" => CandidateSearchMode::StratifiedWide,
            _ => CandidateSearchMode::Neighborhood,
        };
    }
    if let Some(span) = params
        .get("candidate_span_cases")
        .and_then(|v| v.as_i64())
    {
        cfg.span_cases = span as i32;
    }
    if let Some(k) = params.get("n_candidates").and_then(|v| v.as_u64()) {
        cfg.n_candidates = (k as u32).max(1);
    }
    cfg
}

/// Shared rollout forward-sim context (CRN addressing + continuation policy).
#[derive(Clone, Debug)]
pub struct RolloutContext {
    /// Root CRN seed shared with the outer simulation, so every candidate order and every
    /// path index draws from its own reproducible, independently addressable RNG stream.
    pub root_seed: u64,
    /// CRN run-id string; combined with the path index to derive per-path RNG streams
    /// distinct from the outer simulation's own.
    pub run_id: String,
    /// Simulation day the rollout starts from.
    pub day0: u32,
    /// Order-to-delivery lead time in days, used to schedule enqueued orders.
    pub lead_time: u32,
    /// Which weekdays place orders vs. receive deliveries.
    pub schedule: OrderSchedule,
    /// Service-level quantile `alpha` passed through to the continuation ordering policy.
    pub alpha: f64,
    /// Damping factor `rho` passed through to the continuation ordering policy.
    pub rho: f64,
    pub costs: RolloutCosts,
    /// Thermal exposure traces used to draw arrival freshness for simulated deliveries.
    pub shipments: Vec<ShipmentTrace>,
    /// Assumed freshness of in-transit (pipeline) inventory that hasn't arrived yet.
    pub f_pipeline_default: f64,
    /// Rollout horizon in days: how far forward each candidate order is simulated.
    pub h: u32,
    /// Number of CRN-paired sample paths averaged per candidate order.
    pub n_paths: u32,
    /// Candidate order search geometry (neighbourhood or stratified wide lattice).
    pub candidate_search: CandidateSearchConfig,
}

/// Candidate order quantities near `base_q`: whole cases at `base_q +/- radius` cases,
/// clamped at zero, sorted, and deduplicated. Always returns at least one candidate (`[0]`
/// if the neighbourhood is empty), so callers never have to special-case an empty list.
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

fn effective_span_cases(base_cases: i32, cfg: &CandidateSearchConfig) -> i32 {
    if cfg.span_cases > 0 {
        cfg.span_cases
    } else {
        let adaptive = (cfg.span_fraction * f64::from(base_cases)).ceil() as i32;
        adaptive.clamp(cfg.min_span_cases, cfg.max_span_cases)
    }
}

fn backfill_case_multiples(
    out: &mut Vec<u32>,
    base_cases: i32,
    case_size: u32,
    target: usize,
) {
    let cs = case_size.max(1);
    let mut seen: std::collections::BTreeSet<u32> = out.iter().copied().collect();
    let mut delta = 1i32;
    while out.len() < target {
        for sign in [-1i32, 1] {
            let c = (base_cases + sign * delta).max(0) as u32;
            let q = c * cs;
            if seen.insert(q) {
                out.push(q);
                if out.len() >= target {
                    break;
                }
            }
        }
        delta += 1;
        if delta > 10_000 {
            break;
        }
    }
    out.sort_unstable();
    out.dedup();
}

/// Case-multiple candidate orders under [`CandidateSearchConfig`].
///
/// Always includes `base_q` (snapped to a case multiple). Neighbourhood mode delegates
/// to [`candidate_orders`]; wide mode places `n_candidates` points on a stratified lattice.
pub fn candidate_orders_v2(
    base_q: u32,
    case_size: u32,
    cfg: &CandidateSearchConfig,
) -> Vec<u32> {
    let cs = case_size.max(1);
    let base_cases = (base_q / cs) as i32;
    let base_snapped = (base_cases as u32) * cs;

    match cfg.mode {
        CandidateSearchMode::Neighborhood => candidate_orders(base_snapped, cs, cfg.radius),
        CandidateSearchMode::StratifiedWide => {
            let k = cfg.n_candidates.max(1) as usize;
            let span = effective_span_cases(base_cases, cfg);
            let lo = (base_cases - span).max(0);
            let hi = base_cases + span;
            let mut out = vec![base_snapped];
            let extra = k.saturating_sub(1);
            for i in 0..extra {
                let case = if extra <= 1 {
                    lo
                } else {
                    let t = i as f64 / (extra.saturating_sub(1)) as f64;
                    (f64::from(lo) + t * f64::from(hi - lo)).round() as i32
                };
                let q = (case.max(0) as u32) * cs;
                out.push(q);
            }
            out.sort_unstable();
            out.dedup();
            if out.len() < k {
                backfill_case_multiples(&mut out, base_cases, cs, k);
            }
            if !out.contains(&base_snapped) {
                out.push(base_snapped);
                out.sort_unstable();
                out.dedup();
            }
            if out.is_empty() {
                out.push(0);
            }
            out
        }
    }
}

/// Weibull survival weight at effective age τ (ADR 0061).
pub fn w_long(tau: f64, params: &ModelParams) -> f64 {
    weibull_survival(tau, params.beta, params.eta_ref)
}

/// Terminal salvage from unit freshness state: V_T = m * Σ w_long(τ_i) over alive units.
pub fn terminal_salvage_unit_state(
    freshness: &[f64],
    margin: f64,
    params: &ModelParams,
) -> f64 {
    let mut taus: Vec<f64> = freshness
        .iter()
        .filter(|&&f| f > 0.0)
        .map(|&f| f_to_age(f, params.eta_ref))
        .collect();
    taus.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    let weighted: f64 = taus.iter().map(|&tau| w_long(tau, params)).sum();
    margin * weighted
}

/// Terminal salvage V_T = m * E\[f\]-weighted on-hand at horizon (ADR 0061 / 0130 f-native).
pub fn terminal_salvage_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    margin: f64,
) -> f64 {
    margin * effective_inventory_f_belief(lot_counts, f_marginals, f_grid, 0, 0.0)
}

/// Single day's profit: margin on sales, minus waste and lost-sale (stockout) costs.
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

/// Draws one unit's freshness from lot `ell`'s marginal histogram over `f_grid`, via
/// inverse-CDF sampling on the (unnormalized) bin weights. Falls back to the last grid bin
/// if the marginal is all-zero or floating-point error leaves `u` past the accumulated sum.
fn sample_f_from_lot_marginal(
    f_marginals: &[f64],
    ell: usize,
    k: usize,
    f_grid: &[f64],
    rng: &mut SpawnRng,
) -> f64 {
    let start = ell * k;
    let mut total = 0.0;
    for bin in 0..k {
        total += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
    }
    let u = if total > 0.0 {
        rng.next_f64() * total
    } else {
        0.0
    };
    let mut cum = 0.0;
    for bin in 0..k {
        cum += f_marginals.get(start + bin).copied().unwrap_or(0.0).max(0.0);
        if u <= cum {
            return f_grid[bin].clamp(1e-12, 1.0);
        }
    }
    f_grid[k.saturating_sub(1)].clamp(1e-12, 1.0)
}

/// Materializes a per-unit freshness state (and matching `lot_offsets`) from lot-level
/// belief marginals, so a rollout path can be forward-simulated with the same unit-level
/// machinery as the real day-step. Each lot gets `units_per_lot` slots regardless of its
/// actual count: alive units are sampled from the marginal via `sample_f_from_lot_marginal`,
/// and any remaining slots are padded with freshness `0.0` (already-spoiled/absent) so lot
/// widths stay uniform. Sampling uses the dedicated `:birth` stream, keyed by day, so it is
/// CRN-paired across candidate order quantities and paths.
fn unit_state_from_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    units_per_lot: usize,
    root_seed: u64,
    run_id: &str,
    day: u32,
) -> (Vec<f64>, Vec<usize>) {
    let l = lot_counts.len();
    let k = f_grid.len();
    let u = units_per_lot.max(1);
    let mut rng_birth = SpawnRng::spawn_rng(root_seed, run_id, day, STREAM_BIRTH);
    let mut freshness = Vec::new();
    let mut lot_offsets = vec![0usize];
    for ell in 0..l {
        let n = lot_counts[ell].round().max(0.0) as usize;
        let alive = n.min(u);
        let dead = u.saturating_sub(alive);
        for _ in 0..alive {
            freshness.push(sample_f_from_lot_marginal(
                f_marginals,
                ell,
                k,
                f_grid,
                &mut rng_birth,
            ));
        }
        freshness.extend(std::iter::repeat_n(0.0, dead));
        lot_offsets.push(freshness.len());
    }
    (freshness, lot_offsets)
}

fn enqueue(pending: &mut BTreeMap<u32, u32>, day: u32, lead: u32, qty: u32) {
    *pending.entry(day + lead).or_insert(0) += qty;
}

fn pop_arrival(pending: &mut BTreeMap<u32, u32>, day: u32) -> u32 {
    pending.remove(&day).unwrap_or(0)
}

/// One-step rollout: pick the case order with highest CRN-paired path value.
pub fn rollout_order(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    base_q: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
) -> Result<u32, String> {
    if ctx.h == 0 {
        return Err(format!("H must be positive, got {}", ctx.h));
    }
    if ctx.n_paths == 0 {
        return Err(format!(
            "n_rollout_paths must be positive, got {}",
            ctx.n_paths
        ));
    }
    let mut cands = candidate_orders_v2(base_q, params.case_size, &ctx.candidate_search);
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
        for path in 0..ctx.n_paths {
            acc += path_value_f_belief(
                lot_counts,
                f_marginals,
                f_grid,
                q,
                params,
                pending0,
                ctx,
                path,
            );
        }
        let score = acc / f64::from(ctx.n_paths);
        if score > best_score {
            best_score = score;
            best_q = q;
        }
    }
    Ok(best_q)
}

/// Draws the oracle (ground-truth) per-unit arrival freshness for a simulated delivery,
/// or `None` if nothing arrives that day. The rollout simulates against the true arrival
/// law rather than the filter's belief, using the same per-stream RNG addressing
/// (`:arrival_duration` / `:arrival_temp` / `:arrival_pos` / `:arrival_gamma`) as the outer
/// simulation so draws are CRN-paired across candidates and paths.
fn truth_delivery_units(
    arrival_model: &ArrivalModel,
    arrival: u32,
    root_seed: u64,
    path_run: &str,
    sim_day: u32,
    corridor_key: &str,
) -> Option<Vec<f64>> {
    if arrival == 0 {
        return None;
    }
    let mut rng_dur = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_DURATION);
    let mut rng_temp = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_TEMP);
    let mut rng_pos = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_POS);
    let mut rng_gamma = SpawnRng::spawn_rng(root_seed, path_run, sim_day, STREAM_ARRIVAL_GAMMA);
    Some(
        arrival_model
            .draw_truth_delivery(
                corridor_key,
                arrival as usize,
                &mut rng_dur,
                &mut rng_temp,
                &mut rng_pos,
                &mut rng_gamma,
            )
            .unit_f,
    )
}

/// Simulates one rollout sample path forward from `first_order` through `ctx.h` days and
/// returns its total profit (day-by-day sales/waste margin plus terminal salvage of
/// whatever inventory remains at the horizon).
///
/// Day 0 is forced to place `first_order` -- the candidate under evaluation -- while every
/// later day within the horizon falls back to the base damped-survival-weighted policy
/// (`damped_sw_order_f_belief`) so the candidate is scored against a realistic continuation,
/// not a static one. That continuation policy is fed a *truth* belief (`truth_f_belief`,
/// an oracle-resolution histogram over the simulated unit state) rather than a filtered
/// belief, since the rollout has no separate observation model of its own to filter through.
/// All draws (demand, spoilage, allocation, arrivals, births) key off `path_run`, which
/// embeds the path index, so each candidate order is evaluated against the same physical
/// randomness per path -- the CRN pairing that makes comparing candidates meaningful.
fn path_value_f_belief(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    first_order: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
    path: u32,
) -> f64 {
    let path_run = format!("{}|rollout|p{path}", ctx.run_id);
    let upl = params.units_per_lot.max(1);
    let (mut freshness, mut lot_offsets) = unit_state_from_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        upl,
        ctx.root_seed,
        &path_run,
        ctx.day0,
    );
    let mut pending = pending0.clone();
    let mut profit = 0.0;
    let arrival_model = ArrivalModel::embedded();

    for h in 0..ctx.h {
        let sim_day = ctx.day0 + h;
        let pending_sum: u32 = pending.values().copied().sum();
        let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
        let order_qty = if h == 0 {
            first_order
        } else {
            damped_sw_order_f_belief(
                &lc,
                &fm,
                &fg,
                pending_sum,
                sim_day,
                params,
                ctx.alpha,
                ctx.rho,
                Some(&ctx.schedule),
                ctx.f_pipeline_default,
            )
        };
        enqueue(&mut pending, sim_day, ctx.lead_time, order_qty);
        let arrival = pop_arrival(&mut pending, sim_day);

        let mut rng_demand =
            SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(sim_day));
        let mut rng_gamma = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ALLOC);

        let delivery_unit_f =
            truth_delivery_units(
                &arrival_model,
                arrival,
                ctx.root_seed,
                &path_run,
                sim_day,
                &params.arrival_product,
            );
        let mut rng_birth = if arrival > 0 {
            Some(SpawnRng::spawn_rng(
                ctx.root_seed,
                &path_run,
                sim_day,
                STREAM_BIRTH,
            ))
        } else {
            None
        };

        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_unit_f,
            units_per_lot: Some(upl),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            &ctx.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        profit += day_profit(
            out.sales_total,
            out.waste_total,
            out.demand,
            ctx.costs.unit_margin,
            ctx.costs.waste_cost,
            ctx.costs.stockout_penalty,
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }

    let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
    profit + terminal_salvage_f_belief(&lc, &fm, &fg, ctx.costs.unit_margin)
}

/// Test helper: sum arrival units delivered across an inner rollout path.
#[cfg(test)]
fn path_arrival_units_sum(
    lot_counts: &[f64],
    f_marginals: &[f64],
    f_grid: &[f64],
    first_order: u32,
    params: &ModelParams,
    pending0: &BTreeMap<u32, u32>,
    ctx: &RolloutContext,
    path: u32,
) -> u32 {
    let path_run = format!("{}|rollout|p{path}", ctx.run_id);
    let upl = params.units_per_lot.max(1);
    let (mut freshness, mut lot_offsets) = unit_state_from_f_belief(
        lot_counts,
        f_marginals,
        f_grid,
        upl,
        ctx.root_seed,
        &path_run,
        ctx.day0,
    );
    let mut pending = pending0.clone();
    let mut delivered = 0u32;
    let arrival_model = ArrivalModel::embedded();

    for h in 0..ctx.h {
        let sim_day = ctx.day0 + h;
        let pending_sum: u32 = pending.values().copied().sum();
        let (lc, fm, fg) = truth_f_belief(&freshness, &lot_offsets, ORACLE_K);
        let order_qty = if h == 0 {
            first_order
        } else {
            damped_sw_order_f_belief(
                &lc,
                &fm,
                &fg,
                pending_sum,
                sim_day,
                params,
                ctx.alpha,
                ctx.rho,
                Some(&ctx.schedule),
                ctx.f_pipeline_default,
            )
        };
        enqueue(&mut pending, sim_day, ctx.lead_time, order_qty);
        let arrival = pop_arrival(&mut pending, sim_day);
        if arrival > 0 {
            delivered += arrival;
        }

        let mut rng_demand =
            SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_DEMAND);
        let demand = draw_demand_spawn(&mut rng_demand, params, Some(sim_day));
        let mut rng_gamma = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_SPOIL);
        let mut rng_alloc = SpawnRng::spawn_rng(ctx.root_seed, &path_run, sim_day, STREAM_ALLOC);

        let delivery_unit_f =
            truth_delivery_units(
                &arrival_model,
                arrival,
                ctx.root_seed,
                &path_run,
                sim_day,
                &params.arrival_product,
            );
        let mut rng_birth = if arrival > 0 {
            Some(SpawnRng::spawn_rng(
                ctx.root_seed,
                &path_run,
                sim_day,
                STREAM_BIRTH,
            ))
        } else {
            None
        };

        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_unit_f,
            units_per_lot: Some(upl),
        };
        let out = unit_day_step_with_birth(
            &input,
            params,
            &ctx.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        freshness = out.freshness;
        lot_offsets = out.lot_offsets;
    }
    delivered
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
    fn candidate_orders_v2_wide_returns_k_unique_case_multiples_including_base() {
        let cfg = CandidateSearchConfig {
            mode: CandidateSearchMode::StratifiedWide,
            n_candidates: 5,
            span_cases: 4,
            ..CandidateSearchConfig::default()
        };
        let base_q = 24u32;
        let cs = 8u32;
        let got = candidate_orders_v2(base_q, cs, &cfg);
        assert_eq!(got.len(), 5);
        assert!(got.contains(&base_q));
        assert!(got.iter().all(|q| q % cs == 0));
        assert_eq!(got.iter().copied().collect::<std::collections::BTreeSet<_>>().len(), 5);
    }

    #[test]
    fn candidate_orders_v2_wide_span_scales_with_base_cases() {
        let mut cfg = CandidateSearchConfig {
            mode: CandidateSearchMode::StratifiedWide,
            n_candidates: 5,
            span_cases: 0,
            span_fraction: 0.25,
            min_span_cases: 4,
            max_span_cases: 10,
            ..CandidateSearchConfig::default()
        };
        let cs = 8u32;
        let small = candidate_orders_v2(16, cs, &cfg);
        let lo_small = *small.first().unwrap();
        cfg.span_fraction = 0.25;
        let large = candidate_orders_v2(160, cs, &cfg);
        let lo_large = *large.first().unwrap();
        assert!(lo_large <= lo_small || large.last() > small.last());
        let span_small = effective_span_cases(2, &cfg);
        let span_large = effective_span_cases(20, &cfg);
        assert_eq!(span_small, 4);
        assert_eq!(span_large, 5);
    }

    #[test]
    fn candidate_orders_v2_near_zero_includes_zero_when_in_range() {
        let cfg = CandidateSearchConfig {
            mode: CandidateSearchMode::StratifiedWide,
            n_candidates: 5,
            span_cases: 2,
            ..CandidateSearchConfig::default()
        };
        let got = candidate_orders_v2(0, 8, &cfg);
        assert!(got.contains(&0));
        assert!(got.iter().all(|q| q % 8 == 0));
    }

    #[test]
    fn candidate_orders_v2_neighborhood_matches_legacy() {
        let base_q = 24u32;
        let cs = 8u32;
        let radius = 2i32;
        let legacy = candidate_orders(base_q, cs, radius);
        let cfg = CandidateSearchConfig::neighborhood(radius);
        assert_eq!(candidate_orders_v2(base_q, cs, &cfg), legacy);
    }

    fn mk_test_ctx(candidate_search: CandidateSearchConfig) -> RolloutContext {
        RolloutContext {
            root_seed: 1,
            run_id: "t".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 2,
            n_paths: 1,
            candidate_search,
        }
    }

    #[test]
    fn terminal_salvage_unit_state_empty_is_zero() {
        assert_eq!(
            terminal_salvage_unit_state(&[], 2.0, &ModelParams::default()),
            0.0
        );
    }

    #[test]
    fn terminal_salvage_f_belief_matches_effective_inventory() {
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![4.0, 2.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[k - 1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let margin = 2.0;
        let expected =
            margin * effective_inventory_f_belief(&lot_counts, &f_marginals, &f_grid, 0, 0.0);
        assert_eq!(
            terminal_salvage_f_belief(&lot_counts, &f_marginals, &f_grid, margin),
            expected
        );
    }

    #[test]
    fn rollout_rejects_nonpositive_horizon() {
        let p = ModelParams::default();
        let ctx = RolloutContext {
            root_seed: 1,
            run_id: "t".into(),
            day0: 0,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 0,
            n_paths: 1,
            candidate_search: CandidateSearchConfig::neighborhood(1),
        };
        assert!(rollout_order(&[8.0], &[1.0], &f_grid_k(1), 8, &p, &BTreeMap::new(), &ctx).is_err());
    }

    #[test]
    fn rollout_order_returns_nonnegative_case_multiple() {
        let p = ModelParams::default();
        let k = 3usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![10.0, 5.0];
        let mut f_marginals = vec![0.0; 2 * k];
        f_marginals[1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let ctx = mk_test_ctx(CandidateSearchConfig::neighborhood(1));
        let q = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            8,
            &p,
            &BTreeMap::new(),
            &ctx,
        )
        .unwrap();
        assert_eq!(q % p.case_size, 0);
    }

    #[test]
    fn no_repeat_delivery_over_horizon() {
        let p = ModelParams::default();
        let mut order_only_monday = [false; 7];
        order_only_monday[0] = true;
        let schedule = OrderSchedule {
            delivery_weekdays: OrderSchedule::default().delivery_weekdays,
            order_weekdays: order_only_monday,
            lead_time_days: 1,
        };
        let ctx = RolloutContext {
            root_seed: 42,
            run_id: "delivery-once".into(),
            day0: 0,
            lead_time: 1,
            schedule,
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts::default(),
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 3,
            n_paths: 1,
            candidate_search: CandidateSearchConfig::neighborhood(0),
        };
        let first_order = 16u32;
        let delivered = path_arrival_units_sum(
            &[0.0],
            &[1.0],
            &f_grid_k(1),
            first_order,
            &p,
            &BTreeMap::new(),
            &ctx,
            0,
        );
        assert_eq!(delivered, first_order, "pipeline delivers candidate order once");
        assert_ne!(
            delivered,
            first_order * ctx.h,
            "must not re-deliver first_order every inner day"
        );
    }

    #[test]
    #[ignore = "slow rollout MC paths; run with cargo test rollout_costs_flip_winning_order -- --ignored"]
    fn rollout_costs_flip_winning_order() {
        let p = ModelParams::default();
        let k = 5usize;
        let f_grid = f_grid_k(k);
        let lot_counts = vec![30.0, 15.0];
        let mut f_marginals = vec![0.0; 2 * k];
        // High stale inventory under independent per-unit aging: waste_cost flips winner.
        f_marginals[k - 1] = 1.0;
        f_marginals[2 * k - 1] = 1.0;
        let base = damped_sw_order_f_belief(
            &lot_counts,
            &f_marginals,
            &f_grid,
            0,
            6,
            &p,
            0.9,
            0.8,
            Some(&OrderSchedule::default()),
            1.0,
        );
        assert!(base > 0, "fixture needs positive base_q");
        let mk_ctx = |waste: f64| RolloutContext {
            root_seed: 7,
            run_id: "cost-rank".into(),
            day0: 6,
            lead_time: 1,
            schedule: OrderSchedule::default(),
            alpha: 0.9,
            rho: 0.8,
            costs: RolloutCosts {
                unit_margin: 2.0,
                waste_cost: waste,
                stockout_penalty: 0.5,
            },
            shipments: vec![ShipmentTrace::smoke_cool()],
            f_pipeline_default: 1.0,
            h: 6,
            n_paths: 16,
            candidate_search: CandidateSearchConfig::neighborhood(2),
        };
        let low = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base,
            &p,
            &BTreeMap::new(),
            &mk_ctx(0.01),
        )
        .unwrap();
        let high = rollout_order(
            &lot_counts,
            &f_marginals,
            &f_grid,
            base,
            &p,
            &BTreeMap::new(),
            &mk_ctx(50.0),
        )
        .unwrap();
        assert_ne!(low, high, "waste_cost must flip rollout winner on fixture");
    }
}
