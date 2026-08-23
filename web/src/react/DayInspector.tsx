import type { HoverPoint } from "../hoverLink";
import type { Day, ViewModel } from "../types";
import "../styles/dayInspector.css";

export type DayInspectorProps = {
  day: number | null;
  point: HoverPoint;
  vm: ViewModel;
};

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
        className="day-inspector-tooltip"
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
      className="day-inspector-tooltip"
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
    </div>
  );
}
