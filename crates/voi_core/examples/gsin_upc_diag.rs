//! Diagnostic: UPC vs GSIN belief accuracy on a common truth trajectory.
//!
//! Runs one shared physics episode per seed (fixed exogenous order script → identical
//! truth for every channel, CRN), then replays the richest day log through each ObsMask.
//!
//! Metrics are reported both **store-level** (partition-free) and **per-lot**. Per-lot
//! comparison aligns by *arrival order from the newest*: both channels observe the
//! delivery stream, so the bank's j-th-newest segment is truth's j-th-newest lot. Only
//! GSIN additionally learns which lot each sale and spoil came from — that difference is
//! what these numbers are meant to price.
//!
//! Run: `cargo run -p voi_core --release --example gsin_upc_diag [out.json]`

use rand::SeedableRng;
use rand_pcg::Pcg64;

use voi_core::day_step::{alive_by_lot, unit_day_step, UnitDayStepIn};
use voi_core::obs::{mask_for, RichDay};
use voi_core::physics::draw_demand;
use voi_core::policy::effective_inventory_f_belief;
use voi_core::shipments::{arrival_receipt_meta_with_trace, ShipmentTrace};
use voi_core::unit_pf::{filter_step_unit, UnitParticleBank};
use voi_core::{belief_flat_from_unit_bank, truth_f_belief, ModelParams};

const HORIZON: u32 = 60;
const N_PARTICLES: usize = 200;
const BURN_IN: u32 = 10;
const K_BINS: usize = 16;
const N_SEEDS: u64 = 12;
const WIRE_L: usize = 10;
const WIRE_K: usize = 8;
const SCENARIOS: [&str; 6] = ["P0", "P1", "F1", "F2a", "F2", "F3"];

fn stream_rng(root: u64, day: u32, stream: u64) -> Pcg64 {
    Pcg64::seed_from_u64(
        root.wrapping_add(u64::from(day) * 1_000_003)
            .wrapping_add(stream),
    )
}

/// Homogeneous fleet: every delivery takes the same cold trip (lots are interchangeable).
fn shipments_homogeneous() -> Vec<ShipmentTrace> {
    vec![ShipmentTrace::smoke_cool()]
}

/// Heterogeneous fleet: transit duration varies, so lots differ at birth.
fn shipments_heterogeneous() -> Vec<ShipmentTrace> {
    vec![
        ShipmentTrace {
            times_d: vec![0.0, 0.5],
            temps_c: vec![1.0, 1.0],
        },
        ShipmentTrace::smoke_cool(),
        ShipmentTrace {
            times_d: vec![0.0, 4.0],
            temps_c: vec![1.0, 1.0],
        },
    ]
}

struct TruthDay {
    rich: RichDay,
    on_hand: u32,
    alive_f: Vec<f64>,
    /// Every lot ever received, oldest first: `(alive_count, mean_f_of_alive)`.
    lots: Vec<(u32, f64)>,
    eff_inv: f64,
}

