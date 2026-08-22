/**
 * Events pane — last 5 days with Delivered | Sold | Spoiled columns (T-148 layout v6).
 */
import { maskFor, maskFromChannels, type MaskedObsWire } from "../obsMask";
import type { ScheduleWire } from "../engine/types";
import type { ObsChannels } from "../types";

export type EventsPaneProps = {
  vm: {
    episode_day: number;
    config: { obs_scenario: string; obs_channels?: ObsChannels };
  };
  schedule: ScheduleWire | null;
  events: MaskedObsWire[];
  loading?: boolean;
};

const SUNDAY0_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] as const;

/** monday0 weekday for simulation day index (day 1 = epoch Monday). */
function monday0Weekday(day: number): number {
  return ((day - 1) % 7 + 7) % 7;
}

/** Sunday-first label for display chips. */
function sunday0Label(day: number): string {
  const mon0 = monday0Weekday(day);
  const sun0 = (mon0 + 1) % 7;
  return SUNDAY0_LABELS[sun0] ?? "";
}

function formatEpisodeDate(day: number, epoch: string): string {
  const base = new Date(`${epoch}T00:00:00`);
  base.setDate(base.getDate() + day - 1);
  return base.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function isDeliveryDay(day: number, schedule: ScheduleWire): boolean {
  return schedule.delivery_weekdays.includes(monday0Weekday(day));
}

function isOrderDay(day: number, schedule: ScheduleWire): boolean {
  return schedule.order_weekdays.includes(monday0Weekday(day));
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
  return (
    <div className="events-col" data-testid={`events-col-${title.toLowerCase()}`}>
      <h4 className="events-col-title">{title}</h4>
      <table className="events-table">
        <tbody>
          {notObserved ? (
            <tr>
              <td colSpan={2} className="events-not-observed">
                Not observed at this rung
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

export function EventsPane({ vm, schedule, events, loading }: EventsPaneProps) {
  if (loading) {
    return (
      <section className="events-pane panel" aria-label="Events" data-loading>
        <p>Loading events…</p>
      </section>
    );
  }

  const obsMask = vm.config.obs_channels
    ? maskFromChannels(vm.config.obs_channels)
    : maskFor(vm.config.obs_scenario);

  const windowStart = Math.max(1, vm.episode_day - 4);
  const windowEnd = vm.episode_day;
  const windowDays = Array.from(
    { length: windowEnd - windowStart + 1 },
    (_, i) => windowStart + i,
  );

  const eventByDay = new Map(events.map((ev) => [ev.day ?? 0, ev]));

  return (
    <section className="events-pane panel" aria-label="Events">
      <div className="panel-head">
        <h2>Events</h2>
        <span className="panel-note">Last 5 days</span>
      </div>
      <div className="events-list">
        {windowDays.map((day, index) => {
          const ev = eventByDay.get(day);
          const isToday = day === vm.episode_day;
          const epoch = schedule?.epoch ?? "2024-01-01";
          const deliveryChip = schedule && isDeliveryDay(day, schedule);
          const orderChip = schedule && isOrderDay(day, schedule);

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
              ? ev.arrival_lot_ids.map((id) => ({
                  label: `Lot ${id}`,
                  qty: 1,
                }))
              : [];

          return (
            <article
              key={day}
              className={`events-day-card${isToday ? " events-day-card--today" : ""}`}
              data-day={day}
            >
              {index > 0 ? <hr className="events-day-divider" /> : null}
              <header className="events-day-header">
                <h3 className="events-day-heading">
                  {formatEpisodeDate(day, epoch)}
                  <span className="events-day-sub">
                    Day {day} · {sunday0Label(day)}
                  </span>
                </h3>
                <div className="events-day-chips">
                  {deliveryChip ? (
                    <span className="events-chip events-chip--delivery">Delivery</span>
                  ) : null}
                  {orderChip ? (
                    <span className="events-chip events-chip--order">Order</span>
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
                  Pack date {ev.pack_date_days} days
                </p>
              ) : null}

            </article>
          );
        })}
      </div>
    </section>
  );
}
