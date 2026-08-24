import { useEffect, useRef, useState } from "react";
import type { QForecastEntry } from "../charts/tradeoffForecast";
import {
  nearestForecast,
  renderTradeoffCurve,
  renderTradeoffHistogram,
} from "../charts/tradeoffForecast";
import { scenarioTitle } from "../controls";
import { channelsForPreset } from "../obsMask";
import type { ObsChannels, ScenarioId, ViewModel } from "../types";

const CODE_OPTIONS: ObsChannels["code_type"][] = ["upc", "gsin"];
const HISTORY_OPTIONS: ObsChannels["delivery_history"][] = [
  "none",
  "pack_date",
  "temperature_history",
];

const PRESET_IDS: ScenarioId[] = ["P0", "P1", "F1", "F2a", "F2", "F3"];

const CODE_LABEL: Record<ObsChannels["code_type"], string> = {
  upc: "UPC",
  gsin: "GSIN (include lot #)",
};

const HISTORY_LABEL: Record<ObsChannels["delivery_history"], string> = {
  none: "None",
  pack_date: "Pack date",
  temperature_history: "Temperature history",
};

export type TradeoffTab = "curve" | "histogram";

export type SecondaryChromeProps = {
  vm: Pick<ViewModel, "episode_day" | "window_days" | "config">;
  showTruth: boolean;
  catchingUp?: boolean;
  onSetObsChannels: (channels: ObsChannels) => void;
  onSetObsPreset: (id: ScenarioId) => void;
  onShowTruthChange: (show: boolean) => void;
  orderQty: number;
  tradeoffForecasts?: QForecastEntry[];
};

function channelsEqual(a: ObsChannels, b: ObsChannels): boolean {
  return (
    a.code_type === b.code_type &&
    a.scan_waste === b.scan_waste &&
    a.delivery_history === b.delivery_history
  );
}

function activePreset(channels: ObsChannels): ScenarioId | null {
  for (const id of PRESET_IDS) {
    if (channelsEqual(channels, channelsForPreset(id))) return id;
  }
  return null;
}

export function SecondaryChrome({
  showTruth,
  onSetObsChannels,
  onSetObsPreset,
  onShowTruthChange,
  vm,
  orderQty,
  catchingUp = false,
  tradeoffForecasts = [],
}: SecondaryChromeProps) {
  const [activeTab, setActiveTab] = useState<TradeoffTab>("curve");
  const curveHostRef = useRef<HTMLDivElement>(null);
  const histHostRef = useRef<HTMLDivElement>(null);

  const channels =
    vm.config.obs_channels ?? channelsForPreset(vm.config.obs_scenario);
  const preset = activePreset(channels);

  const setChannel = (partial: Partial<ObsChannels>) => {
    onSetObsChannels({ ...channels, ...partial });
  };

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
        <section
          className="secondary-chrome-obs"
          data-testid="obs-channels"
        >
          <span className="field-label">Observation channels</span>

          <div className="obs-channel-group" role="group" aria-label="Code type">
            <span className="obs-channel-label">Code type</span>
            <div className="chip-row">
              {CODE_OPTIONS.map((code_type) => (
                <button
                  key={code_type}
                  type="button"
                  className={`obs-chip${channels.code_type === code_type ? " is-active" : ""}`}
                  data-obs-code-type={code_type}
                  disabled={catchingUp}
                  onClick={() => setChannel({ code_type })}
                >
                  {CODE_LABEL[code_type]}
                </button>
              ))}
            </div>
          </div>

          <div className="obs-channel-group" role="group" aria-label="Scan waste">
            <span className="obs-channel-label">Scan waste</span>
            <button
              type="button"
              className={`obs-chip${channels.scan_waste ? " is-active" : ""}`}
              data-obs-scan-waste={String(channels.scan_waste)}
              disabled={catchingUp}
              onClick={() => setChannel({ scan_waste: !channels.scan_waste })}
            >
              {channels.scan_waste ? "On" : "Off"}
            </button>
          </div>

          <div
            className="obs-channel-group"
            role="group"
            aria-label="Delivery history"
          >
            <span className="obs-channel-label">Delivery history</span>
            <div className="chip-row">
              {HISTORY_OPTIONS.map((delivery_history) => (
                <button
                  key={delivery_history}
                  type="button"
                  className={`obs-chip${channels.delivery_history === delivery_history ? " is-active" : ""}`}
                  data-obs-delivery-history={delivery_history}
                  disabled={catchingUp}
                  onClick={() => setChannel({ delivery_history })}
                >
                  {HISTORY_LABEL[delivery_history]}
                </button>
              ))}
            </div>
          </div>

          <div className="obs-preset-row">
            <label className="obs-preset-label" htmlFor="obs-preset-select">
              Preset
            </label>
            <select
              id="obs-preset-select"
              className="obs-preset-select"
              value={preset ?? ""}
              disabled={catchingUp}
              onChange={(e) => {
                const id = e.target.value as ScenarioId;
                if (id) onSetObsPreset(id);
              }}
            >
              <option value="" disabled={preset !== null}>
                Custom
              </option>
              {PRESET_IDS.map((id) => (
                <option key={id} value={id}>
                  {id} — {scenarioTitle(id)}
                </option>
              ))}
            </select>
          </div>

          <p
            className="obs-catchup-progress"
            id="obs-catchup-progress"
            hidden={!catchingUp}
          >
            Catch-up in progress…
          </p>
        </section>

        <div className="secondary-chrome-truth">
          <div className="obs-truth-copy">
            <span className="truth-toggle-label">Omniscience</span>
            <span className="truth-toggle-hint">
              Visualize unobserved ground-truth
            </span>
          </div>
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