fn run_truth(
    seed: u64,
    params: &ModelParams,
    shipments: &[ShipmentTrace],
    order_script: &dyn Fn(u32) -> u32,
) -> Vec<TruthDay> {
    let mut freshness: Vec<f64> = vec![];
    let mut lot_offsets: Vec<usize> = vec![0];
    let mut lot_ids: Vec<i64> = vec![];
    let mut pending: std::collections::BTreeMap<u32, u32> = std::collections::BTreeMap::new();
    let mut next_lot = 1i64;
    let lead_time = 1u32;
    let mut out_days = Vec::new();

    for day in 0..HORIZON {
        let order = order_script(day);
        *pending.entry(day + lead_time).or_insert(0) += order;
        let arrival = pending.remove(&day).unwrap_or(0);
        let pre_lot_ids = lot_ids.clone();
        let (f_at_receipt, age_at_receipt, pack_date_days, shipment_trace, arrival_lot_ids) =
            if arrival > 0 {
                let mut rs = stream_rng(seed, day, 4);
                let mut rn = stream_rng(seed, day, 5);
                let (f, tau, pack, trace) =
                    arrival_receipt_meta_with_trace(&mut rs, &mut rn, shipments, params, 1.0);
                let lot_id = next_lot;
                lot_ids.push(lot_id);
                next_lot += 1;
                (Some(f), Some(tau), Some(pack), Some(trace), vec![lot_id])
            } else {
                (None, None, None, None, Vec::new())
            };
        let mut rng_d = stream_rng(seed, day, 1);
        let demand = draw_demand(&mut rng_d, params, Some(day));
        let mut rng_gamma = stream_rng(seed, day, 3);
        let mut rng_alloc = stream_rng(seed, day, 2);
        let mut rng_ship = if arrival > 0 {
            Some(stream_rng(seed, day, 4))
        } else {
            None
        };
        let mut rng_sensor = if arrival > 0 {
            Some(stream_rng(seed, day, 5))
        } else {
            None
        };
        let input = UnitDayStepIn {
            freshness: freshness.clone(),
            lot_offsets: lot_offsets.clone(),
            demand: Some(demand),
            gamma_decrement: None,
            deliver: arrival > 0,
            deliver_units: if arrival > 0 { Some(arrival) } else { None },
            delivery_f: None,
            units_per_lot: Some(params.units_per_lot),
            age_at_receipt: None,
            pack_age_mean: None,
        };
        let step = unit_day_step(
            &input,
            params,
            shipments,
            Some(&mut rng_gamma),
            Some(&mut rng_alloc),
            rng_ship.as_mut(),
            rng_sensor.as_mut(),
        );
        freshness = step.freshness;
        lot_offsets = step.lot_offsets;
        let alive = alive_by_lot(&freshness, &lot_offsets);
        let on_hand: u32 = alive.iter().sum();
        let lots: Vec<(u32, f64)> = (0..lot_offsets.len() - 1)
            .map(|ell| {
                let sl = &freshness[lot_offsets[ell]..lot_offsets[ell + 1]];
                let live: Vec<f64> = sl.iter().copied().filter(|&f| f > 0.0).collect();
                let mf = if live.is_empty() {
                    0.0
                } else {
                    live.iter().sum::<f64>() / live.len() as f64
                };
                (alive[ell], mf)
            })
            .collect();
        let (t_counts, t_marg, t_grid) = truth_f_belief(&freshness, &lot_offsets, WIRE_K);
        out_days.push(TruthDay {
            rich: RichDay {
                sales_total: step.sales_total,
                waste_total: step.waste_total,
                arrivals: arrival,
                sales_by: step.sales_by.clone(),
                waste_by: step.waste_by.clone(),
                lot_ids: pre_lot_ids,
                arrival_lot_ids,
                shipment_trace,
                f_at_receipt,
                age_at_receipt,
                pack_date_days,
            },
            on_hand,
            alive_f: freshness.iter().copied().filter(|&f| f > 0.0).collect(),
            lots,
            eff_inv: effective_inventory_f_belief(&t_counts, &t_marg, &t_grid, 0, 1.0),
        });
    }
    out_days
}

fn hist(vals: &[f64], k: usize) -> Vec<f64> {
    let mut h = vec![0.0; k];
    if vals.is_empty() {
        return h;
    }
    for &v in vals {
        let b = ((v.clamp(0.0, 1.0) * (k - 1) as f64).round() as usize).min(k - 1);
        h[b] += 1.0;
    }
    let z: f64 = h.iter().sum();
    for x in &mut h {
        *x /= z;
    }
    h
}

fn tv(a: &[f64], b: &[f64]) -> f64 {
    0.5 * a
        .iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).abs())
        .sum::<f64>()
}

/// Per-day belief-vs-truth trace for one channel on one seed.
#[derive(Default, Clone)]
struct Series {
    day: Vec<u32>,
    truth_on_hand: Vec<f64>,
    belief_on_hand: Vec<f64>,
    truth_mean_f: Vec<f64>,
    belief_mean_f: Vec<f64>,
    ess: Vec<f64>,
}

#[derive(Default, Clone)]
struct Metrics {
    n: f64,
    lot_n: f64,
    count_mae: f64,
    count_bias: f64,
    store_meanf_mae: f64,
    lot_meanf_mae: f64,
    lot_count_mae: f64,
    tv_sum: f64,
    ess_sum: f64,
    eff_inv_mae: f64,
    ms: f64,
    series: Series,
}

impl Metrics {
    fn add(&mut self, o: &Metrics) {
        self.n += o.n;
        self.lot_n += o.lot_n;
        self.count_mae += o.count_mae;
        self.count_bias += o.count_bias;
        self.store_meanf_mae += o.store_meanf_mae;
        self.lot_meanf_mae += o.lot_meanf_mae;
        self.lot_count_mae += o.lot_count_mae;
        self.tv_sum += o.tv_sum;
        self.ess_sum += o.ess_sum;
        self.eff_inv_mae += o.eff_inv_mae;
        self.ms += o.ms;
    }
}

