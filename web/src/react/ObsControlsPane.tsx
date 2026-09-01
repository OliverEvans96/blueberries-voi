import "../styles/obsControls.css";
import type { ObsChannels, ViewModel } from "../types";
import { InfoTip } from "./InfoTip";

const CODE_OPTIONS: ObsChannels["code_type"][] = ["upc", "lgtin"];
const HISTORY_OPTIONS: ObsChannels["delivery_history"][] = [
  "none",
  "pack_date",
  "temperature_history",
];

const CODE_LABEL: Record<ObsChannels["code_type"], string> = {
  upc: "UPC",
  lgtin: "LGTIN (include lot #)",
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
  /** WASM boot — static skeleton until adapter.init settles. */
  booting?: boolean;
};

function ObsControlsBootingSkeleton() {
  return (
    <section
      className="obs-controls-pane panel"
      data-testid="obs-controls-pane"
      aria-label="Observation controls"
      aria-busy="true"
      data-booting="true"
    >
      <div className="panel-head obs-panel-head">
        <span className="heading-with-tip">
          <h2>Observation</h2>
          <InfoTip>
            What the store's inventory system can actually see each day, not
            the hidden ground truth the simulator tracks internally. No
            combination of these switches ever reports freshness directly.
          </InfoTip>
        </span>
        <p className="obs-panel-lead">What the filter can see</p>
      </div>

      <section className="obs-channels" data-testid="obs-channels">
        <div className="obs-channel-group" aria-hidden="true">
          <span className="obs-channel-label">Code type</span>
          <div className="chip-row">
            <span className="obs-chip-skeleton" />
            <span className="obs-chip-skeleton obs-chip-skeleton--wide" />
          </div>
        </div>

        <div className="obs-channel-group" aria-hidden="true">
          <span className="obs-channel-label">Scan waste</span>
          <div className="chip-row">
            <span className="obs-chip-skeleton obs-chip-skeleton--narrow" />
            <span className="obs-chip-skeleton obs-chip-skeleton--narrow" />
          </div>
        </div>

        <div className="obs-channel-group" aria-hidden="true">
          <span className="obs-channel-label">Delivery history</span>
          <div className="chip-row chip-row--wrap">
            <span className="obs-chip-skeleton" />
            <span className="obs-chip-skeleton" />
            <span className="obs-chip-skeleton obs-chip-skeleton--wide" />
          </div>
        </div>
      </section>

      <div className="obs-controls-truth" aria-hidden="true">
        <div className="obs-truth-copy">
          <span className="truth-toggle-label">Omniscience</span>
          <span className="truth-toggle-hint">
            Visualize unobserved ground-truth
          </span>
        </div>
        <span className="truth-toggle-skeleton" />
      </div>
    </section>
  );
}

export function ObsControlsPane({
  showTruth,
  onSetObsChannels,
  onShowTruthChange,
  vm,
  catchingUp = false,
  booting = false,
}: ObsControlsPaneProps) {
  if (booting) {
    return <ObsControlsBootingSkeleton />;
  }

  const channels = vm.config.obs_channels;
  const controlsDisabled = catchingUp;

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
            What the store's inventory system can actually see each day, not
            the hidden ground truth the simulator tracks internally. No
            combination of these switches ever reports freshness directly.
          </InfoTip>
        </span>
        <p className="obs-panel-lead">What the filter can see</p>
      </div>

      <section className="obs-channels" data-testid="obs-channels">
        <div className="obs-channel-group" role="group" aria-label="Code type">
          <span className="obs-channel-label">
            Code type
            <InfoTip>
              UPC can't tell which delivery a unit came from. LGTIN also
              encodes the lot, so the filter can track sales and spoilage
              per lot instead of only storewide.
            </InfoTip>
          </span>
          <div className="chip-row">
            {CODE_OPTIONS.map((code_type) => (
              <button
                key={code_type}
                type="button"
                className={`obs-chip${channels.code_type === code_type ? " is-active" : ""}`}
                data-obs-code-type={code_type}
                disabled={controlsDisabled}
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
              Off: spoiled units are discarded with no count reaching the
              filter. On: a daily spoilage total reaches the filter —
              storewide, or per lot when Code type is LGTIN.
            </InfoTip>
          </span>
          <div className="chip-row">
            <button
              type="button"
              className={`obs-chip${channels.scan_waste ? " is-active" : ""}`}
              data-obs-scan-waste="true"
              disabled={controlsDisabled}
              onClick={() => setChannel({ scan_waste: true })}
            >
              On
            </button>
            <button
              type="button"
              className={`obs-chip${!channels.scan_waste ? " is-active" : ""}`}
              data-obs-scan-waste="false"
              disabled={controlsDisabled}
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
              None reports nothing beyond order quantity. Pack date reports
              time since packing, cutting belief error roughly threefold.
              Temperature history adds a full transit trace, narrowing it
              further.
            </InfoTip>
          </span>
          <div className="chip-row chip-row--wrap">
            {HISTORY_OPTIONS.map((delivery_history) => (
              <button
                key={delivery_history}
                type="button"
                className={`obs-chip${channels.delivery_history === delivery_history ? " is-active" : ""}`}
                data-obs-delivery-history={delivery_history}
                disabled={controlsDisabled}
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
              freshness and arrival time — so you can compare belief to
              reality. Purely a display: it never feeds the filter's belief
              or the ordering policy.
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
          disabled={controlsDisabled}
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
