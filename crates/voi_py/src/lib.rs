//! PyO3 binding layer exposing `voi_core` to Python as `blueberries_voi._core`. Each
//! `#[pyfunction]`/`#[pyclass]` here is a thin, JSON- or primitive-typed adapter over a
//! core Rust function or type -- the underlying model, RNG, and policy logic all live in
//! `voi_core`, so this crate's job is argument marshalling and error translation
//! (`voi_core` errors become `PyValueError`/`PyRuntimeError`), not modeling (ADR 0119).

mod demand_profile;

use demand_profile::PyDemandProfile;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::{IntoPyObject, PyAny};
use serde_json::Value;
use voi_core::physics::draw_demand_spawn;
use voi_core::policy::protection_demand_quantile;
use voi_core::schedule::OrderSchedule;
use voi_core::spawn_rng::SpawnRng;
use voi_core::{
    arrival_artifact_from_json, crate_name, parse_alpha_tune_arm, rollout_order,
    run_alpha_tune_episode, run_closed_loop_episode, run_voi_crn_cell,
    sequential_wor_composition_probs, terminal_salvage_unit_state, w_long, AlphaTuneCosts,
    AlphaTuneRolloutBudgets, CrnBudgets, DayDelta, DemandProfile, EngineSession, ModelParams,
    RolloutContext, RolloutCosts, ShipmentTrace,
};

/// Loads a `DemandProfile` from `source`, treating it as a filesystem path if a file
/// exists there and otherwise parsing it directly as a JSON literal -- lets Python callers
/// pass either a path or an inline JSON string interchangeably.
fn demand_profile_from_source(source: &str) -> PyResult<DemandProfile> {
    let json = if std::path::Path::new(source).is_file() {
        std::fs::read_to_string(source).map_err(|err| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "failed to read demand profile at {source}: {err}"
            ))
        })?
    } else {
        source.to_string()
    };
    DemandProfile::from_json(&json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))
}

/// Lets Python compute a calendar profile's expected demand for `day` from a demand
/// profile given as a JSON string or path, without first constructing a [`PyDemandProfile`].
#[pyfunction]
#[pyo3(signature = (day, json))]
fn demand_profile_mu_from_json_py(day: u32, json: &str) -> PyResult<f64> {
    Ok(demand_profile_from_source(json)?.mu(day))
}

/// Identical to [`demand_profile_mu_from_json_py`]; kept as a separate Python-visible name
/// (`demand_profile_mu_py`) for callers that already depend on that symbol.
#[pyfunction]
#[pyo3(name = "demand_profile_mu_py", signature = (day, json))]
fn demand_profile_mu_py(day: u32, json: &str) -> PyResult<f64> {
    demand_profile_mu_from_json_py(day, json)
}

/// Reads `source` as a file's contents if it names an existing file, otherwise returns it
/// unchanged as a literal JSON string -- the path-or-inline-JSON convention shared across
/// this module's `_from_json` entry points.
fn read_json_source(source: &str) -> PyResult<String> {
    if std::path::Path::new(source).is_file() {
        std::fs::read_to_string(source).map_err(|err| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "failed to read JSON at {source}: {err}"
            ))
        })
    } else {
        Ok(source.to_string())
    }
}

