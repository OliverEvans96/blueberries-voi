/**
 * Events pane — last 5 days with Delivered | Sold | Spoiled columns (T-148 layout v6).
 */
import { useLayoutEffect, useRef } from "react";
import {
  formatTempC,
  lotColor,
  renderDeliveryTempMultiLot,
  tempSummaryFromTrace,
  tracesFromEvent,
} from "../charts/deliveryTempChart";
import { maskFor, maskFromChannels, type MaskedObsWire } from "../obsMask";
import { weekdayLabel, weekdayMonday0 } from "../calendar/nextOrderAdvance";
import type { ScheduleWire } from "../engine/types";
import type { ObsChannels } from "../types";
import { InfoTip } from "./InfoTip";

export type EventsPaneProps = {
  vm: {
    episode_day: number;
    config: { obs_scenario: string; obs_channels?: ObsChannels };
  };
  schedule: ScheduleWire | null;
  events: MaskedObsWire[];
  /** True only when there is no event data to show yet. */
  loading?: boolean;
  /** Background refresh while keeping stale cards visible. */
  refreshing?: boolean;
};

// Delegate to the same epoch-anchored weekday helper the studio's own
// order-day advance logic (`buildStepNOrders` / `nextOrderDayFromSchedule`
// in calendar/nextOrderAdvance.ts) uses — a local `(day - 1) % 7`
// reimplementation here previously disagreed with that authoritative
// convention by exactly one day, so these badges never matched the days
// real deliveries/orders actually landed on (T-151 bugfix).
function isDeliveryDay(day: number, schedule: ScheduleWire): boolean {
  return schedule.delivery_weekdays.includes(weekdayMonday0(day, schedule));
}

function isOrderDay(day: number, schedule: ScheduleWire): boolean {
  return schedule.order_weekdays.includes(weekdayMonday0(day, schedule));
}

type LotRow = { label: string; qty: number };

function lotRows(
  values: number[] | null | undefined,
  lotIds: number[] | null | undefined,
): LotRow[] {
  if (!values?.length || !lotIds?.length) return [];
  const rows: LotRow[] = [];
  const n = Math.min(values.length, lotIds.length);
  for (let i = 0; i < n; i++) {
    const qty = values[i] ?? 0;
    if (qty <= 0) continue;
    rows.push({
      label: `Lot ${lotIds[i]}`,
      qty,
    });
  }
  return rows;
}

function arrivalLotRows(
  arrivals: number,
  lotIds: number[] | null | undefined,
  arrivalsBy: number[] | null | undefined,
): LotRow[] {
  if (!lotIds?.length) return [];
  if (arrivalsBy?.length) {
    return lotRows(arrivalsBy, lotIds);
  }
  if (lotIds.length === 1) {
    return [{ label: `Lot ${lotIds[0]}`, qty: arrivals }];
  }
  const perLot = Math.floor(arrivals / lotIds.length);
  const remainder = arrivals - perLot * lotIds.length;
  return lotIds.map((id, i) => ({
    label: `Lot ${id}`,
    qty: perLot + (i === lotIds.length - 1 ? remainder : 0),
  }));
}

const EVENTS_COLUMN_TIPS: Record<string, string> = {
  Delivered:
    "Units that arrived on the shelf that day. Broken out by lot underneath the total when lot IDs are observed, since that lot detail depends on the current observation channels.",
  Sold: "Units actually sold that day, drawn from whatever was left after spoilage. This can fall short of that day's demand once the shelf runs out of unspoiled units to sell.",
  Spoiled:
    "Units whose freshness reached zero that day and were pulled off the shelf as waste before being counted here, never reaching a customer.",
};

