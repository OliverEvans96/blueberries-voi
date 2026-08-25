//! EngineSession JSON RPC — order schedule + unit PF + rollout (Python day_driver).

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::arrival::{
    ArrivalModel, STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS,
    STREAM_ARRIVAL_TEMP, STREAM_ARRIVAL_TRACE,
};
use crate::arrival_wire::arrival_summary_wire;
use crate::belief_flat::{belief_flat_from_unit_bank, f_grid_k};
use crate::day_step::{
    alive_by_lot, unit_day_step_with_birth, ModelParams, UnitDayStepIn, UnitExit, UnitExitCause,
};
use crate::demand_profile::DemandProfile;
use crate::obs::{
    channels_cache_key, channels_for_preset, channels_json, mask_from_channels,
    preset_for_channels, validate_channels_json, ObsChannels, RichDay,
};
use crate::params::{DEFAULT_L_DIM, DEFAULT_UNITS_PER_LOT};
use crate::physics::{draw_demand, draw_demand_spawn, GammaDecrementTable};
use crate::policy::{case_round_ceil, constant_order, damped_sw_order_f_belief};
use crate::rollout::{rollout_order, RolloutContext, RolloutCosts};
use crate::schedule::OrderSchedule;
use crate::shipments::{mod21_demo_shipments, truth_transit_trace, ShipmentTrace};
use crate::spawn_rng::SpawnRng;
use crate::tradeoff::tradeoff_forecast;
use crate::unit_pf::{filter_step_unit_with_birth_cached, UnitParticleBank};
use crate::voi::truth_f_belief;
use rand::SeedableRng;
use rand_pcg::Pcg64;

/// Whether the ordering policy reads a particle-filter belief or ground-truth freshness.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum BeliefSource {
    /// Standard path: fold masked observations into the unit particle filter each day.
    #[default]
    Filter,
    /// Oracle path: policy sees exact shelf state via [`truth_f_belief`]; filter steps are skipped.
    Truth,
}

impl BeliefSource {
    /// Parse RPC / Python configure strings (`"filter"` | `"truth"`).
    pub fn from_rpc_str(s: &str) -> Result<Self, String> {
        match s.to_ascii_lowercase().as_str() {
            "filter" => Ok(Self::Filter),
            "truth" => Ok(Self::Truth),
            other => Err(format!(
                "belief_source must be 'filter' or 'truth'; got {other:?}"
            )),
        }
    }
}

/// Numeric stream id 7 — dedicated `:birth` CRN for within-lot freshness spread.
const STREAM_BIRTH: u64 = 7;

/// Derives a reproducible per-day, per-stream RNG seed from the root session seed —
/// the CRN (common random numbers) mechanism: every observation rung draws from the
/// same day/stream seed, so profit differences across rungs reflect what a rung could
/// see, not which random seed it happened to draw.
fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

/// Per-obs-channel filter cache: particle bank + per-day flat beliefs for chart replay.
#[derive(Clone, Debug)]
struct RungCache {
    bank: UnitParticleBank,
    /// Last day index folded into `beliefs` for this rung; `-1` means the rung has
    /// never been advanced, i.e. catch-up replay should start from day 0.
    last_day: i32,
    beliefs: Vec<serde_json::Value>,
}

/// The top-level stateful session object that the studio (over RPC) and notebooks
/// drive one simulated day at a time. It owns ground truth (per-unit freshness, lot
/// bookkeeping, the pending delivery pipeline), the unit particle filter and its
/// per-observation-rung belief caches, the order/delivery schedule, and the knobs fed
/// to the ordering policy and rollout. `init` must be called before `step`/`act`; most
/// other pub methods either mutate this state one day at a time or render a slice of
/// it to the JSON wire format the studio consumes.
#[derive(Clone, Debug)]
pub struct EngineSession {
    /// Physics, demand, and case-size knobs shared by ground truth and the filter.
    params: ModelParams,
    /// Ground-truth per-unit freshness, flat across all lots; indexed via `lot_offsets`.
    freshness: Vec<f64>,
    /// Lot boundaries into `freshness`/`lot_ids`: lot `ell` spans
    /// `lot_offsets[ell]..lot_offsets[ell + 1]`.
    lot_offsets: Vec<usize>,
    /// External lot identifiers, one per lot segment in `lot_offsets`.
    lot_ids: Vec<i64>,
    /// Units already ordered but not yet delivered, keyed by arrival day.
    pending: std::collections::BTreeMap<u32, u32>,
    day: u32,
    /// Root RNG seed; every per-day/per-stream RNG (see `stream_rng`/`SpawnRng`) derives
    /// from this so a fixed seed reproduces an entire episode across observation rungs.
    seed: u64,
    /// Diagnostic counter of how many times an RPC/API entry point (`init`, `step`,
    /// `step_n`, `act`) was crossed into; exposed via `host_crossings`.
    crossings: u32,
    initialized: bool,
    /// Particle count backing `bank`; exposed via `n_particles` (leading underscore
    /// because callers read it through that accessor, not the field).
    _n_particles: usize,
    /// Rollout horizon `H` (days) used by the `rollout` policy.
    h: u32,
    /// Number of rollout paths sampled per candidate order when policy is `rollout`.
    n_paths: u32,
    /// Half-width, in cases, of the candidate order search window around the base
    /// damped base-stock quantity when policy is `rollout`.
    radius: i32,
    /// Order lead time in days (delivery day minus order day).
    lead_time: u32,
    /// Whether the unit particle filter runs each day; when `false`, the policy falls
    /// back to an uninformative belief (see `f_belief_for_policy`) unless
    /// [`BeliefSource::Truth`] is active.
    enable_filter: bool,
    /// Where the ordering policy reads its belief: filtered posterior or ground truth.
    belief_source: BeliefSource,
    schedule: OrderSchedule,
    /// Candidate transit temperature traces sampled when drawing a delivery's exposure.
    shipments: Vec<ShipmentTrace>,
    /// Active particle filter bank for the currently selected observation rung.
    bank: UnitParticleBank,
    /// Next lot id to assign to an arriving delivery.
    next_lot: i64,
    /// RPC sequence number, incremented once per `step`/`step_n`/`act` call.
    seq: u32,
    /// `L` dimension (lot slots) of the belief-wire histogram (see `belief_flat.rs`).
    l_dim: usize,
    /// `K` dimension (freshness bins) of the belief-wire histogram.
    k_dim: usize,
    /// Human-readable name of the active observation preset (e.g. `"P1"`), or
    /// `"custom"` when `obs_channels` doesn't match any named preset.
    obs_scenario: String,
    /// Active observation-ladder toggles (POS type, waste scanning, delivery history).
    obs_channels: ObsChannels,
    /// Full per-day ground-truth log (every channel revealed), kept so switching
    /// `obs_scenario` mid-episode can replay history through a different mask instead
    /// of losing it.
    richest_log: Vec<RichDay>,
    /// Per-observation-rung cache of particle bank + belief history, keyed by
    /// `channels_cache_key`, so switching rungs mid-episode only needs to replay the
    /// days that rung hasn't seen yet rather than the whole episode.
    rungs: HashMap<String, RungCache>,
    /// Empty/seed bank state used as the starting point when a rung is first visited.
    bank_init: UnitParticleBank,
    /// Number of days replayed during the most recent `set_obs_channels` catch-up.
    catchup_days_last: u32,
    /// Precomputed Gamma decrement lookup table for the current `params`, shared by
    /// ground truth and the filter to avoid rebuilding it every day.
    gamma_table: GammaDecrementTable,
    /// Fitted arrival-law distributions (duration, temperature, within-pallet position)
    /// used to draw both ground-truth deliveries and filter arrival priors.
    arrival_model: ArrivalModel,
    /// Which product's arrival-model parameters to draw deliveries from.
    arrival_product: String,
    /// Multiplier widening (>1) or narrowing (<1) the within-lot spread of arrival
    /// freshness around its mean; a stress-test knob, 1.0 leaves the draw unchanged.
    spread_scale: f64,
    /// Additive bias, in Celsius, applied to sampled transit temperature before it
    /// feeds the Q10 exposure factor — used to simulate a systematic warm/cool bias.
    transit_temp_bias_c: f64,
}

impl Default for EngineSession {
    fn default() -> Self {
        Self::new(1)
    }
}

impl EngineSession {
    /// Builds a session with default config (16 particles, weekly delivery/order
    /// schedule, the embedded arrival model) for the given root seed. The session is
    /// *not* marked initialized by `new` alone — call `init` (or `reset`) before
    /// `step`/`act`, which also seeds the particle bank and applies the committed
    /// demand profile if none was set.
    pub fn new(seed: u64) -> Self {
        let n = 16usize;
        let params = ModelParams::default();
        let arrival_model = ArrivalModel::embedded();
        Self {
            params: params.clone(),
            freshness: vec![],
            lot_offsets: vec![0],
            lot_ids: vec![],
            pending: std::collections::BTreeMap::new(),
            day: 0,
            seed,
            crossings: 0,
            initialized: false,
            _n_particles: n,
            h: 7,
            n_paths: 2,
            radius: 1,
            lead_time: 1,
            enable_filter: true,
            belief_source: BeliefSource::Filter,
            schedule: OrderSchedule::from_delivery(&[0, 1, 2, 3, 4, 5, 6], 1)
                .unwrap_or_else(|_| OrderSchedule::default()),
            shipments: mod21_demo_shipments("abdella_all"),
            bank: UnitParticleBank::empty(n),
            next_lot: 1,
            seq: 0,
            l_dim: DEFAULT_L_DIM,
            k_dim: 4,
            obs_scenario: "P1".to_string(),
            obs_channels: channels_for_preset("P1").unwrap(),
            richest_log: Vec::new(),
            rungs: HashMap::new(),
            bank_init: UnitParticleBank::empty(n),
            catchup_days_last: 0,
            gamma_table: GammaDecrementTable::for_params(&params),
            arrival_model,
            arrival_product: "abdella_all".to_string(),
            spread_scale: 1.0,
            transit_temp_bias_c: 0.0,
        }
    }

    /// Rebuilds the session to a fresh episode at the given seed and marks it
    /// initialized. Must be called (directly or via `reset`) before `step`/`act`;
    /// re-applies the committed demand profile and re-seeds the particle bank so a
    /// prior episode's state can't leak into the new one.
    pub fn init(&mut self, seed: u64) {
        *self = Self::new(seed);
        self.initialized = true;
        self.crossings += 1;
        if self.params.demand_profile.is_none() {
            apply_demand_profile(&mut self.params, committed_demand_profile());
        }
        if self.uses_filter() {
            self.seed_particle_bank();
        }
    }

    fn uses_filter(&self) -> bool {
        self.enable_filter && self.belief_source == BeliefSource::Filter
    }

    /// Sets whether the ordering policy reads filter posterior or ground-truth freshness.
    pub fn set_belief_source(&mut self, source: BeliefSource) {
        self.belief_source = source;
    }

    /// Replaces the day-of-week/week demand calendar used to draw daily demand.
    pub fn set_demand_profile(&mut self, profile: DemandProfile) {
        apply_demand_profile(&mut self.params, profile);
    }