/// Parses an arrival-model config (JSON string or path) into a `voi_core` `ArrivalModel`
/// and re-serializes just the fields the Python side needs (gamma shape/scale, reference
/// life, Q10 and temperature/position parameters) as a JSON string -- lets Python read a
/// validated arrival model without depending on the full internal `ArrivalModel` shape.
#[pyfunction]
#[pyo3(name = "arrival_model_from_json_py", signature = (source))]
fn arrival_model_from_json_py(source: &str) -> PyResult<String> {
    let json = read_json_source(source)?;
    let model = arrival_artifact_from_json(&json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
    let wire = serde_json::json!({
        "schema_version": model.schema_version,
        "gamma_shape": model.gamma_shape,
        "gamma_scale": model.gamma_scale,
        "reference_life_days": model.reference_life_days,
        "mu_T": model.mu_t,
        "sigma_T": model.sigma_t,
        "sigma_pos": model.sigma_pos,
        "q10": model.q10,
        "T_ref": model.t_ref,
    });
    serde_json::to_string(&wire).map_err(|err| {
        pyo3::exceptions::PyValueError::new_err(format!("failed to serialize arrival wire: {err}"))
    })
}

/// Computes the α-quantile of demand over a protection window starting at `start_day`,
/// i.e. `F^-1(alpha)` from the base-stock ordering rule -- lets Python check the same
/// service-level target the Rust ordering policy uses, optionally overriding the flat
/// `demand_mu`/`demand_vm` with a calendar `demand_profile`.
#[pyfunction]
#[pyo3(signature = (alpha, demand_mu, demand_vm, protection_days, start_day, demand_profile=None))]
fn protection_demand_quantile_py(
    alpha: f64,
    demand_mu: f64,
    demand_vm: f64,
    protection_days: u32,
    start_day: u32,
    demand_profile: Option<&PyDemandProfile>,
) -> PyResult<f64> {
    let mut params = ModelParams {
        demand_mu,
        demand_vm,
        ..ModelParams::default()
    };
    if let Some(profile) = demand_profile {
        params.apply_demand_profile(profile.inner.clone());
    }
    Ok(protection_demand_quantile(
        alpha,
        &params,
        protection_days,
        start_day,
    ))
}

/// Draws one day's realized demand for Python using the same seeded RNG sub-stream
/// (`root_seed`, `run_id`, `day`, `stream`) the Rust engine would use, so Python-side
/// checks and the engine draw the identical number under common random numbers.
#[pyfunction]
#[pyo3(signature = (root_seed, run_id, day, demand_mu, demand_vm, demand_profile=None, stream=":demand"))]
fn draw_demand_at_day_py(
    root_seed: u64,
    run_id: &str,
    day: u32,
    demand_mu: f64,
    demand_vm: f64,
    demand_profile: Option<&PyDemandProfile>,
    stream: &str,
) -> PyResult<u32> {
    let mut params = ModelParams {
        demand_mu,
        demand_vm,
        ..ModelParams::default()
    };
    if let Some(profile) = demand_profile {
        params.apply_demand_profile(profile.inner.clone());
    }
    let mut rng = SpawnRng::spawn_rng(root_seed, run_id, day, stream);
    Ok(draw_demand_spawn(&mut rng, &params, Some(day)))
}

/// Exposes one draw from a named [`SpawnRng`] sub-stream to Python, so Python-side tests
/// can verify they land on the same deterministic value the Rust engine would draw from
/// that `(root_seed, run_id, day, stream)` coordinate.
#[pyfunction]
#[pyo3(signature = (root_seed, run_id, day, stream))]
fn spawn_rng_next_u64_py(root_seed: u64, run_id: &str, day: u32, stream: &str) -> PyResult<u64> {
    use rand::RngCore;
    let mut rng = SpawnRng::spawn_rng(root_seed, run_id, day, stream);
    Ok(rng.next_u64())
}

/// Python entry point for [`sequential_wor_composition_probs`]: returns every way
/// `sales_tot` units could be sold without replacement across cohorts of the given
/// `counts` and `weights`, each paired with its probability.
#[pyfunction]
fn sequential_wor_py(counts: Vec<u32>, sales_tot: i32, weights: Vec<f64>) -> Vec<(Vec<u32>, f64)> {
    sequential_wor_composition_probs(&counts, sales_tot, &weights)
}

/// Runs one VOI comparison cell from Python: builds shipment traces from parallel
/// `times`/`temps` arrays, then evaluates every observation-ladder scenario against shared
/// common random numbers and returns each scenario's name paired with its scored profit.
#[pyfunction]
#[pyo3(signature = (beta, root_seed, n_burn, n_score, filter_n, h, n_rollout_paths, lead_time, times, temps, demand_profile_json=None))]
fn run_voi_crn_cell_py(
    beta: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    filter_n: u32,
    h: u32,
    n_rollout_paths: u32,
    lead_time: u32,
    times: Vec<Vec<f64>>,
    temps: Vec<Vec<f64>>,
    demand_profile_json: Option<&str>,
) -> PyResult<Vec<(String, f64)>> {
    let ships: Vec<ShipmentTrace> = times
        .into_iter()
        .zip(temps)
        .map(|(times_d, temps_c)| ShipmentTrace { times_d, temps_c })
        .collect();
    let budgets = CrnBudgets {
        n_burn,
        n_score,
        filter_n,
        h,
        n_rollout_paths,
        lead_time,
        alpha: 0.9,
        candidate_case_radius: 1,
    };
    let demand_profile = match demand_profile_json {
        Some(json) => Some(
            DemandProfile::from_json(json)
                .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?,
        ),
        None => None,
    };
    Ok(run_voi_crn_cell(
        beta,
        root_seed,
        &ships,
        &budgets,
        &[],
        demand_profile,
    ))
}

/// Runs one alpha-tuning episode for the given `arm_id`/`alpha` and returns just the
/// scored profit; a thin wrapper over [`evaluate_alpha_tune_outcomes_py`] for callers
/// (e.g. an alpha-search loop) that don't need the waste/lost-sales breakdown.
#[pyfunction]
#[pyo3(signature = (
    arm_id,
    alpha,
    root_seed,
    n_burn=2,
    n_score=5,
    lead_time=1,
    rho=0.8,
    unit_margin=2.0,
    waste_cost=1.5,
    stockout_penalty=3.0,
    rollout_h=2,
    n_rollout_paths=1,
    candidate_case_radius=1,
    times=None,
    temps=None,
    demand_mu=30.0,
    demand_vm=2.0,
    case_size=8,
    demand_profile=None,
))]
fn evaluate_alpha_tune_episode_py(
    arm_id: &str,
    alpha: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    lead_time: u32,
    rho: f64,
    unit_margin: f64,
    waste_cost: f64,
    stockout_penalty: f64,
    rollout_h: u32,
    n_rollout_paths: u32,
    candidate_case_radius: i32,
    times: Option<Vec<Vec<f64>>>,
    temps: Option<Vec<Vec<f64>>>,
    demand_mu: f64,
    demand_vm: f64,
    case_size: u32,
    demand_profile: Option<&PyDemandProfile>,
) -> PyResult<f64> {
    let (profit, _, _) = evaluate_alpha_tune_outcomes_inner(
        arm_id,
        alpha,
        root_seed,
        n_burn,
        n_score,
        lead_time,
        rho,
        unit_margin,
        waste_cost,
        stockout_penalty,
        rollout_h,
        n_rollout_paths,
        candidate_case_radius,
        times,
        temps,
        demand_mu,
        demand_vm,
        case_size,
        demand_profile,
    )?;
    Ok(profit)
}

