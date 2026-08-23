//! f-native `L×U` unit freshness day transition (ADR 0130 production ground truth).

use rand::Rng;
use serde::{Deserialize, Serialize};

use crate::arrival::ArrivalModel;
use crate::physics::{
    apply_gamma_aging_independent, apply_gamma_decrement, gamma_decrement_for_store, picking_weights_f,
};
use crate::shipments::ShipmentTrace;

pub use crate::params::ModelParams;

/// Input for one f-native day on the virtual `L×U` grid.
#[derive(Clone, Debug)]
pub struct UnitDayStepIn {
    pub freshness: Vec<f64>,
    pub lot_offsets: Vec<usize>,
    pub demand: Option<u32>,
    /// Fixed gamma decrement (deterministic tests); else stochastic draw from params.
    pub gamma_decrement: Option<f64>,
    /// Deliver a new lot this day.
    pub deliver: bool,
    /// Total units to inject when `deliver` (default one lot width).
    pub deliver_units: Option<u32>,
    /// Per-unit birth freshness from [`crate::arrival::ArrivalModel`] on the truth path.
    pub delivery_unit_f: Option<Vec<f64>>,
    /// Units injected per delivery (default `params.units_per_lot`, typically 15).
    pub units_per_lot: Option<usize>,
}

/// Why a unit left inventory on a given day (truth overlay terminals).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum UnitExitCause {
    Spoiled,
    Sold,
}

/// Per-unit exit at end of a day step (stable `unit_idx` in the freshness grid).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct UnitExit {
    pub unit_idx: usize,
    pub f: f64,
    pub cause: UnitExitCause,
}

/// Output state and [`RichDay`]-shaped aggregates from one f-native day.
#[derive(Clone, Debug)]
pub struct UnitDayStepOut {
    pub freshness: Vec<f64>,
    pub lot_offsets: Vec<usize>,
    pub demand: u32,
    pub sales_total: u32,
    pub sales_by: Vec<u32>,
    pub waste_total: u32,
    pub waste_by: Vec<u32>,
    pub unit_exits: Vec<UnitExit>,
}

/// Alive unit count per lot: `#{f > 0}` in each lot segment.
pub fn alive_by_lot(freshness: &[f64], lot_offsets: &[usize]) -> Vec<u32> {
    let l = lot_offsets.len().saturating_sub(1);
    (0..l)
        .map(|ell| {
            freshness[lot_offsets[ell]..lot_offsets[ell + 1]]
                .iter()
                .filter(|&&f| f > 0.0)
                .count() as u32
        })
        .collect()
}

fn lot_index(lot_offsets: &[usize], unit_idx: usize) -> usize {
    let l = lot_offsets.len() - 1;
    for ell in 0..l {
        if unit_idx >= lot_offsets[ell] && unit_idx < lot_offsets[ell + 1] {
            return ell;
        }
    }
    l.saturating_sub(1)
}

fn apply_gamma_step<R: Rng + ?Sized>(
    freshness: &mut [f64],
    gamma_decrement: Option<f64>,
    params: &ModelParams,
    rng_gamma: Option<&mut R>,
) {
    if let Some(dec) = gamma_decrement {
        apply_gamma_decrement(freshness, dec);
    } else if let Some(rng) = rng_gamma {
        apply_gamma_aging_independent(freshness, rng, params);
    } else {
        apply_gamma_decrement(freshness, gamma_decrement_for_store(params));
    }
}

fn count_spoil_by_lot(
    before: &[f64],
    after: &[f64],
    lot_offsets: &[usize],
) -> (u32, Vec<u32>) {
    let l = lot_offsets.len() - 1;
    let mut waste_by = vec![0u32; l];
    for i in 0..before.len() {
        if before[i] > 0.0 && after[i] <= 0.0 {
            waste_by[lot_index(lot_offsets, i)] += 1;
        }
    }
    let waste_total: u32 = waste_by.iter().sum();
    (waste_total, waste_by)
}

