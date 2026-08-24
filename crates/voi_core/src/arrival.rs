//! Hierarchical arrival freshness model in f-space (ADR 0144 / T-150).

use std::collections::HashMap;
use std::fmt;

use rand::Rng;
use rand_distr::{Distribution, Gamma, LogNormal, Normal};
use serde::Deserialize;

use crate::params::ModelParams;
use crate::physics::{gamma_p, gamma_q, store_temp_factor};

const EMBEDDED_ARRIVAL_JSON: &str = include_str!("../../../data/abdella/arrival_model.json");
const SUPPORTED_SCHEMA_VERSION: u64 = 1;
/// Smallest cumulative exposure Λ ever used in a gamma-shape calculation, so a
/// zero-duration or zero-temperature-factor delivery doesn't collapse the shape to zero.
const LAMBDA_FLOOR: f64 = 1e-12;
/// Resolution of the cached filter CDFs (`ArrivalCdfCache`) and inverse-sampling grid.
const ARRIVAL_GRID: usize = 4096;

/// CRN stream tag for the truth-path transit-duration draw.
pub const STREAM_ARRIVAL_DURATION: &str = ":arrival_duration";
/// CRN stream tag for the truth-path mean-transit-temperature draw.
pub const STREAM_ARRIVAL_TEMP: &str = ":arrival_temp";
/// CRN stream tag for the truth-path within-pallet position draw.
pub const STREAM_ARRIVAL_POS: &str = ":arrival_pos";
/// CRN stream tag for the truth-path per-unit freshness-loss gamma draw.
pub const STREAM_ARRIVAL_GAMMA: &str = ":arrival_gamma";

/// Mutually exclusive channel conditioning for filter-side arrival laws.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ArrivalCondition {
    /// F3: exact cumulative exposure Λ from the observed temperature trace.
    Exposure(f64),
    /// F2 / F2a: pack date as calendar duration in days.
    Duration(i32),
    /// P0 / P1: corridor prior only.
    Prior,
}

/// Failure modes for loading and validating an arrival model artifact.
#[derive(Debug)]
pub enum ArrivalModelError {
    /// The artifact JSON did not parse.
    Json(serde_json::Error),
    /// The artifact parsed but failed a structural check (e.g. mismatched quadrature
    /// node/weight lengths, or no corridors).
    Invalid(String),
    /// The artifact's `schema_version` isn't one this build of `voi_core` understands.
    UnknownSchemaVersion(u64),
}

impl fmt::Display for ArrivalModelError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Json(err) => write!(f, "{err}"),
            Self::Invalid(msg) => f.write_str(msg),
            Self::UnknownSchemaVersion(v) => write!(f, "unknown arrival schema version {v}"),
        }
    }
}

impl std::error::Error for ArrivalModelError {}

/// One truth-path delivery: a single duration/temperature draw shared by every unit in
/// the lot, plus one independent within-pallet position (and hence arrival freshness)
/// draw per unit.
#[derive(Clone, Debug)]
pub struct TruthDeliveryDraw {
    /// Arrival freshness for each unit in the delivery, one draw per unit.
    pub unit_f: Vec<f64>,
    /// Rounded transit duration, in days, as it would appear on a pack date label.
    pub pack_date_days: i32,
    /// Exact (unrounded) transit duration in days.
    pub duration_d: f64,
    /// Sampled mean transit temperature in Celsius for this delivery.
    pub t_bar: f64,
    /// Duration-averaged Q10 temperature factor implied by `t_bar`.
    pub phi_bar: f64,
}

/// A shipping lane's transit-duration prior: delivery duration is `d_min` plus a
/// shifted-gamma delay.
#[derive(Clone, Debug)]
pub struct ArrivalCorridor {
    /// Minimum possible transit duration in days (the delay distribution's shift).
    pub d_min: f64,
    /// Shape parameter of the gamma delay-beyond-`d_min` distribution.
    pub delay_shape: f64,
    /// Scale parameter of the gamma delay-beyond-`d_min` distribution.
    pub delay_scale: f64,
}

