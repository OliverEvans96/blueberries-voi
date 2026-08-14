use pyo3::prelude::*;
use voi_core::crate_name;

/// `blueberries_voi._core` (ADR 0121). Stub until follow-on kernel tickets.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VOI_CORE", crate_name())?;
    Ok(())
}
