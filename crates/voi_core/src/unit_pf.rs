//! Unit-level particle filter for C2 Algorithm A (ADR 0130 / 0135 / 0137).
//!
//! # One code path, two channels
//!
//! `filter_step_unit` runs the same four stages for every observation channel. What
//! changes between UPC and GSIN is only the **resolution of the evidence** fed to each
//! stage, never the stage itself:
//!
//! | Stage | UPC (`code_type = upc`) | GSIN (`code_type = gsin`) |
//! |-------|-------------------------|---------------------------|
//! | Spoilage → Poisson-binomial | pooled `waste_tot` | per-lot `waste_by` |
//! | Sales feasibility | pooled `alive ≥ sales_tot` | per-lot `alive_ℓ ≥ sales_ℓ` |
//! | Cross-lot allocation | *(unobservable)* | `Multinomial(sales_by; lot_share)` |
//! | Sales removal | pooled WOR draw | per-lot WOR conditional on `sales_ℓ` |
//!
//! Each GSIN term is a refinement of the corresponding UPC term on the same state, so
//! GSIN cannot be less informative than UPC (see `unit_ll` module docs for the interval
//! containment argument).
//!
//! # Lot segmentation is observed, not guessed
//!
//! Arrival quantity is present on **every** mask, so the bank carries an explicit
//! `lot_offsets`/`lot_ids` segmentation built from the arrival stream itself — one
//! segment per delivery, exactly as wide as that delivery. Under GSIN, `arrival_lot_ids`
//! supplies real identities so `sales_by` / `waste_by` are matched to segments **by id**.
//! Nothing infers lot boundaries from row length.

use rand::Rng;
use rand::SeedableRng;
use rand_pcg::Pcg64;

use crate::arrival::{resolve_arrival_exposure, split_delivery_qty, ArrivalCondition, ArrivalModel};
use crate::obs::{CodeType, FilterObs};
use crate::physics::{apply_gamma_aging_independent, GammaDecrementTable};
use crate::shipments::ShipmentTrace;
use crate::unit_ll::{
    apply_pb_aging_proposal, loglik_sales_by_units, pb_loglik_by_lot, pb_loglik_pooled,
    pb_sample_deaths, pb_sample_deaths_by_lot, sequential_kernel_path_logprob,
};
use crate::ModelParams;

/// Named RNG sub-stream used to draw birth freshness deterministically from a shared
/// seed. Other call sites (e.g. `rollout.rs`, `session.rs`) define this same tag
/// independently rather than importing it from here.
pub const STREAM_BIRTH: &str = ":birth";

/// Particle bank on the f-native unit grid, with a shared observed lot segmentation.
///
/// Every row has the same length and the same `lot_offsets`, because deliveries are an
/// observed input: all particles agree on *how many* units arrived and *when*, and differ
/// only in the freshness those units carry.
#[derive(Clone, Debug, Default)]
pub struct UnitParticleBank {
    /// Per-particle importance weights, normalized to sum to 1 between filter steps.
    pub weights: Vec<f64>,
    /// Per-particle freshness rows; each row lays every unit across all lots end to
    /// end, segmented by `lot_offsets`.
    pub freshness: Vec<Vec<f64>>,
    /// Segment boundaries into every row: `len == n_lots + 1`, `lot_offsets[0] == 0`.
    pub lot_offsets: Vec<usize>,
    /// Identity per segment — observed `arrival_lot_ids` under GSIN, synthetic under UPC.
    pub lot_ids: Vec<i64>,
}

impl UnitParticleBank {
    /// Zero-init bank: `n` equally weighted particles on an empty shelf (ADR 0136).
    pub fn empty(n: usize) -> Self {
        Self {
            weights: vec![1.0 / n.max(1) as f64; n],
            freshness: vec![vec![]; n],
            lot_offsets: vec![0],
            lot_ids: Vec::new(),
        }
    }