/// The cold-chain arrival model: truth-path draw parameters (duration corridor, transit
/// temperature, within-pallet position, freshness-loss gamma) plus the filter-side
/// channel-conditional laws and their caches, all fit from the committed Abdella arrival
/// artifact.
#[derive(Clone, Debug)]
pub struct ArrivalModel {
    /// Schema version of the artifact this model was built from; validated against
    /// `SUPPORTED_SCHEMA_VERSION` at load time.
    pub schema_version: u64,
    /// Shipping-lane transit-duration priors, keyed by corridor name.
    pub corridors: HashMap<String, ArrivalCorridor>,
    /// Corridor key used when a caller doesn't specify one; `"abdella_all"` if present in
    /// the artifact, otherwise an arbitrary corridor from it.
    pub default_corridor: String,
    /// Mean of the (pre-truncation) mean-transit-temperature normal distribution, in
    /// Celsius.
    pub mu_t: f64,
    /// Standard deviation of the mean-transit-temperature normal distribution.
    pub sigma_t: f64,
    /// Lower truncation bound for mean transit temperature; draws below this are rejected.
    pub temp_floor_c: f64,
    /// Standard deviation (in log-space) of the log-normal within-pallet position
    /// multiplier ψ.
    pub sigma_pos: f64,
    /// Q10 temperature coefficient: the multiplicative change in the Arrhenius rate per
    /// 10°C.
    pub q10: f64,
    /// Reference temperature, in Celsius, at which the Q10 factor is 1.
    pub t_ref: f64,
    /// Shape multiplier `k` of the per-unit freshness-loss gamma distribution;
    /// exposure-scaled shape is `k * Λ`.
    pub gamma_shape: f64,
    /// Scale `θ` of the per-unit freshness-loss gamma distribution.
    pub gamma_scale: f64,
    /// Reference shelf life in days used to calibrate the freshness-loss rate.
    pub reference_life_days: f64,
    /// Quadrature nodes on `[0, 1]`, shared across duration, temperature, and position
    /// integration.
    pub quad_nodes: Vec<f64>,
    /// Quadrature weights matching `quad_nodes`.
    pub quad_weights: Vec<f64>,
    /// Corridor the filter prior (`marginal_cdf`) and F2/F3 caches are currently built
    /// against (T-150 finding 4). Defaults to `default_corridor`; callers with a
    /// configured `arrival_product` must call `set_corridor` so the filter prior matches
    /// the truth path instead of silently staying on `abdella_all`.
    active_corridor: String,
    /// Cached, atom-divided CDF for the `Prior` (P0/P1) channel law, rebuilt whenever
    /// `active_corridor` or the physics parameters change.
    marginal_cdf: ArrivalCdfCache,
    /// Cached `Duration` (F2/F2a) channel laws, keyed by pack-date days.
    f2_cache: HashMap<i32, ArrivalCdfCache>,
    /// Cached `Exposure` (F3) channel laws, keyed by a fixed-point-rounded Λ so
    /// near-identical exposures share a cache entry.
    f3_cache: HashMap<u64, ArrivalCdfCache>,
    /// Most recent `Duration` days the filter actually conditioned on via `law_cdf`
    /// (T-150: the wire adapter reads this instead of re-deriving a pack date, so the
    /// F2 chart tracks the same observation the filter used).
    last_duration_days: Option<i32>,
    /// Most recent `Exposure` Λ the filter actually conditioned on via `law_cdf`
    /// (ADR 0144 Correction 1 / T-150: the wire adapter reads this so the F3 chart
    /// conditions on the observed shipment, never a prior-mean placeholder).
    last_exposure_lambda: Option<f64>,
    /// Fingerprint of the last `marginal_cdf` build (T-150 sync-cache dirty-check).
    prior_build_key: PriorCdfBuildKey,
}

/// Filter-side channel-conditional law, cached on the fixed `ARRIVAL_GRID` grid. Unlike
/// `ArrivalRungLaw`, `cdf` here has the `f = 0` atom divided out (it is conditional on
/// `f > 0`) so `sample_unit_f_from_cache` can invert it directly for the continuous part
/// of the draw.
#[derive(Clone, Debug)]
struct ArrivalCdfCache {
    cdf: Vec<f64>,
    atom_f0: f64,
    mean_f: f64,
    variance_f: f64,
}

/// Physics + corridor fingerprint for the cached filter prior (`marginal_cdf`).
/// When `sync_params` sees a matching key, it skips rebuilding the prior and
/// clearing F2/F3 caches (T-150 sync-cache).
#[derive(Clone, Debug, PartialEq)]
struct PriorCdfBuildKey {
    gamma_shape: f64,
    gamma_scale: f64,
    q10: f64,
    t_ref: f64,
    eta_ref: f64,
    active_corridor: String,
}

impl PriorCdfBuildKey {
    fn from_model(model: &ArrivalModel) -> Self {
        Self {
            gamma_shape: model.gamma_shape,
            gamma_scale: model.gamma_scale,
            q10: model.q10,
            t_ref: model.t_ref,
            eta_ref: model.reference_life_days,
            active_corridor: model.active_corridor.clone(),
        }
    }

    fn from_params(params: &ModelParams, active_corridor: &str) -> Self {
        Self {
            gamma_shape: params.gamma_shape,
            gamma_scale: params.gamma_scale,
            q10: params.q10,
            t_ref: params.t_ref_c,
            eta_ref: params.eta_ref,
            active_corridor: active_corridor.to_string(),
        }
    }
}

/// Chart-ready channel-conditional law (T-150 AC3.3): the raw CDF (atom mass included,
/// unlike the filter's atom-divided `ArrivalCdfCache`) on an explicit grid, plus the
/// atom and the atom-inclusive mean/sd. Computed against an explicit corridor rather
/// than the model's mutable `active_corridor`, and at whatever resolution the caller
/// needs — a chart does not need the filter's 4096-point grid. Uses the same per-point
/// integration (`marginal_cdf_at`) the filter's `build_law_cdf` uses, so a wire adapter
/// built on this can never numerically diverge from the filter.
#[derive(Clone, Debug)]
pub struct ArrivalRungLaw {
    /// `P(f <= x)` on a uniform grid over `[0, 1]`, index `i` corresponding to
    /// `x = i / (len - 1)`; includes the `f = 0` atom mass.
    pub cdf: Vec<f64>,
    /// `P(f = 0)`, the point mass at total spoilage.
    pub atom_f0: f64,
    /// `E[f]` including the `f = 0` atom.
    pub mean_f: f64,
    /// `sd[f]` including the `f = 0` atom.
    pub sd_f: f64,
}

