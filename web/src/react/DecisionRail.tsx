import type { SectionId } from "../sections";
import type { ScenarioId, ViewModel } from "../types";
import { SCENARIO_COPY, OBS_LADDER_IDS } from "../controls";

const LADDER = OBS_LADDER_IDS;

export type DecisionRailProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config" | "pnl_totals">;
  showTruth: boolean;
  catchingUp?: boolean;
  onAdvance: () => void;
  onReset: () => void;
  onAutopilotPlay: () => void;
  onAutopilotPause: () => void;
  onSetObsScenario: (id: ScenarioId) => void;
  onShowTruthChange: (show: boolean) => void;
  orderQty: number;
  onOrderChange: (qty: number) => void;
  activeSection: SectionId;
  autopilotRunning?: boolean;
};

function formatMoney(n: number): string {
  const sign = n < 0 ? "−" : "";
  return `${sign}$${Math.abs(n).toFixed(0)}`;
}

export function DecisionRail({
  vm,
  showTruth,
  onAdvance,
  onReset,
  onAutopilotPlay,
  onAutopilotPause,
  onSetObsScenario,
  onShowTruthChange,
  orderQty,
  onOrderChange,
  autopilotRunning = false,
  catchingUp = false,
}: DecisionRailProps) {
  const atEnd = vm.episode_day >= vm.window_days;
  const t = vm.pnl_totals;

  return (
    <aside className="decision-rail sticky">
      <section className="decision-rail-run">
        <h2 className="decision-rail-heading">Run</h2>
        <label className="field">
          <span className="field-label">Order quantity</span>
          <input
            type="range"
            min={0}
            max={160}
            step={vm.config.case_size}
            value={orderQty}
            onChange={(e) => onOrderChange(Number(e.currentTarget.value))}
          />
        </label>
        <div className="btn-row">
          <button
            type="button"
            className="btn-advance"
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
          <button type="button" className="btn-reset" onClick={onReset}>
            Reset
          </button>
        </div>
      </section>

      <section className="decision-rail-ladder">
        <span className="field-label">Observation scenario</span>
        <div className="chip-row" role="group" aria-label="Observation scenario">
          {LADDER.map((id) => (
            <button
              key={id}
              type="button"
              className={`obs-chip${vm.config.obs_scenario === id ? " is-active" : ""}`}
              data-obs={id}
              title={SCENARIO_COPY[id].title}
              disabled={catchingUp}
              onClick={() => onSetObsScenario(id)}
            >
              {id}
            </button>
          ))}
        </div>
        <p
          className="obs-catchup-progress"
          id="obs-catchup-progress"
          hidden={!catchingUp}
        >
          Catch-up in progress…
        </p>
      </section>

      <section className="decision-rail-truth">
        <span className="truth-toggle-label">Sim truth overlay</span>
        <button
          type="button"
          className={`truth-toggle${showTruth ? " truth-toggle--on" : ""}`}
          role="switch"
          aria-checked={showTruth}
          aria-label="Show true state"
          onClick={() => onShowTruthChange(!showTruth)}
        >
          <span className="truth-toggle-track" aria-hidden="true">
            <span className="truth-toggle-thumb" />
          </span>
          <span className="truth-toggle-text">{showTruth ? "On" : "Off"}</span>
        </button>
      </section>

      <section
        className="decision-rail-pnl"
        data-testid="pnl-consolidated"
        id="chart-pnl-totals"
      >
        <div className="pnl-totals">
          <div className="pnl-row">
            <span className="pnl-label">Episode revenue</span>
            <span className="pnl-value">{formatMoney(t.revenue)}</span>
          </div>
          <div className="pnl-row">
            <span className="pnl-label">Episode cost</span>
            <span className="pnl-value">{formatMoney(t.cost)}</span>
          </div>
          <div className="pnl-row pnl-row--emphasis">
            <span className="pnl-label">Episode profit</span>
            <span className="pnl-value">{formatMoney(t.profit)}</span>
          </div>
        </div>
      </section>
    </aside>
  );
}