    /// Bank over rows that already sit on a fixed `units_per_lot` grid (fixtures/benches).
    pub fn from_rows_uniform_lots(
        weights: Vec<f64>,
        freshness: Vec<Vec<f64>>,
        units_per_lot: usize,
    ) -> Self {
        let len = freshness.first().map_or(0, Vec::len);
        let (lot_offsets, lot_ids) = uniform_segmentation(len, units_per_lot);
        Self {
            weights,
            freshness,
            lot_offsets,
            lot_ids,
        }
    }

    /// Number of lot segments currently held (`lot_offsets.len() - 1`).
    pub fn n_lots(&self) -> usize {
        self.lot_offsets.len().saturating_sub(1)
    }

    fn row_len(&self) -> usize {
        self.freshness.first().map_or(0, Vec::len)
    }

    /// Repair a segmentation that a caller built by struct literal or left stale.
    fn ensure_segmentation(&mut self, units_per_lot: usize) {
        let len = self.row_len();
        let ok = self.lot_offsets.first() == Some(&0)
            && self.lot_offsets.last() == Some(&len)
            && self.lot_ids.len() + 1 == self.lot_offsets.len()
            && self.lot_offsets.windows(2).all(|w| w[0] <= w[1]);
        if !ok {
            let (offsets, ids) = uniform_segmentation(len, units_per_lot);
            self.lot_offsets = offsets;
            self.lot_ids = ids;
        }
    }

    /// Append one delivery as a new segment, using each particle's own vector of
    /// per-unit freshness draws rather than one scalar broadcast across the lot (see
    /// `push_lot`). This is what production birth sampling uses, since arrival
    /// freshness varies unit-to-unit even within a single particle.
    fn push_lot_births(&mut self, lot_id: i64, per_particle: &[Vec<f64>], units: usize) {
        for (row, seg) in self.freshness.iter_mut().zip(per_particle.iter()) {
            debug_assert_eq!(seg.len(), units);
            row.extend(seg.iter().copied());
        }
        let end = self.lot_offsets.last().copied().unwrap_or(0) + units;
        self.lot_offsets.push(end);
        self.lot_ids.push(lot_id);
    }

    /// Drop leading segments that hold no live unit in **any** particle.
    ///
    /// A lot that every particle believes is gone carries no belief mass and cannot be
    /// referenced by a future observation without the filter already having failed. This
    /// is what keeps rows bounded now that nothing blindly drains `units_per_lot`.
    fn prune_dead_prefix(&mut self) {
        let n_lots = self.n_lots();
        let mut drop_lots = 0;
        while drop_lots < n_lots {
            let start = self.lot_offsets[drop_lots];
            let end = self.lot_offsets[drop_lots + 1];
            let any_live = self.freshness.iter().any(|row| {
                row[start.min(row.len())..end.min(row.len())]
                    .iter()
                    .any(|&f| f > 0.0)
            });
            if any_live {
                break;
            }
            drop_lots += 1;
        }
        if drop_lots == 0 {
            return;
        }
        let cut = self.lot_offsets[drop_lots];
        for row in &mut self.freshness {
            row.drain(0..cut.min(row.len()));
        }
        self.lot_offsets.drain(0..drop_lots);
        for off in &mut self.lot_offsets {
            *off -= cut;
        }
        self.lot_ids.drain(0..drop_lots);
    }

