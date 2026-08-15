use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::{IntoPyObject, PyAny};
use rand::SeedableRng;
use rand_pcg::Pcg64;
use serde_json::Value;
use voi_core::{
    crate_name, day_step, filter_step, rollout_order, run_closed_loop_episode, run_voi_crn_cell,
    sequential_wor_composition_probs, weibull_survival, CrnBudgets, DayDelta, DayStepIn,
    EngineSession, FilterObs, ModelParams, ParticleBank, ShipmentTrace,
    DemandProfile,
};

#[pyfunction]
#[pyo3(signature = (day, json))]
fn demand_profile_mu_from_json_py(day: u32, json: &str) -> PyResult<f64> {
    let profile = DemandProfile::from_json(json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
    Ok(profile.mu(day))
}

#[pyfunction]
#[pyo3(name = "demand_profile_mu_py", signature = (day, json))]
fn demand_profile_mu_py(day: u32, json: &str) -> PyResult<f64> {
    demand_profile_mu_from_json_py(day, json)
}

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
#[pyo3(signature = (beta, root_seed, n_burn, n_score, filter_n, h, n_rollout_paths, lead_time, times, temps, demand_profile_json=None))]
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
    demand_profile_json: Option<&str>,
) -> PyResult<Vec<(String, f64)>> {
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
    let demand_profile = match demand_profile_json {
        Some(json) => Some(
            DemandProfile::from_json(json)
                .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?,
        ),
        None => None,
    };
    Ok(run_voi_crn_cell(
        beta,
        root_seed,
        &ships,
        &budgets,
        &[],
        demand_profile,
    ))
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

fn json_to_py<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    match value {
        Value::Null => Ok(py.None().into_bound(py)),
        Value::Bool(b) => {
            let val = *b;
            let borrowed = val.into_pyobject(py)?;
            Ok(<Bound<'_, pyo3::types::PyBool> as Clone>::clone(&borrowed).into_any())
        }
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any())
            } else if let Some(u) = n.as_u64() {
                Ok(u.into_pyobject(py)?.into_any())
            } else if let Some(f) = n.as_f64() {
                Ok(f.into_pyobject(py)?.into_any())
            } else {
                Ok(py.None().into_bound(py))
            }
        }
        Value::String(s) => Ok(s.into_pyobject(py)?.into_any()),
        Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into_any())
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.into_any())
        }
    }
}

fn json_to_py_dict<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyDict>> {
    match value {
        Value::Object(_) => json_to_py(py, value)?.cast_into().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("session wire must be a dict: {e}"))
        }),
        _ => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "session wire value must be a JSON object",
        )),
    }
}

fn wire_snapshot<'py>(py: Python<'py>, session: &EngineSession) -> PyResult<Bound<'py, PyDict>> {
    json_to_py_dict(py, &session.snapshot_value())
}

fn wire_day_delta<'py>(
    py: Python<'py>,
    session: &EngineSession,
    delta: &DayDelta,
) -> PyResult<Bound<'py, PyDict>> {
    json_to_py_dict(py, &session.day_delta_value(delta))
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

    #[pyo3(signature = (seed, lead_time=1, enable_filter=true, h=7, n_paths=2, radius=1, times=vec![], temps=vec![], n_particles=200, l=2, k=4, obs_scenario=None, demand_profile_json=None))]
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
        l: usize,
        k: usize,
        obs_scenario: Option<String>,
        demand_profile_json: Option<String>,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.inner.init(seed);
        self.inner.set_belief_dims(l, k.max(1));
        let demand_profile = demand_profile_json
            .as_deref()
            .and_then(|json| DemandProfile::from_json(json).ok());
        self.inner.configure(
            lead_time,
            enable_filter,
            h,
            n_paths,
            radius,
            ships_from(times, temps),
            n_particles,
            demand_profile,
        );
        if let Some(scenario) = obs_scenario {
            self.inner
                .set_obs_scenario(&scenario)
                .map_err(pyo3::exceptions::PyValueError::new_err)?;
        }
        wire_snapshot(py, &self.inner)
    }

    fn reset<'py>(&mut self, py: Python<'py>, seed: u64) -> PyResult<Bound<'py, PyDict>> {
        self.init(
            py,
            seed,
            1,
            true,
            7,
            2,
            1,
            vec![],
            vec![],
            200,
            2,
            4,
            None,
            None,
        )
    }

    fn step_n<'py>(&mut self, py: Python<'py>, orders: Vec<u32>) -> PyResult<Bound<'py, PyList>> {
        let deltas = self.inner.step_n(&orders);
        let list = PyList::empty(py);
        for d in &deltas {
            list.append(wire_day_delta(py, &self.inner, d)?)?;
        }
        Ok(list)
    }

    fn step<'py>(&mut self, py: Python<'py>, order: u32) -> PyResult<Bound<'py, PyDict>> {
        let d = self.inner.step(order);
        wire_day_delta(py, &self.inner, &d)
    }

    #[pyo3(signature = (
        policy=None,
        order_qty=None,
        q=None,
        alpha=None,
        rho=None,
        H=None,
        h=None,
        n_rollout_paths=None,
        candidate_case_radius=None,
        n_particles=None,
    ))]
    #[allow(non_snake_case)]
    fn act<'py>(
        &mut self,
        py: Python<'py>,
        policy: Option<String>,
        order_qty: Option<u32>,
        q: Option<u32>,
        alpha: Option<f64>,
        rho: Option<f64>,
        H: Option<u32>,
        h: Option<u32>,
        n_rollout_paths: Option<u32>,
        candidate_case_radius: Option<i32>,
        n_particles: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let _ = n_particles;
        let d = self.inner.act(
            policy.as_deref(),
            order_qty.or(q),
            alpha,
            rho,
            H.or(h),
            n_rollout_paths,
            candidate_case_radius,
        );
        wire_day_delta(py, &self.inner, &d)
    }

    fn act_rollout<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = self.inner.act(Some("rollout"), None, None, None, None, None, None);
        wire_day_delta(py, &self.inner, &d)
    }

    fn set_obs_scenario<'py>(
        &mut self,
        py: Python<'py>,
        obs_scenario: String,
    ) -> PyResult<Bound<'py, PyDict>> {
        let snap = self
            .inner
            .set_obs_scenario(&obs_scenario)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        json_to_py_dict(py, &snap)
    }

    fn host_crossings(&self) -> u32 {
        self.inner.host_crossings()
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VOI_CORE", crate_name())?;
    m.add_function(wrap_pyfunction!(demand_profile_mu_from_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(demand_profile_mu_py, m)?)?;
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
