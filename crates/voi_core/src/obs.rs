//! Observation masks and RichObs-shaped FilterObs (ADR 0086 / 0126 / global scan model).

use serde::{Deserialize, Serialize};

use crate::shipments::ShipmentTrace;

/// Which RichObs fields are present under a scenario id or channel combo.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ObsMask {
    /// Today's arrival count is always observable (units in, not units' freshness).
    pub arrivals: bool,
    /// Store-wide unit sales, pooled across lots.
    pub sales_total: bool,
    /// Store-wide waste (spoilage) count, pooled across lots.
    pub waste_total: bool,
    /// Sales broken out per live lot; requires lot-resolved (LGTIN) codes.
    pub sales_by_lot: bool,
    /// Waste broken out per live lot; requires lot-resolved (LGTIN) codes.
    pub waste_by_lot: bool,
    /// Pack date of today's arriving shipment, pinning transit duration `d`.
    pub pack_date: bool,
    /// Lot ids of units currently live in the store's inventory.
    pub lot_ids_live: bool,
    /// Lot ids attached to today's arriving shipment.
    pub arrival_lot_ids: bool,
    /// Full temperature trace for today's arriving shipment, pinning exposure `Lambda`.
    pub temperature_history: bool,
}

/// Global scan observation channels (supersedes ADR 0133 pos/waste/deliveries).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObsChannels {
    /// POS code granularity: pooled UPC vs lot-resolved LGTIN.
    pub code_type: CodeType,
    /// Whether the store scans waste at all (off = spoilage is invisible).
    pub scan_waste: bool,
    /// What, if anything, is known about an arriving delivery's history.
    pub delivery_history: DeliveryHistory,
}

/// Point-of-sale code granularity. `Upc` pools every unit of an item under one barcode, so
/// sales/waste can only be counted store-wide; `Lgtin` carries lot identity, so counts can be
/// attributed to the specific delivery a unit came from.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CodeType {
    Upc,
    Lgtin,
}

/// What a store knows about an arriving delivery's transit history. Neither variant ever
/// reveals arrival freshness directly -- `PackDate` pins the transit duration `d`, and
/// `TemperatureHistory` additionally pins the cumulative thermal exposure `Lambda`.
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
    /// Sales for the day, one entry per live lot, aligned with `lot_ids`.
    pub sales_by: Vec<u32>,
    /// Waste for the day, one entry per live lot, aligned with `lot_ids`.
    pub waste_by: Vec<u32>,
    /// Ids of lots currently live in inventory, in the order `sales_by`/`waste_by` index into.
    pub lot_ids: Vec<i64>,
    /// Ids of lots in today's arriving shipment, if any.
    pub arrival_lot_ids: Vec<i64>,
    /// Per-lot delivery quantities when a receipt splits across L sub-lots (ADR 0149).
    pub arrivals_by: Vec<u32>,
    /// Full temperature/time trace for today's arrival, present only when one was recorded.
    pub shipment_trace: Option<ShipmentTrace>,
    /// Per-lot spliced traces for today's delivery (len = L when multilot).
    pub temp_traces_by_lot: Vec<(i64, ShipmentTrace)>,
    /// Pack date of today's arrival, in days, if known (legacy single-lot / first lot).
    pub pack_date_days: Option<i32>,
    /// Per-lot pack dates when delivery history resolves per sub-lot (ADR 0149).
    pub pack_dates_by_lot: Vec<i32>,
}