    /// Weighted live-unit count and mean freshness per lot, aligned to `n_lots` slots.
    ///
    /// Slots are oldest-first over the **newest** `n_lots` segments; slots the bank no
    /// longer holds (retired, or never delivered) read as `(0.0, 0.0)`. That is the same
    /// alignment ground truth uses for a lot list of the same length, so callers can
    /// compare element-wise without knowing what the filter has retired.
    pub fn lot_summary_aligned(&self, n_lots: usize) -> Vec<(f64, f64)> {
        let w_sum: f64 = self.weights.iter().sum();
        let have = self.n_lots();
        let first = have.saturating_sub(n_lots);
        let pad = n_lots.saturating_sub(have);
        let mut out = vec![(0.0, 0.0); pad];
        for ell in first..have {
            let (start, end) = (self.lot_offsets[ell], self.lot_offsets[ell + 1]);
            let mut count = 0.0;
            let mut mean_f = 0.0;
            if w_sum > 0.0 {
                for (i, row) in self.freshness.iter().enumerate() {
                    if end > row.len() {
                        continue;
                    }
                    let w = self.weights[i];
                    let live: Vec<f64> = row[start..end]
                        .iter()
                        .copied()
                        .filter(|&f| f > 0.0)
                        .collect();
                    count += w * live.len() as f64;
                    if !live.is_empty() {
                        mean_f += w * live.iter().sum::<f64>() / live.len() as f64;
                    }
                }
                count /= w_sum;
                mean_f /= w_sum;
            }
            out.push((count, mean_f));
        }
        out
    }

    /// Next synthetic lot id when the channel does not expose `arrival_lot_ids`.
    fn next_synthetic_lot_id(&self) -> i64 {
        self.lot_ids.iter().copied().max().map_or(0, |m| m + 1)
    }
}

/// Carve `len` units into fixed `units_per_lot`-wide lots (the last lot may be
/// partial). This is a synthetic segmentation for fixtures/benches and for
/// `ensure_segmentation`'s repair fallback -- production lot boundaries instead come
/// from the observed arrival stream.
fn uniform_segmentation(len: usize, units_per_lot: usize) -> (Vec<usize>, Vec<i64>) {
    if len == 0 {
        return (vec![0], Vec::new());
    }
    let upl = units_per_lot.max(1);
    let n_lots = len.div_ceil(upl);
    let offsets: Vec<usize> = (0..=n_lots).map(|i| (i * upl).min(len)).collect();
    let ids: Vec<i64> = (0..n_lots as i64).collect();
    (offsets, ids)
}

/// Systematic resampling from unnormalized log-weights: returns `n` particle indices
/// whose empirical frequencies track `exp(log_w)`. Strata are evenly spaced at
/// `(i + 0.5) / n`, so the draw is deterministic given the weights (no extra RNG
/// input) and lower-variance than independent multinomial sampling.
pub fn systematic_resample(log_w: &[f64]) -> Vec<usize> {
    let n = log_w.len();
    if n == 0 {
        return Vec::new();
    }
    let max = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let mut w: Vec<f64> = log_w.iter().map(|lw| (lw - max).exp()).collect();
    let z: f64 = w.iter().sum();
    if z <= 0.0 {
        return (0..n).collect();
    }
    for x in &mut w {
        *x /= z;
    }
    let mut cdf = vec![0.0; n];
    cdf[0] = w[0];
    for i in 1..n {
        cdf[i] = cdf[i - 1] + w[i];
    }
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let u = (i as f64 + 0.5) / n as f64;
        let idx = cdf.iter().position(|&c| c >= u).unwrap_or(n - 1);
        out.push(idx);
    }
    out
}

/// Project an observed per-lot map onto the bank's segments.
///
/// `obs_ids[j]` names the lot that `values[j]` describes. Returns `None` when the
/// observation attributes a nonzero count to a lot the bank does not hold — the day then
/// degrades to aggregate (UPC-shaped) scoring instead of killing every particle.
pub fn project_lot_map(
    values: &[u32],
    obs_ids: Option<&[i64]>,
    bank_ids: &[i64],
) -> Option<Vec<u32>> {
    let Some(ids) = obs_ids.filter(|ids| ids.len() == values.len()) else {
        // No identities on the wire: only a same-length map can be trusted positionally.
        if values.len() == bank_ids.len() {
            return Some(values.to_vec());
        }
        return None;
    };
    let mut out = vec![0u32; bank_ids.len()];
    let mut matched = vec![false; values.len()];
    for (slot, want) in bank_ids.iter().enumerate() {
        if let Some(j) = ids.iter().position(|id| id == want) {
            out[slot] = values[j];
            matched[j] = true;
        }
    }
    let dropped: u32 = values
        .iter()
        .zip(matched.iter())
        .filter(|(_, &m)| !m)
        .map(|(&v, _)| v)
        .sum();
    if dropped > 0 {
        return None;
    }
    Some(out)
}