/// Runs one alpha-tuning episode for `arm_id` under `alpha` and returns
/// `(scored_profit, scored_waste, scored_lost_sales)` -- the full outcome tuple an
/// alpha-tuning sweep needs, not just the profit scalar `evaluate_alpha_tune_episode_py`
/// returns. `arm_id` names which policy variant to score (parsed by
/// [`parse_alpha_tune_arm`]); when `times`/`temps` are both omitted, a single smoke-test
/// cool shipment trace is used instead.
#[pyfunction]
#[pyo3(signature = (
    arm_id,
    alpha,
    root_seed,
    n_burn=2,
    n_score=5,
    lead_time=1,
    rho=0.8,
    unit_margin=2.0,
    waste_cost=1.5,
    stockout_penalty=3.0,
    rollout_h=2,
    n_rollout_paths=1,
    candidate_case_radius=1,
    times=None,
    temps=None,
    demand_mu=30.0,
    demand_vm=2.0,
    case_size=8,
    demand_profile=None,
))]
fn evaluate_alpha_tune_outcomes_py(
    arm_id: &str,
    alpha: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    lead_time: u32,
    rho: f64,
    unit_margin: f64,
    waste_cost: f64,
    stockout_penalty: f64,
    rollout_h: u32,
    n_rollout_paths: u32,
    candidate_case_radius: i32,
    times: Option<Vec<Vec<f64>>>,
    temps: Option<Vec<Vec<f64>>>,
    demand_mu: f64,
    demand_vm: f64,
    case_size: u32,
    demand_profile: Option<&PyDemandProfile>,
) -> PyResult<(f64, u32, u32)> {
    evaluate_alpha_tune_outcomes_inner(
        arm_id,
        alpha,
        root_seed,
        n_burn,
        n_score,
        lead_time,
        rho,
        unit_margin,
        waste_cost,
        stockout_penalty,
        rollout_h,
        n_rollout_paths,
        candidate_case_radius,
        times,
        temps,
        demand_mu,
        demand_vm,
        case_size,
        demand_profile,
    )
}

