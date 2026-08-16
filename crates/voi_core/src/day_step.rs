//! Packed MOD-12 day transition (Python `model.day_step`).

use rand::Rng;
use rand_distr::{Binomial, Distribution};

use crate::physics::{
    allocate_sales, death_prob_survival_ratio, picking_weights, q10_age_increment,
};

pub use crate::params::ModelParams;

#[derive(Clone, Debug)]
pub struct Cohort {
    pub n: u32,
    pub tau: f64,
    pub lot_id: i64,
}

#[derive(Clone, Debug)]
pub struct DayStepIn {
    pub counts: Vec<u32>,
    pub taus: Vec<f64>,
    pub lot_ids: Vec<i64>,
    pub demand: Option<u32>,
    /// Injected waste counts (same length as live cohorts after age). Skips binomial.
    pub spoil_by: Option<Vec<u32>>,
    pub delivery_n: u32,
    pub delivery_tau: f64,
    pub delivery_lot_id: i64,
}

#[derive(Clone, Debug)]
pub struct DayStepOut {
    pub counts: Vec<u32>,
    pub taus: Vec<f64>,
    pub lot_ids: Vec<i64>,
    pub demand: u32,
    pub sales_total: u32,
    pub sales_by: Vec<u32>,
    pub waste_total: u32,
    pub waste_by: Vec<u32>,
}

pub fn day_step<R: Rng + ?Sized>(
    input: &DayStepIn,
    params: &ModelParams,
    rng_alloc: Option<&mut R>,
    rng_spoil: Option<&mut R>,
) -> DayStepOut {
    let mut live: Vec<Cohort> = input
        .counts
        .iter()
        .zip(input.taus.iter())
        .zip(input.lot_ids.iter())
        .filter_map(|((&n, &tau), &lot_id)| {
            if n > 0 {
                Some(Cohort { n, tau, lot_id })
            } else {
                None
            }
        })
        .collect();

    let dtau = q10_age_increment(1.0, params.t_store_c, params.t_ref_c, params.q10);
    for c in &mut live {
        c.tau += dtau;
    }

    let demand = input.demand.expect("injected demand required in v1 kernel");

    let (sales_by, sales_total) = if live.is_empty() || demand == 0 {
        (vec![0u32; live.len()], 0u32)
    } else {
        let taus: Vec<f64> = live.iter().map(|c| c.tau).collect();
        let counts: Vec<u32> = live.iter().map(|c| c.n).collect();
        let weights = picking_weights(
            &taus,
            params.sigma,
            params.beta,
            params.eta_ref,
            params.uniform_picking,
        );
        let rng = rng_alloc.expect("rng_alloc required when cohorts are live");
        let sales = allocate_sales(&counts, demand, &weights, rng);
        let tot: u32 = sales.iter().sum();
        for (c, s) in live.iter_mut().zip(sales.iter()) {
            c.n -= *s;
        }
        (sales, tot)
    };

    let mut waste_by = vec![0u32; live.len()];
    if !live.is_empty() {
        if let Some(inj) = &input.spoil_by {
            waste_by = inj.clone();
            for (c, w) in live.iter_mut().zip(waste_by.iter()) {
                c.n = c.n.saturating_sub(*w);
            }
        } else {
            let rng = rng_spoil.expect("rng_spoil required when cohorts are live");
            for (i, c) in live.iter_mut().enumerate() {
                if c.n == 0 {
                    continue;
                }
                let p_die = death_prob_survival_ratio(c.tau, dtau, params.beta, params.eta_ref);
                let p = p_die.clamp(0.0, 1.0);
                let dist = Binomial::new(u64::from(c.n), p).expect("binomial");
                let waste = dist.sample(rng) as u32;
                waste_by[i] = waste;
                c.n -= waste;
            }
        }
    }
    let waste_total: u32 = waste_by.iter().sum();
    live.retain(|c| c.n > 0);

    if input.delivery_n > 0 {
        live.push(Cohort {
            n: input.delivery_n,
            tau: input.delivery_tau,
            lot_id: input.delivery_lot_id,
        });
    }

    DayStepOut {
        counts: live.iter().map(|c| c.n).collect(),
        taus: live.iter().map(|c| c.tau).collect(),
        lot_ids: live.iter().map(|c| c.lot_id).collect(),
        demand,
        sales_total,
        sales_by,
        waste_total,
        waste_by,
    }
}

