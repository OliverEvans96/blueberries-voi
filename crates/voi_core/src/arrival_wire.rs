//! Single adapter for the arrival chart wire (T-150 AC3.3). This file does no
//! integration of its own — every number here comes from `arrival.rs`'s own
//! `rung_law_on_grid`, the same per-point CDF (`marginal_cdf_at`) the filter's
//! `build_law_cdf` calls. Two independent implementations of the same integral was
//! the root cause of the studio chart disagreeing with the filter's own belief
//! (`t150_wire_filter_parity_guard`); this adapter only picks which condition a rung
//! observes and reshapes `arrival.rs`'s result into the wire's JSON.

use crate::arrival::{ArrivalCondition, ArrivalModel};
use crate::obs::{CodeType, DeliveryHistory, ObsChannels};

const WIRE_GRID: usize = 81;

/// Which law this rung's chart should show, as an `arrival.rs` condition — never
/// numbers computed here. F3 reads the model's own record of the Λ the filter last
/// actually conditioned on (ADR 0144 Correction 1: F3 conditions on the observed
/// shipment, never a prior-mean placeholder); absent an observation yet, nothing is
/// known, so F3 falls back to the unconditional prior rather than inventing a
/// synthetic Λ. F2 falls back to the corridor's expected duration, which is a
/// meaningful "typical shipment" default even before any pack date has been observed.
fn resolve_condition(model: &ArrivalModel, product: &str, channels: ObsChannels) -> ArrivalCondition {
    match channels.delivery_history {
        DeliveryHistory::TemperatureHistory => model
            .last_exposure_lambda()
            .map(ArrivalCondition::Exposure)
            .unwrap_or(ArrivalCondition::Prior),
        DeliveryHistory::PackDate => {
            let d = model
                .last_duration_days()
                .unwrap_or_else(|| model.mean_delay_for_corridor(product).round() as i32);
            ArrivalCondition::Duration(d)
        }
        DeliveryHistory::None => ArrivalCondition::Prior,
    }
}

/// Maps the observation ladder's three toggles onto the named rung a chart should
/// label itself with (ADR 0133): duration-only delivery history splits into `F2`
/// (LGTIN, lot-resolved) vs `F2a` (UPC, pooled) since the two see the same duration
/// conditioning but at different code-type resolution.
fn rung_name(channels: ObsChannels) -> &'static str {
    match channels.delivery_history {
        DeliveryHistory::TemperatureHistory => "F3",
        DeliveryHistory::PackDate => {
            if channels.code_type == CodeType::Lgtin {
                "F2"
            } else {
                "F2a"
            }
        }
        DeliveryHistory::None => {
            if channels.scan_waste {
                "P1"
            } else {
                "P0"
            }
        }
    }
}

/// Chart-ready arrival summary for the snapshot wire (AC3.3). Delegates the entire
/// integration to `arrival.rs::rung_law_on_grid`; the only work here is picking which
/// condition this rung observes and reshaping the result into the wire's JSON.
///
/// `transit_temp_bias_c` is accepted for call-site stability but not applied here:
/// it is already wired into the truth path (`EngineSession::advance_one`'s biased
/// delivery draw), and `arrival.rs`'s public laws have no bias-shifted variant to
/// delegate to. Adding one — and a `baseline_curve` bias-preview overlay — is a real
/// extension of that surface, not a numerical fix this ticket's failing assertions
/// require, so it is left as a follow-up rather than reimplemented here.
pub fn arrival_summary_wire(
    model: &ArrivalModel,
    product: &str,
    channels: ObsChannels,
    transit_temp_bias_c: f64,
) -> serde_json::Value {
    let _ = transit_temp_bias_c;
    let condition = resolve_condition(model, product, channels);
    let law = if matches!(condition, ArrivalCondition::Prior) && product == model.active_corridor()
    {
        model.prior_rung_law_from_marginal_cache(WIRE_GRID)
    } else {
        model.rung_law_on_grid(condition, product, WIRE_GRID)
    };

    let dx = 1.0 / (WIRE_GRID - 1) as f64;
    let mut pdf = vec![0.0; WIRE_GRID];
    for gi in 1..WIRE_GRID {
        pdf[gi] = ((law.cdf[gi] - law.cdf[gi - 1]) / dx).max(0.0);
    }
    pdf[0] = pdf.get(1).copied().unwrap_or(0.0);

    let curve: Vec<serde_json::Value> = (0..WIRE_GRID)
        .map(|gi| {
            let f = gi as f64 / (WIRE_GRID - 1) as f64;
            serde_json::json!({
                "f": f,
                "density": pdf[gi],
                "cdf": law.cdf[gi],
            })
        })
        .collect();

    serde_json::json!({
        "arrival_product": product,
        "rung": rung_name(channels),
        "mean_f": law.mean_f,
        "sd_f": law.sd_f,
        "f_zero": law.atom_f0,
        "curve": curve,
        "baseline_curve": serde_json::Value::Null,
    })
}