/// Masked observation consumed by `filter_step` (absent = `None`, never invented 0).
#[derive(Clone, Debug)]
pub struct FilterObs {
    /// Store-wide sales count, if `sales_total` is in the mask.
    pub sales_tot: Option<i32>,
    /// Store-wide waste count, if `waste_total` is in the mask.
    pub waste_tot: Option<i32>,
    pub arrivals: u32,
    /// Per-lot sales, aligned with `lot_ids_live`, if `sales_by_lot` is in the mask.
    pub sales_by: Option<Vec<u32>>,
    /// Per-lot waste, aligned with `lot_ids_live`, if `waste_by_lot` is in the mask.
    pub waste_by: Option<Vec<u32>>,
    /// Live lot ids that `sales_by`/`waste_by` index into, if `lot_ids_live` is in the mask.
    pub lot_ids_live: Option<Vec<i64>>,
    /// Lot ids of today's arrival, if `arrival_lot_ids` is in the mask.
    pub arrival_lot_ids: Option<Vec<i64>>,
    /// Per-lot delivery quantities on today's receipt (always populated for filter birth).
    pub arrivals_by: Option<Vec<u32>>,
    /// Pack date of today's arrival in days, if `pack_date` is in the mask.
    pub pack_date_days: Option<i32>,
    /// Per-lot pack dates when `pack_date` is in the mask (F2 wire / filter birth).
    pub pack_dates_by_lot: Option<Vec<i32>>,
    /// Elapsed times (days) for the temperature trace, if `temperature_history` is in the mask.
    pub temp_times_d: Option<Vec<f64>>,
    /// Temperatures (°C) paired with `temp_times_d`, if `temperature_history` is in the mask.
    pub temp_temps_c: Option<Vec<f64>>,
    /// Per-lot temperature traces when `temperature_history` is in the mask (F3 wire / filter birth).
    pub temp_traces_by_lot: Option<Vec<ShipmentTrace>>,
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
            arrivals_by: None,
            pack_date_days: None,
            pack_dates_by_lot: None,
            temp_times_d: None,
            temp_temps_c: None,
            temp_traces_by_lot: None,
        }
    }
}

/// Parses an `ObsChannels` out of an untyped JSON value, defaulting any missing or
/// wrong-typed field so the underlying string enums can report a precise error.
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

/// Parses the wire string forms of `code_type` and `delivery_history` into an `ObsChannels`,
/// erroring on any value outside the known set rather than silently falling back.
pub fn parse_channels(
    code_type: &str,
    scan_waste: bool,
    delivery_history: &str,
) -> Result<ObsChannels, String> {
    let code_type = match code_type {
        "upc" => CodeType::Upc,
        "lgtin" => CodeType::Lgtin,
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

/// Looks up the fixed `ObsChannels` combo behind a named rung (`P0`, `P1`, `F1`, `F1s`,
/// `F2a`, `F2`, `F3`). `F1s` is a channel-identical alias of `F1`. `B-state` is rejected
/// explicitly: it's a verification bypass used to check the filter against ground truth, not
/// a real observation rung, so it must never be turned into a mask that would let a policy
/// see fabricated data.
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
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        }),
        "F2a" => Ok(ObsChannels {
            code_type: CodeType::Upc,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        }),
        "F2" => Ok(ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        }),
        "F3" => Ok(ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::TemperatureHistory,
        }),
        _ => Err(format!("Unknown scenario for ObsMask: {id:?}")),
    }
}

/// Reverse lookup of `channels_for_preset`: returns the named rung matching `ch` exactly, if
/// any. `F1s` is never returned since it is channel-identical to `F1`.
pub fn preset_for_channels(ch: ObsChannels) -> Option<&'static str> {
    for id in ["P0", "P1", "F1", "F2a", "F2", "F3"] {
        if channels_for_preset(id).ok() == Some(ch) {
            return Some(id);
        }
    }
    None
}

/// Canonical string key for `ch`, suitable for cache lookup or as a stable identifier
/// independent of the enums' derived `Debug`/serde representations.
pub fn channels_cache_key(ch: ObsChannels) -> String {
    let code = match ch.code_type {
        CodeType::Upc => "upc",
        CodeType::Lgtin => "lgtin",
    };
    let waste = if ch.scan_waste { "1" } else { "0" };
    let hist = match ch.delivery_history {
        DeliveryHistory::None => "none",
        DeliveryHistory::PackDate => "pack_date",
        DeliveryHistory::TemperatureHistory => "temp",
    };
    format!("code={code}|waste={waste}|hist={hist}")
}

/// Serializes `ch` to the same JSON shape `validate_channels_json` accepts.
pub fn channels_json(ch: ObsChannels) -> serde_json::Value {
    serde_json::json!({
        "code_type": match ch.code_type {
            CodeType::Upc => "upc",
            CodeType::Lgtin => "lgtin",
        },
        "scan_waste": ch.scan_waste,
        "delivery_history": match ch.delivery_history {
            DeliveryHistory::None => "none",
            DeliveryHistory::PackDate => "pack_date",
            DeliveryHistory::TemperatureHistory => "temperature_history",
        },
    })
}

