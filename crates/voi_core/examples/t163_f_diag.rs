//! Quick MC diagnostic for arrival freshness distribution and Prior belief bias.
//!
//! Run: `cargo run -p voi_core --release --example t163_f_diag`

use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::arrival::{ArrivalCondition, ArrivalModel};

fn main() {
    let model = ArrivalModel::embedded();
    let mut rng_d = Pcg64::seed_from_u64(163);
    let mut rng_t = Pcg64::seed_from_u64(164);
    let mut rng_p = Pcg64::seed_from_u64(165);
    let mut rng_g = Pcg64::seed_from_u64(166);
    let n = 5000usize;
    let mut fs = Vec::with_capacity(n);
    let mut lambdas = Vec::with_capacity(n);
    for _ in 0..n {
        let draw = model.draw_truth_delivery(
            "abdella_all",
            1,
            &mut rng_d,
            &mut rng_t,
            &mut rng_p,
            &mut rng_g,
        );
        fs.push(draw.unit_f[0]);
        lambdas.push(draw.lambda);
    }
    fs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = fs.iter().sum::<f64>() / n as f64;
    let pct_below_50 = fs.iter().filter(|&&f| f < 0.5).count() as f64 / n as f64;
    let pct_60_90 = fs
        .iter()
        .filter(|&&f| (0.6..=0.9).contains(&f))
        .count() as f64
        / n as f64;
    let p10 = fs[n / 10];
    let p50 = fs[n / 2];
    let p90 = fs[n * 9 / 10];
    let lam_mean = lambdas.iter().sum::<f64>() / n as f64;
    println!("Truth arrival f: mean={mean:.3} p10={p10:.3} p50={p50:.3} p90={p90:.3}");
    println!("  pct<f0.5={:.1}%  pct in [0.6,0.9]={:.1}%", pct_below_50 * 100.0, pct_60_90 * 100.0);
    println!("  mean lambda={lam_mean:.3}");

    let mut model2 = ArrivalModel::embedded();
    let prior = model2.rung_law_on_grid(ArrivalCondition::Prior, "abdella_all", 64);
    println!(
        "Filter Prior mean_f={:.3} sd={:.3}",
        prior.mean_f, prior.sd_f
    );

    let mut rng_b = Pcg64::seed_from_u64(167);
    let mut filter_fs = Vec::with_capacity(n);
    for _ in 0..n {
        filter_fs.push(
            model2
                .sample_filter_birth_units(ArrivalCondition::Prior, 1, &mut rng_b)[0],
        );
    }
    let filt_mean = filter_fs.iter().sum::<f64>() / n as f64;
    println!("Filter Prior sample mean_f={filt_mean:.3}");
    println!(
        "Belief bias (filter-truth) at Prior: {:.3}",
        filt_mean - mean
    );
}
