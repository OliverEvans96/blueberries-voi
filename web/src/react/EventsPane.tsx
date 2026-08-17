/**
 * Events pane — masked richest_log window (T-127 AC-events-ui).
 */
import { Fragment } from "react";
import { renderDeliveryTempHistory } from "../charts/deliveryTempMock";
import { maskFor, maskFromChannels, type MaskedObsWire } from "../obsMask";
import type { ObsChannels } from "../types";
import { ChartUnavailable } from "./ChartUnavailable";

export type EventsPaneProps = {
  vm: {
    episode_day: number;
    history: { day: number; missed?: number }[];
    config: { obs_scenario: string; obs_channels?: ObsChannels };
  };
  showTruth: boolean;
  events: MaskedObsWire[];
  loading?: boolean;
};

function NotObserved() {
  return (
    <span className="events-not-observed">
      Not observed at this rung
    </span>
  );
}

function formatLotBreakdown(
  values: number[] | null | undefined,
  lotIds: number[] | null | undefined,
): string | null {
  if (!values?.length || !lotIds?.length) return null;
  const n = Math.min(values.length, lotIds.length);
  if (n === 0) return null;
  return Array.from(
    { length: n },
    (_, i) => `Lot ${lotIds[i]}: ${values[i]} ${values[i] === 1 ? "unit" : "units"}`,
  ).join(", ");
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
  const obsMask = vm.config.obs_channels
    ? maskFromChannels(vm.config.obs_channels)
    : maskFor(vm.config.obs_scenario);

  return (
    <section className="events-pane panel" aria-label="Events">
      <div className="panel-head">
        <h2>Events</h2>
      </div>
      <div className="events-list">
        {sortedEvents.map((ev, index) => {
          const missed =
            vm.history.find((h) => h.day === ev.day)?.missed ?? 0;
          const salesBreakdown = formatLotBreakdown(ev.sales_by, ev.lot_ids);
          const wasteBreakdown = formatLotBreakdown(ev.waste_by, ev.lot_ids);
          const deliveryLotId = ev.lot_ids?.[0] ?? 0;
          const isDeliveryDay = ev.arrivals > 0;

          return (
            <Fragment key={ev.day}>
              {index > 0 ? <hr className="events-day-divider" /> : null}
              <article
                className="events-day-card"
                data-day={ev.day}
              >
                <h3 className="events-day-heading">Day {ev.day}</h3>
                <div className="events-row events-row--pos">
                  <span>POS</span>
                  {ev.sales_total != null ? (
                    <>
                      <span>{ev.sales_total}</span>
                      {salesBreakdown ? (
                        <span className="events-breakdown">({salesBreakdown})</span>
                      ) : null}
                    </>
                  ) : (
                    <NotObserved />
                  )}
                </div>
                <div className="events-row events-row--waste">
                  <span>Waste</span>
                  {ev.waste_total != null ? (
                    <>
                      <span>{ev.waste_total}</span>
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
                  <div className="events-row events-row--stockout">
                    <span>Stockout (missed)</span>
                    <span>{missed}</span>
                  </div>
                ) : null}
                {obsMask.pack_date ? (
                  <div className="events-row events-row--pack-date">
                    <span>Pack date</span>
                    {ev.pack_date_days != null ? (
                      <span>{ev.pack_date_days} days</span>
                    ) : (
                      <NotObserved />
                    )}
                  </div>
                ) : null}
                {obsMask.age_at_receipt ? (
                  <div className="events-row events-row--age-receipt">
                    <span>Age at receipt</span>
                    {ev.age_at_receipt != null ? (
                      <span>{ev.age_at_receipt}</span>
                    ) : (
                      <NotObserved />
                    )}
                  </div>
                ) : null}
                <div className="events-row events-row--delivery">
                  <span>Delivery</span>
                  <span>{ev.arrivals}</span>
                  {ev.lot_ids ? (
                    <span className="events-lots">Lots {ev.lot_ids.join(", ")}</span>
                  ) : null}
                </div>
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
