//! Observation masks and RichObs-shaped FilterObs (ADR 0086 / 0126 / global scan model).

use serde::{Deserialize, Serialize};

use crate::shipments::ShipmentTrace;

/// Which RichObs fields are present under a scenario id or channel combo.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ObsMask {
    pub arrivals: bool,
    pub sales_total: bool,
    pub waste_total: bool,
    pub sales_by_lot: bool,
    pub waste_by_lot: bool,
    pub pack_date: bool,
    pub age_at_receipt: bool,
    pub lot_ids_live: bool,
    pub arrival_lot_ids: bool,
    pub temperature_history: bool,
}

/// Global scan observation channels (supersedes ADR 0133 pos/waste/deliveries).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObsChannels {
    pub code_type: CodeType,
    pub scan_waste: bool,
    pub delivery_history: DeliveryHistory,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CodeType {
    Upc,
    Gsin,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeliveryHistory {
    None,
    PackDate,
    TemperatureHistory,
}

/// Richest logged day (DayStepOut + receipt meta). Catch-up applies mask.
#[derive(Clone, Debug, Default)]
pub struct RichDay {
    pub sales_total: u32,
    pub waste_total: u32,
    pub arrivals: u32,
    pub sales_by: Vec<u32>,
    pub waste_by: Vec<u32>,
    pub lot_ids: Vec<i64>,
    pub arrival_lot_ids: Vec<i64>,
    pub shipment_trace: Option<ShipmentTrace>,
    pub f_at_receipt: Option<f64>,
    pub age_at_receipt: Option<f64>,
    pub pack_date_days: Option<i32>,
}

/// Masked observation consumed by `filter_step` (absent = `None`, never invented 0).
#[derive(Clone, Debug)]
pub struct FilterObs {
    pub sales_tot: Option<i32>,
    pub waste_tot: Option<i32>,
    pub arrivals: u32,
    pub sales_by: Option<Vec<u32>>,
    pub waste_by: Option<Vec<u32>>,
    pub lot_ids_live: Option<Vec<i64>>,
    pub arrival_lot_ids: Option<Vec<i64>>,
    pub pack_date_days: Option<i32>,
    pub age_at_receipt: Option<f64>,
    pub f_at_receipt: Option<f64>,
    pub temp_times_d: Option<Vec<f64>>,
    pub temp_temps_c: Option<Vec<f64>>,
}

impl Default for FilterObs {
    fn default() -> Self {
        Self {
            sales_tot: None,
            waste_tot: None,
            arrivals: 0,
            sales_by: None,
            waste_by: None,
            lot_ids_live: None,
            arrival_lot_ids: None,
            pack_date_days: None,
            age_at_receipt: None,
            f_at_receipt: None,
            temp_times_d: None,
            temp_temps_c: None,
        }
    }
}

pub fn validate_channels_json(value: &serde_json::Value) -> Result<ObsChannels, String> {
    let code_type = value
        .get("code_type")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let scan_waste = value
        .get("scan_waste")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let delivery_history = value
        .get("delivery_history")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    parse_channels(code_type, scan_waste, delivery_history)
}

pub fn parse_channels(
    code_type: &str,
    scan_waste: bool,
    delivery_history: &str,
) -> Result<ObsChannels, String> {
    let code_type = match code_type {
        "upc" => CodeType::Upc,
        "gsin" => CodeType::Gsin,
        other => return Err(format!("invalid code_type: {other:?}")),
    };
    let delivery_history = match delivery_history {
        "none" => DeliveryHistory::None,
        "pack_date" => DeliveryHistory::PackDate,
        "temperature_history" => DeliveryHistory::TemperatureHistory,
        other => return Err(format!("invalid delivery_history: {other:?}")),
    };
    Ok(ObsChannels {
        code_type,
        scan_waste,
        delivery_history,
    })
}

pub fn channels_for_preset(id: &str) -> Result<ObsChannels, String> {
    if id == "B-state" {
        return Err(
            "SCN-B-state is a verification bypass, not an ObsMask; do not fabricate observations"
                .into(),
        );
    }
    match id {
        "P0" => Ok(ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: false,
            delivery_history: DeliveryHistory::None,
        }),
        "P1" => Ok(ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        }),
        "F1" | "F1s" => Ok(ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        }),
        "F2a" => Ok(ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        }),
        "F2" => Ok(ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        }),
        "F3" => Ok(ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::TemperatureHistory,
        }),
        _ => Err(format!("Unknown scenario for ObsMask: {id:?}")),
    }
}

