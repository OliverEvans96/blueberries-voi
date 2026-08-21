use criterion::{black_box, criterion_group, criterion_main, Criterion};
use voi_core::schedule::OrderSchedule;
use voi_core::tradeoff::{full_tradeoff_q_candidates, tradeoff_forecast};
use voi_core::{ModelParams, UnitParticleBank};

fn bench_tradeoff_forecast(c: &mut Criterion) {
    let bank = UnitParticleBank::from_rows_uniform_lots(
        vec![0.25; 32],
        (0..32).map(|i| vec![1.0 - (i as f64) * 0.01; 8]).collect(),
        8,
    );
    let params = ModelParams::default();
    let schedule = OrderSchedule::default();
    let candidates = full_tradeoff_q_candidates(params.case_size);
    c.bench_function("tradeoff_forecast_smoke", |b| {
        b.iter(|| {
            black_box(tradeoff_forecast(
                &bank,
                2,
                &params,
                &schedule,
                0,
                42,
                400,
                Some(3),
            ));
        });
    });
    assert!(candidates.len() >= 20);
}

criterion_group!(benches, bench_tradeoff_forecast);
criterion_main!(benches);
