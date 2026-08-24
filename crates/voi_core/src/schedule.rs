//! Order calendar (Python `OrderSchedule`). Day 0 = Monday.

#[derive(Clone, Debug)]
pub struct OrderSchedule {
    pub delivery_weekdays: [bool; 7],
    pub order_weekdays: [bool; 7],
    pub lead_time_days: u32,
}

impl Default for OrderSchedule {
    fn default() -> Self {
        Self::with_delivery(&[0, 2, 4], 1)
    }
}

/// ``order_weekday = (delivery - lead_time + 7) % 7`` for each delivery day; dedupe + sort.
pub fn derive_order_weekdays(delivery: &[u32], lead_time_days: u32) -> Vec<u32> {
    let lt = lead_time_days % 7;
    let mut order: Vec<u32> = delivery
        .iter()
        .map(|&d| (d + 7 - lt) % 7)
        .collect();
    order.sort_unstable();
    order.dedup();
    order
}

impl OrderSchedule {
    pub fn delivery_weekday_list(&self) -> Vec<u32> {
        self.delivery_weekdays
            .iter()
            .enumerate()
            .filter(|(_, &on)| on)
            .map(|(i, _)| i as u32)
            .collect()
    }

    pub fn order_weekday_list(&self) -> Vec<u32> {
        self.order_weekdays
            .iter()
            .enumerate()
            .filter(|(_, &on)| on)
            .map(|(i, _)| i as u32)
            .collect()
    }

    pub fn from_delivery(delivery: &[u32], lead_time_days: u32) -> Result<Self, String> {
        if delivery.is_empty() {
            return Err("delivery_weekdays must be non-empty".into());
        }
        let mut delivery_flags = [false; 7];
        for &d in delivery {
            if d >= 7 {
                return Err(format!("delivery weekday must be 0..6 (monday0), got {d}"));
            }
            delivery_flags[d as usize] = true;
        }
        let order = derive_order_weekdays(delivery, lead_time_days);
        if order.is_empty() {
            return Err("derived order_weekdays must be non-empty".into());
        }
        let mut order_flags = [false; 7];
        for d in order {
            order_flags[d as usize] = true;
        }
        Ok(Self {
            delivery_weekdays: delivery_flags,
            order_weekdays: order_flags,
            lead_time_days,
        })
    }

    pub fn with_delivery(delivery: &[u32], lead_time_days: u32) -> Self {
        Self::from_delivery(delivery, lead_time_days).unwrap_or_else(|_| Self::default())
    }

    fn weekday(day: u32) -> usize {
        // 2024-01-01 was Monday → weekday 0.
        (day % 7) as usize
    }

    pub fn can_order(&self, day: u32) -> bool {
        self.order_weekdays[Self::weekday(day)]
    }

    pub fn next_order_day(&self, day: u32) -> u32 {
        let mut c = day + 1;
        while !self.can_order(c) {
            c += 1;
        }
        c
    }

    /// Stub API reference — full narrative is on the VitePress docs site.
    ///
    /// See the concept pages that cite this symbol in their "In the code" tables.
    pub fn protection_days(&self, day: u32) -> u32 {
        self.next_order_day(day) - day + self.lead_time_days
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn monday0_cannot_order_can_on_sunday() {
        let s = OrderSchedule::default();
        assert!(!s.can_order(0)); // Mon
        assert!(s.can_order(6)); // Sun
        assert!(s.can_order(1)); // Tue
        assert!(s.can_order(3)); // Thu
    }

    #[test]
    fn protection_days_sun_tue_thu() {
        let s = OrderSchedule::default();
        // Sun=6 → next Tue=8 → 8-6+1=3
        assert_eq!(s.protection_days(6), 3);
        assert_eq!(s.protection_days(1), 3);
        assert_eq!(s.protection_days(3), 4);
    }

    #[test]
    fn derive_order_weekdays_default_mwf_lt1() {
        assert_eq!(derive_order_weekdays(&[0, 2, 4], 1), vec![1, 3, 6]);
    }

    #[test]
    fn derive_order_weekdays_lt0_same_as_delivery() {
        assert_eq!(derive_order_weekdays(&[0, 2, 4], 0), vec![0, 2, 4]);
    }

    #[test]
    fn derive_order_weekdays_lt2() {
        assert_eq!(derive_order_weekdays(&[0, 2, 4], 2), vec![0, 2, 5]);
    }

    #[test]
    fn derive_order_weekdays_dedupes() {
        assert_eq!(derive_order_weekdays(&[0, 0, 2], 1), vec![1, 6]);
    }

    #[test]
    fn from_delivery_tuesday_only_lt1() {
        let s = OrderSchedule::from_delivery(&[1], 1).unwrap();
        assert_eq!(s.delivery_weekday_list(), vec![1]);
        assert_eq!(s.order_weekday_list(), vec![0]);
    }

    #[test]
    fn from_delivery_rejects_empty() {
        assert!(OrderSchedule::from_delivery(&[], 1).is_err());
    }
}