/// Shared implementation behind both `evaluate_alpha_tune_*_py` entry points: parses
/// `arm_id`, assembles shipment traces (falling back to a single smoke-test cool shipment
/// when `times`/`temps` are both omitted), applies an optional demand profile override,
/// and runs [`run_alpha_tune_episode`] under the requested cost and rollout budgets.
/// Requiring `times` and `temps` to be provided together (or not at all) keeps the two
/// arrays in sync, since each shipment's temperature trace must line up with its time
/// trace.
fn evaluate_alpha_tune_outcomes_inner(
    arm_id: &str,
    alpha: f64,
    root_seed: u64,
    n_burn: u32,
    n_score: u32,
    lead_time: u32,
    rho: f64,
    unit_margin: f64,
    waste_cost: f64,
    stockout_penalty: f64,
    rollout_h: u32,
    n_rollout_paths: u32,
    candidate_case_radius: i32,
    times: Option<Vec<Vec<f64>>>,
    temps: Option<Vec<Vec<f64>>>,
    demand_mu: f64,
    demand_vm: f64,
    case_size: u32,
    demand_profile: Option<&PyDemandProfile>,
) -> PyResult<(f64, u32, u32)> {
    let arm =
        parse_alpha_tune_arm(arm_id).map_err(|err| pyo3::exceptions::PyValueError::new_err(err))?;
    let ships: Vec<ShipmentTrace> = match (times, temps) {
        (Some(t), Some(tp)) => ships_from(t, tp),
        (None, None) => vec![ShipmentTrace::smoke_cool()],
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "times and temps must both be provided or both omitted",
            ));
        }
    };
    let mut params = ModelParams {
        demand_mu,
        demand_vm,
        case_size,
        ..ModelParams::default()
    };
    if let Some(profile) = demand_profile {
        params.apply_demand_profile(profile.inner.clone());
    }
    let costs = AlphaTuneCosts {
        unit_margin,
        waste_cost,
        stockout_penalty,
    };
    let rollout = AlphaTuneRolloutBudgets {
        h: rollout_h,
        n_rollout_paths,
        candidate_case_radius,
    };
    let ep = run_alpha_tune_episode(
        arm, alpha, rho, root_seed, n_burn, n_score, lead_time, &params, &ships, &costs, &rollout,
    )
    .map_err(|err| pyo3::exceptions::PyRuntimeError::new_err(err))?;
    Ok((ep.scored_profit, ep.scored_waste, ep.scored_lost_sales))
}

/// Runs a fixed-order closed-loop episode (constant order quantity every day, default
/// model params) for Python and returns `(n_days, sales_total, waste_total, scored_sales)`
/// -- a simple baseline episode runner, mostly useful for smoke tests and sanity checks
/// rather than production scoring.
#[pyfunction]
fn run_episode_py(
    n_burn: u32,
    n_score: u32,
    constant_order: u32,
    seed: u64,
) -> (u32, u32, u32, u32) {
    let ep = run_closed_loop_episode(
        n_burn,
        n_score,
        constant_order,
        &voi_core::ModelParams::default(),
        seed,
    )
    .expect("episode");
    (ep.n_days, ep.sales_total, ep.waste_total, ep.scored_sales)
}

