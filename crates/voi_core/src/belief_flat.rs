//! Flatten a `UnitParticleBank` onto the f-native Snapshot `L×K` belief wire (ADR 0130).

use serde_json::Value;

use crate::unit_pf::UnitParticleBank;

fn nearest_bin(value: f64, grid: &[f64]) -> usize {
    grid.iter()
        .enumerate()
        .min_by(|(_, a), (_, b)| (*a - value).abs().partial_cmp(&(*b - value).abs()).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0)
}

/// Freshness bin centers in `[0, 1]` for wire dimension `K`.
pub fn f_grid_k(k: usize) -> Vec<f64> {
    if k == 0 {
        return Vec::new();
    }
    if k == 1 {
        return vec![0.0];
    }
    (0..k).map(|i| i as f64 / ((k - 1) as f64)).collect()
}

/// Flatten `UnitParticleBank` onto the f-native `L×K` belief wire (ADR 0130 / 0137).
///
/// Slots follow the bank's **own** lot segmentation (`lot_offsets`), oldest-first, keeping
/// the newest `l` lots when the shelf holds more. Nothing re-derives lot widths from row
/// length: after ADR 0137 a delivery's segment is exactly as wide as the delivery was.
pub fn belief_flat_from_unit_bank(bank: &UnitParticleBank, l: usize, k: usize) -> Value {
    let grid = f_grid_k(k);
    let n = bank.weights.len();
    let w_sum: f64 = bank.weights.iter().sum();
    let n_lots = bank.n_lots();
    let first_lot = n_lots.saturating_sub(l);

    let mut lot_counts = vec![0.0; l];
    let mut f_marginals = vec![0.0; l.saturating_mul(k)];
    if w_sum > 0.0 && n_lots > 0 && k > 0 {
        for (slot, ell) in (first_lot..n_lots).enumerate() {
            let start = bank.lot_offsets[ell];
            let end = bank.lot_offsets[ell + 1];
            let mut acc = 0.0;
            for i in 0..n {
                let w = bank.weights[i];
                let row = bank.freshness.get(i).map(Vec::as_slice).unwrap_or(&[]);
                if end > row.len() {
                    continue;
                }
                for &f in &row[start..end] {
                    if f > 0.0 {
                        acc += w;
                        f_marginals[slot * k + nearest_bin(f, &grid)] += w;
                    }
                }
            }
            lot_counts[slot] = acc / w_sum;
        }
    }

    if k > 0 {
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

    fn unit_bank_fixture() -> UnitParticleBank {
        UnitParticleBank::from_rows_uniform_lots(vec![1.0], vec![vec![1.0, 1.0, 0.0, 1.0, 0.5, 0.0]], 3)
    }

    #[test]
    fn belief_flat_from_unit_bank_exports_f_wire_keys() {
        let bank = unit_bank_fixture();
        let v = belief_flat_from_unit_bank(&bank, 2, 3);
        assert!(
            v.get("f_grid").is_some(),
            "production wire must export f_grid"
        );
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
        assert!((margs[2] - 1.0).abs() < 1e-9);
        assert!((margs[3 + 1] - 0.5).abs() < 1e-9);
        assert!((margs[3 + 2] - 0.5).abs() < 1e-9);
    }

    #[test]
    fn belief_flat_from_unit_bank_empty_bank_zero_counts_uniform_marginals() {
        let bank = UnitParticleBank::empty(0);
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
        let bank = UnitParticleBank::from_rows_uniform_lots(
            vec![0.25, 0.75],
            vec![
                vec![1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                vec![0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            ],
            3,
        );
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
