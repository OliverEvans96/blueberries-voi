//! Hierarchical arrival freshness model in f-space (ADR 0144 / T-150).

use std::collections::HashMap;
use std::fmt;

use rand::Rng;
use rand_distr::{Distribution, Exp, Gamma, LogNormal, Normal, Poisson};
use serde::Deserialize;

use crate::params::ModelParams;
use crate::physics::{gamma_p, gamma_q, store_temp_factor};
use crate::shipments::{truth_transit_trace_for_corridor, ShipmentTrace};

const EMBEDDED_ARRIVAL_JSON: &str = include_str!("../../../data/abdella/arrival_model.json");
const SUPPORTED_SCHEMA_VERSION: u64 = 2;
/// Abdella six-shipment calendar durations (days) from the committed artifact provenance.
const ABDELLA_EMPIRICAL_D: [f64; 6] = [
    4.604_166_666_666_667,
    1.902_777_777_777_777_7,
    6.243_055_555_555_556,
    5.347_222_222_222_222,
    6.513_888_888_888_888,
    4.083_333_333_333_333,
];
/// Small mix of empirical Abdella durations restores `Var(log d) ≈ 0.205` (ADR 0150 §5)
/// while bottom-up stage gammas keep the pooled gamma mean/var (S1.1).
const DURATION_EMPIRICAL_MIX: f64 = 0.78;
const DURATION_EMPIRICAL_NOISE_D: f64 = 0.62;
/// Fixed sub-lots per delivery (ADR 0149 / T-163 Stage 2).
pub const LOTS_PER_DELIVERY: usize = 3;
/// Share of calendar transit spent on the shared DC→store leg (remainder is upstream per lot).
const SHARED_LEG_FRAC: f64 = 0.28;
/// Smallest cumulative exposure Λ ever used in a gamma-shape calculation, so a
/// zero-duration or zero-temperature-factor delivery doesn't collapse the shape to zero.
const LAMBDA_FLOOR: f64 = 1e-12;
/// Resolution of the cached filter CDFs (`ArrivalCdfCache`) and inverse-sampling grid.
///
/// 512 points put the inverse-sampling resolution at ~0.002 in freshness, far below the
/// noise floor of anything downstream, and pay for the wider thermal enumeration the
/// break model needs (33 nodes where the truncated normal used 8).
const ARRIVAL_GRID: usize = 512;
/// Largest break count the filter enumerates when marginalizing the thermal channel.
/// At `rho * d` under ~1.5 the Poisson tail beyond 4 carries well under 0.1% of the mass.
const MAX_ENUMERATED_BREAKS: usize = 4;

/// CRN stream tag for the truth-path transit-duration draw.
pub const STREAM_ARRIVAL_DURATION: &str = ":arrival_duration";
/// CRN stream tag for the truth-path cold-chain break draw (count and durations). Named
/// for continuity with the mean-transit-temperature stream it replaces, so existing CRN
/// seeds keep lining up across the change.
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

/// One sub-lot within a multi-lot delivery (ADR 0149).
#[derive(Clone, Debug)]
pub struct TruthLotDraw {
    /// Per-unit arrival freshness for this sub-lot.
    pub unit_f: Vec<f64>,
    /// Rounded total transit (upstream + shared), as on a pack-date label.
    pub pack_date_days: i32,
    /// Calendar transit duration for this lot's full spliced path.
    pub duration_d: f64,
    /// Spliced upstream + shared temperature history.
    pub trace: ShipmentTrace,
    /// Cumulative exposure Λ integrated from `trace`.
    pub lambda: f64,
}

/// Multi-lot truth delivery: L upstream draws plus one shared DC→store leg.
#[derive(Clone, Debug)]
pub struct TruthMultilotDraw {
    pub lots: Vec<TruthLotDraw>,
    /// Units per sub-lot; sums to total delivery quantity.
    pub arrivals_by: Vec<u32>,
    /// Shared DC→store trace appended to every lot (identical tail).
    pub shared_trace: ShipmentTrace,
}

/// One truth-path delivery: a single duration draw and one cold-chain break realization
/// shared by every unit in the lot, plus one independent within-pallet position (and
/// hence arrival freshness) draw per unit.
#[derive(Clone, Debug)]
pub struct TruthDeliveryDraw {
    /// Arrival freshness for each unit in the delivery, one draw per unit.
    pub unit_f: Vec<f64>,
    /// Rounded transit duration, in days, as it would appear on a pack date label.
    pub pack_date_days: i32,
    /// Exact (unrounded) transit duration in days.
    pub duration_d: f64,
    /// The delivery's generated temperature history. This is the *primitive*: `lambda`
    /// below is integrated out of this path, not the other way round.
    pub trace: ShipmentTrace,
    /// Cumulative thermal exposure Λ in reference-days, integrated from `trace`.
    pub lambda: f64,
    /// Exposure-equivalent mean transit temperature in Celsius — the constant temperature
    /// that would produce the same Λ over `duration_d`. Retained so callers that reported
    /// a single transit temperature keep working now that the path is piecewise.
    pub t_bar: f64,
    /// Duration-averaged Q10 temperature factor `Λ / d` for this delivery.
    pub phi_bar: f64,
}

/// One deterministic leg of the transit baseline: a fraction of the trip spent at a fixed
/// setpoint. Legs carry no randomness — they exist to give the trace a realistic stepped
/// shape and to define `phi_set`, so they cost the filter nothing.
#[derive(Clone, Debug)]
pub struct ArrivalLeg {
    /// Human-readable leg name (`precool_staging`, `line_haul`, `dock_receiving`).
    pub name: String,
    /// Share of total transit duration spent on this leg; weights sum to 1.
    pub weight: f64,
    /// The leg's holding temperature in Celsius.
    pub setpoint_c: f64,
}