    /// Applies session-wide config (lead time, filter on/off, rollout horizon/paths,
    /// candidate order search radius, shipment traces, particle count, demand profile,
    /// units per lot) and re-seeds the particle bank so the new particle count and
    /// demand/shipment settings take effect immediately.
    pub fn configure(
        &mut self,
        lead_time: u32,
        enable_filter: bool,
        h: u32,
        n_paths: u32,
        radius: i32,
        shipments: Vec<ShipmentTrace>,
        n_particles: usize,
        demand_profile: Option<DemandProfile>,
        units_per_lot: Option<usize>,
    ) {
        self.lead_time = lead_time.max(1);
        self.enable_filter = enable_filter;
        self.h = h.max(1);
        self.n_paths = n_paths.max(1);
        self.radius = radius;
        let n = n_particles.max(1);
        self._n_particles = n;
        self.params.units_per_lot = units_per_lot.unwrap_or(DEFAULT_UNITS_PER_LOT).max(1);
        self.bank = UnitParticleBank::empty(n);
        if !shipments.is_empty() {
            self.shipments = shipments;
        }
        if let Some(profile) = demand_profile {
            apply_demand_profile(&mut self.params, profile);
        } else if self.params.demand_profile.is_none() {
            apply_demand_profile(&mut self.params, committed_demand_profile());
        }
        if self.uses_filter() {
            self.seed_particle_bank();
        }
    }

    /// Sets which weekdays deliveries arrive on and the order lead time; order weekdays
    /// are derived from the delivery weekdays and lead time.
    pub fn set_delivery_schedule(&mut self, delivery: &[u32], lead_time: u32) {
        self.lead_time = lead_time.max(1);
        self.schedule = OrderSchedule::from_delivery(delivery, self.lead_time)
            .unwrap_or_else(|_| OrderSchedule::default());
    }

    /// Resets the particle bank to empty and snapshots it as `bank_init`. Per ADR 0136
    /// the bank starts zero-initialized rather than phantom-prefilled — the filter has
    /// no belief about a shelf it hasn't observed arrivals onto yet.
    fn seed_particle_bank(&mut self) {
        let n = self._n_particles.max(1);
        // ADR 0136: zero-init — empty shelf until observed arrivals (no phantom L×U pre-fill).
        self.bank = UnitParticleBank::empty(n);
        self.bank_init = self.bank.clone();
    }

    pub fn episode_day(&self) -> u32 {
        self.day
    }

    pub fn obs_scenario(&self) -> &str {
        &self.obs_scenario
    }

    pub fn obs_channels(&self) -> ObsChannels {
        self.obs_channels
    }

    /// Apply studio/RPC configure keys (arrival_product, physics knobs, schedule, …).
    pub fn apply_configure(&mut self, params: serde_json::Value) {
        if let Some(seed) = rpc_field(&params, "seed").and_then(|v| v.as_u64()) {
            self.seed = seed;
        }
        self.apply_rpc_configure(&params);
    }

    fn active_rung_key(&self) -> String {
        channels_cache_key(self.obs_channels)
    }

    fn mask_active(&self) -> crate::obs::ObsMask {
        mask_from_channels(self.obs_channels)
    }

    fn belief_from_bank(&self, bank: &UnitParticleBank) -> serde_json::Value {
        belief_flat_from_unit_bank(bank, self.l_dim, self.k_dim)
    }

    /// Renders a rung's sparse per-day belief array to the wire format, dropping the
    /// `Null` placeholder days a rung hasn't been advanced through yet.
    fn belief_history_wire(beliefs: &[serde_json::Value]) -> serde_json::Value {
        let days: Vec<serde_json::Value> = beliefs
            .iter()
            .enumerate()
            .filter(|(_, b)| !b.is_null())
            .map(|(day, belief)| serde_json::json!({ "day": day, "belief": belief }))
            .collect();
        serde_json::Value::Array(days)
    }

    /// Stores the flattened belief for `day_idx` under the currently active rung's
    /// cache entry, growing its sparse `beliefs` vector as needed. No-op when the
    /// filter is disabled, since there is no belief to record.
    fn record_belief_for_day(&mut self, day_idx: u32, bank: &UnitParticleBank) {
        if !self.uses_filter() {
            return;
        }
        let key = self.active_rung_key();
        let belief = self.belief_from_bank(bank);
        let entry = self.rungs.entry(key).or_insert_with(|| RungCache {
            bank: self.bank_init.clone(),
            last_day: -1,
            beliefs: vec![],
        });
        let i = day_idx as usize;
        if entry.beliefs.len() <= i {
            entry.beliefs.resize(i + 1, serde_json::Value::Null);
        }
        entry.beliefs[i] = belief;
        entry.bank = bank.clone();
        entry.last_day = day_idx as i32;
    }

    /// Snapshots the currently active bank into its rung cache entry (keeping that
    /// entry's existing belief history) before switching to a different observation
    /// rung, so the previous rung can be resumed later without re-replaying it.
    fn persist_active_rung(&mut self) {
        if !self.uses_filter() {
            return;
        }
        let key = self.active_rung_key();
        let beliefs = self
            .rungs
            .get(&key)
            .map(|r| r.beliefs.clone())
            .unwrap_or_default();
        self.rungs.insert(
            key,
            RungCache {
                bank: self.bank.clone(),
                last_day: self.day as i32 - 1,
                beliefs,
            },
        );
    }

    fn require_init(&self) {
        if !self.initialized {
            panic!("EngineSession.init() must be called before step/act");
        }
    }

    /// Advances ground truth by exactly one simulated day: rounds and (schedule
    /// permitting) places `order_qty` into the pending pipeline, applies any delivery
    /// due today (drawing its duration/temperature/position/decrement from
    /// `arrival_model` on dedicated CRN streams, then biasing it by
    /// `transit_temp_bias_c`/`spread_scale`), draws demand, and runs `day_step` to
    /// settle sales, spoilage, and the resulting freshness/lot state. When the filter
    /// is enabled it then folds the day's masked observation into `bank` and records
    /// the new belief for the active rung. Each RNG stream is derived from `(seed,
    /// day, stream id)` so re-running a day is reproducible and independent of which
    /// observation rung is active (CRN).
    fn advance_one(&mut self, order_qty: u32) -> DayDelta {
        self.require_init();
        if self.day >= 90 {
            panic!("episode ended at day 90; Reset to start a new episode");
        }
        let mut order = case_round_ceil(order_qty, self.params.case_size);
        if !self.schedule.can_order(self.day) {
            order = 0;
        }
        *self.pending.entry(self.day + self.lead_time).or_insert(0) += order;
        let arrival = self.pending.remove(&self.day).unwrap_or(0);
        let pre_lot_ids = self.lot_ids.clone();
        let (delivery_unit_f, pack_date_days, shipment_trace, arrival_lot_ids) = if arrival > 0 {
            let n_units = arrival as usize;
            let mut rng_dur =
                SpawnRng::spawn_rng(self.seed, "session", self.day, STREAM_ARRIVAL_DURATION);
            let mut rng_temp =
                SpawnRng::spawn_rng(self.seed, "session", self.day, STREAM_ARRIVAL_TEMP);
            let mut rng_pos =
                SpawnRng::spawn_rng(self.seed, "session", self.day, STREAM_ARRIVAL_POS);
            let mut rng_gamma =
                SpawnRng::spawn_rng(self.seed, "session", self.day, STREAM_ARRIVAL_GAMMA);
            let draw = self.arrival_model.draw_truth_delivery(
                &self.arrival_product,
                n_units,
                &mut rng_dur,
                &mut rng_temp,
                &mut rng_pos,
                &mut rng_gamma,
            );
            let biased_t_bar = draw.t_bar + self.transit_temp_bias_c;
            let biased_phi = self.arrival_model.phi_bar_from_t_bar(biased_t_bar);
            let phi_ratio = (biased_phi / draw.phi_bar.max(1e-12)).clamp(0.25, 4.0);
            let mut unit_f: Vec<f64> = draw
                .unit_f
                .iter()
                .map(|&f| {
                    let rem = (1.0 - f).max(0.0);
                    (1.0 - rem * phi_ratio).clamp(0.0, 1.0)
                })
                .collect();
            if (self.spread_scale - 1.0).abs() > 1e-12 && !unit_f.is_empty() {
                let mean = unit_f.iter().sum::<f64>() / unit_f.len() as f64;
                for f in &mut unit_f {
                    *f = (mean + self.spread_scale * (*f - mean)).clamp(0.0, 1.0);
                }
            }
            let mut rng_trace =
                SpawnRng::spawn_rng(self.seed, "session", self.day, STREAM_ARRIVAL_TRACE);
            let trace = truth_transit_trace(
                draw.duration_d,
                biased_phi,
                biased_t_bar,
                self.arrival_model.temp_floor_c,
                self.params.q10,
                self.params.t_ref_c,
                &mut rng_trace,
            );
            let lot_id = self.next_lot;
            self.lot_ids.push(lot_id);
            self.next_lot += 1;
            (
                Some(unit_f),
                Some(draw.pack_date_days),
                Some(trace),
                vec![lot_id],
            )
        } else {
            (None, None, None, Vec::new())
        };
        let demand = if self.params.demand_profile.is_some() {
            let mut rng_d = SpawnRng::spawn_rng(self.seed, "session", self.day, ":demand");
            draw_demand_spawn(&mut rng_d, &self.params, Some(self.day))
        } else {
            let mut rng_d = stream_rng(self.seed, self.day, 1);
            draw_demand(&mut rng_d, &self.params, None)
        };
        let mut rng_gamma = stream_rng(self.seed, self.day, 3);
        let mut rng_alloc = stream_rng(self.seed, self.day, 2);
        let mut rng_birth = if arrival > 0 {
            Some(stream_rng(self.seed, self.day, STREAM_BIRTH))
        } else {
            None
        };
        let input = UnitDayStepIn {
            freshness: self.freshness.clone(),
            lot_offsets: self.lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_unit_f,
            units_per_lot: Some(self.params.units_per_lot),
        };
        let out = unit_day_step_with_birth(
            &input,
            &self.params,
            &self.shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            None,
            None,
            rng_birth.as_mut(),
        );
        self.freshness = out.freshness;
        self.lot_offsets = out.lot_offsets;
        let rich = RichDay {
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            arrivals: arrival,
            sales_by: out.sales_by.clone(),
            waste_by: out.waste_by.clone(),
            lot_ids: pre_lot_ids,
            arrival_lot_ids,
            shipment_trace,
            pack_date_days,
        };
        let day_idx = self.day;
        if self.uses_filter() {
            let obs = self.mask_active().apply(&rich);
            let mut fr = stream_rng(self.seed, day_idx, 6);
            let mut rng_birth_filter = if obs.arrivals > 0 {
                Some(stream_rng(self.seed, day_idx, STREAM_BIRTH))
            } else {
                None
            };
            // `filter_step_unit_with_birth_cached` syncs params and the configured
            // corridor onto `self.arrival_model` itself; an external sync here was
            // redundant (T-150: `sync_params` was rebuilding every CDF twice per day).
            filter_step_unit_with_birth_cached(
                &mut self.bank,
                &obs,
                &self.params,
                &self.shipments,
                &mut fr,
                rng_birth_filter.as_mut(),
                &mut self.gamma_table,
                Some(&mut self.arrival_model),
            );
            let bank = self.bank.clone();
            self.record_belief_for_day(day_idx, &bank);
        }
        let on_hand: u32 = alive_by_lot(&self.freshness, &self.lot_offsets)
            .iter()
            .sum();
        let delta = DayDelta {
            demand: out.demand,
            sales_total: out.sales_total,
            waste_total: out.waste_total,
            on_hand,
            order_qty: order,
            arrivals: arrival,
            episode_day: self.day,
            unit_exits: out.unit_exits,
        };
        self.day += 1;
        self.seq += 1;
        self.richest_log.push(rich);
        delta
    }