/// Resolve channel-conditional arrival law from filter observation.
fn resolve_arrival_f_law(obs: &FilterObs, params: &ModelParams) -> ArrivalCondition {
    if let Some(exposure) = resolve_arrival_exposure(
        obs.temp_temps_c.as_deref(),
        obs.temp_times_d.as_deref(),
        params.q10,
        params.t_ref_c,
    ) {
        return ArrivalCondition::Exposure(exposure);
    }
    if let Some(d) = obs.pack_date_days {
        return ArrivalCondition::Duration(d);
    }
    ArrivalCondition::Prior
}

/// Per-lot arrival law for multi-lot deliveries (S2.7).
fn resolve_arrival_f_law_per_lot(
    obs: &FilterObs,
    lot_idx: usize,
    params: &ModelParams,
) -> ArrivalCondition {
    if let Some(traces) = &obs.temp_traces_by_lot {
        if let Some(tr) = traces.get(lot_idx) {
            if let Some(exposure) = resolve_arrival_exposure(
                Some(&tr.temps_c),
                Some(&tr.times_d),
                params.q10,
                params.t_ref_c,
            ) {
                return ArrivalCondition::Exposure(exposure);
            }
        }
    }
    if let Some(packs) = &obs.pack_date_days_by_lot {
        if let Some(&d) = packs.get(lot_idx) {
            return ArrivalCondition::Duration(d);
        }
    }
    resolve_arrival_f_law(obs, params)
}

fn resolve_arrival_f_laws_per_lot(obs: &FilterObs, n_lots: usize, params: &ModelParams) -> Vec<ArrivalCondition> {
    (0..n_lots)
        .map(|ell| resolve_arrival_f_law_per_lot(obs, ell, params))
        .collect()
}

fn infer_birth_code_type(obs: &FilterObs, code_type: Option<CodeType>) -> CodeType {
    if let Some(ct) = code_type {
        return ct;
    }
    if obs.lot_ids_live.is_some() || obs.sales_by.is_some() || obs.waste_by.is_some() {
        return CodeType::Gsin;
    }
    if let Some(ids) = &obs.arrival_lot_ids {
        if ids.len() > 1 {
            let first = ids.first().copied().unwrap_or(0);
            if (60..100).contains(&first) || first >= 200 {
                return CodeType::Upc;
            }
            return CodeType::Gsin;
        }
    }
    CodeType::Upc
}

/// One unit-PF observation update: adapted aging, obs-resolved scoring, resample, birth.
struct DayEvidence {
    waste_by: Option<Vec<u32>>,
    waste_tot: Option<u32>,
    sales_by: Option<Vec<u32>>,
    sales_tot: Option<u32>,
}

impl DayEvidence {
    /// Project today's raw `FilterObs` counts onto the bank's live lot ids. `waste_by`
    /// is trusted only when `sales_by` also resolved to a lot-scoped map, so a day's
    /// evidence is scored either fully aggregate or fully per-lot, never a per-lot
    /// waste count paired with pooled sales.
    fn resolve(obs: &FilterObs, bank_ids: &[i64], _freshness: &[f64], _offsets: &[usize]) -> Self {
        let sales_by = obs
            .sales_by
            .as_deref()
            .and_then(|v| project_lot_map(v, obs.lot_ids_live.as_deref(), bank_ids));
        let waste_by = if sales_by.is_some() {
            obs.waste_by
                .as_deref()
                .and_then(|v| project_lot_map(v, obs.lot_ids_live.as_deref(), bank_ids))
        } else {
            None
        };
        Self {
            waste_by,
            waste_tot: obs.waste_tot.map(|w| w.max(0) as u32),
            sales_by,
            sales_tot: obs.sales_tot.map(|s| s.max(0) as u32),
        }
    }

