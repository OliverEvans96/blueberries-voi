//! Shared VOI compute kernel (ADR 0119 / 0121).

pub mod day_step;
pub mod physics;
pub mod rbpf;
pub mod session;
pub mod voi;
pub mod wor;

pub use day_step::{advance_days, day_step, DayStepIn, DayStepOut, ModelParams};
pub use physics::{
    allocate_sales, death_prob_hazard_product, death_prob_survival_ratio, draw_demand,
    picking_weights, q10_age_increment, weibull_survival,
};
pub use session::{handle_rpc, EngineSession};
pub use rbpf::{exact_wor_loglik, systematic_resample};
pub use voi::{run_voi_crn_cell_stub, PHYSICS_RUN_ID, VOI_SCENARIOS};
pub use wor::{sequential_wor_composition_prob, sequential_wor_composition_probs};

pub fn crate_name() -> &'static str {
    "voi_core"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_the_kernel_crate() {
        assert_eq!(crate_name(), "voi_core");
    }
}
