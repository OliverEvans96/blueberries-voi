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
//! | Spoilage → `δ` interval | pooled `waste_tot` | intersection over per-lot `waste_by` |
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
use rand_distr::{Distribution, Normal};
use rand_pcg::Pcg64;

use crate::obs::FilterObs;
use crate::physics::{
    age_to_f, apply_gamma_decrement, draw_gamma_decrement, draw_gamma_decrement_truncated,
};
use crate::shipments::{
    arrival_age_from_path, birth_f_f2_dirac, shipment_arrival_age, ShipmentTrace,
};
use crate::unit_ll::{
    delta_interval_loglik, loglik_sales_by_units, sequential_kernel_path_logprob,
    spoil_delta_interval, spoil_delta_interval_by_lot, DeltaInterval, DELTA_ANY,
};
use crate::ModelParams;

/// Particle bank on the f-native unit grid, with a shared observed lot segmentation.
///
/// Every row has the same length and the same `lot_offsets`, because deliveries are an
/// observed input: all particles agree on *how many* units arrived and *when*, and differ
/// only in the freshness those units carry.
#[derive(Clone, Debug, Default)]
pub struct UnitParticleBank {
    pub weights: Vec<f64>,
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

    /// Append one delivery as a new segment on every particle.
    fn push_lot(&mut self, lot_id: i64, births: &[f64], units: usize) {
        for (row, &birth) in self.freshness.iter_mut().zip(births.iter()) {
            row.extend(vec![birth; units]);
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

fn mix_arrival_f<R: Rng + ?Sized>(rng: &mut R, params: &ModelParams) -> f64 {
    let ships = [
        ShipmentTrace {
            times_d: vec![0.0, 0.5],
            temps_c: vec![1.0, 1.0],
        },
        ShipmentTrace::smoke_cool(),
        ShipmentTrace {
            times_d: vec![0.0, 4.0],
            temps_c: vec![1.0, 1.0],
        },
    ];
    let idx = rng.random_range(0..ships.len());
    let _: f64 = rng.random();
    let ages: Vec<f64> = ships
        .iter()
        .map(|s| shipment_arrival_age(s, params.q10, params.t_ref_c))
        .collect();
    let mean: f64 = ages.iter().sum::<f64>() / ages.len() as f64;
    let age = ages[idx];
    age_to_f(mean + (age - mean), params.eta_ref)
}

fn birth_f<R: Rng + ?Sized>(obs: &FilterObs, params: &ModelParams, rng: &mut R) -> f64 {
    if let Some(age) = obs.age_at_receipt {
        return birth_f_f2_dirac(age, params.eta_ref);
    }
    if let (Some(times), Some(temps)) = (&obs.temp_times_d, &obs.temp_temps_c) {
        if times.len() >= 2 && temps.len() == times.len() {
            let age = arrival_age_from_path(temps, times, params.q10, params.t_ref_c);
            return age_to_f(age, params.eta_ref);
        }
    }
    if let Some(pack) = obs.pack_date_days {
        let sd = params.f2a_transit_uncertainty_sd;
        let dist = Normal::new(f64::from(pack), sd).expect("sd > 0");
        let age = dist.sample(rng).max(0.0);
        return age_to_f(age, params.eta_ref);
    }
    mix_arrival_f(rng, params)
}

/// Per-day observation resolved onto the bank's own lot segments.
struct DayEvidence {
    /// Per-segment spoil counts (GSIN + `scan_waste`).
    waste_by: Option<Vec<u32>>,
    /// Store spoil total (any channel with `scan_waste`).
    waste_tot: Option<u32>,
    /// Per-segment sales (GSIN).
    sales_by: Option<Vec<u32>>,
    /// Store sales total (every channel).
    sales_tot: Option<u32>,
}

impl DayEvidence {
    fn resolve(obs: &FilterObs, bank_ids: &[i64]) -> Self {
        let sales_by = obs
            .sales_by
            .as_deref()
            .and_then(|v| project_lot_map(v, obs.lot_ids_live.as_deref(), bank_ids));
        // Lot-resolved waste is only usable when sales are lot-resolved too: the spoil
        // interval is read off pre-aging state, which needs the same segment alignment.
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

    /// Spoilage constraint on today's shared decrement, at the finest observed resolution.
    fn delta_interval(
        &self,
        freshness: &[f64],
        offsets: &[usize],
        params: &ModelParams,
    ) -> (Option<DeltaInterval>, f64) {
        let interval = match (&self.waste_by, self.waste_tot) {
            (Some(by), _) => spoil_delta_interval_by_lot(freshness, offsets, by),
            (None, Some(tot)) => spoil_delta_interval(freshness, tot as usize),
            (None, None) => Some(DELTA_ANY),
        };
        let ll = if self.waste_tot.is_none() {
            0.0
        } else {
            delta_interval_loglik(interval, params)
        };
        (interval, ll)
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
    rng: &mut R,
) -> StepDiagnostics {
    let n = bank.weights.len();
    if n == 0 {
        return StepDiagnostics::default();
    }
    let upl = params.units_per_lot.max(1);
    bank.ensure_segmentation(upl);
    let step_seed = rng.random::<u64>();
    let ev = DayEvidence::resolve(obs, &bank.lot_ids);
    let offsets = bank.lot_offsets.clone();

    let mut log_like = vec![0.0f64; n];
    for p in 0..n {
        let mut path_rng = Pcg64::seed_from_u64(step_seed.wrapping_add(p as u64));
        let row = &mut bank.freshness[p];

        // 1. Spoilage: score the observed decrement interval, then age from within it.
        let (interval, mut ll) = ev.delta_interval(row, &offsets, params);
        let decrement = match interval {
            Some((lo, hi)) => draw_gamma_decrement_truncated(&mut path_rng, params, lo, hi),
            None => draw_gamma_decrement(&mut path_rng, params),
        };
        apply_gamma_decrement(row, decrement);

        // 2. Sales: feasibility (+ cross-lot allocation under GSIN), then WOR removal.
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

    // 3. Birth: one segment per delivery, exactly as wide as the observed arrival.
    if obs.arrivals > 0 {
        let births: Vec<f64> = (0..n).map(|_| birth_f(obs, params, rng)).collect();
        let lot_id = obs
            .arrival_lot_ids
            .as_ref()
            .and_then(|ids| ids.first().copied())
            .unwrap_or_else(|| bank.next_synthetic_lot_id());
        bank.push_lot(lot_id, &births, obs.arrivals as usize);
    }

    // 4. Retire lots no particle believes in, so rows track the live window.
    bank.prune_dead_prefix();
    diag
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;

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
        filter_step_unit(&mut bank, &obs, &params, &mut rng);
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
        filter_step_unit(&mut bank, &obs, &ModelParams::default(), &mut rng);
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
            filter_step_unit(&mut bank, &obs, &params, &mut rng);
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
