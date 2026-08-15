import type { ViewModel } from "../types";
import type { ScheduleWire } from "../engine/types";
import { weekdayLabel } from "../calendar/nextOrderAdvance";
import { scenarioTitle } from "../scenarioCopy";

export type InsightStripProps = {
  vm: ViewModel;
  schedule: ScheduleWire;
};

function formatMoney(n: number): string {
  return `$${n.toFixed(2)}`;
}

function mwfDeliveryHint(schedule: ScheduleWire): string {
  const days = schedule.delivery_weekdays;
  if (
    days.length === 3 &&
    days.includes(0) &&
    days.includes(2) &&
    days.includes(4)
  ) {
    return "MWF delivery";
  }
  return "Delivery schedule";
}

export function InsightStrip({ vm, schedule }: InsightStripProps) {
  const dayLabel = weekdayLabel(vm.episode_day, schedule);
  const scenario = scenarioTitle(vm.config.obs_scenario);

  return (
    <div className="insight-strip" role="status" aria-live="polite">
      <span className="insight-strip-day">
        Day {vm.episode_day} / {vm.window_days}
      </span>
      <span className="insight-strip-weekday">{dayLabel}</span>
      <span className="insight-strip-delivery">{mwfDeliveryHint(schedule)}</span>
      <span className="insight-strip-scenario">{scenario}</span>
      <span className="insight-strip-profit">
        Episode profit {formatMoney(vm.pnl_totals.profit)}
      </span>
    </div>
  );
}
