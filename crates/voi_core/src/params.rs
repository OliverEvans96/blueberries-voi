//! MOD-12 model parameters (Python `model.params.ModelParams`).

use crate::arrival::DEFAULT_ARRIVAL_CORRIDOR;
use crate::demand_profile::DemandProfile;

/// Default virtual lot slots on the f-native `L×U` filter grid (ADR 0130).
pub const DEFAULT_L_DIM: usize = 50;

/// Default virtual units per lot on the f-native `L×U` grid (ADR 0130).
pub const DEFAULT_UNITS_PER_LOT: usize = 15;

/// The one struct holding every tunable default for the simulation: aging physics,
/// demand, picking behavior, and ordering mechanics. Mirrors Python's
/// `model.params.ModelParams` so the two hosts stay parameter-for-parameter identical.
#[derive(Clone, Debug)]
pub struct ModelParams {
    /// Weibull shape parameter for the terminal-salvage survival weight `w_long`
    /// (ADR 0061) — a separate valuation of remaining shelf life at the horizon's end,
    /// not part of the Gamma freshness/spoilage model itself.
    pub beta: f64,
    /// Reference shelf life in days. Anchors `gamma_scale`'s derivation
    /// (`set_reference_life`) and the legacy age↔freshness conversions
    /// (`age_to_f`/`f_to_age`).
    pub eta_ref: f64,
    /// Q10 temperature factor: the multiplier on degradation rate per 10°C above
    /// `t_ref_c`.
    pub q10: f64,
    /// Reference temperature (°C) at which the Q10 factor is 1.
    pub t_ref_c: f64,
    /// Store holding temperature (°C) actually driving the Q10 factor.
    pub t_store_c: f64,
    /// Freshness-weighting exponent for picking: units are drawn with weight
    /// proportional to `max(f, 0)^sigma`, so larger `sigma` biases picking toward
    /// fresher stock. Ignored when `uniform_picking` is set.
    pub sigma: f64,
    /// Legacy constant mean daily demand, used only when `demand_profile` is `None`.
    pub demand_mu: f64,
    /// Variance-to-mean ratio for the negative-binomial demand noise (ADR 0113).
    pub demand_vm: f64,
    /// Units per case; orders are rounded to multiples of this (`case_round`).
    pub case_size: u32,
    /// When true, picking ignores freshness entirely and draws units uniformly at
    /// random instead of freshness-weighted.
    pub uniform_picking: bool,
    /// Optional calendar demand profile; when set, overrides `demand_mu`/`demand_vm`
    /// with a day-of-week/week-varying mean and its matched variance-to-mean ratio.
    pub demand_profile: Option<DemandProfile>,
    /// Gamma aging shape (daily freshness decrement draw).
    pub gamma_shape: f64,
    /// Gamma aging scale before store-temperature Q10 factor.
    pub gamma_scale: f64,
    /// Fixed virtual grid width per lot (`L×U` truth).
    pub units_per_lot: usize,
    /// Corridor key into the embedded arrival artifact's `corridors` map (T-150 finding
    /// 4). Threaded through to both the truth-path draw and the filter prior so they
    /// can never silently diverge onto different corridors.
    pub arrival_product: String,
}

impl Default for ModelParams {
    fn default() -> Self {
        let mut params = Self {
            beta: 2.0,
            eta_ref: 14.0,
            q10: 2.0,
            t_ref_c: 0.0,
            t_store_c: 4.0,
            sigma: 0.5,
            demand_mu: 30.0,
            demand_vm: 2.0,
            case_size: 8,
            uniform_picking: false,
            demand_profile: None,
            gamma_shape: 2.0,
            gamma_scale: 0.0,
            units_per_lot: DEFAULT_UNITS_PER_LOT,
            arrival_product: DEFAULT_ARRIVAL_CORRIDOR.to_string(),
        };
        params.set_reference_life();
        params
    }
}

impl ModelParams {
    /// Derive `gamma_scale` from `gamma_shape` and `eta_ref` so `k·θ·η_ref = 1`.
    pub fn set_reference_life(&mut self) {
        if self.gamma_shape > 0.0 && self.eta_ref > 0.0 {
            self.gamma_scale = 1.0 / (self.gamma_shape * self.eta_ref);
        }
    }

    /// Resolve NB mean: profile μ(day) when configured, else legacy constant μ.
    pub fn demand_mu_for_day(&self, day: u32) -> f64 {
        if let Some(ref profile) = self.demand_profile {
            profile.mu(day)
        } else {
            self.demand_mu
        }
    }

    /// Wire a calendar profile and sync ``demand_vm`` (matches ``session`` / ADR 0113).
    pub fn apply_demand_profile(&mut self, profile: DemandProfile) {
        self.demand_vm = profile.demand_vm();
        self.demand_profile = Some(profile);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EMBEDDED_JSON: &str =
        include_str!("../../../data/freshnet/demand_profile.json");

    #[test]
    fn demand_mu_for_day_legacy_constant() {
        let params = ModelParams::default();
        assert!((params.demand_mu_for_day(7) - 30.0).abs() <= 1e-9);
    }

    #[test]
    fn demand_mu_for_day_profile_backed() {
        let profile = DemandProfile::from_json(EMBEDDED_JSON).expect("embedded profile");
        let mut params = ModelParams::default();
        params.apply_demand_profile(profile.clone());
        assert!((params.demand_vm - profile.demand_vm()).abs() <= 1e-9);
        assert!((params.demand_mu_for_day(7) - profile.mu(7)).abs() <= 1e-9);
        assert!((params.demand_mu_for_day(0) - profile.mu(0)).abs() <= 1e-9);
    }
}
