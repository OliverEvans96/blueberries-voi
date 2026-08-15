//! MOD-12 model parameters (Python `model.params.ModelParams`).

use crate::demand_profile::DemandProfile;

#[derive(Clone, Debug)]
pub struct ModelParams {
    pub beta: f64,
    pub eta_ref: f64,
    pub q10: f64,
    pub t_ref_c: f64,
    pub t_store_c: f64,
    pub sigma: f64,
    pub demand_mu: f64,
    pub demand_vm: f64,
    pub case_size: u32,
    pub uniform_picking: bool,
    pub demand_profile: Option<DemandProfile>,
}

impl Default for ModelParams {
    fn default() -> Self {
        Self {
            beta: 2.0,
            eta_ref: 14.0,
            q10: 3.0,
            t_ref_c: 0.0,
            t_store_c: 4.0,
            sigma: 0.5,
            demand_mu: 30.0,
            demand_vm: 2.0,
            case_size: 8,
            uniform_picking: false,
            demand_profile: None,
        }
    }
}

impl ModelParams {
    /// Resolve NB mean: profile μ(day) when configured, else legacy constant μ.
    pub fn demand_mu_for_day(&self, day: u32) -> f64 {
        if let Some(ref profile) = self.demand_profile {
            profile.mu(day)
        } else {
            self.demand_mu
        }
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
        let params = ModelParams {
            demand_profile: Some(profile.clone()),
            ..ModelParams::default()
        };
        assert!((params.demand_mu_for_day(7) - profile.mu(7)).abs() <= 1e-9);
        assert!((params.demand_mu_for_day(0) - profile.mu(0)).abs() <= 1e-9);
    }
}
