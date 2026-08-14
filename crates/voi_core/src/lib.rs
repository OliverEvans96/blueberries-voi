//! Shared VOI compute kernel (ADR 0119 / 0121).

pub mod day_step;
pub mod episode;
pub mod exact_ll;
pub mod physics;
pub mod policy;
pub mod rbpf;
pub mod rollout;
pub mod schedule;
pub mod session;
pub mod shipments;
pub mod voi;
pub mod wor;

pub use day_step::{advance_days, day_step, DayStepIn, DayStepOut, ModelParams};
pub use episode::{run_closed_loop_episode, EpisodeResult};
pub use exact_ll::log_p_sales_waste_given_ages;
pub use physics::{
    allocate_sales, death_prob_hazard_product, death_prob_survival_ratio, draw_demand,
    picking_weights, q10_age_increment, weibull_survival,
};
pub use rbpf::{exact_wor_loglik, filter_step, systematic_resample, FilterObs, ParticleBank};
pub use rollout::{candidate_orders, rollout_order, terminal_salvage_value};
pub use session::{handle_rpc, DayDelta, EngineSession};
pub use shipments::ShipmentTrace;
pub use voi::{run_voi_crn_cell, CrnBudgets, PHYSICS_RUN_ID, VOI_SCENARIOS};
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
