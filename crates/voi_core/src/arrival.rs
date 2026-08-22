//! Hierarchical arrival freshness model in f-space (ADR 0144 / T-150).

use std::collections::HashMap;
use std::fmt;

use rand::Rng;
use rand_distr::{Distribution, Gamma, LogNormal, Normal};
use serde::Deserialize;

use crate::physics::{gamma_p, gamma_q, store_temp_factor};
use crate::params::ModelParams;

const EMBEDDED_ARRIVAL_JSON: &str = include_str!("../../../data/abdella/arrival_model.json");
const SUPPORTED_SCHEMA_VERSION: u64 = 1;
const LAMBDA_FLOOR: f64 = 1e-12;
const ARRIVAL_GRID: usize = 4096;

pub const STREAM_ARRIVAL_DURATION: &str = ":arrival_duration";
pub const STREAM_ARRIVAL_TEMP: &str = ":arrival_temp";
pub const STREAM_ARRIVAL_POS: &str = ":arrival_pos";
pub const STREAM_ARRIVAL_GAMMA: &str = ":arrival_gamma";

#[derive(Debug)]
pub enum ArrivalModelError {
    Json(serde_json::Error),
    Invalid(String),
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

#[derive(Clone, Debug)]
pub struct TruthDeliveryDraw {
    pub unit_f: Vec<f64>,
    pub pack_date_days: i32,
    pub duration_d: f64,
    pub t_bar: f64,
    pub phi_bar: f64,
}

#[derive(Clone, Debug)]
pub struct ArrivalCorridor {
    pub d_min: f64,
    pub delay_shape: f64,
    pub delay_scale: f64,
    pub mix_weight: f64,
}

#[derive(Clone, Debug)]
pub struct ArrivalModel {
    pub schema_version: u64,
    pub corridors: HashMap<String, ArrivalCorridor>,
    pub default_corridor: String,
    pub mu_t: f64,
    pub sigma_t: f64,
    pub temp_floor_c: f64,
    pub sigma_pos: f64,
    pub q10: f64,
    pub t_ref: f64,
    pub gamma_shape: f64,
    pub gamma_scale: f64,
    pub reference_life_days: f64,
    pub quad_nodes: Vec<f64>,
    pub quad_weights: Vec<f64>,
    marginal_cdf: ArrivalCdfCache,
    f2_cache: HashMap<i32, ArrivalCdfCache>,
    f3_cache: HashMap<u64, ArrivalCdfCache>,
}

#[derive(Clone, Debug)]
struct ArrivalCdfCache {
    cdf: Vec<f64>,
    atom_f0: f64,
    mean_f: f64,
    variance_f: f64,
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
    #[serde(default = "default_mix_weight")]
    mix_weight: f64,
}

fn default_mix_weight() -> f64 {
    1.0
}

/// Single embed accessor for the committed arrival artifact.
pub fn embedded_arrival_model() -> &'static str {
    EMBEDDED_ARRIVAL_JSON
}

pub fn arrival_artifact_from_json(json: &str) -> Result<ArrivalModel, ArrivalModelError> {
    ArrivalModel::from_json(json)
}

impl ArrivalModel {
    pub fn embedded() -> Self {
        Self::from_json(EMBEDDED_ARRIVAL_JSON).expect("embedded arrival artifact")
    }

