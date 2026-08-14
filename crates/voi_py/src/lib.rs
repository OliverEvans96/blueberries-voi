use pyo3::prelude::*;
use voi_core::{
    crate_name, sequential_wor_composition_probs, weibull_survival, EngineSession,
};

#[pyfunction]
fn weibull_survival_py(tau: f64, beta: f64, eta: f64) -> f64 {
    weibull_survival(tau, beta, eta)
}

#[pyfunction]
fn sequential_wor_py(counts: Vec<u32>, sales_tot: i32, weights: Vec<f64>) -> Vec<(Vec<u32>, f64)> {
    sequential_wor_composition_probs(&counts, sales_tot, &weights)
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

    fn step_n(&mut self, orders: Vec<u32>, demand: u32) -> usize {
        self.inner.step_n(&orders, demand).len()
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
    m.add_class::<PyEngineSession>()?;
    Ok(())
}