    /// Poisson-binomial spoilage log-likelihood for the day, dispatching to the
    /// per-lot or pooled scorer depending on which waste evidence resolved. Returns
    /// the waste count consumed alongside the score so the caller can size the
    /// matching death-set draw.
    fn pb_spoilage_loglik(
        &self,
        freshness: &[f64],
        offsets: &[usize],
        table: &GammaDecrementTable,
    ) -> (usize, f64) {
        if self.waste_tot.is_none() {
            return (0, 0.0);
        }
        let w_tot = self.waste_tot.unwrap_or(0) as usize;
        let ll = match &self.waste_by {
            Some(by) => pb_loglik_by_lot(freshness, offsets, by, table),
            None => pb_loglik_pooled(freshness, w_tot as u32, table),
        };
        (w_tot, ll)
    }
}

/// Score today's sales evidence and apply the unscored WOR removal (ADR 0135).
///
/// Runs on freshness that has already been aged, so `alive` here is the post-spoilage
/// live set — exactly the population truth picks from.
fn score_and_remove_sales<R: Rng + ?Sized>(
    freshness: &mut [f64],
    offsets: &[usize],
    ev: &DayEvidence,
    params: &ModelParams,
    path_rng: &mut R,
) -> f64 {
    let Some(sales_tot) = ev.sales_tot else {
        return 0.0;
    };
    let n_lots = offsets.len().saturating_sub(1);

    if let Some(ref sales_by) = ev.sales_by {
        // Per-lot feasibility + the cross-lot allocation UPC structurally cannot see.
        let ll = loglik_sales_by_units(freshness, sales_by, offsets, params);
        if !ll.is_finite() {
            return ll;
        }
        for ell in 0..n_lots {
            let sales = sales_by[ell] as usize;
            if sales > 0 {
                let sl = &mut freshness[offsets[ell]..offsets[ell + 1]];
                let _ = sequential_kernel_path_logprob(sl, sales, params, path_rng);
            }
        }
        return ll;
    }

    // Aggregate channel: feasibility only, then one pooled WOR draw over the store.
    let alive = freshness.iter().filter(|&&f| f > 0.0).count();
    if alive < sales_tot as usize {
        return f64::NEG_INFINITY;
    }
    if sales_tot > 0 {
        let _ = sequential_kernel_path_logprob(freshness, sales_tot as usize, params, path_rng);
    }
    0.0
}

/// Health of one filter update, for regression gates and studio diagnostics.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct StepDiagnostics {
    /// Effective sample size of the pre-resample weights (`1 / Σ w²`, max `N`).
    pub ess: f64,
    /// `log Σ w` before normalization — the incremental observation log-evidence.
    pub log_evidence: f64,
    /// Particles the day's observation ruled out entirely.
    pub infeasible: usize,
}

/// One unit-PF observation update: adapted aging, obs-resolved scoring, resample, birth.
pub fn filter_step_unit<R: Rng + ?Sized>(
    bank: &mut UnitParticleBank,
    obs: &FilterObs,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    rng: &mut R,
) -> StepDiagnostics {
    let mut table = GammaDecrementTable::for_params(params);
    filter_step_unit_with_birth_cached(
        bank,
        obs,
        params,
        shipments,
        rng,
        None::<&mut R>,
        &mut table,
        None,
        None,
    )
}

/// Same as `filter_step_unit`, but lets the caller supply a separate `rng_birth`
/// stream so birth draws can be kept on their own CRN sub-stream instead of sharing
/// `rng`. Builds its own `GammaDecrementTable` per call; use
/// `filter_step_unit_with_birth_cached` to reuse one across many days.
pub fn filter_step_unit_with_birth<R: Rng + ?Sized, B: Rng + ?Sized>(
    bank: &mut UnitParticleBank,
    obs: &FilterObs,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    rng: &mut R,
    rng_birth: Option<&mut B>,
) -> StepDiagnostics {
    let mut table = GammaDecrementTable::for_params(params);
    filter_step_unit_with_birth_cached(
        bank, obs, params, shipments, rng, rng_birth, &mut table, None, None,
    )
}

