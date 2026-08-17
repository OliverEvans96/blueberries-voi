import { useEffect, useRef, useState } from "react";
import type { QForecastEntry } from "../charts/tradeoffForecast";
import {
  nearestForecast,
  renderTradeoffCurve,
  renderTradeoffHistogram,
} from "../charts/tradeoffForecast";
import { OBS_LADDER_IDS, SCENARIO_COPY } from "../controls";
import type { ScenarioId, ViewModel } from "../types";

export type TradeoffTab = "curve" | "histogram";

export type SecondaryChromeProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config">;
  showTruth: boolean;
  catchingUp?: boolean;
  onSetObsScenario: (id: ScenarioId) => void;
  onShowTruthChange: (show: boolean) => void;
  orderQty: number;
  tradeoffForecasts?: QForecastEntry[];
};

export function SecondaryChrome({
  showTruth,
  onSetObsScenario,
  onShowTruthChange,
  vm,
  orderQty,
  catchingUp = false,
  tradeoffForecasts = [],
}: SecondaryChromeProps) {
  const [activeTab, setActiveTab] = useState<TradeoffTab>("curve");
  const curveHostRef = useRef<HTMLDivElement>(null);
  const histHostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = curveHostRef.current;
    if (!host || activeTab !== "curve") return;
    renderTradeoffCurve(host, tradeoffForecasts, orderQty);
  }, [tradeoffForecasts, orderQty, activeTab]);

  useEffect(() => {
    const host = histHostRef.current;
    if (!host || activeTab !== "histogram") return;
    renderTradeoffHistogram(
      host,
      nearestForecast(tradeoffForecasts, orderQty),
      orderQty,
    );
  }, [tradeoffForecasts, orderQty, activeTab]);

  return (
    <div className="secondary-chrome" data-testid="secondary-chrome">
      <div className="secondary-chrome-controls">
        <div className="secondary-chrome-obs">
          <span className="field-label">Observation scenario</span>
          <div
            className="chip-row"
            role="group"
            aria-label="Observation scenario"
          >
            {OBS_LADDER_IDS.map((id) => (
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
        </div>
        <div className="secondary-chrome-truth">
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
        </div>
      </div>

      <div className="secondary-chrome-tradeoff">
        <div
          className="tradeoff-tab-strip"
          role="tablist"
          aria-label="Tradeoff view"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "curve"}
            className={activeTab === "curve" ? "is-active" : ""}
            onClick={() => setActiveTab("curve")}
          >
            Curve
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "histogram"}
            className={activeTab === "histogram" ? "is-active" : ""}
            onClick={() => setActiveTab("histogram")}
          >
            Histogram
          </button>
        </div>
        <div className="tradeoff-chart-panel">
          {activeTab === "curve" ? (
            <div>
              <div className="chart-caption">Tradeoff curve</div>
              <div
                id="tradeoff-curve-host"
                ref={curveHostRef}
                className="tradeoff-chart-host tradeoff-curve"
                data-testid="tradeoff-curve"
              />
            </div>
          ) : (
            <div>
              <div className="chart-caption">Joint histogram</div>
              <div
                id="tradeoff-histogram-host"
                ref={histHostRef}
                className="tradeoff-chart-host tradeoff-histogram"
                data-testid="tradeoff-histogram"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
