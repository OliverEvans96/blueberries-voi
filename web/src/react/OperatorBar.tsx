import type { ViewModel } from "../types";

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
      <h2 className="decision-rail-heading operator-bar-heading">Run</h2>
      <label className="field">
        <span className="field-label">
          Order quantity <em>(case {vm.config.case_size})</em>
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
          Advance
        </button>
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
        <button type="button" className="btn-reset" id="btn-reset" onClick={onReset}>
          Reset
        </button>
      </div>
    </section>
  );
}