/// Exposes the CTL rollout order policy to Python: given the current lot-level belief
/// (`lot_counts`, `f_marginals`, `f_grid`) and a `base_q` damped base-stock order, scores a
/// small band of candidate order quantities around `base_q` by simulating forward and
/// returns the best one. `pending_days`/`pending_qtys` describe orders already in transit;
/// when `times`/`temps` are both omitted, a single smoke-test cool shipment trace stands
/// in for the delivery's thermal exposure.
#[pyfunction]
#[pyo3(signature = (
    lot_counts,
    f_marginals,
    f_grid,
    base_q,
    root_seed,
    run_id,
    day0=0,
    lead_time=1,
    alpha=0.9,
    rho=0.8,
    h=28,
    n_paths=8,
    radius=2,
    unit_margin=2.0,
    waste_cost=1.5,
    stockout_penalty=3.0,
    pending_days=None,
    pending_qtys=None,
    times=None,
    temps=None,
))]
#[allow(clippy::too_many_arguments)]
fn rollout_order_py(
    lot_counts: Vec<f64>,
    f_marginals: Vec<f64>,
    f_grid: Vec<f64>,
    base_q: u32,
    root_seed: u64,
    run_id: &str,
    day0: u32,
    lead_time: u32,
    alpha: f64,
    rho: f64,
    h: u32,
    n_paths: u32,
    radius: i32,
    unit_margin: f64,
    waste_cost: f64,
    stockout_penalty: f64,
    pending_days: Option<Vec<u32>>,
    pending_qtys: Option<Vec<u32>>,
    times: Option<Vec<Vec<f64>>>,
    temps: Option<Vec<Vec<f64>>>,
) -> PyResult<u32> {
    let mut pending = std::collections::BTreeMap::new();
    if let (Some(days), Some(qtys)) = (pending_days, pending_qtys) {
        if days.len() != qtys.len() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "pending_days and pending_qtys must have equal length",
            ));
        }
        for (d, q) in days.into_iter().zip(qtys) {
            pending.insert(d, q);
        }
    }
    let ships: Vec<ShipmentTrace> = match (times, temps) {
        (Some(t), Some(tp)) => ships_from(t, tp),
        (None, None) => vec![ShipmentTrace::smoke_cool()],
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "times and temps must both be provided or both omitted",
            ));
        }
    };
    let schedule = OrderSchedule::from_delivery(&[0, 2, 4], lead_time).unwrap_or_default();
    let ctx = RolloutContext {
        root_seed,
        run_id: run_id.to_string(),
        day0,
        lead_time,
        schedule,
        alpha,
        rho,
        costs: RolloutCosts {
            unit_margin,
            waste_cost,
            stockout_penalty,
        },
        shipments: ships,
        f_pipeline_default: 1.0,
        h,
        n_paths,
        radius,
    };
    rollout_order(
        &lot_counts,
        &f_marginals,
        &f_grid,
        base_q,
        &voi_core::ModelParams::default(),
        &pending,
        &ctx,
    )
    .map_err(pyo3::exceptions::PyRuntimeError::new_err)
}

/// Computes terminal salvage value for a set of on-hand units at their given `freshness`
/// levels, under a Weibull survival weighting parameterized by `beta`/`eta_ref` and scaled
/// by `margin` per unit -- lets Python evaluate the same end-of-horizon salvage term the
/// rollout scorer uses.
#[pyfunction]
fn terminal_salvage_unit_state_py(
    freshness: Vec<f64>,
    margin: f64,
    beta: f64,
    eta_ref: f64,
) -> f64 {
    let mut params = voi_core::ModelParams::default();
    params.beta = beta;
    params.eta_ref = eta_ref;
    terminal_salvage_unit_state(&freshness, margin, &params)
}

/// Weibull survival weight at effective age `tau`, for Python callers checking the same
/// long-run salvage weighting the rollout scorer applies.
#[pyfunction]
fn w_long_py(tau: f64, beta: f64, eta_ref: f64) -> f64 {
    let mut params = voi_core::ModelParams::default();
    params.beta = beta;
    params.eta_ref = eta_ref;
    w_long(tau, &params)
}

fn ships_from(times: Vec<Vec<f64>>, temps: Vec<Vec<f64>>) -> Vec<ShipmentTrace> {
    times
        .into_iter()
        .zip(temps)
        .map(|(times_d, temps_c)| ShipmentTrace { times_d, temps_c })
        .collect()
}