/// The unit-PF's one-day observation update, threading a cached `GammaDecrementTable`
/// and optional reusable `ArrivalModel` through so callers stepping many days
/// (rollouts, tuning) avoid rebuilding either per call.
///
/// Per particle: age each unit -- via the Poisson-binomial death-set proposal when
/// waste counts are observed, or unconditioned independent Gamma decrements
/// otherwise -- then accumulate the day's log-likelihood from spoilage and sales
/// evidence. All particles are then resampled against those weights before anything
/// is born, so a new lot from the channel-conditional arrival law only ever lands on
/// particles that survived the day's evidence, and dead leading lots are pruned last.
///
/// `filter_step_unit` and `filter_step_unit_with_birth` are thin wrappers around this
/// function for callers that don't need to reuse the table/model across steps.
pub fn filter_step_unit_with_birth_cached<R: Rng + ?Sized, B: Rng + ?Sized>(
    bank: &mut UnitParticleBank,
    obs: &FilterObs,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    rng: &mut R,
    mut rng_birth: Option<&mut B>,
    table: &mut GammaDecrementTable,
    arrival_model: Option<&mut ArrivalModel>,
    birth_code_type: Option<CodeType>,
) -> StepDiagnostics {
    let _ = shipments;
    table.rebuild_if_needed(params);
    let n = bank.weights.len();
    if n == 0 {
        return StepDiagnostics::default();
    }
    let upl = params.units_per_lot.max(1);
    bank.ensure_segmentation(upl);
    let step_seed = rng.random::<u64>();
    let offsets = bank.lot_offsets.clone();

    let mut log_like = vec![0.0f64; n];
    for p in 0..n {
        let mut path_rng = Pcg64::seed_from_u64(step_seed.wrapping_add(p as u64));
        let row = &mut bank.freshness[p];
        let ev = DayEvidence::resolve(obs, &bank.lot_ids, row, &offsets);

        let (w_obs, mut ll) = ev.pb_spoilage_loglik(row, &offsets, table);
        if ev.waste_tot.is_some() {
            if ll.is_finite() {
                let (deaths, _log_q) = if let Some(by) = &ev.waste_by {
                    pb_sample_deaths_by_lot(row, &offsets, by, table, &mut path_rng)
                } else {
                    pb_sample_deaths(row, w_obs, table, &mut path_rng)
                };
                if deaths.len() == w_obs {
                    apply_pb_aging_proposal(row, &deaths, params, &mut path_rng);
                } else {
                    ll = f64::NEG_INFINITY;
                }
            }
        } else {
            apply_gamma_aging_independent(row, &mut path_rng, params);
        }

        if ll.is_finite() {
            ll += score_and_remove_sales(row, &offsets, &ev, params, &mut path_rng);
        }
        log_like[p] = if ll.is_finite() { ll } else { -1e300 };
    }

    let mut log_w: Vec<f64> = bank
        .weights
        .iter()
        .zip(log_like.iter())
        .map(|(w, ll)| (w + 1e-300).ln() + ll)
        .collect();
    let mx = log_w.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    for x in &mut log_w {
        *x -= mx;
    }

    let mut w: Vec<f64> = log_w.iter().map(|lw| lw.exp()).collect();
    let z: f64 = w.iter().sum();
    let diag = if z > 0.0 {
        for x in &mut w {
            *x /= z;
        }
        StepDiagnostics {
            ess: 1.0 / w.iter().map(|x| x * x).sum::<f64>(),
            log_evidence: z.ln() + mx,
            infeasible: log_like.iter().filter(|ll| **ll <= -1e299).count(),
        }
    } else {
        StepDiagnostics {
            ess: 0.0,
            log_evidence: f64::NEG_INFINITY,
            infeasible: n,
        }
    };

    let idx = systematic_resample(&log_w);
    bank.freshness = idx.iter().map(|&j| bank.freshness[j].clone()).collect();
    bank.weights = vec![1.0 / n as f64; n];

    // 3. Birth: GSIN splits L segments; UPC merges to one mixture cohort (ADR 0149).
    if obs.arrivals > 0 {
        let arrivals = obs.arrivals as usize;
        let lot_ids = obs
            .arrival_lot_ids
            .clone()
            .unwrap_or_else(|| vec![bank.next_synthetic_lot_id()]);
        let n_lots = lot_ids.len().max(1);
        let code = infer_birth_code_type(obs, birth_code_type);
        let conditions = resolve_arrival_f_laws_per_lot(obs, n_lots, params);
        let birth_seed = rng.random::<u64>();
        let mut local_model;
        let model = if let Some(m) = arrival_model {
            m.sync_params(params);
            m.set_corridor(&params.arrival_product);
            m
        } else {
            local_model = ArrivalModel::embedded();
            local_model.sync_params(params);
            local_model.set_corridor(&params.arrival_product);
            &mut local_model
        };

        if code == CodeType::Upc && n_lots > 1 {
            let lot_id = bank.next_synthetic_lot_id();
            let mut per_particle: Vec<Vec<f64>> = Vec::with_capacity(n);
            for p in 0..n {
                let mut particle_rng = Pcg64::seed_from_u64(birth_seed.wrapping_add(p as u64));
                let fs = if let Some(b) = rng_birth.as_mut() {
                    model.sample_filter_birth_units_mixture(&conditions, arrivals, b)
                } else {
                    model.sample_filter_birth_units_mixture(&conditions, arrivals, &mut particle_rng)
                };
                per_particle.push(fs);
            }
            bank.push_lot_births(lot_id, &per_particle, arrivals);
        } else if n_lots > 1 {
            let widths: Vec<usize> = if let Some(by) = &obs.arrivals_by {
                by.iter().map(|&q| q as usize).collect()
            } else {
                split_delivery_qty(arrivals, n_lots)
                    .into_iter()
                    .map(|q| q as usize)
                    .collect()
            };
            for (ell, (&lot_id, &units)) in lot_ids.iter().zip(widths.iter()).enumerate() {
                if units == 0 {
                    continue;
                }
                let condition = conditions.get(ell).copied().unwrap_or(ArrivalCondition::Prior);
                let mut per_particle: Vec<Vec<f64>> = Vec::with_capacity(n);
                for p in 0..n {
                    let mut particle_rng = Pcg64::seed_from_u64(birth_seed.wrapping_add(p as u64));
                    let fs = if let Some(b) = rng_birth.as_mut() {
                        model.sample_filter_birth_units(condition, units, b)
                    } else {
                        model.sample_filter_birth_units(condition, units, &mut particle_rng)
                    };
                    per_particle.push(fs);
                }
                bank.push_lot_births(lot_id, &per_particle, units);
            }
        } else {
            let lot_id = lot_ids.first().copied().unwrap_or_else(|| bank.next_synthetic_lot_id());
            let condition = conditions.first().copied().unwrap_or(ArrivalCondition::Prior);
            let mut per_particle: Vec<Vec<f64>> = Vec::with_capacity(n);
            for p in 0..n {
                let mut particle_rng = Pcg64::seed_from_u64(birth_seed.wrapping_add(p as u64));
                let fs = if let Some(b) = rng_birth.as_mut() {
                    model.sample_filter_birth_units(condition, arrivals, b)
                } else {
                    model.sample_filter_birth_units(condition, arrivals, &mut particle_rng)
                };
                per_particle.push(fs);
            }
            bank.push_lot_births(lot_id, &per_particle, arrivals);
        }
    }

    // 4. Retire lots no particle believes in, so rows track the live window.
    bank.prune_dead_prefix();
    diag
}

