//! T-163 Stage 2 — three fixed lots per delivery (L = 3), split not multiplied.
//!
//! RED tests for acceptance criteria S2.1–S2.8. Production still mints one lot per
//! delivery; these assertions fail until multi-lot wiring lands.

use rand::SeedableRng;
use rand_pcg::Pcg64;

use voi_core::arrival::{resolve_arrival_exposure, ArrivalCondition, ArrivalModel};
use voi_core::obs::FilterObs;
use voi_core::shipments::calendar_transit_days;
use voi_core::{filter_step_unit, EngineSession, ModelParams, UnitParticleBank};

const LOTS_PER_DELIVERY: usize = 3;

fn step_to_first_delivery(seed: u64) -> (EngineSession, u32, u32) {
    let mut sess = EngineSession::new(seed);
    sess.init(seed);
    sess.set_obs_scenario("F3").expect("F3 scenario");
    let orders = [48u32; 25];
    let mut delivery_day = None;
    let mut arrivals = 0u32;
    for (day, &q) in orders.iter().enumerate() {
        let delta = sess.step(q);
        if delta.arrivals > 0 {
            delivery_day = Some(day as u32);
            arrivals = delta.arrivals;
            break;
        }
    }
    let day = delivery_day.expect("expected at least one delivery in 25 steps");
    (sess, day, arrivals)
}

fn first_delivery_day(events: &serde_json::Value) -> &serde_json::Value {
    events["days"]
        .as_array()
        .expect("events.days array")
        .iter()
        .find(|d| d["arrivals"].as_u64().unwrap_or(0) > 0)
        .expect("at least one delivery day in events wire")
}

fn trace_lambda(trace: &serde_json::Value, q10: f64, t_ref: f64) -> f64 {
    let times: Vec<f64> = trace["times_d"]
        .as_array()
        .expect("trace.times_d")
        .iter()
        .map(|v| v.as_f64().expect("time"))
        .collect();
    let temps: Vec<f64> = trace["temps_c"]
        .as_array()
        .expect("trace.temps_c")
        .iter()
        .map(|v| v.as_f64().expect("temp"))
        .collect();
    resolve_arrival_exposure(Some(&temps), Some(&times), q10, t_ref)
        .expect("trace integrates to Λ")
}

/// Longest shared suffix (by time/temp pairs) across per-lot traces — the DC→store leg.
fn shared_tail_len(traces: &[&serde_json::Value]) -> usize {
    if traces.is_empty() {
        return 0;
    }
    let lens: Vec<usize> = traces
        .iter()
        .map(|t| t["times_d"].as_array().map(|a| a.len()).unwrap_or(0))
        .collect();
    let min_len = *lens.iter().min().unwrap_or(&0);
    for tail in (1..=min_len).rev() {
        let mut ok = true;
        let ref_times: Vec<f64> = traces[0]["times_d"]
            .as_array()
            .unwrap()
            .iter()
            .rev()
            .take(tail)
            .map(|v| v.as_f64().unwrap())
            .collect();
        let ref_temps: Vec<f64> = traces[0]["temps_c"]
            .as_array()
            .unwrap()
            .iter()
            .rev()
            .take(tail)
            .map(|v| v.as_f64().unwrap())
            .collect();
        for tr in &traces[1..] {
            let times: Vec<f64> = tr["times_d"]
                .as_array()
                .unwrap()
                .iter()
                .rev()
                .take(tail)
                .map(|v| v.as_f64().unwrap())
                .collect();
            let temps: Vec<f64> = tr["temps_c"]
                .as_array()
                .unwrap()
                .iter()
                .rev()
                .take(tail)
                .map(|v| v.as_f64().unwrap())
                .collect();
            if times != ref_times || temps != ref_temps {
                ok = false;
                break;
            }
        }
        if ok {
            return tail;
        }
    }
    0
}

fn upstream_lambda(total: f64, shared: f64) -> f64 {
    (total - shared).max(0.0)
}

// --- S2.1: three lot ids per delivery -----------------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn delivery_mints_three_lot_ids() {
    let (sess, _day, _arrivals) = step_to_first_delivery(42);
    let events = sess.events_value(0);
    let day_ev = first_delivery_day(&events);
    let ids = day_ev["arrival_lot_ids"]
        .as_array()
        .expect("arrival_lot_ids on delivery day");
    assert_eq!(
        ids.len(),
        LOTS_PER_DELIVERY,
        "advance_one must mint L={LOTS_PER_DELIVERY} lot ids, got {:?}",
        ids
    );
    let unique: std::collections::HashSet<i64> = ids
        .iter()
        .filter_map(|v| v.as_i64())
        .collect();
    assert_eq!(
        unique.len(),
        LOTS_PER_DELIVERY,
        "lot ids must be distinct: {:?}",
        ids
    );
}