/// Recursively converts an arbitrary Python object into `serde_json::Value`, for accepting
/// loosely-typed `dict`/`list`/scalar params (e.g. [`PyEngineSession::apply_configure`])
/// without a fixed PyO3-derived struct. Type checks run bool before int before float so a
/// Python `bool` (a subclass of `int`) round-trips as JSON `true`/`false` rather than `0`/
/// `1`; anything that isn't `None`, a bool, a number, a string, a dict, or a list is
/// rejected as not JSON-like.
fn py_to_json(obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if obj.is_none() {
        return Ok(Value::Null);
    }
    if let Ok(b) = obj.extract::<bool>() {
        return Ok(Value::Bool(b));
    }
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(Value::Number(i.into()));
    }
    if let Ok(u) = obj.extract::<u64>() {
        return Ok(Value::Number(u.into()));
    }
    if let Ok(f) = obj.extract::<f64>() {
        if let Some(n) = serde_json::Number::from_f64(f) {
            return Ok(Value::Number(n));
        }
    }
    if let Ok(s) = obj.extract::<String>() {
        return Ok(Value::String(s));
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            let key = k.extract::<String>()?;
            map.insert(key, py_to_json(&v)?);
        }
        return Ok(Value::Object(map));
    }
    if let Ok(list) = obj.cast::<pyo3::types::PyList>() {
        let mut arr = Vec::new();
        for item in list.iter() {
            arr.push(py_to_json(&item)?);
        }
        return Ok(Value::Array(arr));
    }
    Err(pyo3::exceptions::PyValueError::new_err(
        "configure params must be a JSON-like dict",
    ))
}

/// Recursively converts a `serde_json::Value` into a Python object -- the inverse of
/// [`py_to_json`], used to hand engine snapshots and day deltas back to Python as native
/// dicts/lists rather than JSON strings the caller would have to parse.
fn json_to_py<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    match value {
        Value::Null => Ok(py.None().into_bound(py)),
        Value::Bool(b) => {
            let val = *b;
            let borrowed = val.into_pyobject(py)?;
            Ok(<Bound<'_, pyo3::types::PyBool> as Clone>::clone(&borrowed).into_any())
        }
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any())
            } else if let Some(u) = n.as_u64() {
                Ok(u.into_pyobject(py)?.into_any())
            } else if let Some(f) = n.as_f64() {
                Ok(f.into_pyobject(py)?.into_any())
            } else {
                Ok(py.None().into_bound(py))
            }
        }
        Value::String(s) => Ok(s.into_pyobject(py)?.into_any()),
        Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into_any())
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.into_any())
        }
    }
}

/// Like [`json_to_py`], but requires `value` to be a JSON object and returns it as a
/// `PyDict` directly -- the shape every engine session snapshot/delta wire value is
/// expected to have.
fn json_to_py_dict<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyDict>> {
    match value {
        Value::Object(_) => json_to_py(py, value)?.cast_into().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("session wire must be a dict: {e}"))
        }),
        _ => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "session wire value must be a JSON object",
        )),
    }
}

/// Converts a session's full state snapshot into a Python dict, for returning to Python
/// from `PyEngineSession` methods that reset or reconfigure the session.
fn wire_snapshot<'py>(py: Python<'py>, session: &EngineSession) -> PyResult<Bound<'py, PyDict>> {
    json_to_py_dict(py, &session.snapshot_value())
}

/// Converts one day's `DayDelta` into a Python dict, for returning to Python from
/// `PyEngineSession` methods that advance the session by one or more days.
fn wire_day_delta<'py>(
    py: Python<'py>,
    session: &EngineSession,
    delta: &DayDelta,
) -> PyResult<Bound<'py, PyDict>> {
    json_to_py_dict(py, &session.day_delta_value(delta))
}

/// Python-visible handle on a `voi_core::EngineSession` -- the stateful, day-by-day
/// simulation object the studio and Python notebooks drive interactively (configure once,
/// then repeatedly `step`/`act`), as opposed to the one-shot episode/rollout functions
/// elsewhere in this module.
#[pyclass]
struct PyEngineSession {
    inner: EngineSession,
}

#[pymethods]
impl PyEngineSession {
    /// Creates a session seeded with `seed`; call [`PyEngineSession::init`] before using it
    /// for anything else.
    #[new]
    fn new(seed: u64) -> Self {
        Self {
            inner: EngineSession::new(seed),
        }
    }

