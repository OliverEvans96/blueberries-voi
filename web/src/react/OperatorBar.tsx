import type { ViewModel } from "../types";

/**
 * OperatorBar — the primary "you are in control" action zone (T-127 layout v2).
 *
 * Split out of DecisionRail so the order-quantity slider and
 * Advance / Autopilot / Reset buttons can live in a compact, full-width bar
 * right under the header — visible without scrolling — instead of being
 * buried at the bottom of the tall third operations-row column.
 */
export type OperatorBarProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config">;
  catchingUp?: boolean;
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
}: OperatorBarProps) {
  const atEnd = vm.episode_day >= vm.window_days;

  return (
    <section className="operator-bar panel" aria-label="Run controls">
      <div className="operator-bar-inner">
        <h2 className="decision-rail-heading operator-bar-heading">Run</h2>
        <label className="field operator-bar-field">
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
            disabled={autopilotRunning || atEnd}
            onClick={onAdvance}
          >
            Advance
          </button>
          <button
            type="button"
            className="btn-autopilot"
            disabled={autopilotRunning || atEnd}
            onClick={onAutopilotPlay}
          >
            Autopilot Play
          </button>
          <button
            type="button"
            className="btn-autopilot"
            disabled={!autopilotRunning}
            onClick={onAutopilotPause}
          >
            Autopilot Pause
          </button>
          <button type="button" className="btn-reset" id="btn-reset" onClick={onReset}>
            Reset
          </button>
        </div>
      </div>
    </section>
  );
}
