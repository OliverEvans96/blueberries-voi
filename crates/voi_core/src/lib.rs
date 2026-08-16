//! Shared VOI compute kernel (ADR 0119 / 0121).

pub mod belief_flat;
pub mod demand_profile;
pub mod params;
pub mod day_step;
mod day_step_legacy;
pub mod episode;
pub mod exact_ll;
pub mod unit_ll;
pub mod unit_pf;
pub mod obs;
pub mod physics;
pub mod policy;
pub mod particle_filter;
pub mod rollout;
pub mod schedule;
pub mod session;
pub mod shipments;
pub mod spawn_rng;
pub mod voi;
pub mod wor;

pub use belief_flat::{mean_bank, particle_bank_to_flat};
pub use demand_profile::{DemandProfile, DemandProfileError};
pub use day_step::{
    advance_days, alive_by_lot, day_step, unit_day_step, Cohort, DayStepIn, DayStepOut,
    UnitDayStepIn, UnitDayStepOut,
};
pub use params::ModelParams;
pub use episode::{run_closed_loop_episode, EpisodeResult};
pub use exact_ll::log_p_sales_waste_given_ages;
pub use unit_ll::{
    loglik_sales_by_units, p1_totals_loglik, sequential_kernel_path_logprob,
};
pub use unit_pf::{filter_step_unit, UnitParticleBank};
pub use obs::{mask_for, FilterObs, ObsMask, RichDay};
pub use physics::{
    age_to_f, allocate_sales, apply_gamma_decrement, death_prob_hazard_product,
    death_prob_survival_ratio, draw_demand, draw_gamma_decrement, f_to_age,
    gamma_decrement_for_store, picking_weights, picking_weights_f, q10_age_increment,
    weibull_survival,
};
pub use particle_filter::{exact_wor_loglik, filter_step, systematic_resample, ParticleBank};
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