function EventsTable({
  title,
  total,
  lotRows: lots,
  notObserved,
}: {
  title: string;
  total: number | null;
  lotRows: LotRow[];
  notObserved?: boolean;
}) {
  const tip = EVENTS_COLUMN_TIPS[title];
  return (
    <div className="events-col" data-testid={`events-col-${title.toLowerCase()}`}>
      <span className="heading-with-tip">
        <h4 className="events-col-title">{title}</h4>
        {tip ? <InfoTip>{tip}</InfoTip> : null}
      </span>
      <table className="events-table">
        <tbody>
          {notObserved ? (
            <tr>
              <td colSpan={2} className="events-not-observed">
                Not observed
              </td>
            </tr>
          ) : (
            <>
              <tr className="events-table-total">
                <th scope="row">Total</th>
                <td>{total ?? 0}</td>
              </tr>
              {lots.map((row) => (
                <tr key={row.label} className="events-table-lot">
                  <th scope="row">{row.label}</th>
                  <td>{row.qty}</td>
                </tr>
              ))}
            </>
          )}
        </tbody>
      </table>
    </div>
  );
}

function DeliveryTempChart({
  ev,
}: {
  ev: MaskedObsWire;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const traces = tracesFromEvent(ev);

  useLayoutEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    renderDeliveryTempMultiLot(host, traces);
  }, [ev]);

  return (
    <section className="events-temp-history" aria-label="Temperature history">
      <span className="heading-with-tip">
        <h4 className="events-temp-heading">Temperature history</h4>
        <InfoTip>
          The logged temperature trace from the delivery truck for that day's
          arriving lot(s) — only available at the highest observation rung,
          where the supplier reports a full temperature-history trace rather
          than just a pack date or nothing at all.
        </InfoTip>
      </span>
      <div
        className="events-temp-summaries"
        data-testid="events-temp-summaries"
      >
        {traces.map((trace, index) => {
          const summary = tempSummaryFromTrace(trace);
          if (!summary) return null;
          return (
            <div
              key={trace.lotId}
              className="events-temp-summary-line"
              data-lot={trace.lotId}
            >
              <span className="events-temp-item">
                <span
                  className="events-temp-lot"
                  style={{ color: lotColor(index) }}
                >
                  Lot {trace.lotId}
                </span>
              </span>
              <span className="events-temp-sep" aria-hidden="true">
                ·
              </span>
              <span className="events-temp-item">
                <span className="events-temp-label">min</span>
                <span className="events-temp-value">
                  {formatTempC(summary.min)}
                </span>
              </span>
              <span className="events-temp-sep" aria-hidden="true">
                ·
              </span>
              <span className="events-temp-item">
                <span className="events-temp-label">max</span>
                <span className="events-temp-value">
                  {formatTempC(summary.max)}
                </span>
              </span>
              <span className="events-temp-sep" aria-hidden="true">
                ·
              </span>
              <span className="events-temp-item">
                <span className="events-temp-label">mean</span>
                <span className="events-temp-value">
                  {formatTempC(summary.mean)}
                </span>
              </span>
              <span className="events-temp-sep" aria-hidden="true">
                ·
              </span>
              <span className="events-temp-item">
                <span className="events-temp-label">std</span>
                <span className="events-temp-value">
                  {formatTempC(summary.std)}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <div
        className="events-temp-chart-host"
        data-day={ev.day}
        ref={hostRef}
      />
    </section>
  );
}

export function EventsPane({
  vm,
  schedule,
  events,
  loading,
  refreshing,
}: EventsPaneProps) {
  const obsMask = vm.config.obs_channels
    ? maskFromChannels(vm.config.obs_channels)
    : maskFor(vm.config.obs_scenario);

  const windowStart = Math.max(1, vm.episode_day - 5);
  const windowEnd = vm.episode_day - 1;
  const windowDays = Array.from(
    { length: Math.max(0, windowEnd - windowStart + 1) },
    (_, i) => windowStart + i,
  ).sort((a, b) => b - a);

  const eventByDay = new Map(events.map((ev) => [ev.day ?? 0, ev]));
  const showInitialLoading = loading && events.length === 0;

  return (
    <section
      className="events-pane panel"
      aria-label="Events"
      data-loading={showInitialLoading ? "true" : undefined}
      data-refreshing={refreshing ? "true" : undefined}
    >
      <div className="panel-head">
        <span className="heading-with-tip">
          <h2>Events</h2>
          <InfoTip>
            A rolling log of the last several completed days' deliveries,
            sales, and spoilage, in the fixed order each day actually
            resolves them: aging, then spoilage, then sales, then delivery.
            Each day's numbers are masked down to whatever the current
            observation channels actually reveal, so a column can show
            "Not observed" even when something happened in the ground truth.
          </InfoTip>
        </span>
        <span className="panel-note">
          Last 5 days
          {showInitialLoading ? (
            <span className="events-refresh-indicator" aria-live="polite">
              Loading events…
            </span>
          ) : null}
          {!showInitialLoading && refreshing ? (
            <span className="events-refresh-indicator" aria-live="polite">
              Updating…
            </span>
          ) : null}
        </span>
      </div>
      <div className="events-list">
        {!showInitialLoading && windowDays.length === 0 ? (
          <p className="events-empty-note">No completed days yet.</p>
        ) : null}
        {windowDays.map((day, index) => {
          const ev = eventByDay.get(day);
          const deliveryDay = schedule ? isDeliveryDay(day, schedule) : false;
          const orderDay = schedule ? isOrderDay(day, schedule) : false;

          const deliveredTotal = ev?.arrivals ?? 0;
          const soldTotal = ev?.sales_total;
          const spoiledTotal = ev?.waste_total;

          const soldLots = obsMask.sales_by_lot
            ? lotRows(ev?.sales_by, ev?.lot_ids)
            : [];
          const spoiledLots = obsMask.waste_by_lot
            ? lotRows(ev?.waste_by, ev?.lot_ids)
            : [];
          const deliveredLots =
            obsMask.arrival_lot_ids && ev?.arrival_lot_ids?.length
              ? arrivalLotRows(
                  deliveredTotal,
                  ev.arrival_lot_ids,
                  ev.arrivals_by ?? null,
                )
              : [];

          // Keyed on an actual delivery with temp data, not the schedule's
          // cosmetic "delivery day" calendar badge (`deliveryDay`) — those
          // can desync (e.g. mid-episode schedule edits), which previously
          // made this chart dead code (T-151 bugfix).
          const showTempChart =
            obsMask.temperature_history &&
            deliveredTotal > 0 &&
            Boolean(
              ev?.temp_traces_by_lot?.length ||
                (ev?.temp_times_d?.length && ev?.temp_temps_c?.length),
            );

          return (
            <article
              key={day}
              className="events-day-card"
              data-day={day}
            >
              {index > 0 ? <hr className="events-day-divider" /> : null}
              <header className="events-day-header">
                <h3 className="events-day-heading">
                  {schedule ? (
                    <>
                      <span className="events-day-weekday">
                        {weekdayLabel(day, schedule)}
                      </span>
                      {" "}
                      <span className="events-day-index">(day {day})</span>
                    </>
                  ) : (
                    <span className="events-day-index">(day {day})</span>
                  )}
                </h3>
                <div className="events-day-markers">
                  {deliveryDay ? (
                    <span className="events-day-marker events-day-marker--delivery">
                      delivery day
                    </span>
                  ) : null}
                  {orderDay ? (
                    <span className="events-day-marker events-day-marker--order">
                      order day
                    </span>
                  ) : null}
                </div>
              </header>

              <div className="events-columns" data-testid="events-columns">
                <EventsTable
                  title="Delivered"
                  total={deliveredTotal}
                  lotRows={deliveredLots}
                  notObserved={!ev && deliveredTotal === 0}
                />
                <EventsTable
                  title="Sold"
                  total={soldTotal ?? null}
                  lotRows={soldLots}
                  notObserved={soldTotal == null}
                />
                <EventsTable
                  title="Spoiled"
                  total={spoiledTotal ?? null}
                  lotRows={spoiledLots}
                  notObserved={spoiledTotal == null}
                />
              </div>

              {ev && obsMask.pack_date && ev.pack_date_days != null ? (
                <p className="events-pack-date">
                  Packed {ev.pack_date_days}{" "}
                  {ev.pack_date_days === 1 ? "day" : "days"} before arrival
                </p>
              ) : null}

              {ev && showTempChart ? <DeliveryTempChart ev={ev} /> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
