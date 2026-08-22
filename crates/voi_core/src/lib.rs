//! Shared VOI compute kernel (ADR 0119 / 0121).

pub mod alpha_tune;
pub mod arrival;
pub mod belief_flat;
pub mod day_step;
pub mod demand_profile;
pub mod episode;
pub mod obs;
pub mod params;
pub mod physics;
pub mod policy;
pub mod rollout;
pub mod schedule;
pub mod session;
pub mod shipments;
pub mod spawn_rng;
pub mod tradeoff;
pub mod unit_ll;
pub mod unit_pf;
pub mod voi;
pub mod wor;

pub use alpha_tune::{
    parse_alpha_tune_arm, run_alpha_tune_episode, AlphaTuneArm, AlphaTuneCosts,
    AlphaTuneEpisodeResult, AlphaTuneRolloutBudgets,
};
pub use arrival::{
    arrival_artifact_from_json, embedded_arrival_model, resolve_arrival_exposure,
    resolve_arrival_f_law_phi_bar, ArrivalCondition, ArrivalModel, ArrivalModelError,
    STREAM_ARRIVAL_DURATION, STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS, STREAM_ARRIVAL_TEMP,
};
pub use belief_flat::{belief_flat_from_unit_bank, f_grid_k};
pub use day_step::{alive_by_lot, unit_day_step, UnitDayStepIn, UnitDayStepOut};
pub use demand_profile::{DemandProfile, DemandProfileError};
pub use episode::{run_closed_loop_episode, EpisodeResult};
pub use obs::{mask_for, FilterObs, ObsMask, RichDay};
pub use params::ModelParams;
pub use physics::{
    age_to_f, allocate_sales, apply_gamma_aging_independent, apply_gamma_decrement,
    death_prob_hazard_product, death_prob_survival_ratio, draw_demand, draw_gamma_decrement,
    draw_gamma_decrement_truncated, f_to_age, gamma_decrement_cdf, gamma_decrement_for_store,
    picking_weights, picking_weights_f, q10_age_increment, weibull_survival, GammaDecrementTable,
};
pub use rollout::{
    candidate_orders, day_profit, rollout_order, terminal_salvage_f_belief,
    terminal_salvage_unit_state, w_long, RolloutContext, RolloutCosts,
};
pub use session::{handle_rpc, DayDelta, EngineSession};
pub use shipments::ShipmentTrace;
pub use tradeoff::{full_tradeoff_q_candidates, tradeoff_forecast};
pub use unit_ll::{
    loglik_sales_by_units, pb_log_pmf, pb_loglik_by_lot, pb_loglik_pooled, pb_sample_deaths,
    pb_sample_deaths_by_lot, sequential_kernel_path_logprob, spoil_probs_from_freshness,
};
pub use unit_pf::{
    filter_step_unit, filter_step_unit_with_birth, filter_step_unit_with_birth_cached,
    systematic_resample, UnitParticleBank,
};
pub use voi::{run_voi_crn_cell, truth_f_belief, CrnBudgets, PHYSICS_RUN_ID, VOI_SCENARIOS};
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
