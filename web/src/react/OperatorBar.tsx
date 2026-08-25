import type { ViewModel } from "../types";
import { InfoTip } from "./InfoTip";

/**
 * OperatorBar — the primary "you are in control" action zone (T-127 layout
 * v3). Split out of DecisionRail so the order-quantity slider and
 * Advance / Autopilot / Reset buttons can live in a compact card mounted at
 * the bottom of the Secondary pane — filling that pane's otherwise-empty
 * whitespace below its single histogram chart — instead of being buried in
 * the tall third operations-row column.
 */
export type OperatorBarProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config">;
  catchingUp?: boolean;
  advancing?: boolean;
  onAdvance: () => void;
  onReset: () => void;
  onAutopilotPlay: () => void;
  onAutopilotPause: () => void;
  orderQty: number;
  onOrderChange: (qty: number) => void;
  autopilotRunning?: boolean;
};

export function OperatorBar({
  vm,
  onAdvance,
  onReset,
  onAutopilotPlay,
  onAutopilotPause,
  orderQty,
  onOrderChange,
  autopilotRunning = false,
  advancing = false,
}: OperatorBarProps) {
  const atEnd = vm.episode_day >= vm.window_days;

  return (
    <section className="operator-bar" aria-label="Run controls">
      <span className="heading-with-tip">
        <h2 className="decision-rail-heading operator-bar-heading">Run</h2>
        <InfoTip>
          Where you set tomorrow's order and step the simulation forward one
          day at a time, or let Autopilot do it on a timer. Each day resolves
          aging, spoilage, sales, and delivery in that fixed order before the
          next day starts.
        </InfoTip>
      </span>
      <label className="field">
        <span className="field-label">
          Order quantity <em>(case {vm.config.case_size})</em>
          <InfoTip>
            How many units to order for the next delivery, snapped to the
            case pack size shown alongside it. This is the quantity Place
            Order (or Autopilot) will submit, and it lands on the shelf as a
            new lot after that day's sales have already been resolved.
          </InfoTip>
        </span>
        <div className="order-row">
          <input
            type="range"
            id="order-range"
            min={0}
            max={Math.max(160, vm.config.case_size * 20)}
            step={vm.config.case_size}
            value={orderQty}
            onInput={(e) => onOrderChange(Number(e.currentTarget.value))}
          />
          <input
            type="number"
            id="order-num"
            min={0}
            max={320}
            step={vm.config.case_size}
            value={orderQty}
            onChange={(e) => onOrderChange(Number(e.currentTarget.value))}
          />
        </div>
      </label>
      <div className="btn-row operator-bar-buttons">
        <button
          type="button"
          className="btn-advance"
          id="btn-advance"
          disabled={autopilotRunning || atEnd || advancing}
          onClick={onAdvance}
        >
          Place Order
        </button>
        <InfoTip>
          Submits the order quantity you've set and advances the simulation
          by one day: that day's aging, spoilage, sales, and delivery all
          resolve together, and the charts update to match.
        </InfoTip>
        <button
          type="button"
          id="btn-autopilot-toggle"
          className={`autopilot-toggle${autopilotRunning ? " autopilot-toggle--on" : ""}`}
          role="switch"
          aria-checked={autopilotRunning}
          aria-label="Autopilot"
          disabled={!autopilotRunning && atEnd}
          onClick={() => (autopilotRunning ? onAutopilotPause() : onAutopilotPlay())}
        >
          <span className="truth-toggle-track" aria-hidden="true">
            <span className="truth-toggle-thumb" />
          </span>
          <span className="autopilot-toggle-text">
            Autopilot: {autopilotRunning ? "On" : "Off"}
          </span>
        </button>
        <InfoTip>
          Repeats the same order-and-advance action as Place Order, on a
          repeating timer, using whichever controller policy is selected in
          the Autopilot tuning tab. It issues the same request the manual
          button does rather than running a separate in-browser
          approximation, so it behaves like the same controller the
          notebooks and CLI can call.
        </InfoTip>
        <button type="button" className="btn-reset" id="btn-reset" onClick={onReset}>
          Reset
        </button>
        <InfoTip alignEnd>
          Re-simulates the full 90-day episode from day one using the
          current parameter values, including a fresh particle-filter run.
          You need this after changing any parameter tagged Reset in the
          tuning dock, since those feed the freshness decay, demand draws,
          or arrival law that already produced the days you've seen so far.
        </InfoTip>
      </div>
    </section>
  );
}
