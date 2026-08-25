import "../styles/obsControls.css";
import type { ObsChannels, ViewModel } from "../types";
import { InfoTip } from "./InfoTip";

const CODE_OPTIONS: ObsChannels["code_type"][] = ["upc", "gsin"];
const HISTORY_OPTIONS: ObsChannels["delivery_history"][] = [
  "none",
  "pack_date",
  "temperature_history",
];

const CODE_LABEL: Record<ObsChannels["code_type"], string> = {
  upc: "UPC",
  gsin: "GSIN (include lot #)",
};

const HISTORY_LABEL: Record<ObsChannels["delivery_history"], string> = {
  none: "None",
  pack_date: "Pack date",
  temperature_history: "Temperature history",
};

export type ObsControlsPaneProps = {
  vm: Pick<ViewModel, "config">;
  showTruth: boolean;
  catchingUp?: boolean;
  onSetObsChannels: (channels: ObsChannels) => void;
  onSetObsPreset: (id: import("../types").ScenarioId) => void;
  onShowTruthChange: (show: boolean) => void;
};

export function ObsControlsPane({
  showTruth,
  onSetObsChannels,
  onShowTruthChange,
  vm,
  catchingUp = false,
}: ObsControlsPaneProps) {
  const channels = vm.config.obs_channels;

  const setChannel = (partial: Partial<ObsChannels>) => {
    onSetObsChannels({ ...channels, ...partial });
  };

  return (
    <section
      className="obs-controls-pane panel"
      data-testid="obs-controls-pane"
      aria-label="Observation controls"
    >
      <div className="panel-head obs-panel-head">
        <span className="heading-with-tip">
          <h2>Observation</h2>
          <InfoTip>
            These toggles set what the store's inventory system can actually
            see each day, not the hidden ground-truth state the simulator
            tracks internally. Every belief is built from three independent
            switches — the code scanned at checkout, whether waste gets
            scanned, and what the supplier reports about a shipment's journey
            — and no combination of them ever reports freshness directly.
          </InfoTip>
        </span>
        <p className="obs-panel-lead">What the filter can see each day</p>
      </div>

      <section className="obs-channels" data-testid="obs-channels">
        <div className="obs-channel-group" role="group" aria-label="Code type">
          <span className="obs-channel-label">
            Code type
            <InfoTip>
              UPC is a plain barcode that looks the same for every clamshell,
              so the register can't tell which delivery a unit came from.
              GSIN also encodes the lot, so scans resolve to a specific
              delivery — letting the filter track sales and spoilage per lot
              instead of only as a storewide total.
            </InfoTip>
          </span>
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
          <span className="obs-channel-label">
            Scan waste
            <InfoTip>
              Off means spoiled units are simply pulled and discarded, with
              no count ever reaching the filter. On means a handheld scanner
              logs culled units each day, giving the filter a daily spoilage
              total — storewide, or broken out per lot when Code type is
              set to GSIN.
            </InfoTip>
          </span>
          <div className="chip-row">
            <button
              type="button"
              className={`obs-chip${channels.scan_waste ? " is-active" : ""}`}
              data-obs-scan-waste="true"
              disabled={catchingUp}
              onClick={() => setChannel({ scan_waste: true })}
            >
              On
            </button>
            <button
              type="button"
              className={`obs-chip${!channels.scan_waste ? " is-active" : ""}`}
              data-obs-scan-waste="false"
              disabled={catchingUp}
              onClick={() => setChannel({ scan_waste: false })}
            >
              Off
            </button>
          </div>
        </div>

        <div
          className="obs-channel-group"
          role="group"
          aria-label="Delivery history"
        >
          <span className="obs-channel-label">
            Delivery history
            <InfoTip>
              None tells the filter nothing about the shipment beyond order
              quantity. Pack date reports the calendar time since packing,
              which alone cuts belief error roughly threefold, since trip
              duration — not temperature — drives most of the
              shipment-to-shipment spoilage variation. Temperature history
              adds a full transit-temperature trace on top of that, narrowing
              the remaining uncertainty a bit further.
            </InfoTip>
          </span>
          <div className="chip-row chip-row--wrap">
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

        <p
          className="obs-catchup-progress"
          id="obs-catchup-progress"
          hidden={!catchingUp}
        >
          Catch-up in progress…
        </p>
      </section>

      <div className="obs-controls-truth">
        <div className="obs-truth-copy">
          <span className="truth-toggle-label">
            Omniscience
            <InfoTip>
              Shows the simulator's hidden ground truth — each lot's real
              freshness, exactly when it arrived, and other state the filter
              never gets to see — purely so you can watch how closely belief
              tracks reality. It never feeds the filter's belief or the
              ordering policy, and it's independent of the Code type, Scan
              waste, and Delivery history channels: switching this on
              doesn't give the filter any new information, it only changes
              what you can see on screen.
            </InfoTip>
          </span>
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
    </section>
  );
}