pub fn preset_for_channels(ch: ObsChannels) -> Option<&'static str> {
    for id in ["P0", "P1", "F1", "F2a", "F2", "F3"] {
        if channels_for_preset(id).ok() == Some(ch) {
            return Some(id);
        }
    }
    None
}

pub fn channels_cache_key(ch: ObsChannels) -> String {
    let code = match ch.code_type {
        CodeType::Upc => "upc",
        CodeType::Gsin => "gsin",
    };
    let waste = if ch.scan_waste { "1" } else { "0" };
    let hist = match ch.delivery_history {
        DeliveryHistory::None => "none",
        DeliveryHistory::PackDate => "pack_date",
        DeliveryHistory::TemperatureHistory => "temp",
    };
    format!("code={code}|waste={waste}|hist={hist}")
}

pub fn channels_json(ch: ObsChannels) -> serde_json::Value {
    serde_json::json!({
        "code_type": match ch.code_type {
            CodeType::Upc => "upc",
            CodeType::Gsin => "gsin",
        },
        "scan_waste": ch.scan_waste,
        "delivery_history": match ch.delivery_history {
            DeliveryHistory::None => "none",
            DeliveryHistory::PackDate => "pack_date",
            DeliveryHistory::TemperatureHistory => "temperature_history",
        },
    })
}

pub fn mask_from_channels(ch: ObsChannels) -> ObsMask {
    let mut m = ObsMask {
        arrivals: true,
        sales_total: true,
        ..ObsMask::default()
    };
    if ch.code_type == CodeType::Gsin {
        m.sales_by_lot = true;
        m.lot_ids_live = true;
        m.arrival_lot_ids = true;
    }
    if ch.scan_waste {
        m.waste_total = true;
        if ch.code_type == CodeType::Gsin {
            m.waste_by_lot = true;
        }
    }
    match ch.delivery_history {
        DeliveryHistory::None => {}
        DeliveryHistory::PackDate => {
            m.pack_date = true;
        }
        DeliveryHistory::TemperatureHistory => {
            m.temperature_history = true;
        }
    }
    m
}

/// Scenario preset → mask. Matches Python ADR 0086 / `mask_for`.
pub fn mask_for(id: &str) -> Result<ObsMask, String> {
    Ok(mask_from_channels(channels_for_preset(id)?))
}