    /// Assembles the full RPC/studio state snapshot: current belief, live lots/units,
    /// pending pipeline, the config actually in effect (`applied_config`), the
    /// delivery/order schedule, and demand/arrival summaries. This is the payload sent
    /// after `init` and after any observation-rung switch.
    pub fn snapshot_value(&self) -> serde_json::Value {
        serde_json::json!({
            "seq": self.seq,
            "episode_day": self.day,
            "belief": self.belief_value(),
            "history": [],
            "live_lots": self.live_lots_value(),
            "live_units": self.live_units_value(),
            "pipeline": self.pipeline_value(),
            "applied_config": {
                "n_particles": self._n_particles,
                "H": self.h,
                "n_rollout_paths": self.n_paths,
                "candidate_case_radius": self.radius,
                "L": self.l_dim,
                "K": self.k_dim,
                "enable_filter": self.enable_filter,
                "belief_source": match self.belief_source {
                    BeliefSource::Filter => "filter",
                    BeliefSource::Truth => "truth",
                },
                "lead_time": self.lead_time,
                "delivery_weekdays": self.schedule.delivery_weekday_list(),
                "obs_scenario": self.obs_scenario,
                "obs_channels": channels_json(self.obs_channels),
                "seed": self.seed,
                "arrival_product": self.arrival_product,
                "spread_scale": self.spread_scale,
                "transit_temp_bias_c": self.transit_temp_bias_c,
                "eta_ref": self.params.eta_ref,
                "q10": self.params.q10,
                "t_ref_c": self.params.t_ref_c,
                "t_store_c": self.params.t_store_c,
            },
            "schedule": schedule_wire(&self.schedule),
            "demand_summary": demand_summary_wire(&self.params),
            "arrival_summary": arrival_summary_wire(
                &self.arrival_model,
                &self.arrival_product,
                self.obs_channels,
                self.transit_temp_bias_c,
            ),
        })
    }

    /// Renders one `DayDelta` (and the live state it leaves behind) to the RPC wire
    /// format sent to the studio after each `step`/`act` call.
    pub fn day_delta_value(&self, d: &DayDelta) -> serde_json::Value {
        serde_json::json!({
            "seq": self.seq,
            "episode_day": d.episode_day,
            "day": {
                "day": d.episode_day,
                "order_qty": d.order_qty,
                "arrivals": d.arrivals,
                "sales_total": d.sales_total,
                "waste_total": d.waste_total,
                "demand": d.demand,
                "L": d.on_hand,
                "unit_exits": self.unit_exits_wire(&d.unit_exits),
            },
            "live_lots": self.live_lots_value(),
            "live_units": self.live_units_value(),
            "pipeline": self.pipeline_value(),
            "drop_oldest": self.seq > 14,
            "belief": self.belief_value(),
        })
    }

    fn belief_value(&self) -> serde_json::Value {
        if self.belief_source == BeliefSource::Truth {
            let (lot_counts, f_marginals, f_grid) =
                truth_f_belief(&self.freshness, &self.lot_offsets, self.k_dim);
            return serde_json::json!({
                "L": self.l_dim,
                "K": self.k_dim,
                "lot_counts": lot_counts,
                "f_marginals": f_marginals,
                "f_grid": f_grid,
            });
        }
        belief_flat_from_unit_bank(&self.bank, self.l_dim, self.k_dim)
    }

    /// Finds which lot segment `unit_idx` falls in by scanning `lot_offsets`. Falls
    /// back to the last lot if no segment contains the index (should not happen for a
    /// valid unit index, but keeps this infallible for wire-building callers).
    fn lot_index_for_unit(&self, unit_idx: usize) -> usize {
        let l = self.lot_offsets.len().saturating_sub(1);
        for ell in 0..l {
            if unit_idx >= self.lot_offsets[ell] && unit_idx < self.lot_offsets[ell + 1] {
                return ell;
            }
        }
        l.saturating_sub(1)
    }

    fn live_units_value(&self) -> serde_json::Value {
        let units: Vec<serde_json::Value> = self
            .freshness
            .iter()
            .enumerate()
            .filter(|(_, &f)| f > 0.0)
            .map(|(unit_idx, &f)| {
                let ell = self.lot_index_for_unit(unit_idx);
                let lot_id = self.lot_ids.get(ell).copied().unwrap_or(ell as i64 + 1);
                serde_json::json!({
                    "unit_id": unit_idx,
                    "lot_id": lot_id,
                    "f": f,
                })
            })
            .collect();
        serde_json::Value::Array(units)
    }

    fn unit_exits_wire(&self, exits: &[UnitExit]) -> serde_json::Value {
        let items: Vec<serde_json::Value> = exits
            .iter()
            .map(|exit| {
                let ell = self.lot_index_for_unit(exit.unit_idx);
                let lot_id = self.lot_ids.get(ell).copied().unwrap_or(ell as i64 + 1);
                serde_json::json!({
                    "unit_id": exit.unit_idx,
                    "lot_id": lot_id,
                    "f": exit.f,
                    "cause": match exit.cause {
                        UnitExitCause::Spoiled => "spoiled",
                        UnitExitCause::Sold => "sold",
                    },
                })
            })
            .collect();
        serde_json::Value::Array(items)
    }

    /// Builds the per-lot wire summary (count, mean freshness, and per-unit freshness
    /// values) for every lot with at least one unit still alive.
    fn live_lots_value(&self) -> serde_json::Value {
        let l = self.lot_offsets.len().saturating_sub(1);
        let alive = alive_by_lot(&self.freshness, &self.lot_offsets);
        let lots: Vec<serde_json::Value> = (0..l)
            .filter(|&ell| alive.get(ell).copied().unwrap_or(0) > 0)
            .map(|ell| {
                let n = alive[ell];
                let start = self.lot_offsets[ell];
                let end = self.lot_offsets.get(ell + 1).copied().unwrap_or(start);
                let mean_f = if n > 0 {
                    self.freshness[start..end]
                        .iter()
                        .filter(|&&f| f > 0.0)
                        .sum::<f64>()
                        / f64::from(n)
                } else {
                    0.0
                };
                let lot_id = self.lot_ids.get(ell).copied().unwrap_or(ell as i64 + 1);
                let f_values: Vec<f64> = self.freshness[start..end]
                    .iter()
                    .copied()
                    .filter(|&f| f > 0.0)
                    .collect();
                serde_json::json!({"lot_id": lot_id, "n": n, "mean_f": mean_f, "f_values": f_values})
            })
            .collect();
        serde_json::Value::Array(lots)
    }

    fn pipeline_value(&self) -> serde_json::Value {
        let pipe: Vec<serde_json::Value> = self
            .pending
            .iter()
            .filter(|(_, &qty)| qty != 0)
            .map(|(&arrival_day, &qty)| serde_json::json!({"arrival_day": arrival_day, "qty": qty}))
            .collect();
        serde_json::Value::Array(pipe)
    }

    /// Sets the `L` (lot slots) and `K` (freshness bins) dimensions of the belief-wire
    /// histogram used for charts and the ordering policy.
    pub fn set_belief_dims(&mut self, l: usize, k: usize) {
        self.l_dim = l;
        self.k_dim = k.max(1);
    }

    /// Advances one day with a caller-chosen order quantity, bypassing policy dispatch.
    pub fn step(&mut self, order: u32) -> DayDelta {
        self.crossings += 1;
        self.advance_one(order)
    }

    /// Advances one day per entry in `orders`, in order, returning each day's delta —
    /// a batch form of `step` for callers stepping a whole pre-computed order sequence.
    pub fn step_n(&mut self, orders: &[u32]) -> Vec<DayDelta> {
        self.crossings += 1;
        orders.iter().map(|&q| self.advance_one(q)).collect()
    }