// --- S2.2: Λ_ℓ = Λ_upstream,ℓ + Λ_shared ------------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn lot_exposure_is_upstream_plus_shared() {
    let model = ArrivalModel::embedded();
    let (sess, _day, _) = step_to_first_delivery(163_002);
    let events = sess.events_value(0);
    let day_ev = first_delivery_day(&events);
    let traces_by_lot = day_ev["temp_traces_by_lot"]
        .as_array()
        .expect("F3 delivery must expose temp_traces_by_lot");
    assert_eq!(
        traces_by_lot.len(),
        LOTS_PER_DELIVERY,
        "expected {LOTS_PER_DELIVERY} per-lot traces"
    );

    let trace_refs: Vec<&serde_json::Value> = traces_by_lot.iter().collect();
    let tail_pts = shared_tail_len(&trace_refs);
    assert!(
        tail_pts >= 2,
        "splined traces must share a DC→store tail (>=2 points), got {tail_pts}"
    );

    let mut shared_lambda = 0.0;
    if tail_pts > 0 {
        let tail_times: Vec<f64> = trace_refs[0]["times_d"]
            .as_array()
            .unwrap()
            .iter()
            .rev()
            .take(tail_pts)
            .map(|v| v.as_f64().unwrap())
            .collect();
        let tail_temps: Vec<f64> = trace_refs[0]["temps_c"]
            .as_array()
            .unwrap()
            .iter()
            .rev()
            .take(tail_pts)
            .map(|v| v.as_f64().unwrap())
            .collect();
        shared_lambda = resolve_arrival_exposure(
            Some(&tail_temps),
            Some(&tail_times),
            model.q10,
            model.t_ref,
        )
        .unwrap_or(0.0);
    }

    let mut total_lambdas = Vec::with_capacity(LOTS_PER_DELIVERY);
    for tr in &trace_refs {
        total_lambdas.push(trace_lambda(tr, model.q10, model.t_ref));
    }
    assert!(
        total_lambdas.iter().any(|&l| (l - shared_lambda).abs() > 1e-6),
        "upstream legs must differ across lots; all Λ_ℓ == Λ_shared"
    );
    for (ell, &lambda_l) in total_lambdas.iter().enumerate() {
        let upstream = upstream_lambda(lambda_l, shared_lambda);
        let recomposed = upstream + shared_lambda;
        assert!(
            (recomposed - lambda_l).abs() < 1e-3 * lambda_l.max(1.0),
            "lot {ell}: Λ_ℓ={lambda_l} must equal Λ_upstream+Λ_shared={recomposed} \
             (shared={shared_lambda})"
        );
    }
}

// --- S2.3: three splined traces with shared tail ------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn per_lot_traces_spliced() {
    let (sess, _day, _) = step_to_first_delivery(163_003);
    let events = sess.events_value(0);
    let day_ev = first_delivery_day(&events);
    let traces = day_ev["temp_traces_by_lot"]
        .as_array()
        .expect("temp_traces_by_lot on delivery day");
    assert_eq!(traces.len(), LOTS_PER_DELIVERY);

    let mut durations = Vec::new();
    for (ell, tr) in traces.iter().enumerate() {
        let lot_id = tr["lot_id"].as_i64().unwrap_or(-1);
        assert!(
            lot_id >= 0,
            "trace {ell} must carry lot_id, got {lot_id:?}"
        );
        let times: Vec<f64> = tr["times_d"]
            .as_array()
            .expect("times_d")
            .iter()
            .map(|v| v.as_f64().unwrap())
            .collect();
        let temps: Vec<f64> = tr["temps_c"]
            .as_array()
            .expect("temps_c")
            .iter()
            .map(|v| v.as_f64().unwrap())
            .collect();
        assert!(times.len() >= 3, "lot {ell}: trace too short");
        assert_eq!(times.len(), temps.len());
        let d = calendar_transit_days(&voi_core::ShipmentTrace {
            times_d: times.clone(),
            temps_c: temps.clone(),
        });
        durations.push(d);
        let min_t = temps.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_t = temps.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        assert!(
            (max_t - min_t).abs() > 0.02,
            "lot {ell}: trace must not be constant"
        );
    }
    let min_d = durations.iter().cloned().fold(f64::INFINITY, f64::min);
    let max_d = durations.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let spread = max_d - min_d;
    assert!(
        spread > 0.05,
        "upstream legs must diverge in duration: {:?}",
        durations
    );
    let trace_refs: Vec<&serde_json::Value> = traces.iter().collect();
    assert!(
        shared_tail_len(&trace_refs) >= 2,
        "traces must converge on identical DC→store tail"
    );
}

