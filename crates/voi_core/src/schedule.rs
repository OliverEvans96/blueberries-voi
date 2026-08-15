//! Order calendar (Python `OrderSchedule`). Day 0 = Monday.

#[derive(Clone, Debug)]
pub struct OrderSchedule {
    pub delivery_weekdays: [bool; 7],
    pub order_weekdays: [bool; 7],
    pub lead_time_days: u32,
}

impl Default for OrderSchedule {
    fn default() -> Self {
        let mut delivery = [false; 7];
        delivery[0] = true;
        delivery[2] = true;
        delivery[4] = true;
        let mut order = [false; 7];
        order[6] = true;
        order[1] = true;
        order[3] = true;
        Self {
            delivery_weekdays: delivery,
            order_weekdays: order,
            lead_time_days: 1,
        }
    }
}

impl OrderSchedule {
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
}