    /// Gets the `(lot_counts, f_marginals, f_grid)` triple the ordering policy needs.
    /// When the filter is enabled this is the flattened particle-bank belief; when
    /// disabled there's no tracked inventory belief, so it synthesizes zero lot counts
    /// with a uniform freshness prior — the "empty shelf" fallback `act` dispatches on.
    fn f_belief_for_policy(&self) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        if self.belief_source == BeliefSource::Truth {
            return truth_f_belief(&self.freshness, &self.lot_offsets, self.k_dim);
        }
        if self.enable_filter {
            let v = belief_flat_from_unit_bank(&self.bank, self.l_dim, self.k_dim);
            (
                json_f64_vec(&v["lot_counts"]),
                json_f64_vec(&v["f_marginals"]),
                json_f64_vec(&v["f_grid"]),
            )
        } else {
            let k = self.k_dim.max(1);
            let grid = f_grid_k(k);
            let uniform = 1.0 / k as f64;
            (vec![0.0; self.l_dim], vec![uniform; self.l_dim * k], grid)
        }
    }

    /// Select an order via policy dispatch on belief mean (filter on) or empty shelf.
    pub fn act(
        &mut self,
        policy: Option<&str>,
        order_qty: Option<u32>,
        alpha: Option<f64>,
        rho: Option<f64>,
        h: Option<u32>,
        n_rollout_paths: Option<u32>,
        candidate_case_radius: Option<i32>,
    ) -> DayDelta {
        self.require_init();
        let pending_sum: u32 = self.pending.values().copied().sum();
        let (lot_counts, f_marginals, f_grid) = self.f_belief_for_policy();
        let f_pipe = 1.0;
        let alpha = alpha.unwrap_or(0.9);
        let rho = rho.unwrap_or(0.8);
        let h = h.unwrap_or(self.h);
        let n_paths = n_rollout_paths.unwrap_or(self.n_paths);
        let radius = candidate_case_radius.unwrap_or(self.radius);
        let name = policy.unwrap_or("rollout").to_ascii_lowercase();
        let q = match name.as_str() {
            "constant" | "const" | "fixed" => {
                constant_order(order_qty.unwrap_or(0), self.params.case_size)
            }
            "damped_sw" | "sw" => damped_sw_order_f_belief(
                &lot_counts,
                &f_marginals,
                &f_grid,
                pending_sum,
                self.day,
                &self.params,
                alpha,
                rho,
                Some(&self.schedule),
                f_pipe,
            ),
            "rollout" | "ctl" | "rollout_order" => {
                let base = damped_sw_order_f_belief(
                    &lot_counts,
                    &f_marginals,
                    &f_grid,
                    pending_sum,
                    self.day,
                    &self.params,
                    alpha,
                    rho,
                    Some(&self.schedule),
                    f_pipe,
                );
                let ctx = RolloutContext {
                    root_seed: self.seed,
                    run_id: format!("session-d{}", self.day),
                    day0: self.day,
                    lead_time: self.lead_time,
                    schedule: self.schedule.clone(),
                    alpha,
                    rho,
                    costs: RolloutCosts::default(),
                    shipments: self.shipments.clone(),
                    f_pipeline_default: f_pipe,
                    h,
                    n_paths,
                    radius,
                };
                rollout_order(
                    &lot_counts,
                    &f_marginals,
                    &f_grid,
                    base,
                    &self.params,
                    &self.pending,
                    &ctx,
                )
                .unwrap_or(base)
            }
            other => panic!("unknown policy {other:?}; use 'constant', 'damped_sw', or 'rollout'"),
        };
        self.crossings += 1;
        self.advance_one(q)
    }

    /// Shorthand for `act` with the `rollout` policy and its own default tuning.
    pub fn act_rollout(&mut self) -> DayDelta {
        self.act(Some("rollout"), None, None, None, None, None, None)
    }

    /// Ends the current episode and starts a new one at `seed` (delegates to `init`).
    pub fn reset(&mut self, seed: u64) {
        self.init(seed);
    }

    /// Switches the active observation-ladder rung to `channels`, replaying whatever
    /// days of `richest_log` that rung's cache hasn't seen yet through its own mask so
    /// its particle bank and belief history are caught up to the current day, then
    /// persists the previous rung's bank so it can be resumed later. Each rung's cache
    /// is keyed by `channels_cache_key` and starts from `bank_init` the first time it's
    /// visited; `catchup_days_last` records how many days this call had to replay, and
    /// the fast path (same channels, already-cached rung) replays nothing. Returns the
    /// same snapshot shape as `snapshot_value`, with `belief_history` for the new rung
    /// attached.
    pub fn set_obs_channels(&mut self, channels: ObsChannels) -> Result<serde_json::Value, String> {
        self.require_init();
        self.catchup_days_last = 0;
        let key = channels_cache_key(channels);
        if channels == self.obs_channels && self.rungs.contains_key(&key) {
            let mut snap = self.snapshot_value();
            if self.uses_filter() {
                if let Some(rung) = self.rungs.get(&key) {
                    if let Some(obj) = snap.as_object_mut() {
                        obj.insert(
                            "belief_history".to_string(),
                            Self::belief_history_wire(&rung.beliefs),
                        );
                    }
                }
            }
            return Ok(snap);
        }
        if self.uses_filter() {
            self.persist_active_rung();
        }
        self.obs_channels = channels;
        self.obs_scenario = preset_for_channels(channels)
            .map(|s| s.to_string())
            .unwrap_or_else(|| "custom".to_string());
        if self.uses_filter() {
            let cached = self
                .rungs
                .get(&key)
                .cloned()
                .unwrap_or_else(|| RungCache {
                    bank: self.bank_init.clone(),
                    last_day: -1,
                    beliefs: vec![],
                });
            let mut bank = cached.bank;
            let last = cached.last_day;
            let mut beliefs = cached.beliefs;
            let now = self.day as i32 - 1;
            let mask = mask_from_channels(channels);
            let mut n = 0u32;
            for day_idx in (last + 1)..=now {
                let log = &self.richest_log[day_idx as usize];
                let obs = mask.apply(log);
                let mut fr = stream_rng(self.seed, day_idx as u32, 6);
                let mut rng_birth_filter = if obs.arrivals > 0 {
                    Some(stream_rng(self.seed, day_idx as u32, STREAM_BIRTH))
                } else {
                    None
                };
                // See advance_one: filter_step_unit_with_birth_cached syncs params and
                // the corridor itself, so an external sync_params here was redundant.
                filter_step_unit_with_birth_cached(
                    &mut bank,
                    &obs,
                    &self.params,
                    &self.shipments,
                    &mut fr,
                    rng_birth_filter.as_mut(),
                    &mut self.gamma_table,
                    Some(&mut self.arrival_model),
                );
                let belief = self.belief_from_bank(&bank);
                let i = day_idx as usize;
                if beliefs.len() <= i {
                    beliefs.resize(i + 1, serde_json::Value::Null);
                }
                beliefs[i] = belief;
                n += 1;
            }
            self.catchup_days_last = n;
            self.bank = bank;
            self.rungs.insert(
                key,
                RungCache {
                    bank: self.bank.clone(),
                    last_day: now,
                    beliefs: beliefs.clone(),
                },
            );
        }
        let mut snap = self.snapshot_value();
        if self.enable_filter {
            if let Some(rung) = self.rungs.get(&self.active_rung_key()) {
                if let Some(obj) = snap.as_object_mut() {
                    obj.insert(
                        "belief_history".to_string(),
                        Self::belief_history_wire(&rung.beliefs),
                    );
                }
            }
        }
        Ok(snap)
    }

    /// Switches to the observation rung named by a preset id (e.g. `"P1"`, `"F2"`);
    /// resolves the preset to `ObsChannels` and delegates to `set_obs_channels`.
    pub fn set_obs_scenario(&mut self, obs_scenario: &str) -> Result<serde_json::Value, String> {
        let channels = channels_for_preset(obs_scenario)?;
        self.set_obs_channels(channels)
    }

    /// Forecasts the demand/spoilage/cost tradeoff over the delivery protection window
    /// from the current belief, for the studio's forward-looking chart.
    pub fn tradeoff_forecast_value(
        &self,
        n_paths: Option<u32>,
        protection_days: Option<u32>,
    ) -> serde_json::Value {
        self.require_init();
        let n_paths = n_paths.unwrap_or(self.n_paths).max(1);
        tradeoff_forecast(
            &self.bank,
            self.l_dim,
            &self.params,
            &self.schedule,
            self.day,
            self.seed,
            n_paths,
            protection_days,
        )
    }

    /// Replays `richest_log` from `since_day` through the currently active observation
    /// mask, returning what that rung would have seen each day — never the raw ground
    /// truth (no channel reveals more than its mask allows).
    pub fn events_value(&self, since_day: u32) -> serde_json::Value {
        self.require_init();
        let mask = self.mask_active();
        if since_day > self.day {
            return serde_json::json!({ "days": [] });
        }
        let start = since_day as usize;
        let end = self.day as usize;
        let days: Vec<serde_json::Value> = self.richest_log[start..end.min(self.richest_log.len())]
            .iter()
            .enumerate()
            .map(|(i, log)| {
                let obs = mask.apply(log);
                serde_json::json!({
                    "day": start as u32 + i as u32,
                    "arrivals": obs.arrivals,
                    "sales_total": obs.sales_tot,
                    "waste_total": obs.waste_tot,
                    "sales_by": obs.sales_by,
                    "waste_by": obs.waste_by,
                    "lot_ids": obs.lot_ids_live,
                    "arrival_lot_ids": obs.arrival_lot_ids,
                    "pack_date_days": obs.pack_date_days,
                    "temp_times_d": obs.temp_times_d,
                    "temp_temps_c": obs.temp_temps_c,
                })
            })
            .collect();
        serde_json::json!({ "days": days })
    }

    /// Current particle filter bank's per-particle weights, for external diagnostics.
    pub fn bank_weights(&self) -> Vec<f64> {
        self.bank.weights.clone()
    }

    /// Number of days the most recent `set_obs_channels`/`set_obs_scenario` call had
    /// to replay to catch that rung's cache up to the current day.
    pub fn catchup_days_last_call(&self) -> u32 {
        self.catchup_days_last
    }

    /// Diagnostic count of RPC/API entry-point calls (`init`, `step`, `step_n`, `act`)
    /// made against this session so far.
    pub fn host_crossings(&self) -> u32 {
        self.crossings
    }

    /// Number of particles backing the unit particle filter bank.
    pub fn n_particles(&self) -> usize {
        self._n_particles
    }
}

const SCHEDULE_EPOCH: &str = "2024-01-01";
const EMBEDDED_DEMAND_PROFILE: &str = include_str!("../../../data/freshnet/demand_profile.json");

/// Loads the demand profile baked into the binary at compile time, used whenever an RPC
/// caller doesn't supply its own `demand_profile`/`demand_profile_json`.
fn committed_demand_profile() -> DemandProfile {
    DemandProfile::from_json(EMBEDDED_DEMAND_PROFILE).expect("embedded demand profile")
}

fn apply_demand_profile(params: &mut ModelParams, profile: DemandProfile) {
    params.apply_demand_profile(profile);
}

fn json_f64_vec(value: &serde_json::Value) -> Vec<f64> {
    value
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default()
}

/// Renders an [`OrderSchedule`]'s weekday bitmaps as the sparse weekday-index arrays the
/// studio front end expects, alongside the fixed [`SCHEDULE_EPOCH`] the weekdays are
/// anchored to.
fn schedule_wire(sched: &OrderSchedule) -> serde_json::Value {
    let delivery: Vec<u32> = sched
        .delivery_weekdays
        .iter()
        .enumerate()
        .filter(|(_, &on)| on)
        .map(|(i, _)| i as u32)
        .collect();
    let order: Vec<u32> = sched
        .order_weekdays
        .iter()
        .enumerate()
        .filter(|(_, &on)| on)
        .map(|(i, _)| i as u32)
        .collect();
    serde_json::json!({
        "delivery_weekdays": delivery,
        "order_weekdays": order,
        "lead_time_days": sched.lead_time_days,
        "epoch": SCHEDULE_EPOCH,
    })
}

/// Summarizes the active demand profile (or the committed default, if none is set) into
/// the scale and day-of-week means the studio charts need, without shipping the full
/// profile over RPC.
fn demand_summary_wire(params: &ModelParams) -> serde_json::Value {
    let profile = params
        .demand_profile
        .as_ref()
        .cloned()
        .unwrap_or_else(committed_demand_profile);
    let scale = profile.scale_target_mu();
    serde_json::json!({
        "scale_mu": scale,
        "dow_means": profile.dow_means(),
    })
}

/// Parses an RPC-supplied demand profile, accepting either a raw JSON string under
/// `demand_profile_json` or a `demand_profile` field that is itself a JSON string or an
/// inline object. Returns `None` if the caller supplied nothing usable, in which case
/// callers fall back to [`committed_demand_profile`].
fn parse_demand_profile_from_rpc(params: &serde_json::Value) -> Option<DemandProfile> {
    if let Some(json) = rpc_str(params, "demand_profile_json") {
        return DemandProfile::from_json(json).ok();
    }
    if let Some(value) = rpc_field(params, "demand_profile") {
        if let Some(json) = value.as_str() {
            return DemandProfile::from_json(json).ok();
        }
        if value.is_object() {
            return DemandProfile::from_json(&value.to_string()).ok();
        }
    }
    None
}