    /// Configures (or reconfigures) the session: sets the RNG seed, belief-grid
    /// dimensions, filter/rollout budgets, shipment thermal traces, particle count,
    /// delivery schedule, and optional demand profile and observation scenario, then
    /// returns a fresh state snapshot. Must be called before `step`/`step_n`/`act`.
    #[pyo3(signature = (seed, lead_time=1, enable_filter=true, h=7, n_paths=2, radius=1, times=vec![], temps=vec![], n_particles=200, l=2, k=4, obs_scenario=None, demand_profile_json=None, delivery_weekdays=None, units_per_lot=None))]
    fn init<'py>(
        &mut self,
        py: Python<'py>,
        seed: u64,
        lead_time: u32,
        enable_filter: bool,
        h: u32,
        n_paths: u32,
        radius: i32,
        times: Vec<Vec<f64>>,
        temps: Vec<Vec<f64>>,
        n_particles: usize,
        l: usize,
        k: usize,
        obs_scenario: Option<String>,
        demand_profile_json: Option<String>,
        delivery_weekdays: Option<Vec<u32>>,
        units_per_lot: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        self.inner.init(seed);
        self.inner.set_belief_dims(l, k.max(1));
        let demand_profile = demand_profile_json
            .as_deref()
            .and_then(|json| DemandProfile::from_json(json).ok());
        self.inner.configure(
            lead_time,
            enable_filter,
            h,
            n_paths,
            radius,
            ships_from(times, temps),
            n_particles,
            demand_profile,
            units_per_lot,
        );
        let delivery =
            delivery_weekdays.unwrap_or_else(|| OrderSchedule::default().delivery_weekday_list());
        self.inner
            .set_delivery_schedule(&delivery, lead_time.max(1));
        if let Some(scenario) = obs_scenario {
            self.inner
                .set_obs_scenario(&scenario)
                .map_err(pyo3::exceptions::PyValueError::new_err)?;
        }
        wire_snapshot(py, &self.inner)
    }

    /// Re-initializes the session with `seed` under the module's default configuration
    /// (equivalent to calling [`PyEngineSession::init`] with all its defaults).
    fn reset<'py>(&mut self, py: Python<'py>, seed: u64) -> PyResult<Bound<'py, PyDict>> {
        self.init(
            py,
            seed,
            1,
            true,
            7,
            2,
            1,
            vec![],
            vec![],
            200,
            2,
            4,
            None,
            None,
            None,
            None,
        )
    }

    /// Advances the session by one day per entry in `orders`, returning each day's delta
    /// (demand, sales, waste, arrivals, unit exits) as a list of dicts in order.
    fn step_n<'py>(&mut self, py: Python<'py>, orders: Vec<u32>) -> PyResult<Bound<'py, PyList>> {
        let deltas = self.inner.step_n(&orders);
        let list = PyList::empty(py);
        for d in &deltas {
            list.append(wire_day_delta(py, &self.inner, d)?)?;
        }
        Ok(list)
    }

    /// Advances the session by one day under a caller-supplied `order` quantity, returning
    /// that day's delta as a dict.
    fn step<'py>(&mut self, py: Python<'py>, order: u32) -> PyResult<Bound<'py, PyDict>> {
        let d = self.inner.step(order);
        wire_day_delta(py, &self.inner, &d)
    }

    /// Advances one day under a chosen ordering `policy` ("constant"/"fixed",
    /// "damped_sw"/"sw", or "rollout"/"ctl", defaulting to rollout), overriding any of the
    /// policy's tuning knobs (`alpha`, `rho`, horizon `H`/`h`, rollout path count,
    /// candidate case radius) for just this call; `order_qty`/`q` are equivalent aliases
    /// for the fixed-order quantity. `n_particles` is accepted for API symmetry but has no
    /// effect here -- particle count is set once in `init`.
    #[pyo3(signature = (
        policy=None,
        order_qty=None,
        q=None,
        alpha=None,
        rho=None,
        H=None,
        h=None,
        n_rollout_paths=None,
        candidate_case_radius=None,
        n_particles=None,
    ))]
    #[allow(non_snake_case)]
    fn act<'py>(
        &mut self,
        py: Python<'py>,
        policy: Option<String>,
        order_qty: Option<u32>,
        q: Option<u32>,
        alpha: Option<f64>,
        rho: Option<f64>,
        H: Option<u32>,
        h: Option<u32>,
        n_rollout_paths: Option<u32>,
        candidate_case_radius: Option<i32>,
        n_particles: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let _ = n_particles;
        let d = self.inner.act(
            policy.as_deref(),
            order_qty.or(q),
            alpha,
            rho,
            H.or(h),
            n_rollout_paths,
            candidate_case_radius,
        );
        wire_day_delta(py, &self.inner, &d)
    }

    /// Shorthand for `act(policy="rollout")` with every other tuning knob left at the
    /// session's configured defaults.
    fn act_rollout<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = self
            .inner
            .act(Some("rollout"), None, None, None, None, None, None);
        wire_day_delta(py, &self.inner, &d)
    }

    /// Switches the session to one of the named observation-ladder rungs (e.g. `P0`..`F3`),
    /// preserving each rung's own belief history across switches, and returns the resulting
    /// state snapshot.
    fn set_obs_scenario<'py>(
        &mut self,
        py: Python<'py>,
        obs_scenario: String,
    ) -> PyResult<Bound<'py, PyDict>> {
        let snap = self
            .inner
            .set_obs_scenario(&obs_scenario)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        json_to_py_dict(py, &snap)
    }

    /// Switches the session's observation ladder directly by its three independent toggles
    /// (`code_type`, `scan_waste`, `delivery_history`) rather than a named preset rung, and
    /// returns the resulting state snapshot.
    fn set_obs_channels<'py>(
        &mut self,
        py: Python<'py>,
        code_type: String,
        scan_waste: bool,
        delivery_history: String,
    ) -> PyResult<Bound<'py, PyDict>> {
        let channels = voi_core::obs::parse_channels(&code_type, scan_waste, &delivery_history)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        let snap = self
            .inner
            .set_obs_channels(channels)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        json_to_py_dict(py, &snap)
    }

    /// Number of host-side round trips (`init`/`reset`/`step`/`step_n`/`act`) made into
    /// this session so far -- useful for diagnosing host/session desync in the studio.
    fn host_crossings(&self) -> u32 {
        self.inner.host_crossings()
    }

    /// Returns the session's current full state as a dict, without advancing it.
    fn snapshot_value<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        wire_snapshot(py, &self.inner)
    }

    /// Applies a partial configuration update from an arbitrary Python dict (converted via
    /// [`py_to_json`]) without requiring a full [`PyEngineSession::init`] call, and returns
    /// the resulting snapshot.
    fn apply_configure<'py>(
        &mut self,
        py: Python<'py>,
        params: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let json = py_to_json(params)?;
        self.inner.apply_configure(json);
        wire_snapshot(py, &self.inner)
    }
}

