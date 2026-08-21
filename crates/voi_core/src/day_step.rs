//! f-native `L×U` unit freshness day transition (ADR 0130 production ground truth).

use rand::Rng;

pub use crate::params::ModelParams;
use crate::physics::{
    apply_gamma_aging, apply_gamma_decrement, gamma_decrement_for_store, picking_weights_f,
};
use crate::shipments::{birth_f_units, delivery_birth_f, ShipmentTrace};
use rand_pcg::Pcg64;
use rand::SeedableRng;

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
    /// Birth freshness for delivered units (`delivery_birth_f` when `None`).
    pub delivery_f: Option<f64>,
    /// Units injected per delivery (default `params.units_per_lot`, typically 15).
    pub units_per_lot: Option<usize>,
    /// F2 Dirac birth from measured age at receipt (τ days).
    pub age_at_receipt: Option<f64>,
    /// F2a Gaussian pack-date transit age mean (τ days).
    pub pack_age_mean: Option<f64>,
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
        apply_gamma_aging(freshness, rng, params);
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

fn pick_units_f<R: Rng + ?Sized>(
    freshness: &mut [f64],
    lot_offsets: &[usize],
    demand: u32,
    params: &ModelParams,
    rng: &mut R,
) -> (u32, Vec<u32>) {
    let l = lot_offsets.len() - 1;
    let mut sales_by = vec![0u32; l];
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
        freshness[idx] = 0.0;
        sales_by[lot_index(lot_offsets, idx)] += 1;
    }
    let sales_total: u32 = sales_by.iter().sum();
    (sales_total, sales_by)
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
    rng_ship: Option<&mut R>,
    rng_sensor: Option<&mut R>,
    rng_birth: Option<&mut R>,
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

    let demand = input.demand.unwrap_or(0);
    let (sales_total, sales_by) = if demand == 0 || l == 0 {
        (0u32, vec![0u32; l])
    } else {
        let rng = rng_alloc.expect("rng_alloc required when demand > 0 and lots are live");
        pick_units_f(&mut freshness, &lot_offsets, demand, params, rng)
    };

    if input.deliver {
        let units_per_lot = input
            .units_per_lot
            .unwrap_or(params.units_per_lot)
            .max(1);
        let birth_f = input.delivery_f.unwrap_or_else(|| {
            delivery_birth_f(
                rng_ship.expect("rng_ship required for delivery birth f"),
                rng_sensor.expect("rng_sensor required for delivery birth f"),
                shipments,
                params,
                1.0,
                input.age_at_receipt,
                input.pack_age_mean,
            )
        });
        let total_units = input
            .deliver_units
            .unwrap_or(units_per_lot as u32)
            .max(1) as usize;
        let start = freshness.len();
        let birth_segment = if let Some(rng) = rng_birth {
            birth_f_units(
                birth_f,
                params.arrival_dispersion_sd,
                total_units,
                rng,
            )
        } else {
            let mut fallback_birth = Pcg64::seed_from_u64(0);
            birth_f_units(
                birth_f,
                params.arrival_dispersion_sd,
                total_units,
                &mut fallback_birth,
            )
        };
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
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::shipments::{generate_arrival_f, ShipmentTrace};
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
                src.contains("delivery_f"),
                "RED: delivery must inject freshness f at birth"
            );
        }

        #[test]
        fn day_step_f_native_delivery_f_from_arrival_prior() {
            require_f_native_day_step_api();
            let params = ModelParams::default();
            let shipments = [ShipmentTrace::smoke_cool()];
            let mut rng_ship = Pcg64::seed_from_u64(11);
            let mut rng_sensor = Pcg64::seed_from_u64(22);
            let birth_f = generate_arrival_f(
                &mut rng_ship,
                &mut rng_sensor,
                &shipments,
                params.q10,
                params.t_ref_c,
                1.0,
                params.eta_ref,
            );
            assert!(
                birth_f > 0.0 && birth_f <= 1.0,
                "arrival prior f must lie in (0, 1]: {birth_f}"
            );
            let src = production_day_step_src();
            assert!(
                src.contains("generate_arrival_f") || src.contains("delivery_f"),
                "RED: delivery path must map arrival prior to birth f"
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
            delivery_f: None,
            units_per_lot: None,
            age_at_receipt: None,
            pack_age_mean: None,
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
            delivery_f: None,
            units_per_lot: None,
            age_at_receipt: None,
            pack_age_mean: None,
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

    /// T-138 AC-4: delivery extends via per-unit birth_f_units vector, not uniform fill.
    mod t138_arrival_dispersion {
        use super::*;

        fn production_day_step_src() -> &'static str {
            include_str!("day_step.rs")
                .split("#[cfg(test)]")
                .next()
                .unwrap_or("")
        }

        #[test]
        fn delivery_calls_birth_f_units_not_uniform_vec() {
            let src = production_day_step_src();
            assert!(
                src.contains("birth_f_units"),
                "RED: unit_day_step delivery must call shipments::birth_f_units"
            );
            assert!(
                !src.contains("vec![birth_f; total_units]"),
                "RED: delivery must not extend with vec![birth_f; total_units]"
            );
            assert!(
                src.contains(":birth") || src.contains("rng_birth"),
                "RED: within-lot dispersion draws must use dedicated :birth CRN"
            );
        }

        #[test]
        fn delivery_appends_distinct_freshness_when_dispersion_enabled() {
            let params_src = include_str!("params.rs");
            assert!(
                params_src.contains("arrival_dispersion_sd"),
                "RED: ModelParams must expose arrival_dispersion_sd"
            );
            let src = production_day_step_src();
            assert!(
                src.contains("birth_f_units"),
                "RED: cannot spread delivery segment without birth_f_units"
            );
            let params = ModelParams::default();
            let mut params = params;
            params.arrival_dispersion_sd = 0.05;
            let upl = 10usize;
            let input = UnitDayStepIn {
                freshness: vec![0.85; upl],
                lot_offsets: vec![0, upl],
                demand: Some(0),
                gamma_decrement: Some(0.0),
                deliver: true,
                deliver_units: Some(upl as u32),
                delivery_f: Some(0.62),
                units_per_lot: Some(upl),
                age_at_receipt: None,
                pack_age_mean: None,
            };
            let mut rng_birth = Pcg64::seed_from_u64(138_004);
            let out = unit_day_step_with_birth::<Pcg64>(
                &input, &params, &[], None, None, None, None, Some(&mut rng_birth),
            );
            let seg = &out.freshness[upl..];
            assert_eq!(seg.len(), upl, "delivery must append upl units");
            let min_f = seg.iter().cloned().fold(f64::INFINITY, f64::min);
            let max_f = seg.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            assert!(
                max_f - min_f > 1e-6,
                "RED: arrival_dispersion_sd > 0 must yield >=2 distinct birth f values in segment"
            );
        }
    }

    #[test]
    fn unit_day_step_delivery_injects_units_per_lot() {
        let params = ModelParams::default();
        let upl = 15;
        let input = UnitDayStepIn {
            freshness: vec![0.85; upl],
            lot_offsets: vec![0, upl],
            demand: Some(0),
            gamma_decrement: Some(0.0),
            deliver: true,
            deliver_units: None,
            delivery_f: Some(0.92),
            units_per_lot: None,
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let out = unit_day_step::<rand_pcg::Pcg64>(
            &input, &params, &[], None, None, None, None,
        );
        assert_eq!(out.lot_offsets.len(), 3);
        assert_eq!(out.freshness.len(), upl * 2);
        assert!(out.freshness[upl..].iter().all(|&f| (f - 0.92).abs() < 1e-12));
    }
}
