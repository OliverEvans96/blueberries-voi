//! Observation masks and RichObs-shaped FilterObs (ADR 0086 / 0126).
//!
//! Production `mask_for` richness is T-117 I1. This module exists so QA tests
//! compile against the public types; stubs do not implement the field table.

/// Which RichObs fields are present under a scenario id.
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
}

/// Richest logged day (DayStepOut + receipt meta). Catch-up applies `mask_for`.
#[derive(Clone, Debug, Default)]
pub struct RichDay {
    pub sales_total: u32,
    pub waste_total: u32,
    pub arrivals: u32,
    pub sales_by: Vec<u32>,
    pub waste_by: Vec<u32>,
    pub lot_ids: Vec<i64>,
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
    pub pack_date_days: Option<i32>,
    pub age_at_receipt: Option<f64>,
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
            pack_date_days: None,
            age_at_receipt: None,
        }
    }
}

/// Scenario → mask. Matches Python ADR 0086 / `mask_for`.
pub fn mask_for(id: &str) -> Result<ObsMask, String> {
    if id == "B-state" {
        return Err("SCN-B-state is a verification bypass, not an ObsMask; \
             do not fabricate observations via mask_for"
            .into());
    }
    let m = match id {
        "P0" => ObsMask {
            arrivals: true,
            sales_total: true,
            ..ObsMask::default()
        },
        "P1" => ObsMask {
            arrivals: true,
            sales_total: true,
            waste_total: true,
            ..ObsMask::default()
        },
        "F1" => ObsMask {
            arrivals: true,
            sales_total: true,
            waste_total: true,
            sales_by_lot: true,
            lot_ids_live: true,
            ..ObsMask::default()
        },
        "F1s" => ObsMask {
            arrivals: true,
            sales_total: true,
            waste_total: true,
            waste_by_lot: true,
            lot_ids_live: true,
            ..ObsMask::default()
        },
        "F2a" => ObsMask {
            arrivals: true,
            sales_total: true,
            waste_total: true,
            pack_date: true,
            ..ObsMask::default()
        },
        "F2" => ObsMask {
            arrivals: true,
            sales_total: true,
            waste_total: true,
            sales_by_lot: true,
            waste_by_lot: true,
            age_at_receipt: true,
            lot_ids_live: true,
            ..ObsMask::default()
        },
        _ => return Err(format!("Unknown scenario for ObsMask: {id:?}")),
    };
    Ok(m)
}

impl ObsMask {
    /// Keep present fields from `rich`; absent = `None` (never invent 0).
    /// `arrivals` is always copied (u32 on every rung).
    pub fn apply(self, rich: &RichDay) -> FilterObs {
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
        ])
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
        assert!(m.waste_total && m.sales_by_lot && m.lot_ids_live);
        assert!(!m.waste_by_lot && !m.pack_date && !m.age_at_receipt);
    }

    #[test]
    fn mask_for_f1s_adds_waste_by_lot_and_lot_ids_live() {
        let m = mask_for("F1s").expect("F1s");
        assert!(m.waste_total && m.waste_by_lot && m.lot_ids_live);
        assert!(!m.sales_by_lot && !m.pack_date && !m.age_at_receipt);
    }

    #[test]
    fn mask_for_f2a_is_p1_plus_pack_date() {
        let m = mask_for("F2a").expect("F2a");
        assert!(m.waste_total && m.pack_date);
        assert!(!m.sales_by_lot && !m.waste_by_lot && !m.age_at_receipt);
        assert!(!m.lot_ids_live);
    }

    #[test]
    fn mask_for_f2_has_maps_age_at_receipt_and_lot_ids() {
        let m = mask_for("F2").expect("F2");
        assert!(m.waste_total && m.sales_by_lot && m.waste_by_lot);
        assert!(m.age_at_receipt && m.lot_ids_live);
        assert!(!m.pack_date);
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
        assert!(obs.pack_date_days.is_none());
        assert!(obs.age_at_receipt.is_none());
    }

    #[test]
    fn apply_f2_keeps_maps_and_age_at_receipt() {
        let rich = RichDay {
            sales_total: 4,
            waste_total: 1,
            arrivals: 8,
            sales_by: vec![4, 0],
            waste_by: vec![0, 1],
            lot_ids: vec![1, 2],
            f_at_receipt: Some(0.9),
            age_at_receipt: Some(1.5),
            pack_date_days: Some(0),
        };
        let obs = mask_for("F2").unwrap().apply(&rich);
        assert_eq!(obs.waste_tot, Some(1));
        assert_eq!(obs.sales_by.as_deref(), Some(&[4u32, 0][..]));
        assert_eq!(obs.waste_by.as_deref(), Some(&[0u32, 1][..]));
        assert_eq!(obs.lot_ids_live.as_deref(), Some(&[1i64, 2][..]));
        assert_eq!(obs.age_at_receipt, Some(1.5));
    }
}
