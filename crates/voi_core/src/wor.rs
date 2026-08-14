//! Mix-radix sequential without-replacement composition PMF (Python sequential_wor).

pub fn sequential_wor_composition_probs(
    counts: &[u32],
    sales_tot: i32,
    weights: &[f64],
) -> Vec<(Vec<u32>, f64)> {
    let l = counts.len();
    if l == 0 {
        return if sales_tot == 0 {
            vec![(Vec::new(), 1.0)]
        } else {
            Vec::new()
        };
    }
    let n_sum: i32 = counts.iter().map(|&c| c as i32).sum();
    if sales_tot < 0 || sales_tot > n_sum {
        return Vec::new();
    }
    if sales_tot == 0 {
        return vec![(vec![0u32; l], 1.0)];
    }
    let sales_tot = sales_tot as u32;

    let dims: Vec<usize> = counts.iter().map(|&c| (c as usize) + 1).collect();
    let mut strides = vec![1usize; l];
    for i in (0..l.saturating_sub(1)).rev() {
        strides[i] = strides[i + 1] * dims[i + 1];
    }
    let size: usize = dims.iter().product();
    let mut cur = vec![0.0f64; size];
    cur[0] = 1.0;

    for _ in 0..sales_tot {
        let active: Vec<usize> = cur
            .iter()
            .enumerate()
            .filter(|(_, &p)| p > 0.0)
            .map(|(i, _)| i)
            .collect();
        if active.is_empty() {
            break;
        }
        let mut nxt = vec![0.0f64; size];
        for &idx in &active {
            let p = cur[idx];
            let mut rem = idx;
            let mut comps = vec![0u32; l];
            for i in 0..l {
                comps[i] = (rem / strides[i]) as u32;
                rem %= strides[i];
            }
            let mut tot = 0.0;
            let mut avail = vec![0.0f64; l];
            for j in 0..l {
                if comps[j] < counts[j] {
                    avail[j] = weights[j];
                    tot += weights[j];
                }
            }
            if tot <= 0.0 {
                continue;
            }
            for j in 0..l {
                if avail[j] > 0.0 {
                    let dest = idx + strides[j];
                    nxt[dest] += p * (avail[j] / tot);
                }
            }
        }
        cur = nxt;
    }

    let mut out = Vec::new();
    for (idx, &p) in cur.iter().enumerate() {
        if p <= 0.0 {
            continue;
        }
        let mut rem = idx;
        let mut comps = vec![0u32; l];
        for i in 0..l {
            comps[i] = (rem / strides[i]) as u32;
            rem %= strides[i];
        }
        out.push((comps, p));
    }
    out
}

