import type { ViewModel } from "../types";
import { HostHoverTip } from "./HostHoverTip";
import { InfoTip } from "./InfoTip";
import { ORDER_Q_SLIDER_MIN_MAX } from "./studioShellDefaults";

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
  /** WASM boot — show shell controls disabled until adapter.init settles. */
  booting?: boolean;
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
  booting = false,
  catchingUp = false,
}: OperatorBarProps) {
  const atEnd = vm.episode_day >= vm.window_days;
  const controlsDisabled = booting || catchingUp;

  return (
    <section
      className="operator-bar"
      aria-label="Run controls"
      aria-busy={booting ? "true" : undefined}
    >
      <span className="heading-with-tip">
        <h2 className="decision-rail-heading operator-bar-heading">Run</h2>
        <InfoTip>
          Set tomorrow's order and step the simulation forward a day at a
          time, or let Autopilot do it on a timer.
        </InfoTip>
      </span>
      <label className="field">
        <span className="field-label">
          Order quantity <em>(cases of {vm.config.case_size})</em>
          <InfoTip>
            Units to order for the next delivery, snapped to the case size
            shown alongside it. Submitted by Place Order or Autopilot.
          </InfoTip>
        </span>
        <div className="order-row">
          <input
            type="range"
            id="order-range"
            min={0}
            max={Math.max(ORDER_Q_SLIDER_MIN_MAX, vm.config.case_size * 20)}
            step={vm.config.case_size}
            value={orderQty}
            disabled={controlsDisabled}
            onInput={(e) => onOrderChange(Number(e.currentTarget.value))}
          />
          <input
            type="number"
            id="order-num"
            min={0}
            max={320}
            step={vm.config.case_size}
            value={orderQty}
            disabled={controlsDisabled}
            onChange={(e) => onOrderChange(Number(e.currentTarget.value))}
          />
        </div>
      </label>
      <div className="btn-row operator-bar-buttons">
        <HostHoverTip tip="Submits your order quantity and advances the simulation by one day.">
          <button
            type="button"
            className="btn-advance"
            id="btn-advance"
            disabled={autopilotRunning || atEnd || advancing || controlsDisabled}
            onClick={onAdvance}
          >
            Place Order
          </button>
        </HostHoverTip>
        <HostHoverTip tip="Repeats Place Order on a timer, using the policy selected in the Autopilot tuning tab.">
          <button
            type="button"
            id="btn-autopilot-toggle"
            className={`autopilot-toggle${autopilotRunning ? " autopilot-toggle--on" : ""}`}
            role="switch"
            aria-checked={autopilotRunning}
            aria-label="Autopilot"
            disabled={controlsDisabled || (!autopilotRunning && atEnd)}
            onClick={() => (autopilotRunning ? onAutopilotPause() : onAutopilotPlay())}
          >
            <span className="truth-toggle-track" aria-hidden="true">
              <span className="truth-toggle-thumb" />
            </span>
            <span className="autopilot-toggle-text">
              Autopilot: {autopilotRunning ? "On" : "Off"}
            </span>
          </button>
        </HostHoverTip>
        <HostHoverTip
          alignEnd
          tip="Re-simulates the full episode from day one with the current parameter values. Needed after changing any parameter tagged Reset in the tuning dock."
        >
          <button
            type="button"
            className="btn-reset"
            id="btn-reset"
            disabled={controlsDisabled}
            onClick={onReset}
          >
            Reset
          </button>
        </HostHoverTip>
      </div>
    </section>
  );
}