#[derive(Deserialize)]
struct ArrivalModelJson {
    schema_version: u64,
    mu_T: f64,
    sigma_T: f64,
    #[serde(default)]
    temp_floor_c: f64,
    sigma_pos: f64,
    q10: f64,
    T_ref: f64,
    gamma_shape: f64,
    gamma_scale: f64,
    reference_life_days: f64,
    quadrature: QuadratureJson,
    corridors: HashMap<String, CorridorJson>,
}

#[derive(Deserialize)]
struct QuadratureJson {
    nodes: Vec<f64>,
    weights: Vec<f64>,
}

#[derive(Deserialize)]
struct CorridorJson {
    d_min: f64,
    delay_shape: f64,
    delay_scale: f64,
}

/// Single embed accessor for the committed arrival artifact.
pub fn embedded_arrival_model() -> &'static str {
    EMBEDDED_ARRIVAL_JSON
}

/// Parse an arrival model artifact from a JSON string (e.g. an uploaded or overridden
/// artifact rather than the embedded default).
pub fn arrival_artifact_from_json(json: &str) -> Result<ArrivalModel, ArrivalModelError> {
    ArrivalModel::from_json(json)
}

/// Standard normal CDF, via the `erf` approximation below.
fn normal_cdf(z: f64) -> f64 {
    0.5 * (1.0 + erf(z / std::f64::consts::SQRT_2))
}

/// Abramowitz & Stegun 7.1.26 rational approximation to the error function (max error
/// ~1.5e-7); good enough for the truncated-normal transit-temperature draw without
/// pulling in a special-functions dependency.
fn erf(x: f64) -> f64 {
    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let x = x.abs();
    let t = 1.0 / (1.0 + 0.3275911 * x);
    let y = 1.0
        - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
            + 0.254829592)
            * t
            * (-x * x).exp();
    sign * y
}

/// Acklam's rational approximation to the standard normal inverse CDF. Used to map
/// quadrature nodes `u ∈ [0, 1]` to draws from the (truncated) normal transit-temperature
/// distribution without needing a root-finder.
fn normal_quantile(u: f64) -> f64 {
    let u = u.clamp(1e-12, 1.0 - 1e-12);
    const A1: f64 = -39.69683028665376;
    const A2: f64 = 220.9460984245205;
    const A3: f64 = -275.9285104469687;
    const A4: f64 = 138.3577518672690;
    const A5: f64 = -30.66479806614719;
    const A6: f64 = 2.506628277459239;
    const B1: f64 = -54.47609879822406;
    const B2: f64 = 161.5858368580409;
    const B3: f64 = -155.6989798598866;
    const B4: f64 = 66.80101284829912;
    const B5: f64 = -13.28068155288572;
    const C1: f64 = -0.007784894002430293;
    const C2: f64 = -0.3223964580401361;
    const C3: f64 = -2.400758227161338;
    const C4: f64 = -2.549732539343734;
    const C5: f64 = 4.374664141464968;
    const C6: f64 = 2.938163982698783;
    const D1: f64 = 0.007784695709041462;
    const D2: f64 = 0.3224671290700398;
    const D3: f64 = 2.445134137142996;
    const D4: f64 = 3.754408661907416;
    const P_LOW: f64 = 0.02425;
    const P_HIGH: f64 = 1.0 - P_LOW;
    if u < P_LOW {
        let q = (-2.0 * u.ln()).sqrt();
        (((((C1 * q + C2) * q + C3) * q + C4) * q + C5) * q + C6)
            / ((((D1 * q + D2) * q + D3) * q + D4) * q + 1.0)
    } else if u > P_HIGH {
        let q = (-2.0 * (1.0 - u).ln()).sqrt();
        -(((((C1 * q + C2) * q + C3) * q + C4) * q + C5) * q + C6)
            / ((((D1 * q + D2) * q + D3) * q + D4) * q + 1.0)
    } else {
        let q = u - 0.5;
        let r = q * q;
        (((((A1 * r + A2) * r + A3) * r + A4) * r + A5) * r + A6) * q
            / (((((B1 * r + B2) * r + B3) * r + B4) * r + B5) * r + 1.0)
    }
}