/// Looks up an RPC parameter, checking the top-level `params` object first and falling
/// back to `params.config`. Every other `rpc_*` helper in this file goes through here, so
/// callers can send fields either flat or nested under `config` interchangeably.
fn rpc_field<'a>(params: &'a serde_json::Value, key: &str) -> Option<&'a serde_json::Value> {
    params
        .get(key)
        .or_else(|| params.get("config").and_then(|c| c.get(key)))
}

fn rpc_u64(params: &serde_json::Value, key: &str) -> Option<u64> {
    rpc_field(params, key).and_then(|v| v.as_u64())
}

fn rpc_i64(params: &serde_json::Value, key: &str) -> Option<i64> {
    rpc_field(params, key).and_then(|v| v.as_i64())
}

fn rpc_bool(params: &serde_json::Value, key: &str) -> Option<bool> {
    rpc_field(params, key).and_then(|v| v.as_bool())
}

fn rpc_f64(params: &serde_json::Value, key: &str) -> Option<f64> {
    rpc_field(params, key).and_then(|v| v.as_f64())
}

/// Coerces a JSON array into a sorted, deduplicated list of valid weekday indices (`0..7`),
/// dropping anything out of range. Returns `None` if nothing valid survives, so callers can
/// tell "no weekdays configured" apart from "an empty list was configured".
fn parse_weekday_list(value: &serde_json::Value) -> Option<Vec<u32>> {
    let arr = value.as_array()?;
    let mut days: Vec<u32> = arr
        .iter()
        .filter_map(|x| x.as_u64())
        .map(|n| n as u32)
        .filter(|&d| d < 7)
        .collect();
    days.sort_unstable();
    days.dedup();
    if days.is_empty() {
        None
    } else {
        Some(days)
    }
}

fn parse_delivery_weekdays_from_rpc(params: &serde_json::Value) -> Option<Vec<u32>> {
    rpc_field(params, "delivery_weekdays").and_then(parse_weekday_list)
}

fn rpc_str<'a>(params: &'a serde_json::Value, key: &str) -> Option<&'a str> {
    rpc_field(params, key).and_then(|v| v.as_str())
}

fn f64_array(value: &serde_json::Value) -> Vec<f64> {
    value
        .as_array()
        .map(|a| a.iter().filter_map(|x| x.as_f64()).collect())
        .unwrap_or_default()
}

/// Parses shipment temperature traces from an RPC configure request, accepting either the
/// current `shipments: [{times_d, temps_c}, ...]` shape or the older parallel `times`/`temps`
/// outer-array shape, in that order of preference. A shipment needs at least two points in
/// each array to be usable, since a trace with one point can't define an exposure interval.
fn parse_shipments_from_rpc(params: &serde_json::Value) -> Vec<ShipmentTrace> {
    if let Some(arr) = rpc_field(params, "shipments").and_then(|v| v.as_array()) {
        let ships: Vec<ShipmentTrace> = arr
            .iter()
            .filter_map(|item| {
                let times = item.get("times_d")?;
                let temps = item.get("temps_c")?;
                Some(ShipmentTrace {
                    times_d: f64_array(times),
                    temps_c: f64_array(temps),
                })
            })
            .collect();
        if !ships.is_empty() {
            return ships;
        }
    }
    let times_outer = rpc_field(params, "times").and_then(|v| v.as_array());
    let temps_outer = rpc_field(params, "temps").and_then(|v| v.as_array());
    if let (Some(times), Some(temps)) = (times_outer, temps_outer) {
        let ships: Vec<ShipmentTrace> = times
            .iter()
            .zip(temps.iter())
            .map(|(t, m)| ShipmentTrace {
                times_d: f64_array(t),
                temps_c: f64_array(m),
            })
            .filter(|s| s.times_d.len() >= 2 && s.temps_c.len() >= 2)
            .collect();
        if !ships.is_empty() {
            return ships;
        }
    }
    Vec::new()
}

impl EngineSession {
    /// Decodes a JSON `"init"`/`"reset"` configure payload and applies every field it
    /// contains to `self`, filling in defaults for anything omitted. Shipment traces fall
    /// back to a synthetic `mod21_demo_shipments` set keyed by `arrival_product` when the
    /// caller doesn't supply real ones. `eta_ref` and `gamma_shape` each re-derive the
    /// reference life and rebuild `gamma_table` unless the request also carries an explicit
    /// `gamma_scale`, so an explicit scale always wins over the derived one.
    fn apply_rpc_configure(&mut self, params: &serde_json::Value) {
        let lead_time = rpc_u64(params, "lead_time").unwrap_or(1) as u32;
        let enable_filter = rpc_bool(params, "enable_filter").unwrap_or(true);
        let h = rpc_u64(params, "H").unwrap_or(7) as u32;
        let n_paths = rpc_u64(params, "n_rollout_paths").unwrap_or(2) as u32;
        let radius = rpc_i64(params, "candidate_case_radius").unwrap_or(1) as i32;
        let n_particles = rpc_u64(params, "n_particles").unwrap_or(200) as usize;
        let arrival_product = rpc_str(params, "arrival_product").map(str::to_string);
        let mut shipments = parse_shipments_from_rpc(params);
        if shipments.is_empty() {
            if let Some(ref product) = arrival_product {
                shipments = mod21_demo_shipments(product);
            }
        }
        let demand_profile = parse_demand_profile_from_rpc(params);
        let units_per_lot = rpc_u64(params, "units_per_lot").map(|n| n as usize);
        if let Some(source) = rpc_str(params, "belief_source") {
            if let Ok(bs) = BeliefSource::from_rpc_str(source) {
                self.belief_source = bs;
            }
        }
        self.lead_time = lead_time.max(1);
        self.configure(
            self.lead_time,
            enable_filter,
            h,
            n_paths,
            radius,
            shipments,
            n_particles,
            demand_profile,
            units_per_lot,
        );
        if let Some(product) = arrival_product {
            self.arrival_product = product;
            self.params.arrival_product = self.arrival_product.clone();
        }
        if let Some(scale) = rpc_f64(params, "spread_scale") {
            self.spread_scale = scale.clamp(0.05, 1.5);
        }
        if let Some(bias) = rpc_f64(params, "transit_temp_bias_c") {
            self.transit_temp_bias_c = bias.clamp(-2.0, 8.0);
        }
        let delivery = parse_delivery_weekdays_from_rpc(params)
            .unwrap_or_else(|| OrderSchedule::default().delivery_weekday_list());
        self.set_delivery_schedule(&delivery, self.lead_time);
        let _ignored_client_order = rpc_field(params, "order_weekdays");
        if let Some(eta) = rpc_f64(params, "eta_ref") {
            self.params.eta_ref = eta;
            if rpc_f64(params, "gamma_scale").is_none() {
                self.params.set_reference_life();
                self.gamma_table = GammaDecrementTable::for_params(&self.params);
            }
        }
        if let Some(scale) = rpc_f64(params, "gamma_scale") {
            self.params.gamma_scale = scale;
            self.gamma_table = GammaDecrementTable::for_params(&self.params);
        }
        if let Some(shape) = rpc_f64(params, "gamma_shape") {
            self.params.gamma_shape = shape;
            if rpc_f64(params, "gamma_scale").is_none() {
                self.params.set_reference_life();
            }
            self.gamma_table = GammaDecrementTable::for_params(&self.params);
        }
        let mut store_physics_changed = false;
        if let Some(q10) = rpc_f64(params, "q10") {
            self.params.q10 = q10;
            store_physics_changed = true;
        }
        if let Some(t_ref) = rpc_f64(params, "t_ref_c") {
            self.params.t_ref_c = t_ref;
            store_physics_changed = true;
        }
        if let Some(t_store) = rpc_f64(params, "t_store_c") {
            self.params.t_store_c = t_store;
            store_physics_changed = true;
        }
        if store_physics_changed {
            self.gamma_table = GammaDecrementTable::for_params(&self.params);
            self.arrival_model.sync_params(&self.params);
        }
    }
}

/// What changed in one simulated day, returned by `"step"`, `"step_n"`, and `"act"`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DayDelta {
    pub demand: u32,
    pub sales_total: u32,
    pub waste_total: u32,
    pub on_hand: u32,
    pub order_qty: u32,
    pub arrivals: u32,
    pub episode_day: u32,
    /// Every unit that left inventory this day, spoiled or sold, with the freshness it
    /// held at the moment it exited.
    pub unit_exits: Vec<UnitExit>,
}

/// A decoded JSON-RPC request: `method` selects the [`EngineSession`] call in
/// [`handle_rpc`]'s dispatch, `params` carries its arguments (missing entirely if the
/// caller sent none), and `id` is echoed back verbatim in the response.
#[derive(Deserialize)]
struct RpcRequest {
    id: serde_json::Value,
    method: String,
    #[serde(default)]
    params: serde_json::Value,
}

