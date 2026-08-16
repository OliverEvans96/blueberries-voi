//! Flatten a `ParticleBank` onto the Snapshot `L×K` belief wire (ADR 0106 / 0126).

use serde_json::Value;

use crate::particle_filter::ParticleBank;
use crate::unit_pf::UnitParticleBank;

const AGE_GRID_LO: f64 = 0.0;
const AGE_GRID_HI: f64 = 8.0;

fn tau_grid_k(k: usize) -> Vec<f64> {
    if k == 0 {
        return Vec::new();
    }
    if k == 1 {
        return vec![AGE_GRID_LO];
    }
    (0..k)
        .map(|i| AGE_GRID_LO + (AGE_GRID_HI - AGE_GRID_LO) * (i as f64) / ((k - 1) as f64))
        .collect()
}

fn nearest_bin(tau: f64, grid: &[f64]) -> usize {
    grid.iter()
        .enumerate()
        .min_by(|(_, a), (_, b)| (*a - tau).abs().partial_cmp(&(*b - tau).abs()).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0)
}

/// Weighted MF lot counts + age marginals on the snapshot `L×K` grid.
#[derive(Clone, Debug)]
pub struct BeliefMean {
    pub lot_counts: Vec<f64>,
    pub age_marginals: Vec<f64>,
    pub tau_grid: Vec<f64>,
}

impl BeliefMean {
    pub fn empty(l: usize, k: usize) -> Self {
        let grid = tau_grid_k(k);
        let uniform = if k > 0 { 1.0 / k as f64 } else { 0.0 };
        Self {
            lot_counts: vec![0.0; l],
            age_marginals: vec![uniform; l.saturating_mul(k.max(1))],
            tau_grid: grid,
        }
    }
}

pub fn belief_mean_from_bank(bank: &ParticleBank, l: usize, k: usize) -> BeliefMean {
    let grid = tau_grid_k(k);
    let n = bank.weights.len();
    let w_sum: f64 = bank.weights.iter().sum();

    let mut lot_counts = vec![0.0; l];
    if w_sum > 0.0 {
        for slot in 0..l {
            let mut acc = 0.0;
            for i in 0..n {
                let c = bank
                    .counts
                    .get(i)
                    .and_then(|row| row.get(slot))
                    .copied()
                    .unwrap_or(0);
                acc += bank.weights[i] * f64::from(c);
            }
            lot_counts[slot] = acc / w_sum;
        }
    }

    let mut age_hist = vec![0.0; l.saturating_mul(k)];
    if k > 0 {
        for i in 0..n {
            let w = if w_sum > 0.0 { bank.weights[i] } else { 0.0 };
            if w == 0.0 {
                continue;
            }
            let taus = bank.taus.get(i).map(Vec::as_slice).unwrap_or(&[]);
            for slot in 0..l {
                let Some(&tau) = taus.get(slot) else {
                    continue;
                };
                let bin = nearest_bin(tau, &grid);
                age_hist[slot * k + bin] += w;
            }
        }
        for slot in 0..l {
            let row = &mut age_hist[slot * k..(slot + 1) * k];
            if lot_counts[slot] > 0.0 {
                let z: f64 = row.iter().sum();
                if z > 0.0 {
                    for x in row.iter_mut() {
                        *x /= z;
                    }
                } else {
                    let u = 1.0 / k as f64;
                    for x in row.iter_mut() {
                        *x = u;
                    }
                }
            } else {
                let u = 1.0 / k as f64;
                for x in row.iter_mut() {
                    *x = u;
                }
            }
        }
    }

    BeliefMean {
        lot_counts,
        age_marginals: age_hist,
        tau_grid: grid,
    }
}

/// Weighted lot counts + age histograms on a fixed `L×K` grid (`tau` in `[0, 8]`).
pub fn particle_bank_to_flat(bank: &ParticleBank, l: usize, k: usize) -> Value {
    let mean = belief_mean_from_bank(bank, l, k);
    serde_json::json!({
        "lot_counts": mean.lot_counts,
        "age_marginals": mean.age_marginals,
        "tau_grid": mean.tau_grid,
        "L": l,
        "K": k,
    })
}