/// Registers every function and class in this module as Python's `blueberries_voi._core`
/// extension module, including a `VOI_CORE` string constant identifying the linked
/// `voi_core` build.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("VOI_CORE", crate_name())?;
    m.add_function(wrap_pyfunction!(demand_profile_mu_from_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(demand_profile_mu_py, m)?)?;
    m.add_function(wrap_pyfunction!(arrival_model_from_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(protection_demand_quantile_py, m)?)?;
    m.add_function(wrap_pyfunction!(draw_demand_at_day_py, m)?)?;
    m.add_function(wrap_pyfunction!(spawn_rng_next_u64_py, m)?)?;
    m.add_function(wrap_pyfunction!(sequential_wor_py, m)?)?;
    m.add_function(wrap_pyfunction!(run_voi_crn_cell_py, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_alpha_tune_episode_py, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_alpha_tune_outcomes_py, m)?)?;
    m.add_function(wrap_pyfunction!(run_episode_py, m)?)?;
    m.add_function(wrap_pyfunction!(rollout_order_py, m)?)?;
    m.add_function(wrap_pyfunction!(terminal_salvage_unit_state_py, m)?)?;
    m.add_function(wrap_pyfunction!(w_long_py, m)?)?;
    m.add_class::<PyDemandProfile>()?;
    m.add_class::<PyEngineSession>()?;
    Ok(())
}