/// The single JSON-RPC entry point both the WASM and PyO3 bindings call into: takes a
/// request as a JSON string and returns a JSON response string, never panicking on bad
/// input. A thread-local [`EngineSession`] holds the simulation state between calls, so a
/// caller's requests on one thread see a consistent running session without threading a
/// handle through the FFI boundary.
///
/// `method` dispatches to the matching `EngineSession` operation: `"init"`/`"reset"` (both
/// aliases for the same handler) seed a fresh session, apply belief-histogram dimensions,
/// run `EngineSession::apply_rpc_configure`, and set the observation channels or scenario
/// from whichever of `obs_channels`/`obs_scenario` (flat or under `config`) was given;
/// `"step"` and `"step_n"` advance the simulation by one or many days under caller-supplied
/// order quantities; `"act"` lets the policy choose the order itself from optional
/// overrides; `"set_obs_scenario"` and `"set_obs_channels"` change what the store can see
/// mid-run; `"tradeoff_forecast"` and `"events"` are read-only queries over the running
/// session. Parse failures, unknown methods, and validation errors from the session all
/// come back as `{"ok": false, "error": {...}}` rather than an `Err`, since this function's
/// contract is "always produce a response string".
pub fn handle_rpc(request_json: &str) -> String {
    let req: RpcRequest = match serde_json::from_str(request_json) {
        Ok(r) => r,
        Err(e) => {
            return format!(
                "{{\"id\":null,\"ok\":false,\"error\":{{\"type\":\"ParseError\",\"message\":{}}}}}",
                serde_json::to_string(&e.to_string()).unwrap()
            );
        }
    };
    use std::cell::RefCell;
    thread_local! {
        static SESSION: RefCell<EngineSession> = RefCell::new(EngineSession::new(0));
    }
    SESSION.with(|s| {
        let mut sess = s.borrow_mut();
        let result = match req.method.as_str() {
            "init" | "reset" => {
                let seed = rpc_u64(&req.params, "seed").unwrap_or(0);
                let l = rpc_u64(&req.params, "L").unwrap_or(DEFAULT_L_DIM as u64) as usize;
                let k = rpc_u64(&req.params, "K").unwrap_or(4) as usize;
                sess.reset(seed);
                sess.set_belief_dims(l, k.max(1));
                sess.apply_rpc_configure(&req.params);
                if let Some(ch) = rpc_field(&req.params, "obs_channels") {
                    if let Ok(channels) = validate_channels_json(ch) {
                        let _ = sess.set_obs_channels(channels);
                    }
                } else if let Some(sc) = rpc_str(&req.params, "obs_scenario") {
                    let _ = sess.set_obs_scenario(sc);
                } else if let Some(cfg) = req.params.get("config") {
                    if let Some(ch) = cfg.get("obs_channels") {
                        if let Ok(channels) = validate_channels_json(ch) {
                            let _ = sess.set_obs_channels(channels);
                        }
                    } else if let Some(sc) = cfg.get("obs_scenario").and_then(|v| v.as_str()) {
                        let _ = sess.set_obs_scenario(sc);
                    }
                }
                sess.snapshot_value()
            }
            "step" => {
                let order = req
                    .params
                    .get("order")
                    .or_else(|| req.params.get("order_qty"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u32;
                let d = sess.step(order);
                sess.day_delta_value(&d)
            }
            "step_n" => {
                let orders: Vec<u32> = req
                    .params
                    .get("orders")
                    .and_then(|v| v.as_array())
                    .map(|a| {
                        a.iter()
                            .filter_map(|x| x.as_u64().map(|n| n as u32))
                            .collect()
                    })
                    .unwrap_or_default();
                sess.crossings += 1;
                let deltas: Vec<serde_json::Value> = orders
                    .iter()
                    .map(|&q| {
                        let d = sess.advance_one(q);
                        sess.day_delta_value(&d)
                    })
                    .collect();
                serde_json::Value::Array(deltas)
            }
            "act" => {
                let policy = req.params.get("policy").and_then(|v| v.as_str());
                let order_qty = req
                    .params
                    .get("order_qty")
                    .or_else(|| req.params.get("q"))
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let alpha = req.params.get("alpha").and_then(|v| v.as_f64());
                let rho = req.params.get("rho").and_then(|v| v.as_f64());
                let h = req
                    .params
                    .get("H")
                    .or_else(|| req.params.get("h"))
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let n_paths = req
                    .params
                    .get("n_rollout_paths")
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let radius = req
                    .params
                    .get("candidate_case_radius")
                    .and_then(|v| v.as_i64())
                    .map(|n| n as i32);
                let d = sess.act(
                    policy,
                    order_qty,
                    alpha,
                    rho,
                    h,
                    n_paths,
                    radius,
                );
                sess.day_delta_value(&d)
            }
            "set_obs_scenario" => {
                let id = req
                    .params
                    .get("obs_scenario")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                match sess.set_obs_scenario(id) {
                    Ok(v) => v,
                    Err(e) => {
                        return format!(
                            "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"ValidationError\",\"message\":{}}}}}",
                            req.id,
                            serde_json::to_string(&e).unwrap()
                        );
                    }
                }
            }
            "set_obs_channels" => {
                let ch = match validate_channels_json(&req.params) {
                    Ok(c) => c,
                    Err(e) => {
                        return format!(
                            "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"ValidationError\",\"message\":{}}}}}",
                            req.id,
                            serde_json::to_string(&e).unwrap()
                        );
                    }
                };
                match sess.set_obs_channels(ch) {
                    Ok(v) => v,
                    Err(e) => {
                        return format!(
                            "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"ValidationError\",\"message\":{}}}}}",
                            req.id,
                            serde_json::to_string(&e).unwrap()
                        );
                    }
                }
            }
            "tradeoff_forecast" => {
                let n_paths = req
                    .params
                    .get("n_paths")
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                let protection_days = req
                    .params
                    .get("protection_days")
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32);
                sess.tradeoff_forecast_value(n_paths, protection_days)
            }
            "events" => {
                let since_day = match req.params.get("since_day").and_then(|v| v.as_u64()) {
                    Some(n) => n as u32,
                    None => {
                        return format!(
                            "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"ValidationError\",\"message\":\"since_day required\"}}}}",
                            req.id
                        );
                    }
                };
                sess.events_value(since_day)
            }
            other => {
                return format!(
                    "{{\"id\":{},\"ok\":false,\"error\":{{\"type\":\"UnknownMethod\",\"message\":{}}}}}",
                    req.id,
                    serde_json::to_string(other).unwrap()
                );
            }
        };
        serde_json::json!({"id": req.id, "ok": true, "result": result}).to_string()
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy::damped_sw_order_f_belief;

    fn t121b_shipment() -> ShipmentTrace {
        ShipmentTrace {
            times_d: vec![0.0, 1.0, 2.0],
            temps_c: vec![1.0, 1.0, 1.0],
        }
    }

    fn warm_t121b_session(seed: u64) -> EngineSession {
        let mut s = EngineSession::new(seed);
        s.init(seed);
        s.set_belief_dims(2, 4);
        // ADR 0136 zero-init: keep filter on so arrivals birth nontrivial belief mass.
        s.configure(1, true, 7, 2, 1, vec![t121b_shipment()], 32, None, None);
        for &q in &[32u32, 0, 32, 0, 32, 0, 32, 0] {
            s.step(q);
        }
        s
    }

    #[test]
    fn step_n_is_one_crossing() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let before = s.host_crossings();
        let _ = s.step_n(&[8, 0, 8]);
        assert_eq!(s.host_crossings(), before + 1);
    }

    #[test]
    fn step_before_init_panics() {
        let mut s = EngineSession::new(1);
        let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            s.step(0);
        }));
        assert!(panicked.is_err());
    }

    #[test]
    fn step_n_empty_orders_returns_empty_sequence() {
        let mut s = EngineSession::new(4);
        s.init(4);
        let deltas = s.step_n(&[]);
        assert!(deltas.is_empty());
    }

    #[test]
    fn step_n_returns_exactly_k() {
        let mut s = EngineSession::new(2);
        s.init(2);
        let orders = [0u32, 8, 0, 16];
        assert_eq!(s.step_n(&orders).len(), 4);
    }

    #[test]
    fn rpc_methods_ok() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        for method in ["step", "step_n", "reset", "act"] {
            let req = format!(
                r#"{{"id":"1","method":"{method}","params":{{"seed":1,"orders":[0,8,0,8,0,8,0],"order":0,"order_qty":0}}}}"#
            );
            let out = handle_rpc(&req);
            assert!(out.contains("\"ok\":true"), "{method}: {out}");
        }
    }

    #[test]
    fn act_rollout_advances_day() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let d = s.act_rollout();
        assert_eq!(d.episode_day, 0);
    }

    #[test]
    fn rpc_init_result_has_flat_belief() {
        let out = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true);
        let belief = &v["result"]["belief"];
        assert!(belief["lot_counts"].is_array(), "{out}");
        assert!(belief["f_marginals"].is_array());
        assert!(belief["f_grid"].is_array());
        assert_eq!(belief["L"], DEFAULT_L_DIM);
        assert_eq!(belief["K"], 4);
        assert_eq!(v["result"]["episode_day"], 0);
        assert_eq!(v["result"]["seq"], 0);
    }

    #[test]
    fn rpc_init_includes_schedule_and_demand_summary() {
        let out = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let schedule = &v["result"]["schedule"];
        assert!(schedule["delivery_weekdays"]
            .as_array()
            .is_some_and(|a| !a.is_empty()));
        assert!(schedule["order_weekdays"]
            .as_array()
            .is_some_and(|a| !a.is_empty()));
        assert_eq!(schedule["epoch"], SCHEDULE_EPOCH);
        let summary = &v["result"]["demand_summary"];
        assert!(summary["scale_mu"].as_f64().is_some_and(|x| x > 0.0));
        assert_eq!(summary["dow_means"].as_array().map(Vec::len), Some(7));
    }

    #[test]
    fn rpc_init_belief_lot_counts_positive_mass() {
        let out = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":1,"config":{"enable_filter":true}}}"#,
        );
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let f_mass: f64 = v["result"]["belief"]["f_marginals"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_f64())
            .sum();
        assert!(
            f_mass > 0.0,
            "filter-enabled init must expose non-zero f marginal mass"
        );
    }

    #[test]
    fn rpc_init_accepts_nested_config_shipments() {
        let out = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":42,"config":{"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[5.0,5.0,5.0]}],"n_particles":64,"H":5,"lead_time":2,"L":2,"K":4,"enable_filter":true,"n_rollout_paths":3,"candidate_case_radius":2,"obs_scenario":"P1"}}}"#,
        );
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let cfg = &v["result"]["applied_config"];
        assert_eq!(cfg["n_particles"], 64);
        assert_eq!(cfg["H"], 5);
        assert_eq!(cfg["lead_time"], 2);
        assert_eq!(cfg["n_rollout_paths"], 3);
        assert_eq!(cfg["candidate_case_radius"], 2);
        assert_eq!(v["result"]["schedule"]["lead_time_days"], 2);
        let warm =
            handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[8,0,0,0,0,0,0,0,0]}}"#);
        let warm_v: serde_json::Value = serde_json::from_str(&warm).unwrap();
        assert_eq!(warm_v["ok"], true, "{warm}");
        let warm_steps = warm_v["result"].as_array().unwrap();
        let f_warm = warm_steps
            .iter()
            .find(|d| d["live_lots"].as_array().is_some_and(|a| !a.is_empty()))
            .and_then(|d| d["live_lots"][0]["mean_f"].as_f64())
            .expect("warm shipment arrival must populate live_lots");
        let smoke = handle_rpc(
            r#"{"id":"3","method":"init","params":{"seed":42,"config":{"lead_time":2,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#,
        );
        assert_eq!(smoke.contains("\"ok\":true"), true);
        let cool =
            handle_rpc(r#"{"id":"4","method":"step_n","params":{"orders":[8,0,0,0,0,0,0,0,0]}}"#);
        let cool_v: serde_json::Value = serde_json::from_str(&cool).unwrap();
        assert_eq!(cool_v["ok"], true, "{cool}");
        let f_cool = cool_v["result"]
            .as_array()
            .unwrap()
            .iter()
            .find(|d| d["live_lots"].as_array().is_some_and(|a| !a.is_empty()))
            .and_then(|d| d["live_lots"][0]["mean_f"].as_f64())
            .expect("smoke shipment arrival must populate live_lots");
        assert!(
            f_warm.is_finite() && f_cool.is_finite(),
            "arrivals must populate live_lots mean_f (warm={f_warm}, cool={f_cool})"
        );
    }

    #[test]
    fn rpc_init_reset_sync_schedule_lead_time() {
        for method in ["init", "reset"] {
            let req = format!(
                r#"{{"id":"1","method":"{method}","params":{{"seed":9,"config":{{"lead_time":4,"shipments":[{{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}}]}}}}}}"#
            );
            let out = handle_rpc(&req);
            let v: serde_json::Value = serde_json::from_str(&out).unwrap();
            assert_eq!(v["ok"], true, "{method}: {out}");
            assert_eq!(v["result"]["applied_config"]["lead_time"], 4);
            assert_eq!(
                v["result"]["schedule"]["lead_time_days"], 4,
                "{method} must sync schedule lead time"
            );
            let expected_order = crate::schedule::derive_order_weekdays(&[0, 2, 4], 4);
            let order: Vec<u32> = v["result"]["schedule"]["order_weekdays"]
                .as_array()
                .unwrap()
                .iter()
                .filter_map(|x| x.as_u64().map(|n| n as u32))
                .collect();
            assert_eq!(order, expected_order, "{method} must re-derive order days");
        }
    }

    #[test]
    fn rpc_configure_custom_delivery_derives_order_weekdays() {
        let req = r#"{"id":"1","method":"init","params":{"seed":1,"config":{"delivery_weekdays":[1,3],"lead_time":2,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#;
        let out = handle_rpc(req);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let delivery: Vec<u32> = v["result"]["schedule"]["delivery_weekdays"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_u64().map(|n| n as u32))
            .collect();
        assert_eq!(delivery, vec![1, 3]);
        let order: Vec<u32> = v["result"]["schedule"]["order_weekdays"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_u64().map(|n| n as u32))
            .collect();
        assert_eq!(order, crate::schedule::derive_order_weekdays(&[1, 3], 2));
        assert_eq!(
            v["result"]["applied_config"]["delivery_weekdays"]
                .as_array()
                .unwrap()
                .len(),
            2
        );
    }

    #[test]
    fn rpc_configure_ignores_client_order_weekdays() {
        let req = r#"{"id":"1","method":"init","params":{"seed":1,"delivery_weekdays":[0,2,4],"order_weekdays":[0,1,2],"lead_time":1,"config":{"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#;
        let out = handle_rpc(req);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let order: Vec<u32> = v["result"]["schedule"]["order_weekdays"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_u64().map(|n| n as u32))
            .collect();
        assert_eq!(order, crate::schedule::derive_order_weekdays(&[0, 2, 4], 1));
    }

    #[test]
    fn rpc_step_live_lots_nonempty_after_arrival() {
        let _ = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":42,"config":{"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#,
        );
        let out =
            handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[0,0,0,0,0,0,8,0]}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let last = v["result"].as_array().unwrap().last().unwrap();
        let lots = last["live_lots"].as_array().expect("live_lots array");
        assert!(
            !lots.is_empty(),
            "arrival after lead_time must surface live_lots"
        );
        assert!(lots[0]["lot_id"].is_number());
        assert!(lots[0]["n"].as_u64().is_some_and(|n| n > 0));
        assert!(lots[0]["mean_f"].is_number());
    }

    #[test]
    fn rpc_step_live_units_wire_after_arrival() {
        let _ = handle_rpc(
            r#"{"id":"1","method":"init","params":{"seed":42,"config":{"lead_time":1,"shipments":[{"times_d":[0.0,1.0,2.0],"temps_c":[1.0,1.0,1.0]}]}}}"#,
        );
        let out =
            handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[0,0,0,0,0,0,8,0]}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        let last = v["result"].as_array().unwrap().last().unwrap();
        let units = last["live_units"].as_array().expect("live_units array");
        assert!(!units.is_empty(), "arrival must surface live_units");
        let n_lots: u64 = last["live_lots"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|l| l["n"].as_u64())
            .sum();
        assert_eq!(
            units.len() as u64,
            n_lots,
            "live_units count must match summed live_lots survivors"
        );
        for u in units {
            assert!(u["unit_id"].is_number());
            assert!(u["lot_id"].is_number());
            assert!(u["f"].is_number());
            assert!(u["f"].as_f64().unwrap_or(0.0) > 0.0);
        }
    }

    #[test]
    fn rpc_step_includes_belief() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let out = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true);
        assert!(v["result"]["belief"]["lot_counts"].is_array(), "{out}");
        assert!(v["result"]["day"]["day"].is_number(), "{out}");
        assert!(v["result"]["drop_oldest"].is_boolean());
    }

    #[test]
    fn rpc_step_n_empty_and_k_match() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let empty = handle_rpc(r#"{"id":"2","method":"step_n","params":{"orders":[]}}"#);
        let v: serde_json::Value = serde_json::from_str(&empty).unwrap();
        assert_eq!(v["ok"], true);
        assert_eq!(v["result"].as_array().map(Vec::len), Some(0));
        let many = handle_rpc(r#"{"id":"3","method":"step_n","params":{"orders":[0,8,0]}}"#);
        let w: serde_json::Value = serde_json::from_str(&many).unwrap();
        assert_eq!(w["result"].as_array().map(Vec::len), Some(3));
        assert!(w["result"][0]["belief"]["lot_counts"].is_array());
    }

    #[test]
    fn rpc_unknown_and_malformed_are_envelopes() {
        let unknown = handle_rpc(r#"{"id":"9","method":"nope","params":{}}"#);
        let u: serde_json::Value = serde_json::from_str(&unknown).unwrap();
        assert_eq!(u["ok"], false);
        assert_eq!(u["error"]["type"], "UnknownMethod");
        let bad = handle_rpc("{not-json");
        let b: serde_json::Value = serde_json::from_str(&bad).unwrap();
        assert_eq!(b["ok"], false);
        assert_eq!(b["error"]["type"], "ParseError");
    }

    #[test]
    fn set_obs_scenario_updates_applied_config_without_reset() {
        let mut live = EngineSession::new(7);
        live.init(7);
        let _ = live.step_n(&[8, 0, 8]);
        let day_before = live.episode_day();
        let snap = live.set_obs_scenario("P0").expect("P0");
        assert_eq!(snap["applied_config"]["obs_scenario"], "P0");
        assert_eq!(live.episode_day(), day_before);
        assert_eq!(snap["episode_day"], day_before);
    }

    #[test]
    fn set_obs_scenario_invalid_id_errors() {
        let mut s = EngineSession::new(1);
        s.init(1);
        assert!(s.set_obs_scenario("P2").is_err());
        assert!(s.set_obs_scenario("B-state").is_err());
    }

    #[test]
    fn set_obs_channels_returns_belief_history_for_episode() {
        let mut s = EngineSession::new(5);
        s.init(5);
        s.set_belief_dims(2, 4);
        let _ = s.step_n(&[8, 0, 8]);
        let snap = s.set_obs_scenario("F2").unwrap();
        let hist = snap["belief_history"]
            .as_array()
            .expect("belief_history array");
        assert_eq!(
            hist.len(),
            3,
            "channel switch must replay beliefs for each simulated day (studio chart)"
        );
        assert_eq!(hist[0]["day"], 0);
        assert_eq!(hist[2]["day"], 2);
        assert!(hist[0]["belief"]["f_marginals"].is_array());
    }

    #[test]
    fn catch_up_matches_never_switched_weights() {
        let mut always = EngineSession::new(11);
        always.init(11);
        always.set_obs_scenario("P0").unwrap();
        let _ = always.step_n(&[8, 0, 8, 0]);
        let w_always = always.bank_weights();

        let mut switched = EngineSession::new(11);
        switched.init(11);
        let _ = switched.step_n(&[8, 0, 8, 0]);
        switched.set_obs_scenario("P0").unwrap();
        let w_switched = switched.bank_weights();
        assert_eq!(w_always, w_switched);
    }

    #[test]
    fn switch_back_is_gap_only() {
        let mut s = EngineSession::new(3);
        s.init(3);
        let _ = s.step_n(&[8, 0, 8]);
        s.set_obs_scenario("F2").unwrap();
        let first = s.catchup_days_last_call();
        assert_eq!(
            first, 3,
            "fresh F2 rung must replay full episode history for chart catch-up"
        );
        let _ = s.step(0);
        s.set_obs_scenario("P1").unwrap();
        let back = s.catchup_days_last_call();
        assert_eq!(back, 1, "switch-back should replay only the unsynced day");
    }

    #[test]
    fn rpc_set_obs_scenario_ok() {
        let _ = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        let _ = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        let out =
            handle_rpc(r#"{"id":"3","method":"set_obs_scenario","params":{"obs_scenario":"F1"}}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["ok"], true, "{out}");
        assert_eq!(v["result"]["applied_config"]["obs_scenario"], "F1");
    }

    #[test]
    fn step_refuses_at_day_90() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let _ = s.step_n(&[0u32; 90]);
        let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            s.step(0);
        }));
        assert!(panicked.is_err());
    }

    #[test]
    fn configure_sets_particle_count() {
        let mut s = EngineSession::new(1);
        s.init(1);
        s.configure(1, true, 7, 2, 1, vec![], 200, None, None);
        assert_eq!(s.n_particles(), 200);
    }

    #[test]
    fn demand_summary_wire_matches_committed_profile() {
        let profile = committed_demand_profile();
        let mut params = ModelParams::default();
        apply_demand_profile(&mut params, profile.clone());
        let wire = demand_summary_wire(&params);
        assert!((wire["scale_mu"].as_f64().unwrap() - profile.scale_target_mu()).abs() <= 1e-9);
        let dow: Vec<f64> = wire["dow_means"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|x| x.as_f64())
            .collect();
        assert_eq!(dow.len(), 7);
        for (got, want) in dow.iter().zip(profile.dow_means()) {
            assert!((got - want).abs() <= 1e-9, "{got} vs {want}");
        }
    }

    #[test]
    fn session_configure_loads_calendar_profile_and_uses_day_in_demand() {
        let mut s = EngineSession::new(0);
        s.init(0);
        s.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let d0 = s.step(0);
        let mut s_dup = EngineSession::new(0);
        s_dup.init(0);
        s_dup.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let d0_dup = s_dup.step(0);
        assert_eq!(
            d0.demand, d0_dup.demand,
            "day-0 demand must be deterministic for fixed seed/config"
        );
        let mut s2 = EngineSession::new(0);
        s2.init(0);
        s2.configure(1, false, 3, 1, 0, vec![], 16, None, None);
        let mut demands = Vec::new();
        for _ in 0..90 {
            let d = s2.step(0);
            demands.push(d.demand);
        }
        let mean: f64 = demands.iter().map(|&d| f64::from(d)).sum::<f64>() / 90.0;
        assert!(
            mean > 20.0 && mean < 40.0,
            "90-day session mean {mean} must fall in [20, 40]"
        );
    }

    fn shannon(p: &[f64]) -> f64 {
        let z: f64 = p.iter().sum();
        if z <= 0.0 {
            return 0.0;
        }
        p.iter()
            .map(|x| {
                let q = *x / z;
                if q > 0.0 {
                    -q * q.ln()
                } else {
                    0.0
                }
            })
            .sum()
    }

    fn json_f64s(v: &serde_json::Value, key: &str) -> Vec<f64> {
        v[key]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .filter_map(|x| x.as_f64())
            .collect()
    }

    fn max_row_entropy(belief: &serde_json::Value) -> f64 {
        let k = belief["K"].as_u64().unwrap_or(0) as usize;
        let l = belief["L"].as_u64().unwrap_or(0) as usize;
        let f_margs = json_f64s(belief, "f_marginals");
        let lot_counts = json_f64s(belief, "lot_counts");
        (0..l)
            .filter(|&i| lot_counts.get(i).copied().unwrap_or(0.0) > 0.0)
            .map(|i| shannon(&f_margs[i * k..(i + 1) * k]))
            .fold(0.0, f64::max)
    }

    fn step_until_arrivals(s: &mut EngineSession, orders: &[u32]) -> u32 {
        let mut arrived = 0u32;
        for &q in orders {
            let d = s.step(q);
            arrived += d.arrivals;
        }
        arrived
    }

    /// AC: F2 vs P0 share live_lots; filter path wired (T-140: marginals may coincide).
    #[test]
    fn f2_belief_differs_from_p0_live_lots_unchanged() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
        let mut f2 = EngineSession::new(42);
        f2.init(42);
        f2.set_obs_scenario("F2").unwrap();
        assert!(step_until_arrivals(&mut f2, &orders) > 0);
        let snap_f2 = f2.snapshot_value();

        let mut p0 = EngineSession::new(42);
        p0.init(42);
        p0.set_obs_scenario("P0").unwrap();
        let _ = p0.step_n(&orders);
        let snap_p0 = p0.snapshot_value();

        assert_eq!(
            snap_f2["live_lots"], snap_p0["live_lots"],
            "physics live_lots must match across rungs"
        );
    }

    /// AC: F2a age mass narrower than P1 (lower entropy).
    #[test]
    fn f2a_age_mass_narrower_than_p1() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0, 8, 0];
        let mut f2a = EngineSession::new(3);
        f2a.init(3);
        f2a.set_obs_scenario("F2a").unwrap();
        let _ = f2a.step_n(&orders);
        let mut p1 = EngineSession::new(3);
        p1.init(3);
        p1.set_obs_scenario("P1").unwrap();
        let _ = p1.step_n(&orders);
        let h_f2a = max_row_entropy(&f2a.snapshot_value()["belief"]);
        let h_p1 = max_row_entropy(&p1.snapshot_value()["belief"]);
        assert!(
            h_f2a <= h_p1 + 1e-9,
            "F2a entropy {h_f2a} should be <= P1 {h_p1}"
        );
    }

    /// AC: after positive waste, P0 vs P1 Snapshot belief (lot_counts or ages) differ.
    #[test]
    fn p0_vs_p1_belief_differs_after_waste() {
        let mut p0 = EngineSession::new(99);
        p0.init(99);
        p0.set_obs_scenario("P0").unwrap();
        let mut p1 = EngineSession::new(99);
        p1.init(99);
        p1.set_obs_scenario("P1").unwrap();
        let mut saw_waste = false;
        for _ in 0..200 {
            let d0 = p0.step(48);
            let d1 = p1.step(48);
            assert_eq!(d0.waste_total, d1.waste_total);
            if d0.waste_total > 0 {
                saw_waste = true;
                break;
            }
        }
        assert!(saw_waste, "fixture must produce waste");
        let b0 = p0.snapshot_value()["belief"].clone();
        let b1 = p1.snapshot_value()["belief"].clone();
        let same_counts = json_f64s(&b0, "lot_counts") == json_f64s(&b1, "lot_counts");
        let same_marginals = json_f64s(&b0, "f_marginals") == json_f64s(&b1, "f_marginals");
        let same_weights = p0.bank_weights() == p1.bank_weights();
        assert!(
            !same_counts || !same_marginals || !same_weights,
            "P0 omits waste LL so posterior must differ from P1"
        );
    }

    /// AC: uneven sales_by → F1 posterior differs from P1.
    #[test]
    fn f1_vs_p1_belief_differs_after_uneven_sales() {
        let orders = [
            32u32, 0, 32, 0, 32, 0, 32, 0, 32, 0, 32, 0, 32, 0, 32, 0, 32, 0, 32, 0,
        ];
        for seed in 1u64..400 {
            let mut f1 = EngineSession::new(seed);
            f1.init(seed);
            f1.set_belief_dims(2, 8);
            f1.set_obs_scenario("F1").unwrap();
            let mut p1 = EngineSession::new(seed);
            p1.init(seed);
            p1.set_belief_dims(2, 8);
            p1.set_obs_scenario("P1").unwrap();
            let mut two_lots = false;
            let mut beliefs_differ = false;
            for &q in &orders {
                let d0 = f1.step(q);
                let d1 = p1.step(q);
                assert_eq!(d0.sales_total, d1.sales_total);
                let n_live = f1.snapshot_value()["live_lots"]
                    .as_array()
                    .map(Vec::len)
                    .unwrap_or(0);
                if n_live >= 2 {
                    two_lots = true;
                }
                let lc = json_f64s(&f1.snapshot_value()["belief"], "lot_counts");
                if two_lots
                    && lc.iter().filter(|&&x| x > 0.0).count() >= 2
                    && d0.sales_total > 0
                    && d0.arrivals == 0
                {
                    let b_f1 = f1.snapshot_value()["belief"].clone();
                    let b_p1 = p1.snapshot_value()["belief"].clone();
                    if json_f64s(&b_f1, "f_marginals") != json_f64s(&b_p1, "f_marginals")
                        || json_f64s(&b_f1, "lot_counts") != json_f64s(&b_p1, "lot_counts")
                    {
                        beliefs_differ = true;
                        break;
                    }
                }
            }
            if two_lots && beliefs_differ {
                assert_eq!(
                    f1.snapshot_value()["live_lots"],
                    p1.snapshot_value()["live_lots"]
                );
                return;
            }
        }
        panic!("fixture must reach two live lots with sales where F1 posterior differs from P1");
    }

    /// T-150 supersedes bc26218: caught-up F2 must differ from never-switching P0.
    #[test]
    fn catch_up_f2_matches_never_switched_and_not_oracle() {
        let orders = [8u32, 0, 8, 0, 8, 0, 8, 0];
        let mut p0_full = EngineSession::new(42);
        p0_full.init(42);
        p0_full.set_belief_dims(4, 8);
        p0_full.set_obs_scenario("P0").unwrap();
        let _ = p0_full.step_n(&orders);
        let m_p0 = json_f64s(&p0_full.snapshot_value()["belief"], "f_marginals");

        let mut switched = EngineSession::new(42);
        switched.init(42);
        switched.set_belief_dims(4, 8);
        switched.set_obs_scenario("P0").unwrap();
        let _ = switched.step_n(&orders[..4]);
        switched.set_obs_scenario("F2").unwrap();
        let _ = switched.step_n(&orders[4..]);
        let m_switch = json_f64s(&switched.snapshot_value()["belief"], "f_marginals");
        assert_ne!(
            m_switch, m_p0,
            "caught-up F2 posterior must not collapse to P0 (T-150 AC2.11)"
        );
        assert!(
            m_switch.iter().any(|&x| x > 0.0),
            "F2 belief must not be oracle-only flat zeros"
        );
    }

    #[test]
    fn set_obs_scenario_rejects_p2_and_b_state() {
        let mut s = EngineSession::new(1);
        s.init(1);
        let p2 = s.set_obs_scenario("P2").unwrap_err();
        assert!(p2.contains("Unknown scenario"), "{p2}");
        let b = s.set_obs_scenario("B-state").unwrap_err();
        assert!(b.contains("bypass") || b.contains("B-state"), "{b}");
    }

    #[test]
    fn act_rollout_uses_belief_not_truth_counts() {
        let s = warm_t121b_session(_SEED);
        let belief = belief_flat_from_unit_bank(&s.bank, s.l_dim, s.k_dim);
        let lot_counts = json_f64s(&belief, "lot_counts");
        let f_marginals = json_f64s(&belief, "f_marginals");
        let f_grid = json_f64s(&belief, "f_grid");
        assert!(
            lot_counts.iter().any(|&x| x > 0.0),
            "fixture must seed nontrivial belief mean"
        );
        let pending_sum: u32 = s.pending.values().copied().sum();
        let f_pipe = 1.0;
        let belief_rollout = {
            let base = damped_sw_order_f_belief(
                &lot_counts,
                &f_marginals,
                &f_grid,
                pending_sum,
                s.day,
                &s.params,
                0.9,
                0.8,
                Some(&s.schedule),
                f_pipe,
            );
            rollout_order(
                &lot_counts,
                &f_marginals,
                &f_grid,
                base,
                &s.params,
                &s.pending,
                &RolloutContext {
                    root_seed: s.seed,
                    run_id: format!("session-d{}", s.day),
                    day0: s.day,
                    lead_time: s.lead_time,
                    schedule: s.schedule.clone(),
                    alpha: 0.9,
                    rho: 0.8,
                    costs: RolloutCosts::default(),
                    shipments: s.shipments.clone(),
                    f_pipeline_default: f_pipe,
                    h: s.h,
                    n_paths: s.n_paths,
                    radius: s.radius,
                },
            )
            .unwrap_or(base)
        };
        let mut live = warm_t121b_session(_SEED);
        let d = live.act(Some("rollout"), None, None, None, None, None, None);
        assert_eq!(d.order_qty, belief_rollout);
    }

    #[test]
    fn act_damped_sw_differs_from_rollout_when_belief_nontrivial() {
        for seed in 1u64..=8 {
            let sw = warm_t121b_session(seed)
                .act(Some("damped_sw"), None, None, None, None, None, None)
                .order_qty;
            let roll = warm_t121b_session(seed)
                .act(Some("rollout"), None, None, None, None, None, None)
                .order_qty;
            if sw != roll {
                return;
            }
        }
        panic!("no seed in 1..=8 separates damped_sw from rollout with nontrivial belief");
    }

    #[test]
    fn act_alpha_budget_changes_damped_sw_order() {
        let mut low = warm_t121b_session(17);
        let q_low = low
            .act(Some("damped_sw"), None, Some(0.5), None, None, None, None)
            .order_qty;

        let mut high = warm_t121b_session(17);
        let q_high = high
            .act(Some("damped_sw"), None, Some(0.99), None, None, None, None)
            .order_qty;

        assert!(
            q_high >= q_low,
            "higher alpha should not reduce damped_sw order"
        );
    }

    #[test]
    fn apply_rpc_configure_parses_belief_source_truth() {
        let mut s = EngineSession::new(0);
        s.init(0);
        s.apply_rpc_configure(&serde_json::json!({
            "belief_source": "truth",
            "enable_filter": false,
        }));
        let snap = s.snapshot_value();
        assert_eq!(snap["applied_config"]["belief_source"], "truth");
        assert_eq!(snap["applied_config"]["enable_filter"], false);
    }

    #[test]
    fn truth_belief_source_skips_filter_updates() {
        let mut s = EngineSession::new(7);
        s.init(7);
        s.set_belief_source(BeliefSource::Truth);
        s.enable_filter = false;
        let w0 = s.bank_weights();
        for _ in 0..40 {
            s.step(32);
        }
        assert_eq!(s.bank_weights(), w0, "truth mode must not mutate particle bank");
        let belief = s.snapshot_value()["belief"].clone();
        let live = s.snapshot_value()["live_lots"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let live_n: f64 = live
            .iter()
            .filter_map(|lot| lot.get("n").and_then(|v| v.as_f64()))
            .sum();
        let belief_n: f64 = json_f64s(&belief, "lot_counts").iter().sum();
        assert!(
            (live_n - belief_n).abs() < 1e-9,
            "truth snapshot belief must match live lot counts"
        );
    }

    const _SEED: u64 = 99;
}