/// Inverse gamma CDF via bracket-and-bisect on the regularized incomplete gamma function
/// (`gamma_p`): doubles an upper bound until it brackets `u`, then bisects to convergence.
/// There is no closed form for the gamma quantile, so this is the standard fallback, used
/// wherever a quadrature node needs to become a delay-beyond-`d_min` draw.
fn gamma_dist_quantile(shape: f64, scale: f64, u: f64) -> f64 {
    let u = u.clamp(1e-12, 1.0 - 1e-12);
    if u <= 0.0 {
        return 0.0;
    }
    let mean = shape * scale;
    let mut hi = mean.max(1e-12) * 4.0;
    while gamma_p(shape, hi / scale) < u && hi < 1e12 {
        hi *= 2.0;
    }
    let mut lo = 0.0;
    for _ in 0..80 {
        let mid = 0.5 * (lo + hi);
        if gamma_p(shape, mid / scale) < u {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}

impl ArrivalModel {
    /// Build the model from the artifact committed into the binary. Panics if that
    /// artifact is malformed, which would indicate a build-time packaging bug rather than
    /// anything a caller can recover from.
    pub fn embedded() -> Self {
        Self::from_json(EMBEDDED_ARRIVAL_JSON).expect("embedded arrival artifact")
    }

    /// Parse and validate an arrival model artifact, then build the filter prior
    /// (`marginal_cdf`) against `default_corridor` so the model is immediately usable.
    pub fn from_json(json: &str) -> Result<Self, ArrivalModelError> {
        let raw: ArrivalModelJson = serde_json::from_str(json).map_err(ArrivalModelError::Json)?;
        if raw.schema_version != SUPPORTED_SCHEMA_VERSION {
            return Err(ArrivalModelError::UnknownSchemaVersion(raw.schema_version));
        }
        if raw.quadrature.nodes.len() != raw.quadrature.weights.len()
            || raw.quadrature.nodes.is_empty()
        {
            return Err(ArrivalModelError::Invalid(
                "quadrature nodes and weights must match and be non-empty".into(),
            ));
        }
        if raw.corridors.is_empty() {
            return Err(ArrivalModelError::Invalid(
                "corridors must be non-empty".into(),
            ));
        }
        let default_corridor = if raw.corridors.contains_key("abdella_all") {
            "abdella_all".to_string()
        } else {
            raw.corridors.keys().next().cloned().unwrap_or_default()
        };
        let corridors = raw
            .corridors
            .into_iter()
            .map(|(k, c)| {
                (
                    k,
                    ArrivalCorridor {
                        d_min: c.d_min,
                        delay_shape: c.delay_shape,
                        delay_scale: c.delay_scale,
                    },
                )
            })
            .collect();
        let mut model = Self {
            schema_version: raw.schema_version,
            corridors,
            default_corridor: default_corridor.clone(),
            mu_t: raw.mu_T,
            sigma_t: raw.sigma_T,
            temp_floor_c: raw.temp_floor_c,
            sigma_pos: raw.sigma_pos,
            q10: raw.q10,
            t_ref: raw.T_ref,
            gamma_shape: raw.gamma_shape,
            gamma_scale: raw.gamma_scale,
            reference_life_days: raw.reference_life_days,
            quad_nodes: raw.quadrature.nodes,
            quad_weights: raw.quadrature.weights,
            active_corridor: default_corridor.clone(),
            marginal_cdf: ArrivalCdfCache::empty(),
            f2_cache: HashMap::new(),
            f3_cache: HashMap::new(),
            last_duration_days: None,
            last_exposure_lambda: None,
            prior_build_key: PriorCdfBuildKey {
                gamma_shape: raw.gamma_shape,
                gamma_scale: raw.gamma_scale,
                q10: raw.q10,
                t_ref: raw.T_ref,
                eta_ref: raw.reference_life_days,
                active_corridor: default_corridor.clone(),
            },
        };
        model.marginal_cdf = model.build_law_cdf(ArrivalCondition::Prior);
        model.prior_build_key = PriorCdfBuildKey::from_model(&model);
        Ok(model)
    }

    /// Look up a corridor by key, falling back to `default_corridor` for an unrecognized
    /// key rather than failing.
    pub fn corridor(&self, product: &str) -> &ArrivalCorridor {
        self.corridors
            .get(product)
            .or_else(|| self.corridors.get(&self.default_corridor))
            .expect("arrival corridor")
    }

    /// Duration-averaged Q10 temperature factor φ̄ for a given mean transit temperature.
    pub fn phi_bar_from_t_bar(&self, t_bar: f64) -> f64 {
        store_temp_factor(t_bar, self.t_ref, self.q10)
    }

    /// Clamp cumulative exposure Λ away from zero so it never collapses the gamma shape
    /// (`gamma_shape * Λ`) to zero in downstream calculations.
    pub fn floor_lambda(lambda: f64) -> f64 {
        lambda.max(LAMBDA_FLOOR)
    }

    /// Map a quadrature node `u ∈ [0, 1]` to a duration day from the shifted-gamma law.
    pub fn quadrature_duration_days(&self, corridor: &ArrivalCorridor, u: f64) -> f64 {
        let delay = gamma_dist_quantile(corridor.delay_shape, corridor.delay_scale, u);
        corridor.d_min + delay
    }

    /// Map a quadrature node `u ∈ [0, 1]` to a truncated-normal mean transit temperature.
    pub fn quadrature_t_bar_c(&self, u: f64) -> f64 {
        self.truncated_normal_quantile(u)
    }

    /// Inverse CDF of the mean-transit-temperature distribution, truncated below at
    /// `temp_floor_c`. Rescales `u` into the CDF mass above the truncation point (`alpha`)
    /// before inverting, so a uniform `u ∈ [0, 1]` maps onto the truncated distribution
    /// rather than the unbounded one.
    fn truncated_normal_quantile(&self, u: f64) -> f64 {
        let u = u.clamp(1e-12, 1.0 - 1e-12);
        let alpha = normal_cdf((self.temp_floor_c - self.mu_t) / self.sigma_t);
        let target = alpha + u * (1.0 - alpha);
        let z = normal_quantile(target);
        (self.mu_t + self.sigma_t * z).max(self.temp_floor_c)
    }

    /// Inverse CDF of the log-normal within-pallet position multiplier ψ.
    fn psi_pos_quantile(&self, u: f64) -> f64 {
        let u = u.clamp(1e-12, 1.0 - 1e-12);
        let z = normal_quantile(u);
        (z * self.sigma_pos).exp().max(1e-6)
    }

    /// `P(f > x | Λ)` using shape-scaled gamma loss.
    pub fn p_f_gt_at(&self, lambda: f64, x: f64) -> f64 {
        let lam = Self::floor_lambda(lambda);
        if x >= 1.0 {
            return 0.0;
        }
        gamma_p(
            self.gamma_shape * lam,
            (1.0 - x).max(0.0) / self.gamma_scale,
        )
    }

    /// `P(f <= x | Λ)` using shape-scaled gamma loss, including the `f = 0` atom.
    pub fn cdf_f_given_lambda(&self, lambda: f64, f: f64) -> f64 {
        let lam = Self::floor_lambda(lambda);
        if f <= 0.0 {
            return self.p_f_zero(lam);
        }
        if f >= 1.0 {
            return 1.0;
        }
        gamma_q(
            self.gamma_shape * lam,
            (1.0 - f).max(0.0) / self.gamma_scale,
        )
    }

    /// Exact atom `P(f = 0 | Λ) = gamma_q(kΛ, 1/θ)` — never grid mass.
    pub fn p_f_zero(&self, lambda: f64) -> f64 {
        let lam = Self::floor_lambda(lambda);
        gamma_q(self.gamma_shape * lam, 1.0 / self.gamma_scale)
    }

    fn sample_truncated_normal<R: Rng + ?Sized>(&self, rng: &mut R) -> f64 {
        let dist = Normal::new(self.mu_t, self.sigma_t).expect("trunc normal");
        for _ in 0..64 {
            let t = dist.sample(rng);
            if t >= self.temp_floor_c {
                return t;
            }
        }
        self.temp_floor_c
    }

    fn draw_psi_pos<R: Rng + ?Sized>(&self, rng: &mut R) -> f64 {
        let dist = LogNormal::new(0.0, self.sigma_pos).expect("lognormal pos");
        dist.sample(rng).max(1e-6)
    }

    /// Truth-path per-unit arrival freshness (one draw per unit).
    pub fn draw_unit_f<R: Rng + ?Sized>(
        &self,
        corridor_key: &str,
        rng_duration: &mut R,
        rng_temp: &mut R,
        rng_pos: &mut R,
        rng_gamma: &mut R,
    ) -> f64 {
        let corridor = self.corridor(corridor_key);
        let delay = Gamma::new(corridor.delay_shape, corridor.delay_scale)
            .expect("delay gamma")
            .sample(rng_duration);
        let d = corridor.d_min + delay;
        let t_bar = self.sample_truncated_normal(rng_temp);
        let phi_bar = self.phi_bar_from_t_bar(t_bar);
        let psi_pos = self.draw_psi_pos(rng_pos);
        let lambda = Self::floor_lambda(d * phi_bar * psi_pos);
        let loss = Gamma::new(self.gamma_shape * lambda, self.gamma_scale)
            .expect("loss gamma")
            .sample(rng_gamma);
        (1.0 - loss).max(0.0)
    }

    /// Truth-path per-delivery draw: one duration and mean-transit-temperature draw
    /// shared by the whole lot, plus an independent within-pallet position (and hence
    /// arrival freshness) draw for each of the `n` units.
    pub fn draw_truth_delivery<R: Rng + ?Sized>(
        &self,
        corridor_key: &str,
        n: usize,
        rng_duration: &mut R,
        rng_temp: &mut R,
        rng_pos: &mut R,
        rng_gamma: &mut R,
    ) -> TruthDeliveryDraw {
        let corridor = self.corridor(corridor_key);
        let delay = Gamma::new(corridor.delay_shape, corridor.delay_scale)
            .expect("delay gamma")
            .sample(rng_duration);
        let duration_d = corridor.d_min + delay;
        let t_bar = self.sample_truncated_normal(rng_temp);
        let phi_bar = self.phi_bar_from_t_bar(t_bar);
        let pack_date_days = duration_d.round() as i32;
        let unit_f = (0..n)
            .map(|_| {
                let psi_pos = self.draw_psi_pos(rng_pos);
                let lambda = Self::floor_lambda(duration_d * phi_bar * psi_pos);
                let loss = Gamma::new(self.gamma_shape * lambda, self.gamma_scale)
                    .expect("loss gamma")
                    .sample(rng_gamma);
                (1.0 - loss).max(0.0)
            })
            .collect();
        TruthDeliveryDraw {
            unit_f,
            pack_date_days,
            duration_d,
            t_bar,
            phi_bar,
        }
    }

    /// `P(f <= x)` at a single point, marginalized by product Gauss quadrature over
    /// whichever latent variables `condition` leaves unpinned: `Prior` integrates over
    /// duration, temperature, and position; `Duration` (pack date known) integrates over
    /// temperature and position only; `Exposure` (Λ known exactly) integrates over
    /// position only. Each combination of quadrature nodes yields one conditional Λ and
    /// hence one closed-form `cdf_f_given_lambda`, which are then weighted and averaged —
    /// this is the numerical core every channel-conditional law in the file is built from.
    fn marginal_cdf_at(&self, condition: ArrivalCondition, corridor_key: &str, f: f64) -> f64 {
        let corridor = self.corridor(corridor_key);
        let mut acc = 0.0;
        let mut w_sum = 0.0;

        match condition {
            ArrivalCondition::Exposure(lot_lambda) => {
                let lot_lambda = Self::floor_lambda(lot_lambda);
                for (&u_psi, &w_psi) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                    let psi = self.psi_pos_quantile(u_psi);
                    let lambda = Self::floor_lambda(lot_lambda * psi);
                    acc += w_psi * self.cdf_f_given_lambda(lambda, f);
                    w_sum += w_psi;
                }
            }
            ArrivalCondition::Duration(d_days) => {
                let d = f64::from(d_days).max(0.0);
                for (&u_t, &w_t) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                    let t_bar = self.truncated_normal_quantile(u_t);
                    let phi = self.phi_bar_from_t_bar(t_bar);
                    let lot_lambda = Self::floor_lambda(d * phi);
                    for (&u_psi, &w_psi) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                        let psi = self.psi_pos_quantile(u_psi);
                        let lambda = Self::floor_lambda(lot_lambda * psi);
                        let w = w_t * w_psi;
                        acc += w * self.cdf_f_given_lambda(lambda, f);
                        w_sum += w;
                    }
                }
            }
            ArrivalCondition::Prior => {
                for (&u_d, &w_d) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                    let d = self.quadrature_duration_days(corridor, u_d);
                    for (&u_t, &w_t) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                        let t_bar = self.truncated_normal_quantile(u_t);
                        let phi = self.phi_bar_from_t_bar(t_bar);
                        let lot_lambda = Self::floor_lambda(d * phi);
                        for (&u_psi, &w_psi) in self.quad_nodes.iter().zip(self.quad_weights.iter())
                        {
                            let psi = self.psi_pos_quantile(u_psi);
                            let lambda = Self::floor_lambda(lot_lambda * psi);
                            let w = w_d * w_t * w_psi;
                            acc += w * self.cdf_f_given_lambda(lambda, f);
                            w_sum += w;
                        }
                    }
                }
            }
        }

        if w_sum > 0.0 {
            acc / w_sum
        } else {
            0.0
        }
    }

    /// Channel-conditional law on an explicit `[0, 1]` grid against an explicit corridor
    /// (T-150 AC3.3). The only public, on-demand entry point for the raw (atom-inclusive)
    /// CDF; `build_law_cdf` below is the filter's cached, atom-divided wrapper around it,
    /// and `arrival_wire.rs` calls it directly so the studio chart can never diverge from
    /// the filter's own integration.
    pub fn rung_law_on_grid(
        &self,
        condition: ArrivalCondition,
        corridor_key: &str,
        grid_len: usize,
    ) -> ArrivalRungLaw {
        let grid_len = grid_len.max(2);
        let mut cdf = vec![0.0; grid_len];
        for (gi, slot) in cdf.iter_mut().enumerate() {
            let f = gi as f64 / (grid_len - 1) as f64;
            *slot = self.marginal_cdf_at(condition, corridor_key, f).clamp(0.0, 1.0);
        }

        let atom_f0 = self
            .marginal_cdf_at(condition, corridor_key, 0.0)
            .clamp(0.0, 1.0);

        let mut mean_acc = 0.0;
        let mut mean_sq_acc = 0.0;
        let mut mass_acc = 0.0;
        for gi in 1..grid_len {
            let f = gi as f64 / (grid_len - 1) as f64;
            let f_prev = (gi - 1) as f64 / (grid_len - 1) as f64;
            let p_hi = cdf[gi];
            let p_lo = if gi == 1 { atom_f0 } else { cdf[gi - 1] };
            let bin_mass = (p_hi - p_lo).max(0.0);
            let f_mid = 0.5 * (f + f_prev);
            mean_acc += f_mid * bin_mass;
            mean_sq_acc += f_mid * f_mid * bin_mass;
            mass_acc += bin_mass;
        }
        mass_acc += atom_f0;

        let mean_f = if mass_acc > 0.0 {
            mean_acc / mass_acc
        } else {
            0.0
        };
        let variance_f = if mass_acc > 0.0 {
            (mean_sq_acc / mass_acc - mean_f * mean_f).max(0.0)
        } else {
            0.0
        };

        ArrivalRungLaw {
            cdf,
            atom_f0,
            mean_f,
            sd_f: variance_f.sqrt(),
        }
    }

    /// Build the filter's cached law for a channel condition, against `active_corridor`
    /// and at the fixed `ARRIVAL_GRID` resolution. Divides the atom mass out of the CDF
    /// (rescaling onto `[0, 1]` conditional on `f > 0`) because `sample_unit_f_from_cache`
    /// samples the atom and the continuous part as two separate steps.
    fn build_law_cdf(&self, condition: ArrivalCondition) -> ArrivalCdfCache {
        let law = self.rung_law_on_grid(condition, &self.active_corridor, ARRIVAL_GRID);
        let denom = (1.0 - law.atom_f0).max(1e-12);
        let cdf: Vec<f64> = law
            .cdf
            .iter()
            .map(|&c| ((c - law.atom_f0) / denom).clamp(0.0, 1.0))
            .collect();

        ArrivalCdfCache {
            cdf,
            atom_f0: law.atom_f0,
            mean_f: law.mean_f,
            variance_f: law.sd_f * law.sd_f,
        }
    }

    /// Unconditional variance of `f` for the F2/F2a (`Duration`) channel law at a given
    /// pack-date duration (includes the `f = 0` atom).
    pub fn variance_f_given_d(&mut self, d_days: i32) -> f64 {
        self.law_cdf(ArrivalCondition::Duration(d_days)).variance_f
    }

    /// Point the filter's prior and F2/F3 caches at a different corridor (T-150 finding
    /// 4: the configured `arrival_product` must reach the filter prior, not just the
    /// truth path). No-op if already active; otherwise invalidates the F2/F3 caches
    /// (built against the old corridor) and rebuilds the prior against the new one.
    pub fn set_corridor(&mut self, corridor_key: &str) {
        if self.active_corridor == corridor_key {
            return;
        }
        self.active_corridor = corridor_key.to_string();
        self.f2_cache.clear();
        self.f3_cache.clear();
        self.marginal_cdf = self.build_law_cdf(ArrivalCondition::Prior);
        self.prior_build_key = PriorCdfBuildKey::from_model(self);
    }

    /// The corridor the filter prior and F2/F3 caches are currently built against.
    pub fn active_corridor(&self) -> &str {
        &self.active_corridor
    }

    /// Most recent `Duration` days the filter conditioned on (T-150 wire adapter).
    pub fn last_duration_days(&self) -> Option<i32> {
        self.last_duration_days
    }

    /// Most recent `Exposure` Λ the filter conditioned on (ADR 0144 C1 / T-150 wire
    /// adapter — `None` means no delivery has been observed on this channel yet).
    pub fn last_exposure_lambda(&self) -> Option<f64> {
        self.last_exposure_lambda
    }

    /// Inverse-sample one arrival freshness draw from a cached channel-conditional law.
    /// First flips a coin against `atom_f0` to decide total spoilage; only if that misses
    /// does it rescale the remaining uniform draw into `[0, 1]` and binary-search +
    /// linearly interpolate the atom-divided CDF, so the `f = 0` point mass never gets
    /// smeared across the grid's first bin.
    pub fn sample_unit_f_from_cache<R: Rng + ?Sized>(
        &self,
        cache: &ArrivalCdfCache,
        rng: &mut R,
    ) -> f64 {
        let u: f64 = rng.random();
        if u < cache.atom_f0 {
            return 0.0;
        }
        let u_adj = (u - cache.atom_f0) / (1.0 - cache.atom_f0).max(1e-12);
        let mut lo = 0usize;
        let mut hi = ARRIVAL_GRID - 1;
        while lo + 1 < hi {
            let mid = (lo + hi) / 2;
            if cache.cdf[mid] < u_adj {
                lo = mid;
            } else {
                hi = mid;
            }
        }
        let f_lo = lo as f64 / (ARRIVAL_GRID - 1) as f64;
        let f_hi = hi as f64 / (ARRIVAL_GRID - 1) as f64;
        let c_lo = cache.cdf[lo];
        let c_hi = cache.cdf[hi];
        if (c_hi - c_lo).abs() < 1e-15 {
            return f_lo;
        }
        let t = (u_adj - c_lo) / (c_hi - c_lo);
        (f_lo * (1.0 - t) + f_hi * t).clamp(0.0, 1.0)
    }

    /// Draw `n` iid arrival freshness values for newly born filter particles under a
    /// given channel condition, sharing one cached law across all `n` draws.
    pub fn sample_filter_birth_units<R: Rng + ?Sized>(
        &mut self,
        condition: ArrivalCondition,
        n: usize,
        rng: &mut R,
    ) -> Vec<f64> {
        let cache = self.law_cdf(condition);
        (0..n)
            .map(|_| self.sample_unit_f_from_cache(&cache, rng))
            .collect()
    }

    /// Unconditional mean `E[f]` for a channel-conditional filter law (includes the `f = 0` atom).
    pub fn filter_law_mean_f(&mut self, condition: ArrivalCondition) -> f64 {
        self.law_cdf(condition).mean_f
    }

    /// Fetch (building and caching on miss) the atom-divided law for a channel condition,
    /// and record it as the most recent duration/exposure the filter conditioned on for
    /// the wire adapter to read back. `Exposure` keys its cache on Λ rounded to six
    /// decimal places so near-identical exposures reuse one entry instead of growing the
    /// cache unboundedly.
    fn law_cdf(&mut self, condition: ArrivalCondition) -> ArrivalCdfCache {
        match condition {
            ArrivalCondition::Exposure(lambda) => {
                self.last_exposure_lambda = Some(lambda);
                let key = (lambda * 1_000_000.0).round() as u64;
                if !self.f3_cache.contains_key(&key) {
                    let built = self.build_law_cdf(ArrivalCondition::Exposure(lambda));
                    self.f3_cache.insert(key, built);
                }
                self.f3_cache.get(&key).unwrap().clone()
            }
            ArrivalCondition::Duration(d) => {
                self.last_duration_days = Some(d);
                if !self.f2_cache.contains_key(&d) {
                    let built = self.build_law_cdf(ArrivalCondition::Duration(d));
                    self.f2_cache.insert(d, built);
                }
                self.f2_cache.get(&d).unwrap().clone()
            }
            ArrivalCondition::Prior => self.marginal_cdf.clone(),
        }
    }

    /// Unconditional variance of `f` for the `Prior` (P0/P1) channel law (includes the
    /// `f = 0` atom).
    pub fn marginal_variance_f(&self) -> f64 {
        self.marginal_cdf.variance_f
    }

    /// Pull the freshness-loss physics parameters (gamma shape/scale, Q10, reference
    /// temperature/life) from `ModelParams` and rebuild the filter prior and F2/F3 caches
    /// if any of them actually changed. A no-op when the fingerprint matches, so callers
    /// can call this every tick without paying for a rebuild each time.
    pub fn sync_params(&mut self, params: &ModelParams) {
        let key = PriorCdfBuildKey::from_params(params, &self.active_corridor);
        if self.prior_build_key == key {
            return;
        }
        self.gamma_shape = params.gamma_shape;
        self.gamma_scale = params.gamma_scale;
        self.q10 = params.q10;
        self.t_ref = params.t_ref_c;
        self.reference_life_days = params.eta_ref;
        self.marginal_cdf = self.build_law_cdf(ArrivalCondition::Prior);
        self.f2_cache.clear();
        self.f3_cache.clear();
        self.prior_build_key = PriorCdfBuildKey::from_model(self);
    }
}

