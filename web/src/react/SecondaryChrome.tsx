import { useEffect, useRef, useState } from "react";
import type { QForecastEntry } from "../charts/tradeoffForecast";
import {
  nearestForecast,
  renderTradeoffCurve,
  renderTradeoffHistogram,
} from "../charts/tradeoffForecast";
import { SCENARIO_COPY } from "../controls";
import { channelsForPreset } from "../obsMask";
import type { ObsChannels, ScenarioId, ViewModel } from "../types";

const POS_OPTIONS: ObsChannels["pos"][] = ["upc_only", "lot_id"];
const WASTE_OPTIONS: ObsChannels["waste"][] = ["none", "daily_counts", "lot_id"];
const DELIVERY_OPTIONS: ObsChannels["deliveries"][] = [
  "quantity_only",
  "pack_date_per_lot",
];

const PRESET_IDS: ScenarioId[] = ["P0", "P1", "F1", "F1s", "F2a", "F2"];

const POS_LABEL: Record<ObsChannels["pos"], string> = {
  upc_only: "UPC only",
  lot_id: "Lot ID",
};

const WASTE_LABEL: Record<ObsChannels["waste"], string> = {
  none: "None",
  daily_counts: "Daily counts",
  lot_id: "Lot ID",
};

const DELIVERY_LABEL: Record<ObsChannels["deliveries"], string> = {
  quantity_only: "Quantity only",
  pack_date_per_lot: "Pack date per lot",
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
    a.pos === b.pos && a.waste === b.waste && a.deliveries === b.deliveries
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

          <div className="obs-channel-group" role="group" aria-label="POS channel">
            <span className="obs-channel-label">POS</span>
            <div className="chip-row">
              {POS_OPTIONS.map((pos) => (
                <button
                  key={pos}
                  type="button"
                  className={`obs-chip${channels.pos === pos ? " is-active" : ""}`}
                  data-obs-pos={pos}
                  disabled={catchingUp}
                  onClick={() => setChannel({ pos })}
                >
                  {POS_LABEL[pos]}
                </button>
              ))}
            </div>
          </div>

          <div className="obs-channel-group" role="group" aria-label="Waste channel">
            <span className="obs-channel-label">Waste</span>
            <div className="chip-row">
              {WASTE_OPTIONS.map((waste) => (
                <button
                  key={waste}
                  type="button"
                  className={`obs-chip${channels.waste === waste ? " is-active" : ""}`}
                  data-obs-waste={waste}
                  disabled={catchingUp}
                  onClick={() => setChannel({ waste })}
                >
                  {WASTE_LABEL[waste]}
                </button>
              ))}
            </div>
          </div>

          <div
            className="obs-channel-group"
            role="group"
            aria-label="Deliveries channel"
          >
            <span className="obs-channel-label">Deliveries</span>
            <div className="chip-row">
              {DELIVERY_OPTIONS.map((deliveries) => (
                <button
                  key={deliveries}
                  type="button"
                  className={`obs-chip${channels.deliveries === deliveries ? " is-active" : ""}`}
                  data-obs-deliveries={deliveries}
                  disabled={catchingUp}
                  onClick={() => setChannel({ deliveries })}
                >
                  {DELIVERY_LABEL[deliveries]}
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
                  {id} — {SCENARIO_COPY[id].title}
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