// --- S2.4: quantity split, not multiplied -------------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn delivery_quantity_split_not_multiplied() {
    let (sess, _day, arrivals) = step_to_first_delivery(163_004);
    let events = sess.events_value(0);
    let day_ev = first_delivery_day(&events);
    assert_eq!(
        day_ev["arrivals"].as_u64().unwrap() as u32,
        arrivals,
        "total arrivals must equal order qty, not L×qty"
    );
    assert!(
        arrivals > LOTS_PER_DELIVERY as u32,
        "test needs splittable qty > L"
    );

    let by_lot = day_ev["arrivals_by"]
        .as_array()
        .expect("arrivals_by per-lot quantities");
    assert_eq!(
        by_lot.len(),
        LOTS_PER_DELIVERY,
        "expected per-lot quantity vector length {LOTS_PER_DELIVERY}"
    );
    let sum: u32 = by_lot
        .iter()
        .map(|v| v.as_u64().unwrap_or(0) as u32)
        .sum();
    assert_eq!(
        sum, arrivals,
        "per-lot quantities must sum to total delivery, not multiply it"
    );
    let max_lot = by_lot
        .iter()
        .map(|v| v.as_u64().unwrap_or(0))
        .max()
        .unwrap_or(0);
    assert!(
        max_lot < u64::from(arrivals),
        "no single lot should hold the entire delivery when L={LOTS_PER_DELIVERY}"
    );
}

// --- S2.5: LGTIN births three segments ---------------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn lgtin_three_segments_per_delivery() {
    use voi_core::shipments::mod21_demo_shipments;

    let arrivals = 40u32;
    let n = 8usize;
    let mut bank = UnitParticleBank::empty(n);
    let lot_ids: Vec<i64> = (100..100 + LOTS_PER_DELIVERY as i64).collect();
    let pack_dates: Vec<i32> = vec![3, 5, 4];
    let obs = FilterObs {
        sales_tot: Some(0),
        waste_tot: Some(0),
        arrivals,
        arrival_lot_ids: Some(lot_ids.clone()),
        pack_date_days: Some(pack_dates[0]),
        ..Default::default()
    };
    let params = ModelParams::default();
    let mut rng = Pcg64::seed_from_u64(163_005);
    filter_step_unit(
        &mut bank,
        &obs,
        &params,
        &mod21_demo_shipments("short_haul"),
        &mut rng,
    );
    assert_eq!(
        bank.lot_ids.len(),
        LOTS_PER_DELIVERY,
        "LGTIN must birth {LOTS_PER_DELIVERY} segments, got ids {:?}",
        bank.lot_ids
    );
    let seg_units: Vec<usize> = bank
        .lot_offsets
        .windows(2)
        .map(|w| w[1] - w[0])
        .collect();
    assert_eq!(seg_units.len(), LOTS_PER_DELIVERY);
    let born: usize = seg_units.iter().sum();
    assert_eq!(
        born, arrivals as usize,
        "segment widths must sum to delivery qty, not L×qty"
    );
    assert!(
        seg_units.iter().all(|&w| w > 0),
        "each LGTIN segment must receive a positive split: {seg_units:?}"
    );
}

// --- S2.6: UPC merged cohort from mixture law ---------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn upc_merged_cohort_uses_mixture_law() {
    use voi_core::shipments::mod21_demo_shipments;

    let body = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src/unit_pf.rs"),
    )
    .expect("read unit_pf.rs");
    assert!(
        body.contains("sample_filter_birth_units_mixture"),
        "UPC birth path must call mixture sampler over per-lot conditions"
    );

    let mut model = ArrivalModel::embedded();
    let conditions = [
        ArrivalCondition::Duration(3),
        ArrivalCondition::Duration(5),
        ArrivalCondition::Duration(7),
    ];
    let mix = model.mixture_law(&conditions);
    let mean_of_vars: f64 = conditions
        .iter()
        .map(|&c| match c {
            ArrivalCondition::Duration(d) => model.variance_f_given_d(d),
            _ => unreachable!(),
        })
        .sum::<f64>()
        / conditions.len() as f64;
    assert!(
        mix.sd_f * mix.sd_f > mean_of_vars * 1.05,
        "mixture variance must exceed average component variance for UPC cohort"
    );

    let arrivals = 39u32;
    let n = 8usize;
    let mut bank = UnitParticleBank::empty(n);
    let obs = FilterObs {
        sales_tot: Some(0),
        waste_tot: Some(0),
        arrivals,
        arrival_lot_ids: Some((200..203).collect()),
        pack_date_days: Some(4),
        ..Default::default()
    };
    let params = ModelParams::default();
    let mut rng = Pcg64::seed_from_u64(163_006);
    filter_step_unit(
        &mut bank,
        &obs,
        &params,
        &mod21_demo_shipments("short_haul"),
        &mut rng,
    );
    assert_eq!(
        bank.lot_ids.len(),
        1,
        "UPC must birth one merged cohort segment, got {:?}",
        bank.lot_ids
    );
    let born = bank.lot_offsets.last().copied().unwrap_or(0);
    assert_eq!(
        born, arrivals as usize,
        "UPC merged segment must span full delivery qty"
    );
}

