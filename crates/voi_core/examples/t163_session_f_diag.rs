//! Session multilot arrival f diagnostic.
//! Run: `cargo run -p voi_core --release --example t163_session_f_diag`

use voi_core::{DemandProfile, EngineSession};

fn main() {
    let seed = 150_211u64;
    let mut sess = EngineSession::new(seed);
    sess.set_demand_profile(
        DemandProfile::from_parts(0.01, [1.0; 7], vec![1.0], 2.0).expect("profile"),
    );
    sess.init(seed);
    let orders: Vec<u32> = (0..80).map(|i| if i % 4 == 0 { 64 } else { 0 }).collect();
    for (day, &ord) in orders.iter().enumerate() {
        let delta = sess.step(ord);
        if delta.arrivals == 0 {
            continue;
        }
        let snap = sess.snapshot_value();
        let lots = snap["live_lots"].as_array().unwrap();
        println!("day={day} arrivals={} n_lots={}", delta.arrivals, lots.len());
        let mut total_n = 0u32;
        let mut weighted_f = 0.0;
        for lot in lots.iter().rev().take(3) {
            let n = lot["n"].as_u64().unwrap_or(0) as u32;
            let mean = lot["mean_f"].as_f64().unwrap_or(0.0);
            println!("  lot_id={} n={n} mean_f={mean:.3}", lot["lot_id"]);
            total_n += n;
            weighted_f += mean * n as f64;
        }
        if total_n > 0 {
            println!("  delivery weighted mean_f={:.3}", weighted_f / total_n as f64);
        }
        // Wrong: last lot only padded (ladder test bug pattern)
        let last = lots.last().unwrap();
        let f_vals: Vec<f64> = last["f_values"].as_array().unwrap().iter().filter_map(|x| x.as_f64()).collect();
        let mut padded = f_vals.clone();
        padded.extend(std::iter::repeat_n(0.0, delta.arrivals as usize - padded.len()));
        let wrong_mean = padded.iter().sum::<f64>() / padded.len() as f64;
        println!("  WRONG last-lot-padded mean={wrong_mean:.3}");
        break;
    }
}
