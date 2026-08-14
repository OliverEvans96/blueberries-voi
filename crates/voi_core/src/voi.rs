//! Episode / VOI cell batch endpoints (smoke contracts).

pub const PHYSICS_RUN_ID: &str = "voi-physics";

pub const VOI_SCENARIOS: &[&str] = &["P0", "P1", "F1", "F1s", "F2a", "F2", "B-state"];

/// Placeholder cell result: one profit per scenario name (kernel fill later).
pub fn run_voi_crn_cell_stub(scenarios: &[&str]) -> Vec<(String, f64)> {
    scenarios
        .iter()
        .map(|s| ((*s).to_string(), 0.0))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Mirrors `test_voi_crn.py::test_physics_run_id_constant`.
    #[test]
    fn physics_run_id_constant() {
        assert_eq!(PHYSICS_RUN_ID, "voi-physics");
    }

    /// Mirrors `test_crn_cell_returns_p0_p1_bstate_profits` (keys only until port).
    #[test]
    fn crn_cell_returns_requested_scenario_keys() {
        let profits = run_voi_crn_cell_stub(&["P0", "P1", "B-state"]);
        let names: Vec<&str> = profits.iter().map(|(k, _)| k.as_str()).collect();
        assert_eq!(names, ["P0", "P1", "B-state"]);
    }

    #[test]
    fn crn_cell_accepts_full_column_set() {
        let profits = run_voi_crn_cell_stub(VOI_SCENARIOS);
        assert!(profits.iter().any(|(k, _)| k == "F2a"));
        assert!(profits.iter().any(|(k, _)| k == "F2"));
        assert_eq!(profits.len(), 7);
    }
}