// --- S2.7: resolve_arrival_f_law is per-lot ---------------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn resolve_arrival_f_law_per_lot() {
    let body = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src/unit_pf.rs"),
    )
    .expect("read unit_pf.rs");
    assert!(
        body.contains("resolve_arrival_f_law_per_lot")
            || (body.contains("for ") && body.contains("pack_dates_by_lot")),
        "unit_pf must resolve arrival law per lot, not once per delivery"
    );

    let mut sess_f2 = EngineSession::new(163_007);
    sess_f2.init(163_007);
    sess_f2.set_obs_scenario("F2").expect("F2");
    let orders = [48u32; 25];
    for &q in &orders {
        let delta = sess_f2.step(q);
        if delta.arrivals > 0 {
            break;
        }
    }
    let events = sess_f2.events_value(0);
    let day_ev = first_delivery_day(&events);
    let pack_dates = day_ev["pack_dates_by_lot"]
        .as_array()
        .expect("F2 events must expose per-lot pack dates");
    assert_eq!(pack_dates.len(), LOTS_PER_DELIVERY);
    let distinct: std::collections::HashSet<i64> = pack_dates
        .iter()
        .filter_map(|v| v.as_i64())
        .collect();
    assert!(
        distinct.len() >= 2,
        "per-lot pack dates must differ across upstream legs: {:?}",
        pack_dates
    );
}

// --- S2.8: FilterObs per-lot fields, no new mask ----------------------------

#[test]
#[ignore = "T-163 multilot EngineSession stepping; slow: run via cargo test -- --ignored"]
fn filter_obs_carries_per_lot_pack_dates_and_traces() {
    let mask_body = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src/obs.rs"),
    )
    .expect("read obs.rs");
    assert!(
        !mask_body.contains("delivery_history_by_lot"),
        "must not add delivery_history_by_lot mask field"
    );

    let (sess, _day, _) = step_to_first_delivery(163_008);
    let events = sess.events_value(0);
    let day_ev = first_delivery_day(&events);

    assert!(
        day_ev["pack_dates_by_lot"].is_null(),
        "F3 must not expose per-lot pack dates (pack_date not in mask)"
    );

    let traces = day_ev["temp_traces_by_lot"]
        .as_array()
        .expect("events wire must carry per-lot temperature traces on F3 delivery days");
    assert_eq!(traces.len(), LOTS_PER_DELIVERY);
    for (ell, tr) in traces.iter().enumerate() {
        let times = tr["times_d"].as_array().expect("times_d");
        let temps = tr["temps_c"].as_array().expect("temps_c");
        assert_eq!(times.len(), temps.len());
        assert!(
            times.len() >= 2,
            "lot {ell}: trace must have multiple points"
        );
        assert!(
            tr["lot_id"].as_i64().is_some(),
            "lot {ell}: trace must name its lot_id"
        );
    }

    let mut sess_p0 = EngineSession::new(163_008);
    sess_p0.init(163_008);
    sess_p0.set_obs_scenario("P0").expect("P0");
    let orders = [48u32; 25];
    for &q in &orders {
        let delta = sess_p0.step(q);
        if delta.arrivals > 0 {
            break;
        }
    }
    let p0_events = sess_p0.events_value(0);
    let p0_day = first_delivery_day(&p0_events);
    assert!(
        p0_day["pack_dates_by_lot"].is_null(),
        "P0 must not leak per-lot pack dates"
    );
    assert!(
        p0_day["temp_traces_by_lot"].is_null(),
        "P0 must not leak per-lot temperature traces"
    );
}
