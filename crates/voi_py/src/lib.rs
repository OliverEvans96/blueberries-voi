use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rand::SeedableRng;
use rand_pcg::Pcg64;
use voi_core::{
    crate_name, day_step, filter_step, rollout_order, run_closed_loop_episode, run_voi_crn_cell,
    sequential_wor_composition_probs, weibull_survival, CrnBudgets, DayDelta, DayStepIn,
    EngineSession, FilterObs, ModelParams, ParticleBank, ShipmentTrace,
};

#[pyfunction]
fn weibull_survival_py(tau: f64, beta: f64, eta: f64) -> f64 {
    weibull_survival(tau, beta, eta)
}

#[pyfunction]
fn sequential_wor_py(counts: Vec<u32>, sales_tot: i32, weights: Vec<f64>) -> Vec<(Vec<u32>, f64)> {
    sequential_wor_composition_probs(&counts, sales_tot, &weights)
}

#[pyfunction]
fn day_step_injected(
    counts: Vec<u32>,
    taus: Vec<f64>,
    lot_ids: Vec<i64>,
    demand: u32,
    delivery_n: u32,
    delivery_tau: f64,
    delivery_lot_id: i64,
    seed: u64,
) -> (Vec<u32>, Vec<f64>, Vec<i64>, u32, u32, u32) {
    let params = ModelParams::default();
    let input = DayStepIn {
        counts,
        taus,
        lot_ids,
        demand: Some(demand),
        spoil_by: None,
        delivery_n,
        delivery_tau,
        delivery_lot_id,
    };
    let mut rng_a = Pcg64::seed_from_u64(seed);
    let mut rng_s = Pcg64::seed_from_u64(seed.wrapping_add(1));
    let out = day_step(&input, &params, Some(&mut rng_a), Some(&mut rng_s));
    (
        out.counts,
        out.taus,
        out.lot_ids,
        out.demand,
        out.sales_total,
        out.waste_total,
    )
}

#[pyfunction]
fn run_voi_crn_cell_py(
    beta: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    filter_n: u32,
    h: u32,
    n_rollout_paths: u32,
    lead_time: u32,
    times: Vec<Vec<f64>>,
    temps: Vec<Vec<f64>>,
) -> Vec<(String, f64)> {
    let ships: Vec<ShipmentTrace> = times
        .into_iter()
        .zip(temps)
        .map(|(times_d, temps_c)| ShipmentTrace { times_d, temps_c })
        .collect();
    let budgets = CrnBudgets {
        n_burn,
        n_score,
        filter_n,
        h,
        n_rollout_paths,
        lead_time,
        alpha: 0.9,
    };
    run_voi_crn_cell(beta, root_seed, &ships, &budgets, &[])
}

#[pyfunction]
fn run_episode_py(
    n_burn: u32,
    n_score: u32,
    constant_order: u32,
    seed: u64,
) -> (u32, u32, u32, u32) {
    let ep = run_closed_loop_episode(
        n_burn,
        n_score,
        constant_order,
        &ModelParams::default(),
        seed,
    )
    .expect("episode");
    (ep.n_days, ep.sales_total, ep.waste_total, ep.scored_sales)
}

#[pyfunction]
fn rollout_order_py(counts: Vec<u32>, taus: Vec<f64>, base_q: u32, seed: u64, h: u32) -> u32 {
    let ids: Vec<i64> = (1..=counts.len() as i64).collect();
    rollout_order(
        &counts,
        &taus,
        &ids,
        base_q,
        &ModelParams::default(),
        seed,
        h,
        1,
        1,
    )
    .expect("rollout")
}

#[pyfunction]
fn filter_step_py(
    counts: Vec<Vec<u32>>,
    taus: Vec<Vec<f64>>,
    sales: i32,
    waste: i32,
    seed: u64,
) -> Vec<f64> {
    let n = counts.len();
    let bank = ParticleBank {
        weights: vec![1.0 / n as f64; n],
        counts,
        taus,
    };
    let obs = FilterObs {
        sales_tot: Some(sales),
        waste_tot: Some(waste),
        arrivals: 0,
        ..Default::default()
    };
    let mut rng = Pcg64::seed_from_u64(seed);
    filter_step(&bank, &obs, &ModelParams::default(), &mut rng).weights
}

fn ships_from(times: Vec<Vec<f64>>, temps: Vec<Vec<f64>>) -> Vec<ShipmentTrace> {
    times
        .into_iter()
        .zip(temps)
        .map(|(times_d, temps_c)| ShipmentTrace { times_d, temps_c })
        .collect()
}

fn py_belief<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let b = PyDict::new(py);
    b.set_item("lot_counts", PyList::empty(py))?;
    b.set_item("age_marginals", PyList::empty(py))?;
    b.set_item("tau_grid", PyList::empty(py))?;
    b.set_item("L", 0)?;
    b.set_item("K", 0)?;
    Ok(b)
}

