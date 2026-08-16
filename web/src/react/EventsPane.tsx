/**
 * Events pane — masked richest_log window (T-127 AC-events-ui).
 */
import type { MaskedObsWire } from "../obsMask";
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

function NotObserved() {
  return (
    <span className="events-not-observed">
      Not observed at this rung
    </span>
  );
}

export function EventsPane({ vm, showTruth, events, loading }: EventsPaneProps) {
  if (loading) {
    return (
      <section className="events-pane panel" aria-label="Events" data-loading>
        <p>Loading events…</p>
      </section>
    );
  }

  return (
    <section className="events-pane panel" aria-label="Events">
      <div className="panel-head">
        <h2>Events</h2>
      </div>
      {events.map((ev) => {
        const missed =
          vm.history.find((h) => h.day === ev.day)?.missed ?? 0;
        return (
          <article key={ev.day} className="events-day-card" data-day={ev.day}>
            <h3 className="events-day-heading">Day {ev.day}</h3>
            <div className="events-row events-row--pos">
              <span>POS</span>
              {ev.sales_total != null ? (
                <>
                  <span>{ev.sales_total}</span>
                  {ev.sales_by ? (
                    <span className="events-breakdown">
                      ({ev.sales_by.join(", ")})
                    </span>
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
                  {ev.waste_by ? (
                    <span className="events-breakdown">
                      ({ev.waste_by.join(", ")})
                    </span>
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
            <div className="events-row events-row--delivery">
              <span>Delivery</span>
              <span>{ev.arrivals}</span>
              {ev.lot_ids ? (
                <span className="events-lots">Lots {ev.lot_ids.join(", ")}</span>
              ) : null}
            </div>
          </article>
        );
      })}
    </section>
  );
}