#[cfg(test)]
mod tests {
    use rand::Rng;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    use crate::obs::FilterObs;
    use crate::params::ModelParams;
    use crate::shipments::mod21_demo_shipments;

    use super::{filter_step_unit, project_lot_map, UnitParticleBank};

    #[test]
    fn unit_pf_filter_step_p1_updates_weights() {
        let upl = 15;
        let units = upl * 2;
        let n = 4;
        let mut rng = Pcg64::seed_from_u64(1);
        let mut bank = UnitParticleBank::from_rows_uniform_lots(
            vec![0.25; n],
            (0..n)
                .map(|_| {
                    (0..units)
                        .map(|_| 0.5 + rng.random::<f64>() * 0.3)
                        .collect()
                })
                .collect(),
            upl,
        );
        let obs = FilterObs {
            sales_tot: Some(3),
            waste_tot: Some(1),
            arrivals: 0,
            ..Default::default()
        };
        let params = ModelParams::default();
        let ships = mod21_demo_shipments("short_haul");
        filter_step_unit(&mut bank, &obs, &params, &ships, &mut rng);
        let s: f64 = bank.weights.iter().sum();
        assert!((s - 1.0).abs() < 1e-9);
        assert_eq!(bank.freshness.len(), n);
    }

    #[test]
    fn unit_pf_router_sales_by_scores_finite() {
        let upl = 15;
        let units = upl * 2;
        let n = 2;
        let mut rng = Pcg64::seed_from_u64(2);
        let mut bank = UnitParticleBank::from_rows_uniform_lots(
            vec![0.5, 0.5],
            vec![vec![0.8; units], vec![0.6; units]],
            upl,
        );
        let obs = FilterObs {
            sales_tot: Some(4),
            waste_tot: Some(0),
            arrivals: 0,
            sales_by: Some(vec![2, 2]),
            waste_by: Some(vec![0, 0]),
            lot_ids_live: Some(vec![0, 1]),
            ..Default::default()
        };
        let ships = mod21_demo_shipments("short_haul");
        filter_step_unit(&mut bank, &obs, &ModelParams::default(), &ships, &mut rng);
        assert_eq!(bank.freshness.len(), n);
    }

