import type { Day, ViewModel } from "../types";

export type DayInspectorProps = {
  day: number | null;
  vm: ViewModel;
};

function beliefOneLiner(vm: ViewModel): string {
  const m = vm.belief.age_marginal;
  if (m && m.length > 0) {
    const peak = m.indexOf(Math.max(...m));
    return `Belief peaks near age bin ${peak}.`;
  }
  return "Belief updating from observed sales and shrink.";
}

export function DayInspector({ day, vm }: DayInspectorProps) {
  if (day == null) {
    return (
      <div className="day-inspector day-inspector--empty" role="status">
        Hover a day in the store timeline for details.
      </div>
    );
  }

  const row: Day | undefined = vm.history.find((d) => d.day === day);
  if (!row) {
    return (
      <div className="day-inspector" role="status">
        Day {day} — no history yet.
      </div>
    );
  }

  return (
    <div className="day-inspector" role="status" data-day={day}>
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
