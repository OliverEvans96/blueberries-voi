//! `voi_core` is the shared compute kernel for the **Blueberries VOI** project:
//! a value-of-information study asking how much a grocery store's profit
//! changes when it can see more about the true freshness of the blueberries
//! on its shelf, not just how old they are. This crate holds the *one* Rust
//! implementation of that world — the shelf physics (aging, spoilage,
//! demand), the particle filter that turns a store's partial observations
//! into a belief about what's actually on the shelf, and the ordering policy
//! that acts on that belief. Every other part of the project calls into this
//! crate rather than re-implementing any of it (ADR 0119 / 0121).
//!
//! This is the API-level reference: what a function does, what it takes and
//! returns, and any invariant a caller needs to know. For the *why* — why a
//! particle filter and not a closed-form model, why freshness and not age,
//! what each observation "rung" actually sees — see the project's narrative
//! documentation site,
//! [oliverevans.dev/docs/blueberries](https://oliverevans.dev/docs/blueberries/),
//! which links back to the relevant item here from every concept page.
//!
//! # Two doors into this crate
//!
//! Nothing outside this crate talks to Python or a browser directly. Both
//! wrappers below are thin adapters that marshal arguments in and JSON or
//! primitive types out, so the physics, RNG, and policy logic stay defined
//! exactly once, here:
//!
//! - **[voi_py](../_core/index.html)** — PyO3 bindings, compiled as the
//!   `blueberries_voi._core` extension module. Python notebooks, the CLI, and
//!   `pytest` all reach `voi_core` through this door.
//! - **[voi_wasm](../voi_wasm/index.html)** — a `wasm-bindgen` binding
//!   compiled to WebAssembly and loaded by the in-browser "studio" (a React +
//!   D3 app). It exposes a single [`handle_rpc`] JSON-in/JSON-out entry
//!   point, so the browser drives the identical [`EngineSession`] the native
//!   build uses.
//!
//! Both wrappers depend on this crate, not the other way around — `voi_core`
//! has no knowledge of Python or JavaScript.
//!
//! | Piece | Crate / package | Role |
//! | --- | --- | --- |
//! | Shelf physics, particle filter, ordering policy | `voi_core` (this crate) | The one implementation of the model |
//! | Native Python bindings | `voi_py` (`blueberries_voi._core`) | Notebooks, CLI, `pytest` |
//! | WebAssembly bindings | `voi_wasm` | The in-browser studio |
//! | In-browser studio (React + D3) | `@oliverevans96/blueberries-voi-studio` | Runs `voi_wasm` in a browser |
//!
//! # Where to start reading
//!
//! - [`EngineSession`] and [`handle_rpc`] — the stateful session both
//!   wrappers drive, one JSON RPC call at a time (`init`, `step`, `act`, ...).
//! - [`run_closed_loop_episode`] — runs a full simulated episode (physics +
//!   filter + policy) directly, without going through the RPC layer; used by
//!   offline experiments and notebooks.
//! - [`ModelParams`] — the parameters that define one scenario: a demand
//!   calendar, cold-chain noise, which observation rung the store is on, and
//!   so on.

pub mod alpha_tune;
pub mod arrival;
pub mod arrival_wire;
pub mod belief_flat;
pub mod day_step;
pub mod demand_profile;
pub mod episode;
pub mod joint_arrival_calib;
pub mod obs;
pub mod params;
pub mod physics;
pub mod policy;
pub mod protection_sim;
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
    resolve_arrival_f_law_phi_bar, ArrivalCondition, ArrivalLeg, ArrivalModel, ArrivalModelError,
    ArrivalRungLaw, TruthDeliveryDraw, DEFAULT_ARRIVAL_CORRIDOR, STREAM_ARRIVAL_DURATION,
    STREAM_ARRIVAL_GAMMA, STREAM_ARRIVAL_POS, STREAM_ARRIVAL_REGIME, STREAM_ARRIVAL_TEMP,
};
pub use belief_flat::{belief_flat_from_unit_bank, f_grid_k};
pub use day_step::{alive_by_lot, unit_day_step, UnitDayStepIn, UnitDayStepOut};
pub use demand_profile::{DemandProfile, DemandProfileError};
pub use episode::{run_closed_loop_episode, EpisodeResult};
pub use joint_arrival_calib::{
    ac2_11a_ratio, ac2_19_d8_margin, ac2_19_min_margin, apply_config, benchmark_fast_trial,
    benchmark_fast_vs_slow, configured_model, evaluate_fast_trial, evaluate_trial,
    passes_ac2_11a, passes_fast_gates, truth_band, JointCalibFastResult, JointCalibTrialMetrics,
};
pub use obs::{mask_for, FilterObs, ObsMask, RichDay};
pub use params::ModelParams;
pub use policy::{
    case_round, case_round_ceil, constant_order, damped_sw_order_f_belief,
    effective_inventory_f_belief, nbinom_ppf, protection_demand_quantile, rung0_order_f_belief,
    INITIAL_STOCK_ALPHA,
};
pub use physics::{
    age_to_f, allocate_sales, apply_gamma_aging_independent, apply_gamma_decrement,
    death_prob_hazard_product, death_prob_survival_ratio, draw_demand, draw_gamma_decrement,
    draw_gamma_decrement_truncated, f_to_age, gamma_decrement_cdf, gamma_decrement_for_store,
    picking_weights, picking_weights_f, q10_age_increment, weibull_survival, GammaDecrementTable,
};
pub use protection_sim::{
    bank_start_state, initial_stock_sla_pb, sla_mc_order_f_belief, sla_pb_order_f_belief,
    simulate_protection_path, McSlaModel, OpeningStockPbModel, PbSlaModel, ProtectionPathResult,
    ProtectionWindow, SlaModel, SurvivalCurveCache,
};
pub use rollout::{
    candidate_orders, day_profit, rollout_order, terminal_salvage_f_belief,
    terminal_salvage_unit_state, w_long, RolloutContext, RolloutCosts,
};
pub use session::{handle_rpc, BeliefSource, DayDelta, EngineSession};
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

/// Crate name string, used by the PyO3 and WASM hosts to identify this kernel build.
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
