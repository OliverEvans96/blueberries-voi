import type { SectionId } from "../sections";
import type { ScenarioId, ViewModel } from "../types";
import type { QForecastEntry } from "../charts/tradeoffForecast";
import { SCENARIO_COPY, OBS_LADDER_IDS } from "../controls";
import {
  nearestForecast,
  renderTradeoffCurve,
  renderTradeoffHistogram,
} from "../charts/tradeoffForecast";

const LADDER = OBS_LADDER_IDS;

export type DecisionRailProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config">;
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
  tradeoffForecasts?: QForecastEntry[];
};

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
  tradeoffForecasts = [],
}: DecisionRailProps) {
  const atEnd = vm.episode_day >= vm.window_days;

  return (
    <aside className="decision-rail sticky">
      <section className="decision-rail-run">
        <h2 className="decision-rail-heading">Run</h2>
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
        <div className="tradeoff-charts" data-testid="tradeoff-charts">
          <div>
            <div className="chart-caption">Tradeoff curve</div>
            <div
              id="tradeoff-curve-host"
              className="tradeoff-chart-host"
              ref={(node) => {
                if (node) renderTradeoffCurve(node, tradeoffForecasts, orderQty);
              }}
            />
          </div>
          <div>
            <div className="chart-caption">Joint histogram</div>
            <div
              id="tradeoff-histogram-host"
              className="tradeoff-chart-host"
              ref={(node) => {
                if (node) {
                  renderTradeoffHistogram(
                    node,
                    nearestForecast(tradeoffForecasts, orderQty),
                  );
                }
              }}
            />
          </div>
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
    </aside>
  );
}