    #[test]
    fn arrivals_append_one_segment_of_exactly_that_width() {
        let n = 4;
        let mut rng = Pcg64::seed_from_u64(7);
        let mut bank = UnitParticleBank::empty(n);
        let params = ModelParams::default();
        for qty in [8u32, 24, 16] {
            let obs = FilterObs {
                sales_tot: Some(0),
                waste_tot: Some(0),
                arrivals: qty,
                ..Default::default()
            };
            let ships = mod21_demo_shipments("short_haul");
            filter_step_unit(&mut bank, &obs, &params, &ships, &mut rng);
        }
        assert_eq!(bank.lot_offsets, vec![0, 8, 32, 48]);
        assert_eq!(bank.n_lots(), 3);
        for row in &bank.freshness {
            assert_eq!(row.len(), 48);
        }
    }

    #[test]
    fn project_lot_map_matches_by_identity_not_position() {
        // Bank holds lots 7 and 8; the observation still lists retired lots 5 and 6.
        let got = project_lot_map(&[0, 0, 3, 1], Some(&[5, 6, 7, 8]), &[7, 8]);
        assert_eq!(got, Some(vec![3, 1]));
    }

    #[test]
    fn project_lot_map_refuses_to_silently_drop_counts() {
        let got = project_lot_map(&[2, 0, 3], Some(&[5, 7, 8]), &[7, 8]);
        assert_eq!(got, None, "sales on a retired lot must not be discarded");
    }

    #[test]
    fn prune_drops_only_fully_dead_leading_lots() {
        let mut bank = UnitParticleBank {
            weights: vec![0.5, 0.5],
            freshness: vec![vec![0.0, 0.0, 0.4, 0.0], vec![0.0, 0.0, 0.0, 0.9]],
            lot_offsets: vec![0, 2, 4],
            lot_ids: vec![11, 12],
        };
        bank.prune_dead_prefix();
        assert_eq!(bank.lot_ids, vec![12]);
        assert_eq!(bank.lot_offsets, vec![0, 2]);
        assert_eq!(bank.freshness[0], vec![0.4, 0.0]);
    }
}