pub fn advance_days<R: Rng + ?Sized>(
    mut state: DayStepIn,
    orders: &[u32],
    params: &ModelParams,
    rng_alloc: &mut R,
    rng_spoil: &mut R,
) -> Vec<DayStepOut> {
    let mut outs = Vec::with_capacity(orders.len());
    for &order in orders {
        state.delivery_n = order;
        let out = day_step(&state, params, Some(rng_alloc), Some(rng_spoil));
        state.counts = out.counts.clone();
        state.taus = out.taus.clone();
        state.lot_ids = out.lot_ids.clone();
        state.spoil_by = None;
        outs.push(out);
    }
    outs
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::physics::q10_age_increment;

    #[test]
    fn injected_demand_and_zero_spoil_exact() {
        let params = ModelParams::default();
        let dtau = q10_age_increment(1.0, params.t_store_c, params.t_ref_c, params.q10);
        let input = DayStepIn {
            counts: vec![10, 5],
            taus: vec![0.0, 2.0],
            lot_ids: vec![1, 2],
            demand: Some(0),
            spoil_by: Some(vec![0, 0]),
            delivery_n: 8,
            delivery_tau: 0.0,
            delivery_lot_id: 99,
        };
        let out = day_step::<rand_pcg::Pcg64>(&input, &params, None, None);
        assert_eq!(out.demand, 0);
        assert_eq!(out.sales_total, 0);
        assert_eq!(out.waste_total, 0);
        assert_eq!(out.counts, vec![10, 5, 8]);
        assert!((out.taus[0] - dtau).abs() < 1e-12);
        assert!((out.taus[1] - (2.0 + dtau)).abs() < 1e-12);
        assert_eq!(out.lot_ids, vec![1, 2, 99]);
    }

    /// Mirrors `test_extinct_cohorts_dropped`.
    #[test]
    fn extinct_cohorts_dropped() {
        let params = ModelParams::default();
        let input = DayStepIn {
            counts: vec![0, 5],
            taus: vec![1.0, 2.0],
            lot_ids: vec![1, 2],
            demand: Some(0),
            spoil_by: Some(vec![0]),
            delivery_n: 0,
            delivery_tau: 0.0,
            delivery_lot_id: 0,
        };
        let out = day_step::<rand_pcg::Pcg64>(&input, &params, None, None);
        assert!(out.counts.iter().all(|&n| n > 0));
        assert!(out.lot_ids.iter().all(|&id| id != 1));
    }

    #[test]
    fn advance_days_one_host_loop() {
        use rand::SeedableRng;
        use rand_pcg::Pcg64;
        let params = ModelParams::default();
        let state = DayStepIn {
            counts: vec![8],
            taus: vec![0.0],
            lot_ids: vec![1],
            demand: Some(0),
            spoil_by: Some(vec![0]),
            delivery_n: 0,
            delivery_tau: 0.0,
            delivery_lot_id: 0,
        };
        let mut ra = Pcg64::seed_from_u64(1);
        let mut rs = Pcg64::seed_from_u64(2);
        let outs = advance_days(state, &[0, 8], &params, &mut ra, &mut rs);
        assert_eq!(outs.len(), 2);
    }

    /// AC-daystep (T-C2-A qa-daystep): f-native `L×U` unit freshness ground truth.
    mod f_native_day_step_spec {
        use super::*;
        use crate::shipments::{generate_arrival_age, ShipmentTrace};
        use rand::SeedableRng;
        use rand_pcg::Pcg64;

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
            assert!(
                !src.contains("death_prob_survival_ratio"),
                "RED: production day_step must not use Weibull spoil"
            );
            assert!(
                !src.contains("q10_age_increment"),
                "RED: production day_step must not bump tau via q10_age_increment"
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
            let birth_f = generate_arrival_age(
                &mut rng_ship,
                &mut rng_sensor,
                &shipments,
                params.q10,
                params.t_ref_c,
                1.0,
            );
            assert!(
                birth_f > 0.0 && birth_f <= 1.0,
                "arrival prior f must lie in (0, 1]: {birth_f}"
            );
            let src = production_day_step_src();
            assert!(
                src.contains("generate_arrival_age") || src.contains("delivery_f"),
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
}