/// Weighted mean lot counts and ages across particles (policy / ordering belief).
pub fn mean_bank(bank: &ParticleBank) -> (Vec<u32>, Vec<f64>) {
    if bank.counts.is_empty() {
        return (vec![], vec![]);
    }
    let l = bank.counts[0].len();
    let mean = belief_mean_from_bank(bank, l, 1);
    let taus: Vec<f64> = (0..l)
        .map(|slot| {
            let mut acc = 0.0;
            for (i, w) in bank.weights.iter().enumerate() {
                if slot < bank.taus[i].len() {
                    acc += w * bank.taus[i][slot];
                }
            }
            acc
        })
        .collect();
    (
        mean.lot_counts
            .iter()
            .map(|x| x.round().max(0.0) as u32)
            .collect(),
        taus,
    )
}

/// Freshness bin centers in `[0, 1]` for wire dimension `K`.
pub fn f_grid_k(k: usize) -> Vec<f64> {
    if k == 0 {
        return Vec::new();
    }
    if k == 1 {
        return vec![0.0];
    }
    (0..k)
        .map(|i| i as f64 / ((k - 1) as f64))
        .collect()
}

/// Flatten `UnitParticleBank` onto the f-native `L×K` belief wire (ADR 0130).
pub fn belief_flat_from_unit_bank(bank: &UnitParticleBank, l: usize, k: usize) -> Value {
    let grid = f_grid_k(k);
    let n = bank.weights.len();
    let w_sum: f64 = bank.weights.iter().sum();
    let units_per_lot = if l > 0 && !bank.freshness.is_empty() {
        bank.freshness[0].len() / l
    } else {
        0
    };

    let mut lot_counts = vec![0.0; l];
    if w_sum > 0.0 && units_per_lot > 0 {
        for slot in 0..l {
            let start = slot * units_per_lot;
            let end = start + units_per_lot;
            let mut acc = 0.0;
            for i in 0..n {
                let alive = bank
                    .freshness
                    .get(i)
                    .and_then(|row| row.get(start..end))
                    .map(|units| units.iter().filter(|&&f| f > 0.0).count() as f64)
                    .unwrap_or(0.0);
                acc += bank.weights[i] * alive;
            }
            lot_counts[slot] = acc / w_sum;
        }
    }

    let mut f_marginals = vec![0.0; l.saturating_mul(k)];
    if k > 0 {
        if w_sum > 0.0 && units_per_lot > 0 {
            for i in 0..n {
                let w = bank.weights[i];
                if w == 0.0 {
                    continue;
                }
                let freshness = bank.freshness.get(i).map(Vec::as_slice).unwrap_or(&[]);
                for slot in 0..l {
                    let start = slot * units_per_lot;
                    let end = start + units_per_lot;
                    if end > freshness.len() {
                        continue;
                    }
                    for &f in &freshness[start..end] {
                        if f > 0.0 {
                            let bin = nearest_bin(f, &grid);
                            f_marginals[slot * k + bin] += w;
                        }
                    }
                }
            }
        }
        for slot in 0..l {
            let row = &mut f_marginals[slot * k..(slot + 1) * k];
            let z: f64 = row.iter().sum();
            if z > 0.0 {
                for x in row.iter_mut() {
                    *x /= z;
                }
            } else {
                let u = 1.0 / k as f64;
                for x in row.iter_mut() {
                    *x = u;
                }
            }
        }
    }

    serde_json::json!({
        "f_grid": grid,
        "f_marginals": f_marginals,
        "lot_counts": lot_counts,
        "L": l,
        "K": k,
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
    fn mean_bank_empty_returns_empty_vecs() {
        let bank = ParticleBank {
            weights: vec![],
            counts: vec![],
            taus: vec![],
        };
        let (counts, taus) = mean_bank(&bank);
        assert!(counts.is_empty());
        assert!(taus.is_empty());
    }

    #[test]
    fn mean_bank_weighted_mean_rounds_counts() {
        let bank = ParticleBank {
            weights: vec![0.25, 0.75],
            counts: vec![vec![4, 0], vec![0, 8]],
            taus: vec![vec![0.0, 8.0], vec![0.0, 8.0]],
        };
        let (counts, taus) = mean_bank(&bank);
        assert_eq!(counts, vec![1, 6]);
        assert!((taus[0] - 0.0).abs() < 1e-9);
        assert!((taus[1] - 8.0).abs() < 1e-9);
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

    // --- T-C2-A AC-belief: f_grid / f_marginals / lot_counts from unit bank ---

    fn unit_bank_fixture() -> crate::unit_pf::UnitParticleBank {
        // L=2, U=3: lot0 [1,1,0], lot1 [1,0.5,0] → alive counts 2 and 2.
        UnitParticleBank {
            weights: vec![1.0],
            freshness: vec![vec![1.0, 1.0, 0.0, 1.0, 0.5, 0.0]],
        }
    }

    #[test]
    fn belief_flat_from_unit_bank_exports_f_wire_keys() {
        let bank = unit_bank_fixture();
        let v = belief_flat_from_unit_bank(&bank, 2, 3);
        assert!(v.get("f_grid").is_some(), "production wire must export f_grid");
        assert!(
            v.get("f_marginals").is_some(),
            "production wire must export f_marginals"
        );
        assert!(
            v.get("tau_grid").is_none(),
            "f-native wire must not export tau_grid"
        );
        assert!(
            v.get("age_marginals").is_none(),
            "f-native wire must not export age_marginals"
        );
    }

    #[test]
    fn belief_flat_from_unit_bank_f_grid_in_unit_interval() {
        let bank = unit_bank_fixture();
        let k = 4usize;
        let v = belief_flat_from_unit_bank(&bank, 2, k);
        let grid: Vec<f64> = v["f_grid"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert_eq!(grid.len(), k);
        assert!((grid[0] - 0.0).abs() < 1e-12);
        assert!((grid[k - 1] - 1.0).abs() < 1e-12);
        for &f in &grid {
            assert!((0.0..=1.0).contains(&f), "f_grid[{f}] out of [0,1]");
        }
    }

    #[test]
    fn belief_flat_from_unit_bank_lot_counts_are_alive_only() {
        let bank = unit_bank_fixture();
        let v = belief_flat_from_unit_bank(&bank, 2, 3);
        let counts: Vec<f64> = v["lot_counts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert_eq!(counts.len(), 2);
        assert!((counts[0] - 2.0).abs() < 1e-9);
        assert!((counts[1] - 2.0).abs() < 1e-9);
    }

    #[test]
    fn belief_flat_from_unit_bank_marginals_row_major_and_normalized() {
        let bank = unit_bank_fixture();
        let k = 3usize;
        let v = belief_flat_from_unit_bank(&bank, 2, k);
        let margs: Vec<f64> = v["f_marginals"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert_eq!(margs.len(), 2 * k);
        for ell in 0..2 {
            let row: f64 = margs[ell * k..(ell + 1) * k].iter().sum();
            assert!((row - 1.0).abs() < 1e-9, "lot {ell} marginal must sum to 1");
        }
        // lot0: both alive units at f=1 → last bin.
        assert!((margs[2] - 1.0).abs() < 1e-9);
        // lot1: f=1 and f=0.5 → bins 2 and 1 on grid [0, 0.5, 1].
        assert!((margs[3 + 1] - 0.5).abs() < 1e-9);
        assert!((margs[3 + 2] - 0.5).abs() < 1e-9);
    }

    #[test]
    fn belief_flat_from_unit_bank_empty_bank_zero_counts_uniform_marginals() {
        let bank = crate::unit_pf::UnitParticleBank {
            weights: vec![],
            freshness: vec![],
        };
        let k = 4usize;
        let v = belief_flat_from_unit_bank(&bank, 2, k);
        assert_eq!(v["L"], 2);
        assert_eq!(v["K"], k);
        for c in v["lot_counts"].as_array().unwrap() {
            assert_eq!(c.as_f64().unwrap(), 0.0);
        }
        let margs: Vec<f64> = v["f_marginals"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert_eq!(margs.len(), 2 * k);
        let u = 1.0 / k as f64;
        for x in margs {
            assert!((x - u).abs() < 1e-12);
        }
    }

    #[test]
    fn belief_flat_from_unit_bank_weighted_particles() {
        let bank = crate::unit_pf::UnitParticleBank {
            weights: vec![0.25, 0.75],
            freshness: vec![
                vec![1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                vec![0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            ],
        };
        let v = belief_flat_from_unit_bank(&bank, 2, 3);
        let counts: Vec<f64> = v["lot_counts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        assert!((counts[0] - (0.25 * 2.0 + 0.75 * 0.0)).abs() < 1e-9);
        assert!((counts[1] - (0.25 * 0.0 + 0.75 * 3.0)).abs() < 1e-9);
    }

    #[test]
    fn belief_flat_from_unit_bank_k_matches_session_k_dim() {
        let bank = unit_bank_fixture();
        for k in [1usize, 4, 8] {
            let v = belief_flat_from_unit_bank(&bank, 2, k);
            assert_eq!(v["K"].as_u64().unwrap() as usize, k);
            assert_eq!(v["f_grid"].as_array().unwrap().len(), k);
            assert_eq!(v["f_marginals"].as_array().unwrap().len(), 2 * k);
        }
    }
}