impl ArrivalCdfCache {
    fn empty() -> Self {
        Self {
            cdf: vec![0.0; ARRIVAL_GRID],
            atom_f0: 0.0,
            mean_f: 0.0,
            variance_f: 0.0,
        }
    }
}

/// Exact cumulative exposure Λ from an observed temperature trace (reference-days).
pub fn resolve_arrival_exposure(
    obs_temps: Option<&[f64]>,
    obs_times: Option<&[f64]>,
    q10: f64,
    t_ref: f64,
) -> Option<f64> {
    let (times, temps) = (obs_times?, obs_temps?);
    if times.len() < 2 || temps.len() != times.len() {
        return None;
    }
    let mut exposure = 0.0;
    for i in 0..times.len() - 1 {
        let dt = times[i + 1] - times[i];
        if dt <= 0.0 {
            continue;
        }
        let t_mid = 0.5 * (temps[i] + temps[i + 1]);
        exposure += dt * store_temp_factor(t_mid, t_ref, q10);
    }
    if exposure <= 1e-12 {
        return None;
    }
    Some(exposure)
}

/// Arrhenius-equivalent mean temperature factor φ̄ = Λ / d from a trace (fixture helper).
pub fn resolve_arrival_f_law_phi_bar(
    obs_temps: Option<&[f64]>,
    obs_times: Option<&[f64]>,
    q10: f64,
    t_ref: f64,
) -> Option<f64> {
    let (times, temps) = (obs_times?, obs_temps?);
    if times.len() < 2 || temps.len() != times.len() {
        return None;
    }
    let mut exposure = 0.0;
    let mut duration = 0.0;
    for i in 0..times.len() - 1 {
        let dt = times[i + 1] - times[i];
        if dt <= 0.0 {
            continue;
        }
        duration += dt;
        let t_mid = 0.5 * (temps[i] + temps[i + 1]);
        exposure += dt * store_temp_factor(t_mid, t_ref, q10);
    }
    if duration <= 1e-12 {
        return None;
    }
    Some(exposure / duration)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    fn committed_from_file() -> ArrivalModel {
        const SUFFIX: &str = "model.json";
        let path = format!(
            "{}/../../data/abdella/arrival_{}",
            env!("CARGO_MANIFEST_DIR"),
            SUFFIX
        );
        let json = std::fs::read_to_string(path).expect("read committed arrival artifact");
        ArrivalModel::from_json(&json).expect("parse committed arrival artifact")
    }

    #[test]
    fn embedded_matches_committed_file() {
        let embedded = ArrivalModel::embedded();
        let file = committed_from_file();
        assert_eq!(embedded.schema_version, file.schema_version);
        assert!((embedded.gamma_scale - file.gamma_scale).abs() < 1e-12);
        assert_eq!(embedded.corridors.len(), file.corridors.len());
    }

    #[test]
    fn rejects_unknown_schema_version() {
        let json = r#"{"schema_version":99,"mu_T":1,"sigma_T":1,"sigma_pos":0.1,"q10":3,"T_ref":0,"gamma_shape":2,"gamma_scale":0.03,"reference_life_days":14,"quadrature":{"nodes":[0.5],"weights":[1.0]},"corridors":{"x":{"d_min":1,"delay_shape":1,"delay_scale":1}}}"#;
        let err = ArrivalModel::from_json(json).unwrap_err();
        assert!(matches!(err, ArrivalModelError::UnknownSchemaVersion(99)));
    }

    #[test]
    fn analytic_cdf_matches_monte_carlo() {
        let model = ArrivalModel::embedded();
        let lambda = 4.0;
        let x = 0.3;
        let p_gt = model.p_f_gt_at(lambda, x);
        let p_zero = model.p_f_zero(lambda);
        let mut rng = Pcg64::seed_from_u64(150_209);
        let n = 50_000;
        let mut gt = 0usize;
        let mut zero = 0usize;
        for _ in 0..n {
            let loss = Gamma::new(model.gamma_shape * lambda, model.gamma_scale)
                .unwrap()
                .sample(&mut rng);
            let f = (1.0 - loss).max(0.0);
            if f > x {
                gt += 1;
            }
            if f <= 0.0 {
                zero += 1;
            }
        }
        assert!((gt as f64 / n as f64 - p_gt).abs() < 0.02);
        assert!((zero as f64 / n as f64 - p_zero).abs() < 0.02);
    }
}
