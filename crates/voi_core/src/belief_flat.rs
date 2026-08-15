//! Flatten a `ParticleBank` onto the Snapshot `L×K` belief wire (ADR 0106 / 0126).
//! Production flattening is T-117 I2 — stub returns an empty grid so tests stay RED.

use serde_json::Value;

use crate::rbpf::ParticleBank;

/// Weighted lot counts + age histograms on a fixed `L×K` grid (`tau` in `[0, 8]`).
pub fn particle_bank_to_flat(_bank: &ParticleBank, _l: usize, _k: usize) -> Value {
    serde_json::json!({
        "lot_counts": [],
        "age_marginals": [],
        "tau_grid": [],
        "L": 0,
        "K": 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ParticleBank;

    fn tau_grid_k(k: usize) -> Vec<f64> {
        if k <= 1 {
            return vec![0.0; k];
        }
        (0..k)
            .map(|i| 8.0 * (i as f64) / ((k - 1) as f64))
            .collect()
    }

    fn nearest_bin(tau: f64, grid: &[f64]) -> usize {
        grid.iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| (*a - tau).abs().partial_cmp(&(*b - tau).abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }

    #[test]
    fn empty_bank_pads_l_by_k_zero_counts() {
        let bank = ParticleBank {
            weights: vec![],
            counts: vec![],
            taus: vec![],
        };
        let v = particle_bank_to_flat(&bank, 2, 4);
        assert_eq!(v["L"], 2);
        assert_eq!(v["K"], 4);
        assert_eq!(v["lot_counts"].as_array().unwrap().len(), 2);
        assert_eq!(v["age_marginals"].as_array().unwrap().len(), 8);
        assert_eq!(v["tau_grid"].as_array().unwrap().len(), 4);
        for c in v["lot_counts"].as_array().unwrap() {
            assert_eq!(c.as_f64().unwrap(), 0.0);
        }
    }

    #[test]
    fn weighted_lot_counts_and_age_histogram() {
        let bank = ParticleBank {
            weights: vec![0.25, 0.75],
            counts: vec![vec![4, 0], vec![0, 8]],
            taus: vec![vec![0.0, 8.0], vec![0.0, 8.0]],
        };
        let k = 3usize;
        let v = particle_bank_to_flat(&bank, 2, k);
        assert_eq!(v["L"], 2);
        assert_eq!(v["K"], 3);
        let counts: Vec<f64> = v["lot_counts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert!((counts[0] - (0.25 * 4.0 + 0.75 * 0.0)).abs() < 1e-9);
        assert!((counts[1] - (0.25 * 0.0 + 0.75 * 8.0)).abs() < 1e-9);

        let grid = tau_grid_k(k);
        let ages: Vec<f64> = v["age_marginals"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert_eq!(ages.len(), 2 * k);
        let bin0 = nearest_bin(0.0, &grid);
        let bin8 = nearest_bin(8.0, &grid);
        // Lot 0 mass only from particle 0 at tau=0; lot 1 from particle 1 at tau=8.
        let row0: f64 = ages.iter().take(k).sum();
        let row1: f64 = ages.iter().skip(k).take(k).sum();
        assert!((row0 - 1.0).abs() < 1e-6 || counts[0] == 0.0);
        assert!((row1 - 1.0).abs() < 1e-6 || counts[1] == 0.0);
        if counts[0] > 0.0 {
            assert!(ages[bin0] > 0.5);
        }
        if counts[1] > 0.0 {
            assert!(ages[k + bin8] > 0.5);
        }
    }

    #[test]
    fn truncates_or_pads_to_l() {
        let bank = ParticleBank {
            weights: vec![1.0],
            counts: vec![vec![1, 2, 3]],
            taus: vec![vec![1.0, 2.0, 3.0]],
        };
        let short = particle_bank_to_flat(&bank, 2, 4);
        assert_eq!(short["L"], 2);
        assert_eq!(short["lot_counts"].as_array().unwrap().len(), 2);
        assert_eq!(short["age_marginals"].as_array().unwrap().len(), 8);

        let long = particle_bank_to_flat(&bank, 5, 4);
        assert_eq!(long["L"], 5);
        assert_eq!(long["lot_counts"].as_array().unwrap().len(), 5);
        let pad = long["lot_counts"][4].as_f64().unwrap();
        assert_eq!(pad, 0.0);
    }
}
