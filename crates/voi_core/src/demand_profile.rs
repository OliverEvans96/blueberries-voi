//! FreshNet calendar demand profile (ADR 0113 / T-121 C1).
//!
//! μ(day) = scale_target_mu * dow_factors[day % 7] * week_factors[min(day // 7, W-1)]

use serde::Deserialize;
use std::fmt;

#[derive(Clone, Debug, PartialEq)]
pub struct DemandProfile {
    scale_target_mu: f64,
    dow_factors: [f64; 7],
    week_factors: Vec<f64>,
    demand_vm: f64,
}

#[derive(Debug)]
pub enum DemandProfileError {
    Json(serde_json::Error),
    Invalid(String),
}

impl fmt::Display for DemandProfileError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Json(err) => write!(f, "{err}"),
            Self::Invalid(msg) => f.write_str(msg),
        }
    }
}

impl std::error::Error for DemandProfileError {}

#[derive(Deserialize)]
struct DemandProfileJson {
    scale_target_mu: f64,
    dow_factors: Vec<f64>,
    week_factors: Vec<f64>,
    #[serde(default = "default_demand_vm")]
    demand_vm: f64,
}

fn default_demand_vm() -> f64 {
    2.0
}

impl DemandProfile {
    pub fn from_json(json: &str) -> Result<Self, DemandProfileError> {
        let raw: DemandProfileJson =
            serde_json::from_str(json).map_err(DemandProfileError::Json)?;
        Self::from_parsed(raw)
    }

    pub fn from_parts(
        scale_target_mu: f64,
        dow_factors: [f64; 7],
        week_factors: Vec<f64>,
        demand_vm: f64,
    ) -> Result<Self, DemandProfileError> {
        Self::from_parsed(DemandProfileJson {
            scale_target_mu,
            dow_factors: dow_factors.to_vec(),
            week_factors,
            demand_vm,
        })
    }

    fn from_parsed(raw: DemandProfileJson) -> Result<Self, DemandProfileError> {
        if raw.dow_factors.len() != 7 {
            return Err(DemandProfileError::Invalid(
                "dow_factors must have length 7 (monday0)".into(),
            ));
        }
        if raw.week_factors.is_empty() {
            return Err(DemandProfileError::Invalid(
                "week_factors must be non-empty".into(),
            ));
        }
        if raw.scale_target_mu <= 0.0 {
            return Err(DemandProfileError::Invalid(
                "scale_target_mu must be positive".into(),
            ));
        }
        let mut dow_factors = [0.0; 7];
        for (slot, value) in dow_factors.iter_mut().zip(raw.dow_factors) {
            *slot = value;
        }
        Ok(Self {
            scale_target_mu: raw.scale_target_mu,
            dow_factors,
            week_factors: raw.week_factors,
            demand_vm: raw.demand_vm,
        })
    }

    pub fn mu(&self, day: u32) -> f64 {
        let dow = (day % 7) as usize;
        let week_cap = self.week_factors.len().saturating_sub(1) as u32;
        let week = (day / 7).min(week_cap) as usize;
        self.scale_target_mu * self.dow_factors[dow] * self.week_factors[week]
    }

    pub fn demand_vm(&self) -> f64 {
        self.demand_vm
    }

    pub fn scale_target_mu(&self) -> f64 {
        self.scale_target_mu
    }

    /// Chart-ready DOW means (scale × dow factor); week factors omitted.
    pub fn dow_means(&self) -> [f64; 7] {
        std::array::from_fn(|i| self.scale_target_mu * self.dow_factors[i])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EMBEDDED_JSON: &str =
        include_str!("../../../data/freshnet/demand_profile.json");

    fn committed_profile() -> DemandProfile {
        DemandProfile::from_json(EMBEDDED_JSON).expect("embedded profile")
    }

    fn committed_profile_from_file() -> DemandProfile {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../data/freshnet/demand_profile.json"
        );
        let json = std::fs::read_to_string(path).expect("read committed profile");
        DemandProfile::from_json(&json).expect("parse committed profile")
    }

    #[test]
    fn from_json_parses_committed_file() {
        let profile = committed_profile_from_file();
        assert!((profile.mu(0) - 24.318_236_947_2).abs() <= 1e-9);
        assert_eq!(profile.demand_vm(), 2.0);
    }

    #[test]
    fn mu_matches_golden_days_embedded() {
        let profile = committed_profile();
        let expected = [
            (0_u32, 24.318_236_947_2),
            (6, 29.483_144_295_36),
            (7, 23.696_669_026_8),
            (13, 28.729_562_663_34),
            (89, 47.547_434_176_8),
        ];
        for (day, want) in expected {
            let got = profile.mu(day);
            assert!(
                (got - want).abs() <= 1e-9,
                "mu({day})={got} expected {want}"
            );
        }
    }

    #[test]
    fn from_json_rejects_bad_dow_length() {
        let err = DemandProfile::from_json(
            r#"{"scale_target_mu":1.0,"dow_factors":[1.0],"week_factors":[1.0]}"#,
        )
        .unwrap_err();
        assert!(err.to_string().contains("dow_factors"));
    }
}
