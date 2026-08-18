/**
 * Events pane — protection-interval daily log (T-128).
 */
import { Fragment } from "react";
import { renderDeliveryTempHistory } from "../charts/deliveryTempMock";
import { maskFor, type MaskedObsWire } from "../obsMask";
import { ChartUnavailable } from "./ChartUnavailable";

export type EventsPaneProps = {
  vm: {
    episode_day: number;
    history: { day: number; missed?: number }[];
    config: { obs_scenario: string };
  };
  showTruth: boolean;
  events: MaskedObsWire[];
  loading?: boolean;
};

const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function weekdayLabel(day: number): string {
  return WEEKDAYS[((day - 1) % 7 + 7) % 7] ?? "";
}

function NotObserved() {
  return <span className="events-not-observed">Not observed at this rung</span>;
}

function formatLotBreakdown(
  values: number[] | null | undefined,
  lotIds: number[] | null | undefined,
): string | null {
  if (!values?.length || !lotIds?.length) return null;
  const parts: string[] = [];
  const n = Math.min(values.length, lotIds.length);
  for (let i = 0; i < n; i++) {
    const qty = values[i] ?? 0;
    if (qty <= 0) continue;
    parts.push(
      `Lot ${lotIds[i]}: ${qty} ${qty === 1 ? "unit" : "units"}`,
    );
  }
  return parts.length ? parts.join(", ") : null;
}


export function EventsPane({ vm, showTruth, events, loading }: EventsPaneProps) {
  if (loading) {
    return (
      <section className="events-pane panel" aria-label="Events" data-loading>
        <p>Loading events…</p>
      </section>
    );
  }

  const sortedEvents = [...events].sort(
    (a, b) => (b.day ?? 0) - (a.day ?? 0),
  );
  const obsMask = maskFor(vm.config.obs_scenario);
  const todayDay = vm.episode_day;

  return (
    <section className="events-pane panel" aria-label="Events">
      <div className="panel-head">
        <h2>Events</h2>
      </div>
      <div className="events-list">
        {sortedEvents.map((ev, index) => {
          const missed =
            vm.history.find((h) => h.day === ev.day)?.missed ?? 0;
          const salesBreakdown = obsMask.sales_by_lot
            ? formatLotBreakdown(ev.sales_by, ev.lot_ids)
            : null;
          const wasteBreakdown = obsMask.waste_by_lot
            ? formatLotBreakdown(ev.waste_by, ev.lot_ids)
            : null;
          const isDeliveryDay = ev.arrivals > 0;
          const isToday = ev.day === todayDay;
          const deliveryLotId = ev.lot_ids?.[0] ?? 0;

          return (
            <Fragment key={ev.day}>
              {index > 0 ? <hr className="events-day-divider" /> : null}
              <article
                className={`events-day-card${isToday ? " events-day-card--today" : ""}`}
                data-day={ev.day}
              >
                <h3 className="events-day-heading">
                  Day {ev.day ?? 0}
                  {weekdayLabel(ev.day ?? 0)
                    ? ` · ${weekdayLabel(ev.day ?? 0)}`
                    : ""}
                </h3>

                {isDeliveryDay ? (
                  <div className="events-line events-line--delivery">
                    <span className="events-line-label">Delivery</span>
                    <span className="events-line-value">
                      {ev.arrivals} units
                    </span>
                    {obsMask.age_at_receipt && ev.age_at_receipt != null ? (
                      <span className="events-line-detail">
                        harvested day{" "}
                        {Math.round((ev.day ?? 0) - ev.age_at_receipt)}
                      </span>
                    ) : null}
                    {obsMask.pack_date && ev.pack_date_days != null ? (
                      <span className="events-line-detail">
                        Pack date {ev.pack_date_days} days
                      </span>
                    ) : null}
                    {obsMask.lot_ids_live && ev.lot_ids?.length ? (
                      <span className="events-lots">
                        Lots {ev.lot_ids.join(", ")}
                      </span>
                    ) : null}
                  </div>
                ) : null}

                <div className="events-line events-line--sales">
                  <span className="events-line-label">Sales</span>
                  {ev.sales_total != null ? (
                    <>
                      <span className="events-line-value">
                        {ev.sales_total} units
                      </span>
                      {salesBreakdown ? (
                        <span className="events-breakdown">({salesBreakdown})</span>
                      ) : null}
                    </>
                  ) : (
                    <NotObserved />
                  )}
                </div>

                <div className="events-line events-line--waste">
                  <span className="events-line-label">Waste</span>
                  {ev.waste_total != null ? (
                    <>
                      <span className="events-line-value">
                        {ev.waste_total} units
                      </span>
                      {wasteBreakdown ? (
                        <span className="events-breakdown">({wasteBreakdown})</span>
                      ) : null}
                    </>
                  ) : (
                    <ChartUnavailable
                      plotId={`events-waste-${ev.day}`}
                      caption="Not observed at this rung"
                    />
                  )}
                </div>

                {showTruth ? (
                  <div className="events-line events-line--stockout">
                    <span className="events-line-label">Stockout (missed)</span>
                    <span className="events-line-value">{missed} units</span>
                  </div>
                ) : null}

                {obsMask.pack_date && !isDeliveryDay && ev.pack_date_days != null ? (
                  <div className="events-line events-line--pack-date">
                    <span className="events-line-label">Pack date</span>
                    <span className="events-line-value">
                      {ev.pack_date_days} days
                    </span>
                  </div>
                ) : null}

                {obsMask.age_at_receipt && ev.age_at_receipt != null ? (
                  <div className="events-line events-line--age-receipt">
                    <span className="events-line-label">Age at receipt</span>
                    <span className="events-line-value">{ev.age_at_receipt}</span>
                  </div>
                ) : null}

                {isDeliveryDay ? (
                  <div className="events-temp-history" data-illustrative="true">
                    <div className="chart-caption events-temp-caption">
                      temp. history (illustrative)
                    </div>
                    <div
                      className="events-temp-chart-host"
                      data-day={ev.day}
                      ref={(node) => {
                        if (node) {
                          renderDeliveryTempHistory(
                            node,
                            ev.day ?? 0,
                            deliveryLotId,
                          );
                        }
                      }}
                    />
                  </div>
                ) : null}
              </article>
            </Fragment>
          );
        })}
      </div>
    </section>
  );
}