/// Derives which `RichDay` fields are visible from the three independent channel toggles.
/// Arrivals and store-wide sales are always on. Per-lot breakdowns only turn on under
/// `Lgtin` codes, since pooled `Upc` codes can't attribute a sale/waste event to a lot; waste
/// fields only turn on when `scan_waste` is set, and `waste_by_lot` further requires `Lgtin`.
/// `delivery_history` selects pack-date and/or temperature channels: `PackDate` sets
/// `pack_date` only; `TemperatureHistory` sets both `temperature_history` and `pack_date`
/// (temp history includes pack date so Event Log / filter birth keep calendar dates).
pub fn mask_from_channels(ch: ObsChannels) -> ObsMask {
    let mut m = ObsMask {
        arrivals: true,
        sales_total: true,
        ..ObsMask::default()
    };
    if ch.code_type == CodeType::Lgtin {
        m.sales_by_lot = true;
        m.lot_ids_live = true;
        m.arrival_lot_ids = true;
    }
    if ch.scan_waste {
        m.waste_total = true;
        if ch.code_type == CodeType::Lgtin {
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
            m.pack_date = true;
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
            if !rich.temp_traces_by_lot.is_empty() {
                let (_, t) = &rich.temp_traces_by_lot[0];
                (Some(t.times_d.clone()), Some(t.temps_c.clone()))
            } else {
                rich.shipment_trace.as_ref().map_or((None, None), |t| {
                    (Some(t.times_d.clone()), Some(t.temps_c.clone()))
                })
            }
        } else {
            (None, None)
        };
        let per_lot_traces = if self.temperature_history
            && rich.arrivals > 0
            && !rich.temp_traces_by_lot.is_empty()
        {
            Some(
                rich.temp_traces_by_lot
                    .iter()
                    .map(|(_, t)| t.clone())
                    .collect(),
            )
        } else {
            None
        };
        let pack_by_lot = if self.pack_date
            && rich.arrivals > 0
            && !rich.pack_dates_by_lot.is_empty()
        {
            Some(rich.pack_dates_by_lot.clone())
        } else {
            None
        };
        let arrivals_by = if rich.arrivals > 0 && !rich.arrivals_by.is_empty() {
            Some(rich.arrivals_by.clone())
        } else {
            None
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
            arrivals_by,
            pack_date_days: if self.pack_date {
                rich.pack_date_days
            } else {
                None
            },
            pack_dates_by_lot: pack_by_lot,
            temp_times_d,
            temp_temps_c,
            temp_traces_by_lot: per_lot_traces,
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
            code_type: CodeType::Lgtin,
            scan_waste: false,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: false,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: false,
            delivery_history: DeliveryHistory::TemperatureHistory,
        },
        ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        },
        ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::PackDate,
        },
        ObsChannels {
            code_type: CodeType::Lgtin,
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
                if ch.code_type == CodeType::Lgtin {
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
                    assert!(f["pack_date"] && f["temperature_history"]);
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
        }
    }

    #[test]
    fn f2_preset_uses_pack_date_not_age() {
        let ch = channels_for_preset("F2").unwrap();
        assert_eq!(ch.delivery_history, DeliveryHistory::PackDate);
        let m = mask_from_channels(ch);
        assert!(m.pack_date);
    }

    #[test]
    fn f3_preset_uses_temperature_history() {
        let ch = channels_for_preset("F3").unwrap();
        let m = mask_from_channels(ch);
        assert!(m.temperature_history && m.pack_date);
    }

    #[test]
    fn channels_cache_key_canonical() {
        let ch = ObsChannels {
            code_type: CodeType::Lgtin,
            scan_waste: true,
            delivery_history: DeliveryHistory::None,
        };
        assert_eq!(channels_cache_key(ch), "code=lgtin|waste=1|hist=none");
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
        assert!(!f["lot_ids_live"]);
    }

    #[test]
    fn mask_for_p1_adds_waste_total() {
        let m = mask_for("P1").expect("P1");
        assert!(m.arrivals && m.sales_total && m.waste_total);
        assert!(!m.sales_by_lot && !m.waste_by_lot);
        assert!(!m.pack_date);
        assert!(!m.lot_ids_live);
    }

    #[test]
    fn mask_for_f1_adds_sales_by_lot_and_lot_ids_live() {
        let m = mask_for("F1").expect("F1");
        assert!(m.waste_total && m.sales_by_lot && m.lot_ids_live && m.waste_by_lot);
        assert!(!m.pack_date);
    }

    #[test]
    fn mask_for_f1s_matches_f1() {
        assert_eq!(mask_for("F1s").unwrap(), mask_for("F1").unwrap());
    }

    #[test]
    fn mask_for_f2a_is_p1_plus_pack_date() {
        let m = mask_for("F2a").expect("F2a");
        assert!(m.waste_total && m.pack_date);
        assert!(!m.sales_by_lot && !m.waste_by_lot);
        assert!(!m.lot_ids_live);
    }

    #[test]
    fn mask_for_f2_has_maps_and_pack_date() {
        let m = mask_for("F2").expect("F2");
        assert!(m.waste_total && m.sales_by_lot && m.waste_by_lot);
        assert!(m.pack_date && m.lot_ids_live && m.arrival_lot_ids);
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
            pack_date_days: Some(3),
            ..Default::default()
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
            pack_date_days: Some(1),
            ..Default::default()
        };
        let obs = mask_for("F3").unwrap().apply(&rich);
        assert_eq!(obs.temp_times_d.as_deref(), Some(&[0.0, 1.0, 2.0][..]));
        assert_eq!(obs.temp_temps_c.as_deref(), Some(&[1.0, 1.0, 1.0][..]));
        assert_eq!(obs.arrival_lot_ids.as_deref(), Some(&[11i64][..]));
    }

    /// Temperature-history (F3) must keep pack dates on the masked obs — WASM Event Log
    /// reads these fields after `ObsMask::apply`, so nulling them silently blanks the column.
    #[test]
    fn apply_f3_keeps_pack_date_with_temperature_history() {
        let rich = RichDay {
            sales_total: 0,
            waste_total: 0,
            arrivals: 8,
            sales_by: vec![],
            waste_by: vec![],
            lot_ids: vec![10],
            arrival_lot_ids: vec![11],
            shipment_trace: Some(ShipmentTrace {
                times_d: vec![0.0, 1.0],
                temps_c: vec![2.0, 3.0],
            }),
            pack_date_days: Some(4),
            pack_dates_by_lot: vec![3, 4],
            ..Default::default()
        };
        let mask = mask_for("F3").unwrap();
        assert!(mask.temperature_history && mask.pack_date);
        let obs = mask.apply(&rich);
        assert_eq!(obs.pack_date_days, Some(4));
        assert_eq!(obs.pack_dates_by_lot.as_deref(), Some(&[3i32, 4][..]));
        assert!(obs.temp_times_d.is_some());
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
            pack_date_days: Some(5),
            ..Default::default()
        };
        let obs = mask_for("F2").unwrap().apply(&rich);
        assert_eq!(obs.waste_tot, Some(1));
        assert_eq!(obs.sales_by.as_deref(), Some(&[4u32, 0][..]));
        assert_eq!(obs.waste_by.as_deref(), Some(&[0u32, 1][..]));
        assert_eq!(obs.lot_ids_live.as_deref(), Some(&[1i64, 2][..]));
        assert_eq!(obs.arrival_lot_ids.as_deref(), Some(&[3i64][..]));
        assert_eq!(obs.pack_date_days, Some(5));
    }

    #[test]
    fn apply_p0_omits_per_lot_delivery_metadata() {
        let rich = RichDay {
            sales_total: 4,
            waste_total: 0,
            arrivals: 48,
            sales_by: vec![],
            waste_by: vec![],
            lot_ids: vec![],
            arrival_lot_ids: vec![1, 2, 3],
            pack_date_days: Some(5),
            pack_dates_by_lot: vec![3, 5, 4],
            temp_traces_by_lot: vec![
                (
                    1,
                    ShipmentTrace {
                        times_d: vec![0.0, 1.0],
                        temps_c: vec![2.0, 3.0],
                    },
                ),
                (
                    2,
                    ShipmentTrace {
                        times_d: vec![0.0, 1.0],
                        temps_c: vec![2.0, 3.0],
                    },
                ),
                (
                    3,
                    ShipmentTrace {
                        times_d: vec![0.0, 1.0],
                        temps_c: vec![2.0, 3.0],
                    },
                ),
            ],
            ..Default::default()
        };
        let obs = mask_for("P0").unwrap().apply(&rich);
        assert_eq!(obs.pack_date_days, None);
        assert_eq!(obs.pack_dates_by_lot, None);
        assert_eq!(obs.temp_times_d, None);
        assert_eq!(obs.temp_temps_c, None);
        assert!(obs.temp_traces_by_lot.is_none());
    }
}
