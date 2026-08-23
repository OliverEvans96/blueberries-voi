import type { HoverPoint } from "../hoverLink";
import type { Day, ViewModel } from "../types";
import "../styles/dayInspector.css";

export type DayInspectorProps = {
  day: number | null;
  point: HoverPoint;
  vm: ViewModel;
};

function beliefOneLiner(vm: ViewModel): string {
  const m = vm.belief.f_marginal;
  if (m && m.length > 0) {
    const peak = m.indexOf(Math.max(...m));
    return `Belief peaks near freshness bin ${peak}.`;
  }
  return "Belief updating from observed sales and shrink.";
}

export function DayInspector({ day, point, vm }: DayInspectorProps) {
  if (day == null || point == null) {
    return null;
  }

  const tooltipStyle = {
    left: `${point.clientX + 12}px`,
    top: `${point.clientY + 12}px`,
  };

  const row: Day | undefined = vm.history.find((d) => d.day === day);
  if (!row) {
    return (
      <div
        className="day-inspector day-inspector-tooltip"
        role="status"
        data-day={day}
        style={tooltipStyle}
      >
        Day {day} — no history yet.
      </div>
    );
  }

  return (
    <div
      className="day-inspector day-inspector-tooltip"
      role="status"
      data-day={day}
      style={tooltipStyle}
    >
      <strong>Day {day}</strong>
      <ul className="day-inspector-stats">
        <li>Sales: {row.sales_total}</li>
        <li>Waste: {row.waste_total}</li>
        <li>Stockout: {row.stockout}</li>
        <li>Order qty: {row.order_qty}</li>
      </ul>
      <p className="day-inspector-belief">{beliefOneLiner(vm)}</p>
    </div>
  );
}
