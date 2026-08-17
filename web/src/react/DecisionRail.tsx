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
  onSetObsScenario: (id: ScenarioId) => void;
  onShowTruthChange: (show: boolean) => void;
  orderQty: number;
  activeSection: SectionId;
  tradeoffForecasts?: QForecastEntry[];
};

export function DecisionRail({
  showTruth,
  onSetObsScenario,
  onShowTruthChange,
  vm,
  orderQty,
  catchingUp = false,
  tradeoffForecasts = [],
}: DecisionRailProps) {
  return (
    <aside className="decision-rail sticky">
      <section className="decision-rail-tradeoffs">
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