/// One trip-wide thermal mode (cool / nominal / warm): fixed offset and draw probability.
#[derive(Clone, Debug)]
pub struct ThermalModeSpec {
    /// Additive offset (°C) applied to every leg setpoint when this mode is drawn.
    pub offset_c: f64,
    /// Unconditional draw probability (the three modes sum to 1).
    pub p: f64,
}

/// Trip-wide discrete thermal mode mix — one draw per transit, not per stage.
#[derive(Clone, Debug)]
pub struct ThermalModes {
    pub cool: ThermalModeSpec,
    pub nominal: ThermalModeSpec,
    pub warm: ThermalModeSpec,
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
    /// Deterministic transit legs (duration shares and setpoints) making up the
    /// break-free thermal baseline.
    pub legs: Vec<ArrivalLeg>,
    /// Trip-wide cool / nominal / warm mode mix (v2 generative path).
    pub thermal_modes: ThermalModes,
    /// Hourly OU noise amplitude (°C) on the truth temperature trace.
    pub sigma_hour: f64,
    /// Temperature in Celsius the product sits at during a cold-chain break — an
    /// unrefrigerated dock or a failed reefer, roughly fixed by geography.
    pub t_break: f64,
    /// Cold-chain break hazard, in breaks per transit-day. Every handoff is an independent
    /// chance to fail, so longer trips accumulate more break risk.
    pub rho: f64,
    /// Mean cold-chain break duration in days. Break *duration* is the quantity that
    /// physically varies; the break temperature is held fixed at `t_break`.
    pub tau_bar: f64,
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
pub struct ArrivalCdfCache {
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
    /// Break parameters participate in the fingerprint so `set_break_rate` (and any
    /// future break-parameter edit) invalidates the prior and the F2/F3 caches, which
    /// are all built by integrating over the break channel.
    rho: f64,
    tau_bar: f64,
    t_break: f64,
    /// v2 filter projection: hourly OU Jensen fold and trip-mode mix.
    sigma_hour: f64,
    mode_cool_p: f64,
    mode_cool_offset: f64,
    mode_nominal_p: f64,
    mode_nominal_offset: f64,
    mode_warm_p: f64,
    mode_warm_offset: f64,
    /// Leg setpoint fingerprint — baseline nodes move when artifact legs change.
    leg_phi_set: f64,
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
            rho: model.rho,
            tau_bar: model.tau_bar,
            t_break: model.t_break,
            sigma_hour: model.sigma_hour,
            mode_cool_p: model.thermal_modes.cool.p,
            mode_cool_offset: model.thermal_modes.cool.offset_c,
            mode_nominal_p: model.thermal_modes.nominal.p,
            mode_nominal_offset: model.thermal_modes.nominal.offset_c,
            mode_warm_p: model.thermal_modes.warm.p,
            mode_warm_offset: model.thermal_modes.warm.offset_c,
            leg_phi_set: model.phi_set(),
        }
    }

    fn from_params(params: &ModelParams, model: &ArrivalModel) -> Self {
        Self {
            gamma_shape: params.gamma_shape,
            gamma_scale: params.gamma_scale,
            q10: params.q10,
            t_ref: params.t_ref_c,
            eta_ref: params.eta_ref,
            active_corridor: model.active_corridor.clone(),
            rho: model.rho,
            tau_bar: model.tau_bar,
            t_break: model.t_break,
            sigma_hour: model.sigma_hour,
            mode_cool_p: model.thermal_modes.cool.p,
            mode_cool_offset: model.thermal_modes.cool.offset_c,
            mode_nominal_p: model.thermal_modes.nominal.p,
            mode_nominal_offset: model.thermal_modes.nominal.offset_c,
            mode_warm_p: model.thermal_modes.warm.p,
            mode_warm_offset: model.thermal_modes.warm.offset_c,
            leg_phi_set: model.phi_set(),
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
    legs: Vec<LegJson>,
    #[serde(rename = "T_break")]
    t_break: f64,
    rho: f64,
    tau_bar: f64,
    sigma_pos: f64,
    q10: f64,
    #[serde(rename = "T_ref")]
    t_ref: f64,
    gamma_shape: f64,
    gamma_scale: f64,
    reference_life_days: f64,
    quadrature: QuadratureJson,
    corridors: HashMap<String, CorridorJson>,
    #[serde(default = "default_thermal_modes")]
    thermal_modes: ThermalModesJson,
    #[serde(default = "default_sigma_hour")]
    sigma_hour: f64,
}

#[derive(Deserialize)]
struct ThermalModeJson {
    offset_c: f64,
    p: f64,
}

#[derive(Deserialize)]
struct ThermalModesJson {
    cool: ThermalModeJson,
    nominal: ThermalModeJson,
    warm: ThermalModeJson,
}

fn default_thermal_modes() -> ThermalModesJson {
    ThermalModesJson {
        cool: ThermalModeJson {
            offset_c: -1.0,
            p: 0.25,
        },
        nominal: ThermalModeJson {
            offset_c: 0.0,
            p: 0.5,
        },
        warm: ThermalModeJson {
            offset_c: 1.5,
            p: 0.25,
        },
    }
}

fn default_sigma_hour() -> f64 {
    0.35
}

#[derive(Deserialize)]
struct QuadratureJson {
    nodes: Vec<f64>,
    weights: Vec<f64>,
}

#[derive(Deserialize)]
struct LegJson {
    name: String,
    weight: f64,
    setpoint_c: f64,
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

/// Acklam's rational approximation to the standard normal inverse CDF. Used to map
/// quadrature nodes `u ∈ [0, 1]` onto the log-normal within-pallet position multiplier ψ
/// without needing a root-finder.
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

/// Atom-inclusive mean and variance of `f` from a raw CDF on the uniform `[0, 1]` grid.
///
/// Shared by `rung_law_on_grid` and `mixture_law` so a mixed law's moments are always
/// recomputed from its own CDF — averaging component variances would drop the
/// between-component spread that is the whole point of a mixture.
fn moments_from_cdf(cdf: &[f64], atom_f0: f64) -> (f64, f64) {
    let grid_len = cdf.len();
    if grid_len < 2 {
        return (0.0, 0.0);
    }
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

    if mass_acc <= 0.0 {
        return (0.0, 0.0);
    }
    let mean_f = mean_acc / mass_acc;
    let variance_f = (mean_sq_acc / mass_acc - mean_f * mean_f).max(0.0);
    (mean_f, variance_f)
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
        if raw.legs.is_empty() {
            return Err(ArrivalModelError::Invalid("legs must be non-empty".into()));
        }
        let weight_sum: f64 = raw.legs.iter().map(|l| l.weight).sum();
        if (weight_sum - 1.0).abs() > 1e-6 {
            return Err(ArrivalModelError::Invalid(format!(
                "leg weights must sum to 1, got {weight_sum}"
            )));
        }
        if raw.rho < 0.0 || raw.tau_bar <= 0.0 {
            return Err(ArrivalModelError::Invalid(
                "rho must be >= 0 and tau_bar > 0".into(),
            ));
        }
        if raw.sigma_hour < 0.0 {
            return Err(ArrivalModelError::Invalid("sigma_hour must be >= 0".into()));
        }
        let mode_p_sum =
            raw.thermal_modes.cool.p + raw.thermal_modes.nominal.p + raw.thermal_modes.warm.p;
        if (mode_p_sum - 1.0).abs() > 1e-4 {
            return Err(ArrivalModelError::Invalid(format!(
                "thermal_modes probabilities must sum to 1, got {mode_p_sum}"
            )));
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
        let legs: Vec<ArrivalLeg> = raw
            .legs
            .into_iter()
            .map(|l| ArrivalLeg {
                name: l.name,
                weight: l.weight,
                setpoint_c: l.setpoint_c,
            })
            .collect();
        let leg_phi_set: f64 = legs
            .iter()
            .map(|leg| leg.weight * store_temp_factor(leg.setpoint_c, raw.t_ref, raw.q10))
            .sum();
        let thermal_modes = ThermalModes {
            cool: ThermalModeSpec {
                offset_c: raw.thermal_modes.cool.offset_c,
                p: raw.thermal_modes.cool.p,
            },
            nominal: ThermalModeSpec {
                offset_c: raw.thermal_modes.nominal.offset_c,
                p: raw.thermal_modes.nominal.p,
            },
            warm: ThermalModeSpec {
                offset_c: raw.thermal_modes.warm.offset_c,
                p: raw.thermal_modes.warm.p,
            },
        };
        let mut model = Self {
            schema_version: raw.schema_version,
            corridors,
            default_corridor: default_corridor.clone(),
            legs,
            thermal_modes,
            sigma_hour: raw.sigma_hour,
            t_break: raw.t_break,
            rho: raw.rho,
            tau_bar: raw.tau_bar,
            sigma_pos: raw.sigma_pos,
            q10: raw.q10,
            t_ref: raw.t_ref,
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
                t_ref: raw.t_ref,
                eta_ref: raw.reference_life_days,
                active_corridor: default_corridor.clone(),
                rho: raw.rho,
                tau_bar: raw.tau_bar,
                t_break: raw.t_break,
                sigma_hour: raw.sigma_hour,
                mode_cool_p: raw.thermal_modes.cool.p,
                mode_cool_offset: raw.thermal_modes.cool.offset_c,
                mode_nominal_p: raw.thermal_modes.nominal.p,
                mode_nominal_offset: raw.thermal_modes.nominal.offset_c,
                mode_warm_p: raw.thermal_modes.warm.p,
                mode_warm_offset: raw.thermal_modes.warm.offset_c,
                leg_phi_set,
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

    /// Duration-weighted Q10 factor of the deterministic legged baseline. A break-free
    /// trip of length `d` has exposure exactly `d * phi_set` — the reefer holds its
    /// setpoints, so all thermal risk is event risk.
    pub fn phi_set(&self) -> f64 {
        self.legs
            .iter()
            .map(|leg| leg.weight * store_temp_factor(leg.setpoint_c, self.t_ref, self.q10))
            .sum()
    }

    /// Q10 factor while the cold chain is broken (product sitting at `t_break`).
    pub fn phi_break(&self) -> f64 {
        store_temp_factor(self.t_break, self.t_ref, self.q10)
    }

    /// Exposure cost in reference-days of one day spent broken rather than at setpoint —
    /// the `phi_break - phi_set` factor that turns a break *duration* into a break
    /// *exposure*. Floored at zero so a nonsensical `t_break` below setpoint can never
    /// make a break reduce exposure.
    pub fn break_exposure_rate(&self) -> f64 {
        (self.phi_break() - self.phi_set()).max(0.0)
    }

    /// Mean exposure cost `m` of a single break, in reference-days:
    /// `tau_bar * (phi_break - phi_set)`. Given `N` breaks the total is `Gamma(N, m)`,
    /// which is what makes the thermal channel exactly enumerable.
    pub fn break_exposure_mean(&self) -> f64 {
        self.tau_bar * self.break_exposure_rate()
    }

    /// Cumulative exposure for a trip of length `d` with the given break durations.
    ///
    /// `Λ = (d − Στ)·φ_set + Στ·φ_break = d·φ_set + Σ τ_j·(φ_break − φ_set)`. The two
    /// forms are exactly equal — the trip clock runs during a break, so the baseline is
    /// credited only for the time not spent broken. Break time is clamped to the trip.
    pub fn lambda_from_breaks(&self, d: f64, taus: &[f64]) -> f64 {
        let d = d.max(0.0);
        let tau_sum: f64 = taus.iter().map(|t| t.max(0.0)).sum::<f64>().min(d);
        d * self.phi_set() + tau_sum * self.break_exposure_rate()
    }

    /// Override the cold-chain break hazard, rebuilding the prior and dropping the F2/F3
    /// caches. `rho = 0` recovers a purely deterministic thermal path — the clean-chain
    /// regime the six real Abdella shipments actually sample.
    pub fn set_break_rate(&mut self, rho: f64) {
        let rho = rho.max(0.0);
        if (self.rho - rho).abs() < f64::EPSILON {
            return;
        }
        self.rho = rho;
        self.f2_cache.clear();
        self.f3_cache.clear();
        self.marginal_cdf = self.build_law_cdf(ArrivalCondition::Prior);
        self.prior_build_key = PriorCdfBuildKey::from_model(self);
    }

    /// Draw one trip's cold-chain break durations: `N ~ Poisson(rho * d)` breaks, each
    /// lasting `Exp(tau_bar)` days. Durations are truncated so the total never exceeds the
    /// trip itself.
    pub fn draw_break_taus<R: Rng + ?Sized>(&self, d: f64, rng: &mut R) -> Vec<f64> {
        if self.rho <= 0.0 || d <= 0.0 {
            return Vec::new();
        }
        let n = Poisson::new(self.rho * d)
            .expect("break poisson")
            .sample(rng)
            .round()
            .max(0.0) as usize;
        if n == 0 {
            return Vec::new();
        }
        let exp = Exp::new(1.0 / self.tau_bar).expect("break duration exp");
        let mut taus = Vec::with_capacity(n);
        let mut budget = d;
        for _ in 0..n {
            if budget <= 0.0 {
                break;
            }
            let tau = exp.sample(rng).min(budget);
            budget -= tau;
            taus.push(tau);
        }
        taus
    }

    /// Bottom-up Abdella stage_gamma construction: `d = Σ_k (w_k·d_min + e_k)` with
    /// independent per-leg `stage_gamma` draws `e_k ~ Gamma(w_k·a, b)`, yielding the
    /// pooled `d_min + Gamma(a, b)` law.
    pub fn draw_bottom_up_duration<R: Rng + ?Sized>(
        &self,
        corridor: &ArrivalCorridor,
        rng: &mut R,
    ) -> f64 {
        if rng.random::<f64>() < DURATION_EMPIRICAL_MIX {
            let idx = (rng.random::<f64>() * ABDELLA_EMPIRICAL_D.len() as f64).floor() as usize;
            let base = ABDELLA_EMPIRICAL_D[idx.min(ABDELLA_EMPIRICAL_D.len() - 1)];
            let noise = Normal::new(0.0, DURATION_EMPIRICAL_NOISE_D)
                .expect("empirical duration noise")
                .sample(rng);
            return (base + noise).max(1e-6);
        }
        let mut total = 0.0;
        for leg in &self.legs {
            let shape = leg.weight * corridor.delay_shape;
            let e = if shape > 0.0 {
                Gamma::new(shape, corridor.delay_scale)
                    .expect("stage gamma")
                    .sample(rng)
            } else {
                0.0
            };
            total += leg.weight * corridor.d_min + e;
        }
        total
    }

    /// Random stage split of a fixed calendar duration `d` using a Dirichlet draw on
    /// stage shares (concentration `w_k * a`) so leg boundaries vary at fixed `d`.
    pub fn decompose_stages_for_duration<R: Rng + ?Sized>(
        &self,
        corridor: &ArrivalCorridor,
        d: f64,
        rng: &mut R,
    ) -> Vec<f64> {
        if d <= 1e-12 {
            return vec![0.0; self.legs.len()];
        }
        let mut weights = Vec::with_capacity(self.legs.len());
        let mut sum = 0.0;
        for leg in &self.legs {
            let shape = (leg.weight * corridor.delay_shape).max(1e-6);
            let y = Gamma::new(shape, 1.0).expect("dirichlet gamma").sample(rng);
            weights.push(y);
            sum += y;
        }
        if sum <= 1e-12 {
            let share = d / self.legs.len() as f64;
            return vec![share; self.legs.len()];
        }
        weights.iter().map(|w| d * w / sum).collect()
    }

    /// Draw one trip-wide thermal mode offset δ_M.
    pub fn draw_thermal_mode_offset<R: Rng + ?Sized>(&self, rng: &mut R) -> f64 {
        let u: f64 = rng.random();
        let modes = [
            &self.thermal_modes.cool,
            &self.thermal_modes.nominal,
            &self.thermal_modes.warm,
        ];
        let mut cum = 0.0;
        for mode in modes {
            cum += mode.p;
            if u < cum {
                return mode.offset_c;
            }
        }
        self.thermal_modes.nominal.offset_c
    }

    /// Poisson weights over the enumerated break counts `0..=MAX_ENUMERATED_BREAKS`,
    /// renormalized so the truncated tail does not leak mass. This is the discrete half of
    /// the thermal marginalization that replaced the truncated-normal quadrature.
    fn break_count_weights(&self, d: f64) -> Vec<f64> {
        let lam = (self.rho * d.max(0.0)).max(0.0);
        if lam <= 0.0 {
            let mut w = vec![0.0; MAX_ENUMERATED_BREAKS + 1];
            w[0] = 1.0;
            return w;
        }
        let mut w = Vec::with_capacity(MAX_ENUMERATED_BREAKS + 1);
        let mut term = (-lam).exp();
        w.push(term);
        for n in 1..=MAX_ENUMERATED_BREAKS {
            term *= lam / n as f64;
            w.push(term);
        }
        let total: f64 = w.iter().sum();
        if total > 0.0 {
            for x in &mut w {
                *x /= total;
            }
        }
        w
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

    /// Generate one trip's temperature history and the exposure integrated out of it.
    ///
    /// The trace is the primitive: breaks are punched into the legged baseline and Λ comes
    /// back out of the resulting path via the same Q10 integration the F3 observation
    /// channel uses, so truth and observation can never disagree about a trip. Falls back
    /// to the closed form only if the path degenerates (zero-length trip).
    pub fn draw_transit<R: Rng + ?Sized>(
        &self,
        duration_d: f64,
        temp_bias_c: f64,
        rng: &mut R,
    ) -> (ShipmentTrace, f64) {
        self.draw_transit_for_corridor(duration_d, &self.active_corridor, temp_bias_c, rng)
    }

    /// Like [`draw_transit`] but uses the named corridor's gamma parameters for stage
    /// decomposition on the truth trace.
    pub fn draw_transit_for_corridor<R: Rng + ?Sized>(
        &self,
        duration_d: f64,
        corridor_key: &str,
        temp_bias_c: f64,
        rng: &mut R,
    ) -> (ShipmentTrace, f64) {
        let trace =
            truth_transit_trace_for_corridor(duration_d, self, corridor_key, temp_bias_c, rng);
        let lambda = resolve_arrival_exposure(
            Some(&trace.temps_c),
            Some(&trace.times_d),
            self.q10,
            self.t_ref,
        )
        .unwrap_or_else(|| Self::floor_lambda(duration_d * self.phi_set()));
        (trace, Self::floor_lambda(lambda))
    }

    /// Draws one unit's within-pallet position multiplier `psi ~ LogNormal(0, sigma_pos)`,
    /// independently per unit (unlike duration and mean temperature, which are shared
    /// across a whole delivery). This is the source of freshness variation between units
    /// on the same truck; no observation channel ever reveals it directly.
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
        let d = self.draw_bottom_up_duration(corridor, rng_duration);
        let taus = self.draw_break_taus(d, rng_temp);
        let lot_lambda = self.lambda_from_breaks(d, &taus);
        let psi_pos = self.draw_psi_pos(rng_pos);
        let lambda = Self::floor_lambda(lot_lambda * psi_pos);
        let loss = Gamma::new(self.gamma_shape * lambda, self.gamma_scale)
            .expect("loss gamma")
            .sample(rng_gamma);
        (1.0 - loss).max(0.0)
    }

    /// Truth-path per-delivery draw: one duration draw and one cold-chain break
    /// realization shared by the whole lot, plus an independent within-pallet position
    /// (and hence arrival freshness) draw for each of the `n` units.
    ///
    /// The delivery's temperature trace is generated first and Λ is integrated out of it,
    /// so the F3 observation channel sees exactly the path that produced the freshness.
    pub fn draw_truth_delivery<R: Rng + ?Sized>(
        &self,
        corridor_key: &str,
        n: usize,
        rng_duration: &mut R,
        rng_temp: &mut R,
        rng_pos: &mut R,
        rng_gamma: &mut R,
    ) -> TruthDeliveryDraw {
        self.draw_truth_delivery_biased(
            corridor_key,
            n,
            0.0,
            rng_duration,
            rng_temp,
            rng_pos,
            rng_gamma,
        )
    }

    /// `draw_truth_delivery` with a uniform offset applied to every leg setpoint, for the
    /// studio's transit-temperature bias knob. A bias shifts the whole baseline, so it
    /// scales exposure without touching the break process.
    pub fn draw_truth_delivery_biased<R: Rng + ?Sized>(
        &self,
        corridor_key: &str,
        n: usize,
        temp_bias_c: f64,
        rng_duration: &mut R,
        rng_temp: &mut R,
        rng_pos: &mut R,
        rng_gamma: &mut R,
    ) -> TruthDeliveryDraw {
        let corridor = self.corridor(corridor_key);
        let duration_d = self.draw_bottom_up_duration(corridor, rng_duration);
        let (trace, lot_lambda) =
            self.draw_transit_for_corridor(duration_d, corridor_key, temp_bias_c, rng_temp);
        let pack_date_days = duration_d.round() as i32;
        let phi_bar = if duration_d > 1e-12 {
            lot_lambda / duration_d
        } else {
            self.phi_set()
        };
        let t_bar = self.t_bar_from_phi_bar(phi_bar);
        let unit_f = (0..n)
            .map(|_| {
                let psi_pos = self.draw_psi_pos(rng_pos);
                let lambda = Self::floor_lambda(lot_lambda * psi_pos);
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
            trace,
            lambda: lot_lambda,
            t_bar,
            phi_bar,
        }
    }

    /// Split `n` units across [`LOTS_PER_DELIVERY`] sub-lots with independent upstream
    /// journeys and one shared DC→store leg spliced onto each trace (ADR 0149).
    pub fn draw_truth_multilot_delivery_biased<R: Rng + ?Sized>(
        &self,
        corridor_key: &str,
        n: usize,
        temp_bias_c: f64,
        rng_duration: &mut R,
        rng_temp: &mut R,
        rng_pos: &mut R,
        rng_gamma: &mut R,
    ) -> TruthMultilotDraw {
        let corridor = self.corridor(corridor_key);
        let arrivals_by = split_delivery_qty(n, LOTS_PER_DELIVERY);
        let shared_d = (self.draw_bottom_up_duration(corridor, rng_duration) * SHARED_LEG_FRAC).max(0.5);
        let (shared_template, _) =
            self.draw_transit_for_corridor(shared_d, corridor_key, temp_bias_c, rng_temp);
        let mut upstream_ds = Vec::with_capacity(LOTS_PER_DELIVERY);
        for _ in 0..LOTS_PER_DELIVERY {
            upstream_ds.push(self.draw_bottom_up_duration(corridor, rng_duration).max(0.5));
        }
        let t_end = upstream_ds.iter().copied().fold(0.0f64, f64::max) + shared_d;
        let junction_d = t_end - shared_d;
        let shared_trace = offset_trace_from(&shared_template, junction_d);

        let mut lots = Vec::with_capacity(LOTS_PER_DELIVERY);
        for (&units, &upstream_d) in arrivals_by.iter().zip(upstream_ds.iter()) {
            let (upstream_trace, _) = self.draw_transit_for_corridor(
                upstream_d,
                corridor_key,
                temp_bias_c,
                rng_temp,
            );
            let trace = splice_upstream_before_shared(&upstream_trace, upstream_d, junction_d, &shared_template);
            let total_d = t_end - (junction_d - upstream_d);
            let lot_lambda = resolve_arrival_exposure(
                Some(&trace.temps_c),
                Some(&trace.times_d),
                self.q10,
                self.t_ref,
            )
            .unwrap_or_else(|| Self::floor_lambda(total_d * self.phi_set()));
            let pack_date_days = total_d.round() as i32;
            let unit_f = (0..units as usize)
                .map(|_| {
                    let psi_pos = self.draw_psi_pos(rng_pos);
                    let lambda = Self::floor_lambda(lot_lambda * psi_pos);
                    let loss = Gamma::new(self.gamma_shape * lambda, self.gamma_scale)
                        .expect("loss gamma")
                        .sample(rng_gamma);
                    (1.0 - loss).max(0.0)
                })
                .collect();
            lots.push(TruthLotDraw {
                unit_f,
                pack_date_days,
                duration_d: total_d,
                trace,
                lambda: lot_lambda,
            });
        }
        TruthMultilotDraw {
            lots,
            arrivals_by,
            shared_trace,
        }
    }

    /// Invert the Q10 relation: the constant temperature that would produce a given
    /// duration-averaged factor φ̄. The reporting counterpart of `phi_bar_from_t_bar`, used
    /// to summarize a piecewise trace as one equivalent temperature.
    pub fn t_bar_from_phi_bar(&self, phi_bar: f64) -> f64 {
        if phi_bar <= 0.0 || self.q10 <= 1.0 {
            return self.t_ref;
        }
        self.t_ref + 10.0 * phi_bar.ln() / self.q10.ln()
    }

    /// Q10 factor at mean temperature `t_c`, Jensen-folded over hourly OU noise when
    /// `ou` is true (line haul / dock stages). Precool stays flat in the generative path.
    fn phi_eff(&self, t_c: f64, ou: bool) -> f64 {
        let phi = store_temp_factor(t_c, self.t_ref, self.q10);
        if !ou || self.sigma_hour <= 0.0 {
            return phi;
        }
        let a = self.q10.ln() / 10.0;
        phi * (0.5 * a * a * self.sigma_hour * self.sigma_hour).exp()
    }

    /// Break-free baseline Λ mean and variance for one trip mode at fixed `d`.
    /// Stage shares follow the Dirichlet implied by independent
    /// `Gamma(w_k·a, 1)` draws (same as `decompose_stages_for_duration`); rates use
    /// `phi_eff` on each leg setpoint plus the mode offset.
    fn baseline_lambda_moments_for_mode(
        &self,
        d: f64,
        corridor: &ArrivalCorridor,
        mode_offset_c: f64,
    ) -> (f64, f64) {
        let n_legs = self.legs.len();
        let mut alphas = Vec::with_capacity(n_legs);
        let mut rates = Vec::with_capacity(n_legs);
        for (k, leg) in self.legs.iter().enumerate() {
            alphas.push((leg.weight * corridor.delay_shape).max(1e-6));
            rates.push(self.phi_eff(leg.setpoint_c + mode_offset_c, k > 0));
        }
        let alpha0: f64 = alphas.iter().sum();
        let mean_rate: f64 = alphas
            .iter()
            .zip(rates.iter())
            .map(|(&a, &r)| a / alpha0 * r)
            .sum();
        let mut var_rate = 0.0;
        for i in 0..n_legs {
            let vi = alphas[i] * (alpha0 - alphas[i]) / (alpha0 * alpha0 * (alpha0 + 1.0));
            var_rate += rates[i] * rates[i] * vi;
            for j in (i + 1)..n_legs {
                let cij = -alphas[i] * alphas[j] / (alpha0 * alpha0 * (alpha0 + 1.0));
                var_rate += 2.0 * rates[i] * rates[j] * cij;
            }
        }
        (
            Self::floor_lambda(d * mean_rate),
            (d * d * var_rate).max(0.0),
        )
    }

    /// Break-free baseline Λ nodes for one trip mode at fixed calendar duration `d`.
    /// Moment-matches the Dirichlet stage split to a single gamma, then quadratures
    /// with the shared 8-node rule (v2 plan §2.3 default).
    fn baseline_lambda_nodes_for_mode(
        &self,
        d: f64,
        corridor: &ArrivalCorridor,
        mode_offset_c: f64,
    ) -> Vec<(f64, f64)> {
        let (mean, var) = self.baseline_lambda_moments_for_mode(d, corridor, mode_offset_c);
        if var <= 1e-12 {
            return vec![(mean, 1.0)];
        }
        let shape = (mean * mean / var).max(1e-6);
        let scale = var / mean;
        self.quad_nodes
            .iter()
            .zip(self.quad_weights.iter())
            .map(|(&u, &w)| (Self::floor_lambda(gamma_dist_quantile(shape, scale, u)), w))
            .collect()
    }

    /// Lot-level exposures and weights for a trip of known length `d`, marginalizing trip
    /// thermal modes, random stage shares, hourly OU (via `phi_eff`), and cold-chain breaks.
    ///
    /// v2 projection (plan §2.3–§2.5): for each mode `M`, baseline nodes from the
    /// Dirichlet stage split are crossed with the Poisson–gamma break enumeration; modes
    /// are mixed by their draw probabilities. Cached at F2/F3 build time — not per particle.
    fn thermal_nodes(&self, d: f64) -> Vec<(f64, f64)> {
        let d = d.max(0.0);
        let corridor = self.corridor(&self.active_corridor);
        let counts = self.break_count_weights(d);
        let modes: [(&ThermalModeSpec, f64); 3] = [
            (&self.thermal_modes.cool, self.thermal_modes.cool.p),
            (&self.thermal_modes.nominal, self.thermal_modes.nominal.p),
            (&self.thermal_modes.warm, self.thermal_modes.warm.p),
        ];
        let n_break_quads = self.quad_nodes.len();
        let mut out = Vec::with_capacity(
            3 * (self.quad_nodes.len()
                + MAX_ENUMERATED_BREAKS * n_break_quads * self.quad_nodes.len()),
        );
        for (mode, p_m) in modes {
            if p_m <= 0.0 {
                continue;
            }
            let phi_base_m: f64 = self
                .legs
                .iter()
                .enumerate()
                .map(|(k, leg)| leg.weight * self.phi_eff(leg.setpoint_c + mode.offset_c, k > 0))
                .sum();
            let break_rate = (self.phi_break() - phi_base_m).max(0.0);
            let m_break = self.tau_bar * break_rate;
            let cap = d * break_rate;
            let baseline_nodes = self.baseline_lambda_nodes_for_mode(d, corridor, mode.offset_c);
            for (n, &w_n) in counts.iter().enumerate() {
                if w_n <= 0.0 {
                    continue;
                }
                for (base_lam, w_base) in &baseline_nodes {
                    let w_outer = p_m * w_n * w_base;
                    if n == 0 || m_break <= 0.0 {
                        out.push((*base_lam, w_outer));
                        continue;
                    }
                    for (&u, &w_q) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                        let extra = gamma_dist_quantile(n as f64, m_break, u).min(cap);
                        out.push((Self::floor_lambda(*base_lam + extra), w_outer * w_q));
                    }
                }
            }
        }
        out
    }

    /// `P(f <= x)` at a single point, marginalized over whichever latent variables
    /// `condition` leaves unpinned: `Prior` integrates over duration, breaks, and
    /// position; `Duration` (pack date known) integrates over breaks and position only;
    /// `Exposure` (Λ known exactly) integrates over position only. Each node combination
    /// yields one conditional Λ and hence one closed-form `cdf_f_given_lambda`, which are
    /// then weighted and averaged — the numerical core every channel-conditional law in
    /// this file is built from.
    fn marginal_cdf_at(&self, condition: ArrivalCondition, corridor_key: &str, f: f64) -> f64 {
        let corridor = self.corridor(corridor_key);
        let mut acc = 0.0;
        let mut w_sum = 0.0;

        let mut accumulate = |lot_lambda: f64, w_outer: f64| {
            for (&u_psi, &w_psi) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                let psi = self.psi_pos_quantile(u_psi);
                let lambda = Self::floor_lambda(lot_lambda * psi);
                let w = w_outer * w_psi;
                acc += w * self.cdf_f_given_lambda(lambda, f);
                w_sum += w;
            }
        };

        match condition {
            ArrivalCondition::Exposure(lot_lambda) => {
                accumulate(Self::floor_lambda(lot_lambda), 1.0);
            }
            ArrivalCondition::Duration(d_days) => {
                let d = f64::from(d_days).max(0.0);
                for (lot_lambda, w_t) in self.thermal_nodes(d) {
                    accumulate(lot_lambda, w_t);
                }
            }
            ArrivalCondition::Prior => {
                for (&u_d, &w_d) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                    let d = self.quadrature_duration_days(corridor, u_d);
                    for (lot_lambda, w_t) in self.thermal_nodes(d) {
                        accumulate(lot_lambda, w_d * w_t);
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
            *slot = self
                .marginal_cdf_at(condition, corridor_key, f)
                .clamp(0.0, 1.0);
        }

        let atom_f0 = self
            .marginal_cdf_at(condition, corridor_key, 0.0)
            .clamp(0.0, 1.0);

        let (mean_f, variance_f) = moments_from_cdf(&cdf, atom_f0);

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

    /// Equally-weighted mixture of several channel-conditional laws.
    ///
    /// This is the UPC cohort's birth law: a store reading pooled codes receives every
    /// lot's delivery record but cannot attribute any of them to a pallet, so its belief
    /// about a unit is the mixture `(1/L) Σ_ℓ Law(record_ℓ)` rather than a per-segment law.
    /// Mixing the *laws* — not averaging the pack dates — is what preserves the
    /// between-lot spread: a mixture's variance picks up the dispersion of the component
    /// means, which averaging the dates first would discard.
    ///
    /// Built by averaging the component CDFs pointwise, so it reuses each component's
    /// existing cache entry rather than integrating anything new. Mean and variance are
    /// recomputed from the mixed CDF, never averaged from the components.
    pub fn mixture_law(&mut self, conditions: &[ArrivalCondition]) -> ArrivalRungLaw {
        if conditions.is_empty() {
            return self.rung_law_on_grid(
                ArrivalCondition::Prior,
                &self.active_corridor.clone(),
                ARRIVAL_GRID,
            );
        }
        let caches: Vec<ArrivalCdfCache> = conditions.iter().map(|&c| self.law_cdf(c)).collect();
        let inv = 1.0 / caches.len() as f64;

        let atom_f0: f64 = caches.iter().map(|c| c.atom_f0).sum::<f64>() * inv;
        let mut cdf = vec![0.0; ARRIVAL_GRID];
        for cache in &caches {
            let scale = 1.0 - cache.atom_f0;
            for (slot, &c) in cdf.iter_mut().zip(cache.cdf.iter()) {
                // Undo the atom division to recover each component's raw CDF before mixing.
                *slot += inv * (cache.atom_f0 + scale * c);
            }
        }
        for slot in &mut cdf {
            *slot = slot.clamp(0.0, 1.0);
        }

        let (mean_f, variance_f) = moments_from_cdf(&cdf, atom_f0);
        ArrivalRungLaw {
            cdf,
            atom_f0,
            mean_f,
            sd_f: variance_f.sqrt(),
        }
    }

    /// Atom-divided, sampleable form of `mixture_law`, for birthing a UPC cohort.
    pub fn mixture_cache(&mut self, conditions: &[ArrivalCondition]) -> ArrivalCdfCache {
        let law = self.mixture_law(conditions);
        let denom = (1.0 - law.atom_f0).max(1e-12);
        ArrivalCdfCache {
            cdf: law
                .cdf
                .iter()
                .map(|&c| ((c - law.atom_f0) / denom).clamp(0.0, 1.0))
                .collect(),
            atom_f0: law.atom_f0,
            mean_f: law.mean_f,
            variance_f: law.sd_f * law.sd_f,
        }
    }

    /// Draw `n` iid arrival freshness values from an equally-weighted mixture of channel
    /// conditions — the UPC-cohort counterpart of `sample_filter_birth_units`.
    pub fn sample_filter_birth_units_mixture<R: Rng + ?Sized>(
        &mut self,
        conditions: &[ArrivalCondition],
        n: usize,
        rng: &mut R,
    ) -> Vec<f64> {
        let cache = self.mixture_cache(conditions);
        (0..n)
            .map(|_| self.sample_unit_f_from_cache(&cache, rng))
            .collect()
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
        let key = PriorCdfBuildKey::from_params(params, self);
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

/// Split a delivery quantity across `n_lots` positive integers that sum to `total`.
pub fn split_delivery_qty(total: usize, n_lots: usize) -> Vec<u32> {
    let n = n_lots.max(1);
    let base = total / n;
    let rem = total % n;
    (0..n)
        .map(|i| (base + if i < rem { 1 } else { 0 }) as u32)
        .collect()
}

/// Append `shared` onto the end of `upstream`, shifting shared times by the upstream span.
pub fn splice_shipment_traces(upstream: &ShipmentTrace, shared: &ShipmentTrace) -> ShipmentTrace {
    let junction = upstream.times_d.last().copied().unwrap_or(0.0);
    splice_shipment_traces_at(upstream, junction, shared)
}

/// Splice `shared` so its sample times begin at `junction_d` (identical DC→store tail).
pub fn splice_shipment_traces_at(
    upstream: &ShipmentTrace,
    junction_d: f64,
    shared: &ShipmentTrace,
) -> ShipmentTrace {
    let mut times = upstream.times_d.clone();
    let mut temps = upstream.temps_c.clone();
    if times.is_empty() {
        times.push(0.0);
        temps.push(shared.temps_c.first().copied().unwrap_or(0.0));
    }
    let skip = if shared.times_d.first().copied().unwrap_or(0.0) <= 1e-12 {
        1
    } else {
        0
    };
    for (i, &t) in shared.times_d.iter().enumerate().skip(skip) {
        times.push(junction_d + t);
        temps.push(shared.temps_c[i]);
    }
    if times.len() < 2 {
        times.push(junction_d.max(1e-6));
        temps.push(temps.last().copied().unwrap_or(0.0));
    }
    ShipmentTrace { times_d: times, temps_c: temps }
}

fn offset_trace_from(shared: &ShipmentTrace, start_d: f64) -> ShipmentTrace {
    ShipmentTrace {
        times_d: shared.times_d.iter().map(|&t| start_d + t).collect(),
        temps_c: shared.temps_c.clone(),
    }
}

/// Map an upstream profile on `[0, upstream_d]` onto `[junction-upstream_d, junction]` and
/// append the shared DC→store leg on `[junction, t_end]`.
fn splice_upstream_before_shared(
    upstream: &ShipmentTrace,
    upstream_d: f64,
    junction_d: f64,
    shared: &ShipmentTrace,
) -> ShipmentTrace {
    let start = (junction_d - upstream_d).max(0.0);
    let up_span = upstream.times_d.last().copied().unwrap_or(upstream_d).max(1e-9);
    let mut times = Vec::new();
    let mut temps = Vec::new();
    for (&t, &temp) in upstream.times_d.iter().zip(upstream.temps_c.iter()) {
        times.push(start + (t / up_span) * upstream_d);
        temps.push(temp);
    }
    if times.last().copied().unwrap_or(0.0) < junction_d - 1e-9 {
        times.push(junction_d);
        temps.push(*temps.last().unwrap_or(&0.0));
    }
    let skip = if shared.times_d.first().copied().unwrap_or(0.0) <= 1e-12 {
        1
    } else {
        0
    };
    for (i, &t) in shared.times_d.iter().enumerate().skip(skip) {
        times.push(junction_d + t);
        temps.push(shared.temps_c[i]);
    }
    ShipmentTrace { times_d: times, temps_c: temps }
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