fn run_channel(scenario: &str, days: &[TruthDay], params: &ModelParams, seed: u64) -> Metrics {
    let mask = mask_for(scenario).expect("valid scenario");
    let n = N_PARTICLES;
    let mut bank = UnitParticleBank::empty(n);
    let mut m = Metrics::default();
    let t0 = std::time::Instant::now();
    for (d, td) in days.iter().enumerate() {
        let obs = mask.apply(&td.rich);
        let mut frng = stream_rng(seed, d as u32, 6);
        let diag = filter_step_unit(&mut bank, &obs, params, &mut frng);
        if (d as u32) < BURN_IN {
            continue;
        }
        m.n += 1.0;
        m.ess_sum += diag.ess;

        // Store-level: expected live count, mean f, and freshness histogram.
        let mut exp_alive = 0.0;
        let mut all_alive_f: Vec<f64> = Vec::new();
        let mut meanf_acc = 0.0;
        let mut meanf_w = 0.0;
        for row in &bank.freshness {
            let live: Vec<f64> = row.iter().copied().filter(|&f| f > 0.0).collect();
            exp_alive += live.len() as f64 / n as f64;
            if !live.is_empty() {
                meanf_acc += live.iter().sum::<f64>() / live.len() as f64;
                meanf_w += 1.0;
            }
            all_alive_f.extend(live);
        }
        let truth_mf = if td.alive_f.is_empty() {
            0.0
        } else {
            td.alive_f.iter().sum::<f64>() / td.alive_f.len() as f64
        };
        let bel_mf = if meanf_w > 0.0 {
            meanf_acc / meanf_w
        } else {
            0.0
        };
        m.count_mae += (exp_alive - f64::from(td.on_hand)).abs();
        m.count_bias += exp_alive - f64::from(td.on_hand);
        m.store_meanf_mae += (bel_mf - truth_mf).abs();
        m.tv_sum += tv(&hist(&all_alive_f, K_BINS), &hist(&td.alive_f, K_BINS));
        m.series.day.push(d as u32);
        m.series.truth_on_hand.push(f64::from(td.on_hand));
        m.series.belief_on_hand.push(exp_alive);
        m.series.truth_mean_f.push(truth_mf);
        m.series.belief_mean_f.push(bel_mf);
        m.series.ess.push(diag.ess);

        // Per-lot, aligned by arrival order from the newest.
        let n_bank = bank.n_lots();
        for j in 0..td.lots.len() {
            let (t_count, t_mean_f) = td.lots[td.lots.len() - 1 - j];
            if j >= n_bank {
                if t_count > 0 {
                    m.lot_n += 1.0;
                    m.lot_count_mae += f64::from(t_count);
                    m.lot_meanf_mae += t_mean_f;
                }
                continue;
            }
            let ell = n_bank - 1 - j;
            let (start, end) = (bank.lot_offsets[ell], bank.lot_offsets[ell + 1]);
            let mut c = 0.0;
            let mut mf = 0.0;
            let mut mf_w = 0.0;
            for row in &bank.freshness {
                let live: Vec<f64> = row[start..end]
                    .iter()
                    .copied()
                    .filter(|&f| f > 0.0)
                    .collect();
                c += live.len() as f64 / n as f64;
                if !live.is_empty() {
                    mf += live.iter().sum::<f64>() / live.len() as f64;
                    mf_w += 1.0;
                }
            }
            if t_count == 0 && c == 0.0 {
                continue;
            }
            m.lot_n += 1.0;
            m.lot_count_mae += (c - f64::from(t_count)).abs();
            m.lot_meanf_mae += ((if mf_w > 0.0 { mf / mf_w } else { 0.0 }) - t_mean_f).abs();
        }

        // Controller-facing summary through the studio belief wire.
        let wire = belief_flat_from_unit_bank(&bank, WIRE_L, WIRE_K);
        let jf = |k: &str| -> Vec<f64> {
            wire[k]
                .as_array()
                .map(|a| a.iter().filter_map(serde_json::Value::as_f64).collect())
                .unwrap_or_default()
        };
        let eff = effective_inventory_f_belief(
            &jf("lot_counts"),
            &jf("f_marginals"),
            &jf("f_grid"),
            0,
            1.0,
        );
        m.eff_inv_mae += (eff - td.eff_inv).abs();
    }
    m.ms = t0.elapsed().as_secs_f64() * 1000.0 / days.len() as f64;
    m
}

