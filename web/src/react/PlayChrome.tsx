import { useEffect, useState } from "react";
import type { ControlsCallbacks, ControlsState } from "../controls";
import { EPISODE_HORIZON } from "../controls";
import {
  pipelineDeliveryHint,
  weekdayLabel,
} from "../calendar/nextOrderAdvance";
import { saveShowTruth } from "../showTruth";

function snap(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  const cs = Math.max(1, Math.round(caseSize));
  return Math.round(qty / cs) * cs;
}

export type PlayChromeViewProps = {
  state: ControlsState;
  autopilotRunning: boolean;
  showTruth: boolean;
  truthClassTarget: HTMLElement | null;
  notifyTruthOnMount: boolean;
  callbacks: Pick<
    ControlsCallbacks,
    | "onOrderChange"
    | "onAdvance"
    | "onReset"
    | "onAutopilotPlay"
    | "onAutopilotPause"
    | "onShowTruthChange"
  >;
};

export function PlayChromeView({
  state,
  autopilotRunning,
  showTruth: showTruthProp,
  truthClassTarget,
  notifyTruthOnMount,
  callbacks,
}: PlayChromeViewProps) {
  const [showTruth, setShowTruthLocal] = useState(showTruthProp);
  const caseSize = state.config.case_size;
  const orderSnapped = snap(state.orderQty, caseSize);
  const atEnd = state.episodeDay >= EPISODE_HORIZON;
  const orderMax = Math.max(160, caseSize * 20);

  const truthTarget =
    truthClassTarget ??
    (typeof document !== "undefined"
      ? (document.getElementById("app") ?? document.body)
      : null);

  useEffect(() => {
    setShowTruthLocal(showTruthProp);
  }, [showTruthProp]);

  useEffect(() => {
    if (!notifyTruthOnMount) {
      truthTarget?.classList.toggle("studio--show-truth", showTruthProp);
    }
  }, [notifyTruthOnMount, showTruthProp, truthTarget]);

  useEffect(() => {
    if (notifyTruthOnMount) {
      truthTarget?.classList.toggle("studio--show-truth", showTruth);
    }
  }, [showTruth, notifyTruthOnMount, truthTarget]);

  function setShowTruth(on: boolean, notify = true): void {
    setShowTruthLocal(on);
    truthTarget?.classList.toggle("studio--show-truth", on);
    if (notify) {
      saveShowTruth(on);
      callbacks.onShowTruthChange?.(on);
    }
  }

  function setOrder(raw: number): void {
    callbacks.onOrderChange(snap(raw, caseSize));
  }

  const dayLabel =
    state.schedule != null
      ? `Weekday ${weekdayLabel(state.episodeDay, state.schedule)}`
      : "";
  const deliveryHint =
    state.schedule != null
      ? pipelineDeliveryHint(state.episodeDay, state.schedule)
      : "";

  return (
    <div className="play-chrome">
      <label className="field">
        <span className="field-label">
          Order quantity <em id="case-em">(case {caseSize})</em>
        </span>
        <div className="order-row">
          <input
            type="range"
            id="order-range"
            min={0}
            max={orderMax}
            step={caseSize}
            value={orderSnapped}
            onInput={(e) => setOrder(Number(e.currentTarget.value))}
          />
          <input
            type="number"
            id="order-num"
            min={0}
            max={320}
            step={caseSize}
            value={orderSnapped}
            onChange={(e) => setOrder(Number(e.currentTarget.value))}
          />
        </div>
      </label>
      <div className="btn-row btn-row-play">
        <button
          type="button"
          className="btn-advance"
          id="btn-advance"
          disabled={autopilotRunning || atEnd}
          onClick={() => {
            if (autopilotRunning || atEnd) return;
            callbacks.onAdvance();
          }}
        >
          Advance to next order day
        </button>
        <button
          type="button"
          className="btn-autopilot"
          id="btn-autopilot-play"
          aria-label="Autopilot Play"
          disabled={autopilotRunning || atEnd}
          onClick={() => {
            if (atEnd) return;
            callbacks.onAutopilotPlay?.();
          }}
        >
          Autopilot Play
        </button>
        <button
          type="button"
          className="btn-autopilot"
          id="btn-autopilot-pause"
          aria-label="Autopilot Pause"
          disabled={!autopilotRunning}
          onClick={() => callbacks.onAutopilotPause?.()}
        >
          Autopilot Pause
        </button>
        <button
          type="button"
          className="btn-reset"
          id="btn-reset"
          onClick={() => callbacks.onReset()}
        >
          Reset episode
        </button>
      </div>
      <div className="truth-toggle-row">
        <span className="truth-toggle-label">Sim truth overlay</span>
        <button
          type="button"
          className={`truth-toggle${showTruth ? " truth-toggle--on" : ""}`}
          id="btn-show-truth"
          role="switch"
          aria-checked={showTruth ? "true" : "false"}
          aria-label="Show true state"
          onClick={() => setShowTruth(!showTruth)}
        >
          <span className="truth-toggle-track" aria-hidden="true">
            <span className="truth-toggle-thumb" />
          </span>
          <span className="truth-toggle-text">{showTruth ? "On" : "Off"}</span>
        </button>
      </div>
      <p className="hint" id="autopilot-hint">
        While Autopilot is running, Advance is disabled — pause Autopilot to step
        manually.
      </p>
      <p className="hint" id="episode-end-hint" hidden={!atEnd}>
        The episode finished at day 90. Reset to start another episode.
      </p>
      <div className="meta-line" id="order-meta">
        {`Episode day ${state.episodeDay} · pending inbound ${state.pendingOrder} units`}
      </div>
      <div className="day-label" id="day-label">
        {dayLabel}
      </div>
      <div className="delivery-hint" id="delivery-hint">
        {deliveryHint}
      </div>
      <div className="dirty-banner" id="dirty-banner" hidden={!state.configDirty}>
        Config edited — new days use it; <strong>Reset</strong> regenerates history
        from seed.
      </div>
    </div>
  );
}