fn py_delta<'py>(py: Python<'py>, d: &DayDelta) -> PyResult<Bound<'py, PyDict>> {
    let day = PyDict::new(py);
    day.set_item("day", d.episode_day)?;
    day.set_item("order_qty", d.order_qty)?;
    day.set_item("arrivals", d.arrivals)?;
    day.set_item("sales_total", d.sales_total)?;
    day.set_item("waste_total", d.waste_total)?;
    day.set_item("demand", d.demand)?;
    day.set_item("L", d.on_hand)?;
    let m = PyDict::new(py);
    m.set_item("seq", d.episode_day)?;
    m.set_item("episode_day", d.episode_day)?;
    m.set_item("day", day)?;
    m.set_item("live_lots", PyList::empty(py))?;
    m.set_item("pipeline", PyList::empty(py))?;
    m.set_item("drop_oldest", false)?;
    m.set_item("belief", py_belief(py)?)?;
    Ok(m)
}

fn py_snapshot<'py>(py: Python<'py>, episode_day: u32) -> PyResult<Bound<'py, PyDict>> {
    let m = PyDict::new(py);
    m.set_item("seq", 0)?;
    m.set_item("episode_day", episode_day)?;
    m.set_item("belief", py_belief(py)?)?;
    m.set_item("history", PyList::empty(py))?;
    m.set_item("live_lots", PyList::empty(py))?;
    m.set_item("pipeline", PyList::empty(py))?;
    Ok(m)
}

#[pyclass]
struct PyEngineSession {
    inner: EngineSession,
}

#[pymethods]
impl PyEngineSession {
    #[new]
    fn new(seed: u64) -> Self {
        Self {
            inner: EngineSession::new(seed),
        }
    }

    #[pyo3(signature = (seed, lead_time=1, enable_filter=true, h=7, n_paths=2, radius=1, times=vec![], temps=vec![], n_particles=200))]
    fn init<'py>(
        &mut self,
        py: Python<'py>,
        seed: u64,
        lead_time: u32,
        enable_filter: bool,
        h: u32,
        n_paths: u32,
        radius: i32,
        times: Vec<Vec<f64>>,
        temps: Vec<Vec<f64>>,
        n_particles: usize,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.inner.init(seed);
        self.inner.configure(
            lead_time,
            enable_filter,
            h,
            n_paths,
            radius,
            ships_from(times, temps),
            n_particles,
        );
        py_snapshot(py, self.inner.episode_day())
    }

    fn reset<'py>(&mut self, py: Python<'py>, seed: u64) -> PyResult<Bound<'py, PyDict>> {
        self.init(py, seed, 1, true, 7, 2, 1, vec![], vec![], 200)
    }

    fn step_n<'py>(&mut self, py: Python<'py>, orders: Vec<u32>) -> PyResult<Bound<'py, PyList>> {
        let deltas = self.inner.step_n(&orders);
        let list = PyList::empty(py);
        for d in &deltas {
            list.append(py_delta(py, d)?)?;
        }
        Ok(list)
    }

    fn step<'py>(&mut self, py: Python<'py>, order: u32) -> PyResult<Bound<'py, PyDict>> {
        let d = self.inner.step(order);
        py_delta(py, &d)
    }

    #[pyo3(signature = (policy=None))]
    fn act<'py>(
        &mut self,
        py: Python<'py>,
        policy: Option<String>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let _ = policy;
        let d = self.inner.act_rollout();
        py_delta(py, &d)
    }

    fn act_rollout<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        self.act(py, Some("rollout".into()))
    }

    fn set_obs_scenario<'py>(
        &mut self,
        py: Python<'py>,
        obs_scenario: String,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.inner
            .set_obs_scenario(&obs_scenario)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        let snap = py_snapshot(py, self.inner.episode_day())?;
        let cfg = PyDict::new(py);
        cfg.set_item("obs_scenario", self.inner.obs_scenario())?;
        snap.set_item("applied_config", cfg)?;
        Ok(snap)
    }

    fn host_crossings(&self) -> u32 {
        self.inner.host_crossings()
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VOI_CORE", crate_name())?;
    m.add_function(wrap_pyfunction!(weibull_survival_py, m)?)?;
    m.add_function(wrap_pyfunction!(sequential_wor_py, m)?)?;
    m.add_function(wrap_pyfunction!(day_step_injected, m)?)?;
    m.add_function(wrap_pyfunction!(run_voi_crn_cell_py, m)?)?;
    m.add_function(wrap_pyfunction!(run_episode_py, m)?)?;
    m.add_function(wrap_pyfunction!(rollout_order_py, m)?)?;
    m.add_function(wrap_pyfunction!(filter_step_py, m)?)?;
    m.add_class::<PyEngineSession>()?;
    Ok(())
}