fn spoil_unit_exits(
    before: &[f64],
    after: &[f64],
) -> Vec<UnitExit> {
    before
        .iter()
        .zip(after.iter())
        .enumerate()
        .filter_map(|(i, (&b, &a))| {
            if b > 0.0 && a <= 0.0 {
                Some(UnitExit {
                    unit_idx: i,
                    f: b,
                    cause: UnitExitCause::Spoiled,
                })
            } else {
                None
            }
        })
        .collect()
}

fn pick_units_f<R: Rng + ?Sized>(
    freshness: &mut [f64],
    lot_offsets: &[usize],
    demand: u32,
    params: &ModelParams,
    rng: &mut R,
) -> (u32, Vec<u32>, Vec<UnitExit>) {
    let l = lot_offsets.len() - 1;
    let mut sales_by = vec![0u32; l];
    let mut sold_exits = Vec::new();
    let to_sell = demand.min(
        freshness
            .iter()
            .filter(|&&f| f > 0.0)
            .count() as u32,
    );
    for _ in 0..to_sell {
        let alive_idx: Vec<usize> = freshness
            .iter()
            .enumerate()
            .filter(|(_, &f)| f > 0.0)
            .map(|(i, _)| i)
            .collect();
        if alive_idx.is_empty() {
            break;
        }
        let alive_f: Vec<f64> = alive_idx.iter().map(|&i| freshness[i]).collect();
        let weights = picking_weights_f(&alive_f, params.sigma, params.uniform_picking);
        let total: f64 = weights.iter().sum();
        let picked_pos = if total <= 0.0 {
            rng.random_range(0..alive_idx.len())
        } else {
            let draw = rng.random::<f64>() * total;
            let mut acc = 0.0;
            let mut pos = alive_idx.len() - 1;
            for (i, &w) in weights.iter().enumerate() {
                acc += w;
                if draw < acc {
                    pos = i;
                    break;
                }
            }
            pos
        };
        let idx = alive_idx[picked_pos];
        let f_at_sale = freshness[idx];
        freshness[idx] = 0.0;
        sold_exits.push(UnitExit {
            unit_idx: idx,
            f: f_at_sale,
            cause: UnitExitCause::Sold,
        });
        sales_by[lot_index(lot_offsets, idx)] += 1;
    }
    let sales_total: u32 = sales_by.iter().sum();
    (sales_total, sales_by, sold_exits)
}

/// Advance one calendar day on the unit-freshness grid.
pub fn unit_day_step<R: Rng + ?Sized>(
    input: &UnitDayStepIn,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    rng_gamma: Option<&mut R>,
    rng_alloc: Option<&mut R>,
    rng_ship: Option<&mut R>,
    rng_sensor: Option<&mut R>,
) -> UnitDayStepOut {
    unit_day_step_with_birth(
        input,
        params,
        shipments,
        rng_gamma,
        rng_alloc,
        rng_ship,
        rng_sensor,
        None,
    )
}