fn json_series(s: &Series) -> String {
    let arr = |v: &[f64]| {
        v.iter()
            .map(|x| format!("{x:.6}"))
            .collect::<Vec<_>>()
            .join(",")
    };
    format!(
        r#"{{"day":[{}],"truth_on_hand":[{}],"belief_on_hand":[{}],"truth_mean_f":[{}],"belief_mean_f":[{}],"ess":[{}]}}"#,
        s.day
            .iter()
            .map(u32::to_string)
            .collect::<Vec<_>>()
            .join(","),
        arr(&s.truth_on_hand),
        arr(&s.belief_on_hand),
        arr(&s.truth_mean_f),
        arr(&s.belief_mean_f),
        arr(&s.ess),
    )
}

fn report(
    title: &str,
    shipments: &[ShipmentTrace],
    params: &ModelParams,
    order_every: u32,
    order_qty: u32,
) -> Vec<String> {
    println!("\n=== {title} ===");
    println!(
        "{:<5} {:>8} {:>8} {:>10} {:>9} {:>10} {:>8} {:>8} {:>7} {:>7}",
        "chan",
        "cnt_MAE",
        "cnt_bias",
        "storeF_MAE",
        "lotF_MAE",
        "lotCnt_MAE",
        "hist_TV",
        "effInv",
        "ESS",
        "ms/day"
    );
    let mut rows = Vec::new();
    for scenario in SCENARIOS {
        let mut agg = Metrics::default();
        let mut first_series = Series::default();
        for i in 0..N_SEEDS {
            let seed = 90_000 + i * 7;
            let days = run_truth(seed, params, shipments, &|d| {
                if d % order_every == 0 {
                    order_qty
                } else {
                    0
                }
            });
            let m = run_channel(scenario, &days, params, seed + 1);
            if i == 0 {
                first_series = m.series.clone();
            }
            agg.add(&m);
        }
        let n = agg.n.max(1.0);
        let ln = agg.lot_n.max(1.0);
        let (cnt, bias, sf, lf, lc, tvm, ei, ess, ms) = (
            agg.count_mae / n,
            agg.count_bias / n,
            agg.store_meanf_mae / n,
            agg.lot_meanf_mae / ln,
            agg.lot_count_mae / ln,
            agg.tv_sum / n,
            agg.eff_inv_mae / n,
            agg.ess_sum / n,
            agg.ms / N_SEEDS as f64,
        );
        println!(
            "{scenario:<5} {cnt:>8.3} {bias:>8.3} {sf:>10.4} {lf:>9.4} {lc:>10.3} {tvm:>8.3} {ei:>8.3} {ess:>7.1} {ms:>7.2}"
        );
        rows.push(format!(
            r#"{{"regime":"{title}","channel":"{scenario}","count_mae":{cnt:.6},"count_bias":{bias:.6},"store_mean_f_mae":{sf:.6},"lot_mean_f_mae":{lf:.6},"lot_count_mae":{lc:.6},"hist_tv":{tvm:.6},"eff_inv_mae":{ei:.6},"ess":{ess:.3},"ms_per_day":{ms:.4},"series":{}}}"#,
            json_series(&first_series)
        ));
    }
    rows
}

fn main() {
    let mut params = ModelParams::default();
    params.demand_mu = 12.0;
    // Order cadence sized so several lots coexist on the shelf — the regime where lot
    // attribution is a live question. mu = 12/day, so 44 units every 3 days ~ 1.2x demand.
    let mut rows = Vec::new();
    rows.extend(report(
        "Homogeneous fleet, overlapping lots",
        &shipments_homogeneous(),
        &params,
        3,
        44,
    ));
    rows.extend(report(
        "Heterogeneous fleet, overlapping lots",
        &shipments_heterogeneous(),
        &params,
        3,
        44,
    ));
    rows.extend(report(
        "Heterogeneous fleet, deep shelf",
        &shipments_heterogeneous(),
        &params,
        3,
        72,
    ));
    if let Some(path) = std::env::args().nth(1) {
        let json = format!("[\n  {}\n]\n", rows.join(",\n  "));
        std::fs::write(&path, json).expect("write diagnostic json");
        println!("\nwrote {path}");
    }
}