pub fn sequential_wor_composition_prob(counts: &[u32], sales: &[u32], weights: &[f64]) -> f64 {
    let demand: i32 = sales.iter().map(|&s| s as i32).sum();
    let table = sequential_wor_composition_probs(counts, demand, weights);
    table
        .into_iter()
        .find(|(c, _)| c.as_slice() == sales)
        .map(|(_, p)| p)
        .unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    const ATOL: f64 = 1e-12;

    fn mass(table: &[(Vec<u32>, f64)], key: &[u32]) -> f64 {
        table
            .iter()
            .find(|(c, _)| c.as_slice() == key)
            .map(|(_, p)| *p)
            .unwrap_or(0.0)
    }

    #[test]
    fn two_by_two_one_sale_uniform() {
        let t = sequential_wor_composition_probs(&[2, 2], 1, &[1.0, 1.0]);
        let s: f64 = t.iter().map(|(_, p)| p).sum();
        assert!((s - 1.0).abs() < ATOL);
        assert!((mass(&t, &[0, 1]) - 0.5).abs() < ATOL);
        assert!((mass(&t, &[1, 0]) - 0.5).abs() < ATOL);
    }

    #[test]
    fn three_cohort_sales_two() {
        let t = sequential_wor_composition_probs(&[2, 1, 1], 2, &[0.5, 0.3, 0.2]);
        let s: f64 = t.iter().map(|(_, p)| p).sum();
        assert!((s - 1.0).abs() < ATOL);
        assert!((mass(&t, &[0, 1, 1]) - 0.160_714_285_714_285_73).abs() < ATOL);
        assert!((mass(&t, &[1, 0, 1]) - 0.225).abs() < ATOL);
        assert!((mass(&t, &[1, 1, 0]) - 0.364_285_714_285_714_27).abs() < ATOL);
        assert!((mass(&t, &[2, 0, 0]) - 0.25).abs() < ATOL);
    }

    #[test]
    fn edge_cases() {
        let z = sequential_wor_composition_probs(&[], 0, &[]);
        assert_eq!(z.len(), 1);
        assert!(z[0].0.is_empty());
        let zero = sequential_wor_composition_probs(&[2, 1], 0, &[1.0, 1.0]);
        assert_eq!(zero[0].0, vec![0, 0]);
        assert!(sequential_wor_composition_probs(&[1], 3, &[1.0]).is_empty());
        assert!(sequential_wor_composition_probs(&[], 1, &[]).is_empty());
        assert!(sequential_wor_composition_probs(&[2, 2], -1, &[1.0, 1.0]).is_empty());
        assert!(sequential_wor_composition_probs(&[2, 2], 5, &[1.0, 1.0]).is_empty());
        let zeros = sequential_wor_composition_probs(&[0, 0], 0, &[1.0, 1.0]);
        assert_eq!(zeros[0].0, vec![0, 0]);
        let full = sequential_wor_composition_probs(&[3, 3], 6, &[1.0, 1.0]);
        let s: f64 = full.iter().map(|(_, p)| p).sum();
        assert!((s - 1.0).abs() < ATOL);
    }

    /// Mirrors `test_sequential_wor_numpy.py::test_numpy_dp_matches_frozen_python_ref`.
    #[test]
    fn numpy_dp_param_cases_sum_to_one() {
        let cases: &[(&[u32], i32, &[f64])] = &[
            (&[2, 2], 0, &[1.0, 2.0]),
            (&[2, 2], 1, &[1.0, 2.0]),
            (&[2, 2], 2, &[1.0, 2.0]),
            (&[3, 2], 3, &[0.5, 1.5]),
            (&[2, 2, 2], 2, &[1.0, 1.0, 1.0]),
            (&[3, 1, 2], 3, &[2.0, 1.0, 0.5]),
            (&[1, 1, 1], 2, &[1.0, 3.0, 2.0]),
        ];
        for &(counts, sales_tot, w) in cases {
            let t = sequential_wor_composition_probs(counts, sales_tot, w);
            if sales_tot == 0 {
                assert_eq!(t.len(), 1);
                continue;
            }
            let s: f64 = t.iter().map(|(_, p)| p).sum();
            assert!((s - 1.0).abs() < ATOL, "sum={s} counts={counts:?}");
        }
    }

    /// Mirrors `test_fixed_weights_not_remaining_times_weights`.
    #[test]
    fn fixed_weights_not_remaining_times_weights() {
        let counts = [2u32, 2];
        let weights = [1.0, 3.0];
        let t = sequential_wor_composition_probs(&counts, 1, &weights);
        assert!((mass(&t, &[1, 0]) - 0.25).abs() < 1e-15);
        assert!((mass(&t, &[0, 1]) - 0.75).abs() < 1e-15);
        let t2 = sequential_wor_composition_probs(&counts, 2, &weights);
        assert!((mass(&t2, &[0, 2]) - 0.75 * 0.75).abs() < 1e-15);
        assert!((mass(&t2, &[1, 1]) - (0.25 * 0.75 + 0.75 * 0.25)).abs() < 1e-15);
        assert!((mass(&t2, &[2, 0]) - 0.25 * 0.25).abs() < 1e-15);
    }

    /// Mirrors `test_composition_probs_align_with_allocate_sales_monte_carlo` (looser atol).
    #[test]
    fn composition_probs_align_with_allocate_sales_monte_carlo() {
        use crate::physics::allocate_sales;
        use rand::SeedableRng;
        use rand_pcg::Pcg64;
        let counts = [2u32, 2];
        let w = [1.0, 3.0];
        let sales_tot = 2i32;
        let table = sequential_wor_composition_probs(&counts, sales_tot, &w);
        let mut rng = Pcg64::seed_from_u64(0);
        let n_mc = 20_000u32;
        let mut freq: std::collections::HashMap<Vec<u32>, u32> = std::collections::HashMap::new();
        for _ in 0..n_mc {
            let sold = allocate_sales(&counts, sales_tot as u32, &w, &mut rng);
            *freq.entry(sold).or_insert(0) += 1;
        }
        for (key, p) in table {
            let emp = f64::from(*freq.get(&key).unwrap_or(&0)) / f64::from(n_mc);
            assert!(
                (emp - p).abs() < 0.03,
                "{key:?}: emp={emp} dp={p}"
            );
        }
    }
}