impl ObsMask {
    /// Keep present fields from `rich`; absent = `None` (never invent 0).
    pub fn apply(self, rich: &RichDay) -> FilterObs {
        let (temp_times_d, temp_temps_c) = if self.temperature_history {
            rich.shipment_trace.as_ref().map_or((None, None), |t| {
                (
                    Some(t.times_d.clone()),
                    Some(t.temps_c.clone()),
                )
            })
        } else {
            (None, None)
        };
        FilterObs {
            sales_tot: if self.sales_total {
                Some(rich.sales_total as i32)
            } else {
                None
            },
            waste_tot: if self.waste_total {
                Some(rich.waste_total as i32)
            } else {
                None
            },
            arrivals: rich.arrivals,
            sales_by: if self.sales_by_lot {
                Some(rich.sales_by.clone())
            } else {
                None
            },
            waste_by: if self.waste_by_lot {
                Some(rich.waste_by.clone())
            } else {
                None
            },
            lot_ids_live: if self.lot_ids_live {
                Some(rich.lot_ids.clone())
            } else {
                None
            },
            arrival_lot_ids: if self.arrival_lot_ids {
                Some(rich.arrival_lot_ids.clone())
            } else {
                None
            },
            pack_date_days: if self.pack_date {
                rich.pack_date_days
            } else {
                None
            },
            age_at_receipt: if self.age_at_receipt {
                rich.age_at_receipt
            } else {
                None
            },
            f_at_receipt: None,
            temp_times_d,
            temp_temps_c,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn present_fields(m: &ObsMask) -> HashMap<&'static str, bool> {
        HashMap::from([
            ("arrivals", m.arrivals),
            ("sales_total", m.sales_total),
            ("waste_total", m.waste_total),
            ("sales_by_lot", m.sales_by_lot),
            ("waste_by_lot", m.waste_by_lot),
            ("pack_date", m.pack_date),
            ("age_at_receipt", m.age_at_receipt),
            ("lot_ids_live", m.lot_ids_live),
            ("arrival_lot_ids", m.arrival_lot_ids),
            ("temperature_history", m.temperature_history),
        ])
    }

    const ALL_CHANNELS: [ObsChannels; 12] = [
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: false,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: false,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: false,
            delivery_history: DeliveryHistory::TemperatureHistory,
        },
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::TemperatureHistory,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: false,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: false,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: false,
            delivery_history: DeliveryHistory::TemperatureHistory,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::TemperatureHistory,
        },
    ];

    #[test]
    fn mask_from_channels_all_twelve_combos() {
        for ch in ALL_CHANNELS {
            let m = mask_from_channels(ch);
            let f = present_fields(&m);
            assert!(f["arrivals"] && f["sales_total"]);
            assert!(!f["age_at_receipt"]);
            if ch.code_type == CodeType::Gsin {
                assert!(f["sales_by_lot"] && f["lot_ids_live"] && f["arrival_lot_ids"]);
            } else {
                assert!(!f["sales_by_lot"] && !f["lot_ids_live"] && !f["arrival_lot_ids"]);
            }
            if !ch.scan_waste {
                assert!(!f["waste_total"] && !f["waste_by_lot"]);
            } else if ch.code_type == CodeType::Upc {
                assert!(f["waste_total"] && !f["waste_by_lot"]);
            } else {
                assert!(f["waste_total"] && f["waste_by_lot"]);
            }
            match ch.delivery_history {
                DeliveryHistory::None => {
                    assert!(!f["pack_date"] && !f["temperature_history"]);
                }
                DeliveryHistory::PackDate => {
                    assert!(f["pack_date"] && !f["temperature_history"]);
                }
                DeliveryHistory::TemperatureHistory => {
                    assert!(!f["pack_date"] && f["temperature_history"]);
                }
            }
        }
    }

    #[test]
    fn preset_round_trip_matches_mask_for() {
        for id in ["P0", "P1", "F1", "F1s", "F2a", "F2", "F3"] {
            let ch = channels_for_preset(id).unwrap();
            let from_ch = mask_from_channels(ch);
            let from_id = mask_for(id).unwrap();
            assert_eq!(from_ch, from_id);
            assert!(!from_ch.age_at_receipt);
        }
    }

    #[test]
    fn f2_preset_uses_pack_date_not_age() {
        let ch = channels_for_preset("F2").unwrap();
        assert_eq!(ch.delivery_history, DeliveryHistory::PackDate);
        let m = mask_from_channels(ch);
        assert!(m.pack_date && !m.age_at_receipt && !m.temperature_history);
    }

    #[test]
    fn f3_preset_uses_temperature_history() {
        let ch = channels_for_preset("F3").unwrap();
        let m = mask_from_channels(ch);
        assert!(m.temperature_history && !m.pack_date);
    }

    #[test]
    fn channels_cache_key_canonical() {
        let ch = ObsChannels {
            code_type: CodeType::Gsin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        };
        assert_eq!(channels_cache_key(ch), "code=gsin|waste=1|hist=none");
    }

    #[test]
    fn parse_channels_rejects_invalid_enum() {
        assert!(parse_channels("bad", false, "none").is_err());
        assert!(parse_channels("upc", false, "bad").is_err());
    }

    #[test]
    fn mask_for_p0_has_arrivals_and_sales_total_only() {
        let m = mask_for("P0").expect("P0 is a valid rung");
        let f = present_fields(&m);
        assert!(f["arrivals"]);
        assert!(f["sales_total"]);
        assert!(!f["waste_total"]);
        assert!(!f["sales_by_lot"]);
        assert!(!f["waste_by_lot"]);
        assert!(!f["pack_date"]);
        assert!(!f["age_at_receipt"]);
        assert!(!f["lot_ids_live"]);
    }

    #[test]
    fn mask_for_p1_adds_waste_total() {
        let m = mask_for("P1").expect("P1");
        assert!(m.arrivals && m.sales_total && m.waste_total);
        assert!(!m.sales_by_lot && !m.waste_by_lot);
        assert!(!m.pack_date && !m.age_at_receipt);
        assert!(!m.lot_ids_live);
    }

    #[test]
    fn mask_for_f1_adds_sales_by_lot_and_lot_ids_live() {
        let m = mask_for("F1").expect("F1");
        assert!(m.waste_total && m.sales_by_lot && m.lot_ids_live && m.waste_by_lot);
        assert!(!m.pack_date && !m.age_at_receipt);
    }

    #[test]
    fn mask_for_f1s_matches_f1() {
        assert_eq!(mask_for("F1s").unwrap(), mask_for("F1").unwrap());
    }

    #[test]
    fn mask_for_f2a_is_p1_plus_pack_date() {
        let m = mask_for("F2a").expect("F2a");
        assert!(m.waste_total && m.pack_date);
        assert!(!m.sales_by_lot && !m.waste_by_lot && !m.age_at_receipt);
        assert!(!m.lot_ids_live);
    }

    #[test]
    fn mask_for_f2_has_maps_and_pack_date() {
        let m = mask_for("F2").expect("F2");
        assert!(m.waste_total && m.sales_by_lot && m.waste_by_lot);
        assert!(m.pack_date && m.lot_ids_live && m.arrival_lot_ids);
        assert!(!m.age_at_receipt);
    }

    #[test]
    fn mask_for_p2_and_b_state_error_like_python() {
        let p2 = mask_for("P2").expect_err("P2 is out");
        assert!(p2.contains("Unknown scenario") || p2.contains("P2"), "{p2}");
        let b = mask_for("B-state").expect_err("B-state is not a mask");
        assert!(
            b.contains("bypass") || b.contains("B-state") || b.contains("fabricate"),
            "{b}"
        );
    }

    #[test]
    fn apply_p0_omits_waste_never_invents_zero() {
        let rich = RichDay {
            sales_total: 4,
            waste_total: 2,
            arrivals: 8,
            sales_by: vec![3, 1],
            waste_by: vec![2, 0],
            lot_ids: vec![10, 11],
            arrival_lot_ids: vec![12],
            shipment_trace: None,
            f_at_receipt: Some(0.85),
            age_at_receipt: Some(2.0),
            pack_date_days: Some(3),
        };
        let obs = mask_for("P0").unwrap().apply(&rich);
        assert_eq!(obs.arrivals, 8);
        assert_eq!(obs.sales_tot, Some(4));
        assert_eq!(obs.waste_tot, None);
        assert!(obs.sales_by.is_none());
        assert!(obs.waste_by.is_none());
        assert!(obs.lot_ids_live.is_none());
        assert!(obs.arrival_lot_ids.is_none());
        assert!(obs.pack_date_days.is_none());
        assert!(obs.age_at_receipt.is_none());
        assert!(obs.temp_times_d.is_none());
    }

    #[test]
    fn apply_f3_passes_shipment_trace() {
        let rich = RichDay {
            sales_total: 0,
            waste_total: 0,
            arrivals: 8,
            sales_by: vec![],
            waste_by: vec![],
            lot_ids: vec![10],
            arrival_lot_ids: vec![11],
            shipment_trace: Some(ShipmentTrace {
                times_d: vec![0.0, 1.0, 2.0],
                temps_c: vec![1.0, 1.0, 1.0],
            }),
            f_at_receipt: Some(0.9),
            age_at_receipt: Some(1.0),
            pack_date_days: Some(1),
        };
        let obs = mask_for("F3").unwrap().apply(&rich);
        assert_eq!(obs.temp_times_d.as_deref(), Some(&[0.0, 1.0, 2.0][..]));
        assert_eq!(obs.temp_temps_c.as_deref(), Some(&[1.0, 1.0, 1.0][..]));
        assert_eq!(obs.arrival_lot_ids.as_deref(), Some(&[11i64][..]));
    }

    #[test]
    fn apply_f2_keeps_maps_and_pack_date() {
        let rich = RichDay {
            sales_total: 4,
            waste_total: 1,
            arrivals: 8,
            sales_by: vec![4, 0],
            waste_by: vec![0, 1],
            lot_ids: vec![1, 2],
            arrival_lot_ids: vec![3],
            shipment_trace: None,
            f_at_receipt: Some(0.9),
            age_at_receipt: Some(1.5),
            pack_date_days: Some(5),
        };
        let obs = mask_for("F2").unwrap().apply(&rich);
        assert_eq!(obs.waste_tot, Some(1));
        assert_eq!(obs.sales_by.as_deref(), Some(&[4u32, 0][..]));
        assert_eq!(obs.waste_by.as_deref(), Some(&[0u32, 1][..]));
        assert_eq!(obs.lot_ids_live.as_deref(), Some(&[1i64, 2][..]));
        assert_eq!(obs.arrival_lot_ids.as_deref(), Some(&[3i64][..]));
        assert_eq!(obs.pack_date_days, Some(5));
        assert!(obs.age_at_receipt.is_none());
    }
}
