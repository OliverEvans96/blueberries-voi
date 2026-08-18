use pyo3::prelude::*;
use voi_core::DemandProfile;

#[pyclass(name = "DemandProfile", module = "blueberries_voi._core")]
pub struct PyDemandProfile {
    pub(crate) inner: DemandProfile,
}

#[pymethods]
impl PyDemandProfile {
    #[new]
    #[pyo3(signature = (scale_target_mu, dow_factors, week_factors, demand_vm=2.0))]
    fn new(
        scale_target_mu: f64,
        dow_factors: Vec<f64>,
        week_factors: Vec<f64>,
        demand_vm: f64,
    ) -> PyResult<Self> {
        if dow_factors.len() != 7 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "dow_factors must have length 7 (monday0)",
            ));
        }
        let mut dow = [0.0; 7];
        for (slot, value) in dow.iter_mut().zip(dow_factors) {
            *slot = value;
        }
        let inner = DemandProfile::from_parts(scale_target_mu, dow, week_factors, demand_vm)
            .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
        Ok(Self { inner })
    }

    fn mu(&self, day: u32) -> f64 {
        self.inner.mu(day)
    }
}