    pub fn from_json(json: &str) -> Result<Self, ArrivalModelError> {
        let raw: ArrivalModelJson =
            serde_json::from_str(json).map_err(ArrivalModelError::Json)?;
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
            return Err(ArrivalModelError::Invalid("corridors must be non-empty".into()));
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
                        mix_weight: c.mix_weight,
                    },
                )
            })
            .collect();
        let mut model = Self {
            schema_version: raw.schema_version,
            corridors,
            default_corridor,
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
            marginal_cdf: ArrivalCdfCache::empty(),
            f2_cache: HashMap::new(),
            f3_cache: HashMap::new(),
        };
        model.marginal_cdf = model.build_marginal_cdf(None, None);
        Ok(model)
    }

    pub fn corridor(&self, product: &str) -> &ArrivalCorridor {
        self.corridors
            .get(product)
            .or_else(|| self.corridors.get(&self.default_corridor))
            .expect("arrival corridor")
    }

    pub fn phi_bar_from_t_bar(&self, t_bar: f64) -> f64 {
        store_temp_factor(t_bar, self.t_ref, self.q10)
    }

    pub fn floor_lambda(lambda: f64) -> f64 {
        // floor Λ before forming Gamma(kΛ, θ) — ill-conditioned at Λ → 0.
        lambda.max(LAMBDA_FLOOR)
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

    fn expected_delay(corridor: &ArrivalCorridor) -> f64 {
        corridor.d_min + corridor.delay_shape * corridor.delay_scale
    }

    fn sample_truncated_normal<R: Rng + ?Sized>(
        &self,
        rng: &mut R,
    ) -> f64 {
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

    fn build_marginal_cdf(
        &self,
        pack_date_days: Option<i32>,
        phi_bar: Option<f64>,
    ) -> ArrivalCdfCache {
        let mut mean_acc = 0.0;
        let mut mean_sq_acc = 0.0;
        let mut mass_acc = 0.0;

        let corridor_keys: Vec<&String> = self.corridors.keys().collect();
        let mix_total: f64 = corridor_keys
            .iter()
            .map(|k| self.corridors[*k].mix_weight)
            .sum::<f64>()
            .max(1e-12);

        let mut cdf = vec![0.0; ARRIVAL_GRID];
        for gi in 0..ARRIVAL_GRID {
            let f = gi as f64 / (ARRIVAL_GRID - 1) as f64;
            let mut p = 0.0;
            for key in &corridor_keys {
                let corridor = &self.corridors[*key];
                let w_corr = corridor.mix_weight / mix_total;
                for (&node, &weight) in self.quad_nodes.iter().zip(self.quad_weights.iter()) {
                    let d = if let Some(pd) = pack_date_days {
                        f64::from(pd).max(0.0)
                    } else {
                        let delay_mean = Self::expected_delay(corridor);
                        let delay_span = corridor.delay_scale * 2.0;
                        (corridor.d_min + delay_mean + delay_span * (2.0 * node - 1.0)).max(0.0)
                    };
                    let phi = if let Some(pb) = phi_bar {
                        pb
                    } else {
                        let t_span = self.sigma_t * 2.5;
                        let t_bar =
                            (self.mu_t + t_span * (2.0 * node - 1.0)).max(self.temp_floor_c);
                        self.phi_bar_from_t_bar(t_bar)
                    };
                    let lambda = Self::floor_lambda(d * phi);
                    let lam = lambda;
                    p += w_corr * weight * self.cdf_f_given_lambda(lam, f);
                }
            }
            cdf[gi] = p.clamp(0.0, 1.0);
        }
        for gi in 1..ARRIVAL_GRID {
            let f = gi as f64 / (ARRIVAL_GRID - 1) as f64;
            let f_prev = (gi - 1) as f64 / (ARRIVAL_GRID - 1) as f64;
            let bin_mass = (cdf[gi] - cdf[gi - 1]).max(0.0);
            let f_mid = 0.5 * (f + f_prev);
            mean_acc += f_mid * bin_mass;
            mean_sq_acc += f_mid * f_mid * bin_mass;
            mass_acc += bin_mass;
        }

        let representative_lambda = {
            let corridor = self.corridor(&self.default_corridor);
            let d = pack_date_days
                .map(f64::from)
                .unwrap_or_else(|| Self::expected_delay(corridor));
            let phi = phi_bar.unwrap_or_else(|| self.phi_bar_from_t_bar(self.mu_t));
            Self::floor_lambda(d * phi)
        };
        let atom_acc = self.p_f_zero(representative_lambda);
        if mass_acc > 0.0 {
            mean_acc /= mass_acc;
            mean_sq_acc /= mass_acc;
        }
        let variance = (mean_sq_acc - mean_acc * mean_acc).max(0.0);

        ArrivalCdfCache {
            cdf,
            atom_f0: atom_acc,
            mean_f: mean_acc,
            variance_f: variance,
        }
    }

    fn marginal_cache(&self) -> &ArrivalCdfCache {
        &self.marginal_cdf
    }

    pub fn variance_f_given_d(&mut self, d_days: i32) -> f64 {
        if !self.f2_cache.contains_key(&d_days) {
            let cache = self.build_marginal_cdf(Some(d_days), None);
            self.f2_cache.insert(d_days, cache);
        }
        self.f2_cache.get(&d_days).unwrap().variance_f
    }

    pub fn variance_f_given_phi_bar(&mut self, phi_bar: f64) -> f64 {
        let key = (phi_bar * 1_000_000.0).round() as u64;
        if !self.f3_cache.contains_key(&key) {
            let cache = self.build_marginal_cdf(None, Some(phi_bar));
            self.f3_cache.insert(key, cache);
        }
        self.f3_cache.get(&key).unwrap().variance_f
    }

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

    pub fn sample_filter_birth_units<R: Rng + ?Sized>(
        &mut self,
        pack_date_days: Option<i32>,
        phi_bar: Option<f64>,
        n: usize,
        rng: &mut R,
    ) -> Vec<f64> {
        let cache = if let Some(pb) = phi_bar {
            let key = (pb * 1_000_000.0).round() as u64;
            if !self.f3_cache.contains_key(&key) {
                let built = self.build_marginal_cdf(None, Some(pb));
                self.f3_cache.insert(key, built);
            }
            self.f3_cache.get(&key).unwrap().clone()
        } else if let Some(d) = pack_date_days {
            if !self.f2_cache.contains_key(&d) {
                let built = self.build_marginal_cdf(Some(d), None);
                self.f2_cache.insert(d, built);
            }
            self.f2_cache.get(&d).unwrap().clone()
        } else {
            self.marginal_cdf.clone()
        };
        (0..n)
            .map(|_| self.sample_unit_f_from_cache(&cache, rng))
            .collect()
    }

    pub fn marginal_variance_f(&self) -> f64 {
        self.marginal_cdf.variance_f
    }

    pub fn sync_params(&mut self, params: &ModelParams) {
        self.gamma_shape = params.gamma_shape;
        self.gamma_scale = params.gamma_scale;
        self.q10 = params.q10;
        self.t_ref = params.t_ref_c;
        self.reference_life_days = params.eta_ref;
        self.marginal_cdf = self.build_marginal_cdf(None, None);
        self.f2_cache.clear();
        self.f3_cache.clear();
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

/// Channel-conditional arrival law resolution for the filter birth step.
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
    fn monotone_ladder_variance_strict() {
        let mut model = ArrivalModel::embedded();
        let var_marg = model.marginal_variance_f();
        let var_d = model.variance_f_given_d(4);
        let phi = model.phi_bar_from_t_bar(2.7);
        let var_phi = model.variance_f_given_phi_bar(phi);
        assert!(var_phi < var_d, "var_phi={var_phi} var_d={var_d}");
        assert!(var_d < var_marg, "var_d={var_d} var_marg={var_marg}");
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
