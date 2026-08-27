//! Ladder MAE diagnostic for T-163 calibration sweeps.
//!
//! Run: `cargo run -p voi_core --release --example ladder_sweep`

use voi_core::arrival::{ArrivalCondition, ArrivalModel, resolve_arrival_exposure};
use voi_core::{DemandProfile, EngineSession, ModelParams};

fn mae(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| (x - y).abs()).sum::<f64>() / a.len() as f64
}

fn law_mean(model: &mut ArrivalModel, c: ArrivalCondition) -> f64 {
    model.filter_law_mean_f(c)
}

fn main() {
    let seed = 150_211u64;
    let mut sess = EngineSession::new(seed);
    sess.set_demand_profile(
        DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("profile"),
    );
    sess.init(seed);
    sess.set_obs_scenario("P0").unwrap();
    let params = ModelParams::default();

    let orders: Vec<u32> = (0..80).map(|i| if i % 4 == 0 { 64 } else { 0 }).collect();
    let mut deliveries = Vec::new();
    for (day, &ord) in orders.iter().enumerate() {
        let delta = sess.step(ord);
        if delta.arrivals == 0 {
            continue;
        }
        let snap = sess.snapshot_value();
        let lots = snap["live_lots"].as_array().unwrap();
        let start = lots.len().saturating_sub(voi_core::arrival::LOTS_PER_DELIVERY);
        let mut unit_f = Vec::new();
        for lot in &lots[start..] {
            let n = lot["n"].as_u64().unwrap() as usize;
            let mut vals: Vec<f64> = lot["f_values"]
                .as_array()
                .unwrap()
                .iter()
                .filter_map(|x| x.as_f64())
                .collect();
            vals.extend(std::iter::repeat_n(0.0, n.saturating_sub(vals.len())));
            unit_f.extend(vals);
        }
        let truth_mean = unit_f.iter().sum::<f64>() / unit_f.len() as f64;
        deliveries.push((day as u32, truth_mean));
    }

    sess.set_obs_scenario("F2").unwrap();
    let events_f2 = sess.events_value(0);
    sess.set_obs_scenario("F3").unwrap();
    let events_f3 = sess.events_value(0);

    let mut truth = Vec::new();
    let mut packs = Vec::new();
    let mut exposures = Vec::new();
    for (day, truth_mean) in &deliveries {
        let day_f2 = events_f2["days"]
            .as_array()
            .unwrap()
            .iter()
            .find(|d| d["day"].as_u64() == Some(*day as u64))
            .unwrap();
        packs.push(day_f2["pack_date_days"].as_i64().unwrap() as i32);
        let day_f3 = events_f3["days"]
            .as_array()
            .unwrap()
            .iter()
            .find(|d| d["day"].as_u64() == Some(*day as u64))
            .unwrap();
        let times: Vec<f64> = day_f3["temp_times_d"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        let temps: Vec<f64> = day_f3["temp_temps_c"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect();
        exposures.push(
            resolve_arrival_exposure(Some(&temps), Some(&times), params.q10, params.t_ref_c).unwrap(),
        );
        truth.push(*truth_mean);
    }

    let mut model = ArrivalModel::embedded();
    model.sync_params(&ModelParams::default());
    let p0 = vec![law_mean(&mut model, ArrivalCondition::Prior); truth.len()];
    let f2: Vec<f64> = packs
        .iter()
        .map(|&d| law_mean(&mut model, ArrivalCondition::Duration(d)))
        .collect();
    let f3: Vec<f64> = exposures
        .iter()
        .map(|&lam| law_mean(&mut model, ArrivalCondition::Exposure(lam)))
        .collect();
    let (mp0, mf2, mf3) = (mae(&p0, &truth), mae(&f2, &truth), mae(&f3, &truth));
    println!(
        "ref_life={:.0} n={} P0={mp0:.4} F2={mf2:.4} F3={mf3:.4} ratio={:.2}",
        model.reference_life_days,
        truth.len(),
        mp0 / mf2.max(1e-12)
    );
    println!("truth mean={:.3} sd={:.3}", mean(&truth), sd(&truth));
    println!("P0 pred={:.3} F2 pred mean={:.3} sd={:.3}", p0[0], mean(&f2), sd(&f2));
    println!("pack_date sd={:.3}", sd(&packs.iter().map(|&p| p as f64).collect::<Vec<_>>()));
}

fn mean(v: &[f64]) -> f64 {
    v.iter().sum::<f64>() / v.len() as f64
}

fn sd(v: &[f64]) -> f64 {
    let m = mean(v);
    (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (v.len() - 1) as f64).sqrt()
}
