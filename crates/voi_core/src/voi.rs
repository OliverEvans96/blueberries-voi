//! SIM-02 outer-loop CRN cell: shared physics across knowledge scenarios.

use crate::episode::run_closed_loop_episode;
use crate::rollout::day_profit;
use crate::ModelParams;

pub const PHYSICS_RUN_ID: &str = "voi-physics";

pub const VOI_SCENARIOS: &[&str] = &["P0", "P1", "F1", "F1s", "F2a", "F2", "B-state"];

/// One FFI: all 7 scenarios, shared physics seed (Rust PCG; not NumPy-identical).
pub fn run_voi_crn_cell(
    beta: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
) -> Vec<(String, f64)> {
    let mut params = ModelParams::default();
    params.beta = beta;
    let mut out = Vec::with_capacity(VOI_SCENARIOS.len());
    for (i, name) in VOI_SCENARIOS.iter().enumerate() {
        // Shared physics seed; scenario index only keys filter-like variation later.
        let ep = run_closed_loop_episode(n_burn, n_score, 8, &params, root_seed)
            .expect("episode");
        let profit = day_profit(ep.scored_sales, ep.scored_waste, ep.scored_sales, 2.0, 1.5, 3.0);
        let _ = i;
        out.push(((*name).to_string(), profit));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn physics_run_id_constant() {
        assert_eq!(PHYSICS_RUN_ID, "voi-physics");
    }

    #[test]
    fn crn_cell_returns_p0_p1_bstate_profits() {
        let profits = run_voi_crn_cell(2.0, 7, 1, 2);
        let names: Vec<&str> = profits.iter().map(|(k, _)| k.as_str()).collect();
        assert!(names.contains(&"P0"));
        assert!(names.contains(&"P1"));
        assert!(names.contains(&"B-state"));
        assert_eq!(profits.len(), 7);
        assert!(profits.iter().all(|(_, v)| v.is_finite()));
    }

    #[test]
    fn crn_cell_accepts_full_column_set() {
        let profits = run_voi_crn_cell(1.5, 3, 1, 1);
        assert!(profits.iter().any(|(k, _)| k == "F2a"));
        assert!(profits.iter().any(|(k, _)| k == "F2"));
    }

    #[test]
    fn shared_physics_seed_stable_across_reruns() {
        let a = run_voi_crn_cell(2.0, 11, 1, 1);
        let b = run_voi_crn_cell(2.0, 11, 1, 1);
        assert_eq!(a, b);
    }
}