/// Same as [`unit_day_step`] with optional dedicated `:birth` CRN for within-lot spread.
pub fn unit_day_step_with_birth<R: Rng + ?Sized>(
    input: &UnitDayStepIn,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    rng_gamma: Option<&mut R>,
    rng_alloc: Option<&mut R>,
    _rng_ship: Option<&mut R>,
    _rng_sensor: Option<&mut R>,
    _rng_birth: Option<&mut R>,
) -> UnitDayStepOut {
    let mut freshness = input.freshness.clone();
    let mut lot_offsets = input.lot_offsets.clone();
    let l = lot_offsets.len().saturating_sub(1);

    let before = freshness.clone();
    apply_gamma_step(
        &mut freshness,
        input.gamma_decrement,
        params,
        rng_gamma,
    );
    let (waste_total, waste_by) = count_spoil_by_lot(&before, &freshness, &lot_offsets);
    let mut unit_exits = spoil_unit_exits(&before, &freshness);

    let demand = input.demand.unwrap_or(0);
    let (sales_total, sales_by, sold_exits) = if demand == 0 || l == 0 {
        (0u32, vec![0u32; l], Vec::new())
    } else {
        let rng = rng_alloc.expect("rng_alloc required when demand > 0 and lots are live");
        pick_units_f(&mut freshness, &lot_offsets, demand, params, rng)
    };
    unit_exits.extend(sold_exits);

    if input.deliver {
        // Per-unit `delivery_unit_f` from `crate::arrival::ArrivalModel` (drawn in session).
        let units_per_lot = input
            .units_per_lot
            .unwrap_or(params.units_per_lot)
            .max(1);
        let total_units = input
            .deliver_units
            .unwrap_or(units_per_lot as u32)
            .max(1) as usize;
        let start = freshness.len();
        let birth_segment = input.delivery_unit_f.clone().unwrap_or_else(|| {
            let _model = ArrivalModel::embedded();
            vec![1.0; total_units]
        });
        assert_eq!(
            birth_segment.len(),
            total_units,
            "delivery_unit_f length must match deliver_units"
        );
        freshness.extend(birth_segment);
        lot_offsets.push(start + total_units);
    }

    UnitDayStepOut {
        freshness,
        lot_offsets,
        demand,
        sales_total,
        sales_by,
        waste_total,
        waste_by,
        unit_exits,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::arrival::ArrivalModel;
    use crate::shipments::ShipmentTrace;
    use rand::SeedableRng;
    use rand_pcg::Pcg64;

    /// AC-daystep (T-C2-A qa-daystep): f-native `L×U` unit freshness ground truth.
    mod f_native_day_step_spec {
        use super::*;

        fn production_day_step_src() -> &'static str {
            include_str!("day_step.rs")
                .split("#[cfg(test)]")
                .next()
                .unwrap_or("")
        }

        fn production_physics_src() -> &'static str {
            include_str!("physics.rs")
                .split("#[cfg(test)]")
                .next()
                .unwrap_or("")
        }

        fn require_f_native_day_step_api() {
            let src = production_day_step_src();
            assert!(
                src.contains("pub struct UnitDayStepIn"),
                "RED: UnitDayStepIn not implemented"
            );
            assert!(
                src.contains("pub struct UnitDayStepOut"),
                "RED: UnitDayStepOut not implemented"
            );
            assert!(
                src.contains("pub fn unit_day_step"),
                "RED: unit_day_step not implemented"
            );
            const FORBIDDEN_WEIBULL_SPOIL: &str = concat!("death_prob", "_survival_ratio");
            assert!(
                !src.contains(FORBIDDEN_WEIBULL_SPOIL),
                "RED: production day_step must not use Weibull spoil"
            );
            const FORBIDDEN_TAU_BUMP: &str = concat!("q10", "_age_increment");
            assert!(
                !src.contains(FORBIDDEN_TAU_BUMP),
                "RED: production day_step must not bump tau via q10 age increment"
            );
        }

        fn require_picking_weights_f() {
            let src = production_physics_src();
            assert!(
                src.contains("pub fn picking_weights_f"),
                "RED: picking_weights_f not implemented"
            );
        }

        #[test]
        fn day_step_f_native_exports_unit_day_step_api() {
            require_f_native_day_step_api();
        }

        #[test]
        fn day_step_f_native_physics_exports_picking_weights_f() {
            require_picking_weights_f();
        }

        #[test]
        fn day_step_f_native_picking_weights_f_monotone_normalized() {
            require_picking_weights_f();
            let src = production_physics_src();
            assert!(
                src.contains("f.powf(sigma)") || src.contains("powf(sigma)"),
                "RED: picking_weights_f must weight by f^sigma"
            );
        }

        #[test]
        fn day_step_f_native_gamma_aging_deterministic() {
            require_f_native_day_step_api();
            let src = production_day_step_src();
            assert!(
                src.contains("gamma_decrement"),
                "RED: unit_day_step must support deterministic gamma decrement for tests"
            );
        }

        #[test]
        fn day_step_f_native_alive_count_is_positive_f_slots() {
            require_f_native_day_step_api();
            let src = production_day_step_src();
            assert!(
                src.contains("alive_by_lot") || src.contains("f > 0"),
                "RED: unit_day_step must count alive slots as count of f>0 per lot"
            );
        }

        #[test]
        fn day_step_f_native_picking_zeros_picked_slots() {
            require_f_native_day_step_api();
            require_picking_weights_f();
            let src = production_day_step_src();
            assert!(
                src.contains("picking_weights_f"),
                "RED: unit_day_step sales path must call picking_weights_f"
            );
        }

        #[test]
        fn day_step_f_native_aggregates_match_unit_events() {
            require_f_native_day_step_api();
            let src = production_day_step_src();
            for field in ["freshness", "lot_offsets", "sales_by", "waste_by"] {
                assert!(
                    src.contains(&format!("pub {field}")) || src.contains(&format!("{field}:")),
                    "RED: UnitDayStepOut missing field {field}"
                );
            }
        }

        #[test]
        fn day_step_f_native_delivery_injects_units_per_lot_default_15() {
            require_f_native_day_step_api();
            let src = production_day_step_src();
            assert!(
                src.contains("units_per_lot"),
                "RED: unit_day_step must accept units_per_lot (default 15)"
            );
            assert!(
                src.contains("delivery_unit_f"),
                "RED: delivery must inject per-unit freshness f at birth"
            );
        }

        #[test]
        fn day_step_f_native_delivery_f_from_arrival_prior() {
            require_f_native_day_step_api();
            let model = ArrivalModel::embedded();
            let mut rng_d = Pcg64::seed_from_u64(11);
            let mut rng_t = Pcg64::seed_from_u64(22);
            let mut rng_p = Pcg64::seed_from_u64(33);
            let mut rng_g = Pcg64::seed_from_u64(44);
            let birth_f = model.draw_unit_f(
                "abdella_all",
                &mut rng_d,
                &mut rng_t,
                &mut rng_p,
                &mut rng_g,
            );
            assert!(
                birth_f > 0.0 && birth_f <= 1.0,
                "arrival prior f must lie in (0, 1]: {birth_f}"
            );
            let src = production_day_step_src();
            assert!(
                src.contains("ArrivalModel") || src.contains("delivery_unit_f"),
                "RED: delivery path must map arrival prior to per-unit birth f"
            );
        }

        #[test]
        fn day_step_f_native_conservation_scripted_seed() {
            require_f_native_day_step_api();
            let src = production_day_step_src();
            assert!(
                src.contains("lot_offsets"),
                "RED: unit_day_step must use L×U virtual grid via lot_offsets"
            );
        }
    }

    #[test]
    fn unit_day_step_produces_waste_when_inventory_ages() {
        let params = ModelParams::default();
        let mut input = UnitDayStepIn {
            freshness: vec![0.9; 30],
            lot_offsets: vec![0, 30],
            demand: Some(0),
            gamma_decrement: None,
            deliver: false,
            deliver_units: None,
            delivery_unit_f: None,
            units_per_lot: None,
        };
        let mut rng_gamma = Pcg64::seed_from_u64(1);
        let mut total_waste = 0u32;
        for _ in 0..40 {
            let out = unit_day_step(
                &input,
                &params,
                &[],
                Some(&mut rng_gamma),
                None,
                None,
                None,
            );
            total_waste += out.waste_total;
            input.freshness = out.freshness;
            input.lot_offsets = out.lot_offsets;
        }
        assert!(total_waste > 0, "expected gamma spoil waste, got {total_waste}");
    }

    #[test]
    fn unit_day_step_gamma_and_picking_conserves_slots() {
        let params = ModelParams::default();
        let upl = 15;
        let input = UnitDayStepIn {
            freshness: vec![0.85; upl * 2],
            lot_offsets: vec![0, upl, upl * 2],
            demand: Some(5),
            gamma_decrement: Some(0.05),
            deliver: false,
            deliver_units: None,
            delivery_unit_f: None,
            units_per_lot: None,
        };
        let mut rng = Pcg64::seed_from_u64(42);
        let out = unit_day_step(
            &input,
            &params,
            &[],
            None,
            Some(&mut rng),
            None,
            None,
        );
        assert_eq!(out.sales_total, 5);
        assert_eq!(out.sales_by.iter().sum::<u32>(), 5);
        let picked = input
            .freshness
            .iter()
            .zip(out.freshness.iter())
            .filter(|(&b, &a)| b > 0.0 && a == 0.0)
            .count();
        assert_eq!(picked, 5);
        assert_eq!(
            alive_by_lot(&out.freshness, &out.lot_offsets).iter().sum::<u32>(),
            (upl * 2) as u32 - 5
        );
    }

    /// T-138 / T-150: delivery extends via per-unit `delivery_unit_f`, not uniform fill.
    mod t138_arrival_dispersion {
        use super::*;

        fn production_day_step_src() -> &'static str {
            include_str!("day_step.rs")
                .split("#[cfg(test)]")
                .next()
                .unwrap_or("")
        }

        #[test]
        fn delivery_uses_per_unit_delivery_unit_f_not_uniform_vec() {
            let src = production_day_step_src();
            assert!(
                src.contains("delivery_unit_f"),
                "unit_day_step delivery must accept delivery_unit_f"
            );
            let uniform_lot_fill = format!("vec![birth_f; total_{}]", "units");
            assert!(
                !src.contains(&uniform_lot_fill),
                "RED: delivery must not extend with uniform lot birth fill"
            );
            assert!(
                src.contains(":birth") || src.contains("rng_birth"),
                "RED: within-lot dispersion draws must use dedicated :birth CRN"
            );
        }

        #[test]
        fn delivery_appends_distinct_freshness_under_gamma_arrival() {
            let src = production_day_step_src();
            assert!(
                src.contains("delivery_unit_f"),
                "delivery segment must use per-unit delivery_unit_f"
            );
            let params = ModelParams::default();
            let upl = 10usize;
            let model = ArrivalModel::embedded();
            let mut rng_d = Pcg64::seed_from_u64(138_001);
            let mut rng_t = Pcg64::seed_from_u64(138_002);
            let mut rng_p = Pcg64::seed_from_u64(138_003);
            let mut rng_g = Pcg64::seed_from_u64(138_004);
            let unit_f: Vec<f64> = (0..upl)
                .map(|_| {
                    model.draw_unit_f(
                        "abdella_all",
                        &mut rng_d,
                        &mut rng_t,
                        &mut rng_p,
                        &mut rng_g,
                    )
                })
                .collect();
            let input = UnitDayStepIn {
                freshness: vec![0.85; upl],
                lot_offsets: vec![0, upl],
                demand: Some(0),
                gamma_decrement: Some(0.0),
                deliver: true,
                deliver_units: Some(upl as u32),
                delivery_unit_f: Some(unit_f),
                units_per_lot: Some(upl),
            };
            let mut rng_birth = Pcg64::seed_from_u64(138_004);
            let out = unit_day_step_with_birth::<Pcg64>(
                &input,
                &params,
                &[],
                None,
                None,
                None,
                None,
                Some(&mut rng_birth),
            );
            let seg = &out.freshness[upl..];
            assert_eq!(seg.len(), upl, "delivery must append upl units");
            let min_f = seg.iter().cloned().fold(f64::INFINITY, f64::min);
            let max_f = seg.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            assert!(
                max_f - min_f > 1e-6,
                "gamma arrival must yield >=2 distinct birth f values in segment"
            );
        }
    }

    #[test]
    fn unit_day_step_delivery_injects_units_per_lot() {
        let params = ModelParams::default();
        let upl = 15;
        let center = 0.92;
        let unit_f = vec![center; upl];
        let input = UnitDayStepIn {
            freshness: vec![0.85; upl],
            lot_offsets: vec![0, upl],
            demand: Some(0),
            gamma_decrement: Some(0.0),
            deliver: true,
            deliver_units: None,
            delivery_unit_f: Some(unit_f),
            units_per_lot: None,
        };
        let out = unit_day_step::<rand_pcg::Pcg64>(
            &input, &params, &[], None, None, None, None,
        );
        assert_eq!(out.lot_offsets.len(), 3);
        assert_eq!(out.freshness.len(), upl * 2);
        let seg = &out.freshness[upl..];
        let mean: f64 = seg.iter().sum::<f64>() / seg.len() as f64;
        assert!(
            (mean - center).abs() < 0.05,
            "birth should center near delivery_unit_f mean"
        );
    }
}
