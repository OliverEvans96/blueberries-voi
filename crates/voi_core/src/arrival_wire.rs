//! Single adapter for arrival chart wire (T-150 AC3.3). All `arrival.rs` coupling lives here.

use crate::arrival::{ArrivalCorridor, ArrivalModel};
use crate::obs::{DeliveryHistory, ObsChannels};

const WIRE_GRID: usize = 81;
const WIRE_QUAD: usize = 8;

fn expected_delay(corridor: &ArrivalCorridor) -> f64 {
    corridor.d_min + corridor.delay_shape * corridor.delay_scale
}

fn wire_condition(
    channels: ObsChannels,
    model: &ArrivalModel,
    product: &str,
) -> (Option<i32>, Option<f64>) {
    match channels.delivery_history {
        DeliveryHistory::TemperatureHistory => {
            let phi = model.phi_bar_from_t_bar(model.mu_t);
            (None, Some(phi))
        }
        DeliveryHistory::PackDate => {
            let corridor = model.corridor(product);
            let d = expected_delay(corridor).round() as i32;
            (Some(d), None)
        }
        DeliveryHistory::None => (None, None),
    }
}

fn corridor_cdf_at(
    model: &ArrivalModel,
    corridor: &ArrivalCorridor,
    pack_date_days: Option<i32>,
    phi_bar: Option<f64>,
    transit_temp_bias_c: f64,
    f: f64,
) -> f64 {
    let mut p = 0.0;
    let mut w_sum = 0.0;
    for i in 0..WIRE_QUAD {
        for j in 0..WIRE_QUAD {
            for k in 0..WIRE_QUAD {
                let u = (i as f64 + 0.5) / WIRE_QUAD as f64;
                let v = (j as f64 + 0.5) / WIRE_QUAD as f64;
                let w_pos = (k as f64 + 0.5) / WIRE_QUAD as f64;
                let w = 1.0 / (WIRE_QUAD * WIRE_QUAD * WIRE_QUAD) as f64;

                let d = if let Some(pd) = pack_date_days {
                    f64::from(pd).max(0.0)
                } else {
                    let delay_mean = expected_delay(corridor);
                    let delay_span = corridor.delay_scale * 2.0;
                    (corridor.d_min + delay_mean + delay_span * (2.0 * u - 1.0)).max(0.0)
                };
                let phi = if let Some(pb) = phi_bar {
                    pb
                } else {
                    let t_span = model.sigma_t * 2.5;
                    let t_bar = (model.mu_t + transit_temp_bias_c + t_span * (2.0 * v - 1.0))
                        .max(model.temp_floor_c);
                    model.phi_bar_from_t_bar(t_bar)
                };
                // Lognormal(0, sigma_pos): map uniform → quantile via exp(sigma * Φ⁻¹); use symmetric grid.
                let z = 2.0 * w_pos - 1.0;
                let psi_pos = (model.sigma_pos * z).exp().max(1e-6);
                let lambda = ArrivalModel::floor_lambda(d * phi * psi_pos);
                p += w * model.cdf_f_given_lambda(lambda, f);
                w_sum += w;
            }
        }
    }
    if w_sum > 0.0 {
        p /= w_sum;
    }
    p.clamp(0.0, 1.0)
}

fn corridor_summary(
    model: &ArrivalModel,
    product: &str,
    pack_date_days: Option<i32>,
    phi_bar: Option<f64>,
    transit_temp_bias_c: f64,
) -> (Vec<f64>, Vec<f64>, f64, f64, f64) {
    let corridor = model.corridor(product).clone();
    let mut cdf = vec![0.0; WIRE_GRID];
    for gi in 0..WIRE_GRID {
        let f = gi as f64 / (WIRE_GRID - 1) as f64;
        cdf[gi] = corridor_cdf_at(
            model,
            &corridor,
            pack_date_days,
            phi_bar,
            transit_temp_bias_c,
            f,
        );
    }

    let representative_lambda = {
        let d = pack_date_days
            .map(f64::from)
            .unwrap_or_else(|| expected_delay(&corridor));
        let phi =
            phi_bar.unwrap_or_else(|| model.phi_bar_from_t_bar(model.mu_t + transit_temp_bias_c));
        ArrivalModel::floor_lambda(d * phi)
    };
    let f_zero = model.p_f_zero(representative_lambda);

    let mut mean_acc = 0.0;
    let mut mean_sq_acc = 0.0;
    let mut mass_acc = 0.0;
    for gi in 1..WIRE_GRID {
        let f = gi as f64 / (WIRE_GRID - 1) as f64;
        let f_prev = (gi - 1) as f64 / (WIRE_GRID - 1) as f64;
        let bin_mass = (cdf[gi] - cdf[gi - 1]).max(0.0);
        let f_mid = 0.5 * (f + f_prev);
        mean_acc += f_mid * bin_mass;
        mean_sq_acc += f_mid * f_mid * bin_mass;
        mass_acc += bin_mass;
    }
    if mass_acc > 0.0 {
        mean_acc /= mass_acc;
        mean_sq_acc /= mass_acc;
    }
    let sd_f = (mean_sq_acc - mean_acc * mean_acc).max(0.0).sqrt();

    let mut pdf: Vec<f64> = vec![0.0; WIRE_GRID];
    let dx = 1.0 / (WIRE_GRID - 1) as f64;
    for gi in 1..WIRE_GRID {
        pdf[gi] = ((cdf[gi] - cdf[gi - 1]) / dx).max(0.0);
    }
    pdf[0] = pdf.get(1).copied().unwrap_or(0.0);

    (cdf, pdf, f_zero, mean_acc, sd_f)
}

/// Chart-ready arrival summary for the snapshot wire (AC3.3).
pub fn arrival_summary_wire(
    model: &ArrivalModel,
    product: &str,
    channels: ObsChannels,
    transit_temp_bias_c: f64,
) -> serde_json::Value {
    let (pack_date_days, phi_bar) = wire_condition(channels, model, product);
    let (cdf, pdf, f_zero, mean_f, sd_f) =
        corridor_summary(model, product, pack_date_days, phi_bar, transit_temp_bias_c);

    let baseline_curve: Option<Vec<serde_json::Value>> = if transit_temp_bias_c.abs() > 1e-9 {
        let (_, pdf_zero, _, _, _) = corridor_summary(model, product, pack_date_days, phi_bar, 0.0);
        Some(
            (0..WIRE_GRID)
                .map(|gi| {
                    let f = gi as f64 / (WIRE_GRID - 1) as f64;
                    serde_json::json!({ "f": f, "density": pdf_zero[gi] })
                })
                .collect(),
        )
    } else {
        None
    };

    let curve: Vec<serde_json::Value> = (0..WIRE_GRID)
        .map(|gi| {
            let f = gi as f64 / (WIRE_GRID - 1) as f64;
            serde_json::json!({
                "f": f,
                "density": pdf[gi],
                "cdf": cdf[gi],
            })
        })
        .collect();

    let rung = match channels.delivery_history {
        DeliveryHistory::TemperatureHistory => "F3",
        DeliveryHistory::PackDate => {
            if channels.code_type == crate::obs::CodeType::Gsin {
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
    };

    serde_json::json!({
        "arrival_product": product,
        "rung": rung,
        "mean_f": mean_f,
        "sd_f": sd_f,
        "f_zero": f_zero,
        "curve": curve,
        "baseline_curve": baseline_curve,
    })
}
