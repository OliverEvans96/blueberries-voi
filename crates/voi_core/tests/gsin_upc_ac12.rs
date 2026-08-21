//! AC-8: count_bias guard under unified gamma arrival (T-140 / ADR 0141).
use std::collections::BTreeMap;

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::day_step::{alive_by_lot, unit_day_step_with_birth, UnitDayStepIn};
use voi_core::obs::{mask_for, RichDay};
use voi_core::physics::draw_demand;
use voi_core::shipments::{arrival_receipt_meta_with_trace, shipment_arrival_age, ShipmentTrace};
use voi_core::unit_pf::{filter_step_unit_with_birth, UnitParticleBank};
use voi_core::ModelParams;

const HORIZON: u32 = 60;
const N_PARTICLES: usize = 200;
const BURN_IN: u32 = 10;
const N_SEEDS: u64 = 12;
const STREAM_BIRTH: u64 = 7;
const SCENARIOS: [&str; 4] = ["P1", "F1", "F2a", "F3"];
const BIAS_MAX: f64 = 0.11;

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root
            .wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

struct TruthDay {
    rich: RichDay,
    on_hand: u32,
}

fn run_truth(seed: u64, params: &ModelParams, order_qty: u32) -> Vec<TruthDay> {
    let shipments = vec![ShipmentTrace::smoke_cool()];
    let mut freshness = vec![];
    let mut lot_offsets = vec![0];
    let mut lot_ids = vec![];
    let mut pending = BTreeMap::new();
    let mut next_lot = 1i64;
    let mut out = vec![];
    for day in 0..HORIZON {
        let order = if day % 3 == 0 { order_qty } else { 0 };
        *pending.entry(day + 1).or_insert(0) += order;
        let arrival = pending.remove(&day).unwrap_or(0);
        let pre = lot_ids.clone();
        let (f, age, pack, trace, alids) = if arrival > 0 {
            let mut rs = stream_rng(seed, day, 4);
            let mut rn = stream_rng(seed, day, 5);
            let (f, tau, p, t) =
                arrival_receipt_meta_with_trace(&mut rs, &mut rn, &shipments, params, 1.0);
            lot_ids.push(next_lot);
            next_lot += 1;
            (Some(f), Some(tau), Some(p), Some(t), vec![next_lot - 1])
        } else {
            (None, None, None, None, vec![])
        };
        let mut rd = stream_rng(seed, day, 1);
        let demand = draw_demand(&mut rd, params, Some(day));
        let mut rg = stream_rng(seed, day, 3);
        let mut ra = stream_rng(seed, day, 2);
        let mut rs = if arrival > 0 {
            Some(stream_rng(seed, day, 4))
        } else {
            None
        };
        let mut rn = if arrival > 0 {
            Some(stream_rng(seed, day, 5))
        } else {
            None
        };
        let mut rb = if arrival > 0 {
            Some(stream_rng(seed, day, STREAM_BIRTH))
        } else {
            None
        };
        let delivery_lambda = trace.as_ref().map(|t| {
            shipment_arrival_age(t, params.q10, params.t_ref_c)
        });
        let step = unit_day_step_with_birth(
            &UnitDayStepIn {
                freshness: freshness.clone(),
                lot_offsets: lot_offsets.clone(),
                demand: Some(demand),
                gamma_decrement: None,
                deliver: arrival > 0,
                deliver_units: if arrival > 0 { Some(arrival) } else { None },
                delivery_f: f,
                delivery_lambda,
                units_per_lot: Some(params.units_per_lot),
                age_at_receipt: age,
                pack_age_mean: pack.map(f64::from),
            },
            params,
            &shipments,
            Some(&mut rg),
            Some(&mut ra),
            rs.as_mut(),
            rn.as_mut(),
            rb.as_mut(),
        );
        freshness = step.freshness;
        lot_offsets = step.lot_offsets;
        let on_hand: u32 = alive_by_lot(&freshness, &lot_offsets).iter().sum();
        out.push(TruthDay {
            rich: RichDay {
                sales_total: step.sales_total,
                waste_total: step.waste_total,
                arrivals: arrival,
                sales_by: step.sales_by.clone(),
                waste_by: step.waste_by.clone(),
                lot_ids: pre,
                arrival_lot_ids: alids,
                shipment_trace: trace,
                f_at_receipt: f,
                age_at_receipt: age,
                pack_date_days: pack,
            },
            on_hand,
        });
    }
    out
}

fn run_bias(sc: &str, days: &[TruthDay], params: &ModelParams, shipments: &[ShipmentTrace], seed: u64) -> f64 {
    let mask = mask_for(sc).unwrap();
    let mut bank = UnitParticleBank::empty(N_PARTICLES);
    let mut ab = 0.0;
    let mut n: f64 = 0.0;
    for (d, td) in days.iter().enumerate() {
        let obs = mask.apply(&td.rich);
        let mut fr = stream_rng(seed, d as u32, 6);
        let mut rb = if obs.arrivals > 0 {
            Some(stream_rng(seed, d as u32, STREAM_BIRTH))
        } else {
            None
        };
        filter_step_unit_with_birth(
            &mut bank,
            &obs,
            params,
            shipments,
            &mut fr,
            rb.as_mut(),
        );
        if (d as u32) < BURN_IN {
            continue;
        }
        n += 1.0;
        let mut ea = 0.0;
        for row in &bank.freshness {
            ea += alive_by_lot(row, &bank.lot_offsets).iter().sum::<u32>() as f64;
        }
        ab += ea / N_PARTICLES as f64 - f64::from(td.on_hand);
    }
    ab / n.max(1.0)
}

fn mean_bias(sc: &str) -> f64 {
    let mut p = ModelParams::default();
    p.demand_mu = 12.0;
    let shipments = vec![ShipmentTrace::smoke_cool()];
    let mut m = 0.0;
    for i in 0..N_SEEDS {
        let seed = 90_000 + i * 7;
        let days = run_truth(seed, &p, 44);
        m += run_bias(sc, &days, &p, &shipments, seed + 1);
    }
    m / N_SEEDS as f64
}

#[test]
fn gsin_upc_homogeneous_fleet_count_bias_guard() {
    for sc in SCENARIOS {
        let bias = mean_bias(sc);
        assert!(
            bias.abs() <= BIAS_MAX + 1e-9,
            "{sc} count_bias={bias} exceeds {BIAS_MAX}"
        );
    }
}
