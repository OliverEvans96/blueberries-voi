import type {
  ArrivalProduct,
  Economics,
  ObsScenarioKey,
  ScenarioId,
  SimConfig,
  ViewModel,
} from "./types";
import type { SectionId } from "./sections";
import { defaultIntervalMsForPolicy } from "./autopilotLoop";
import type { ScheduleWire } from "./engine/types";
import { PARAM_LABELS, type ControlTier } from "./paramLabels";
import { controlAvailability } from "./scenarioAvailability";
import { infoTipHtml } from "./infoTip";

/** Studio episode length (ADR 0122 / T-112). */
export const EPISODE_HORIZON = 90;

/** Locked chip copy (ADR 0110 / T-089). */
export const SCENARIO_COPY: Record<
  ObsScenarioKey,
  { title: string; description: string }
> = {
  P0: {
    title: "Books only",
    description: "Receipts and POS totals only — no daily waste.",
  },
  P1: {
    title: "Shrink gun",
    description: "Adds storewide daily waste totals.",
  },
  F1: {
    title: "Lot ID at POS",
    description: "Sales broken out by lot.",
  },
  F1s: {
    title: "Lot ID on shrink",
    description: "Waste broken out by lot.",
  },
  F2a: {
    title: "Pack date on ASN",
    description: "Narrows the arrival freshness prior only.",
  },
  F2: {
    title: "GSIN + pack date",
    description: "Lot-resolved scans with pack date on delivery ASN.",
  },
  F3: {
    title: "Temperature history",
    description: "Lot-resolved scans with observed cold-chain trace at delivery.",
  },
  custom: {
    title: "Custom channels",
    description: "Observation channels do not match a named preset.",
  },
};

export function scenarioTitle(id: ObsScenarioKey | string): string {
  const copy = SCENARIO_COPY[id as ObsScenarioKey];
  return copy?.title ?? "Unknown scenario";
}

export function scenarioDescription(id: ObsScenarioKey | string): string {
  const copy = SCENARIO_COPY[id as ObsScenarioKey];
  return copy?.description ?? "";
}

/**
 * Catch-up UX (T-113): obs-catchup-progress; obs chips disabled while catchingUp.
 * Ladder chip ids (DecisionRail): data-obs="P0" data-obs="P1" data-obs="F1"
 * data-obs="F1s" data-obs="F2a" data-obs="F2"
 */
export const OBS_LADDER_IDS: ScenarioId[] = [
  "P0",
  "P1",
  "F1",
  "F1s",
  "F2a",
  "F2",
];

export type ControlsCallbacks = {
  onOrderChange: (qty: number) => void;
  onAdvance: () => void;
  onReset: () => void;
  onAutopilotPlay?: () => void;
  onAutopilotPause?: () => void;
  onEconomicsChange: (partial: Partial<Economics>) => void;
  onConfigChange: (partial: Partial<SimConfig>) => void;
  onSetObsScenario?: (id: ScenarioId) => void;
  onControllerChange?: (partial: Partial<ControllerControlsState>) => void;
  onShowTruthChange?: (show: boolean) => void;
};

export type ControlsState = {
  orderQty: number;
  economics: Economics;
  config: SimConfig;
  configDirty: boolean;
  catchingUp?: boolean;
  episodeDay: number;
  pendingOrder: number;
  /** Snapshot schedule for weekday / pipeline chrome (T-086). */
  schedule: ScheduleWire | null;
};

/** Autopilot / ActOpts knobs (T-099); not ModelParams until Reset. */
export type ControllerPolicy = "damped_sw" | "rollout" | "constant";

export type ControllerControlsState = {
  policy: ControllerPolicy;
  alpha: number;
  rho: number;
  H: number;
  n_rollout_paths: number;
  candidate_case_radius: number;
  n_particles: number;
  intervalMs: number;
};

/** ADR 0099 dialed browser budgets + CTL-01 defaults. */
export const DEFAULT_CONTROLLER_CONTROLS: ControllerControlsState = {
  policy: "damped_sw",
  alpha: 0.9,
  rho: 0.8,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
  n_particles: 200,
  intervalMs: 500,
};


/**
 * σ (picking variability) drives `w ∝ f^σ`, a power-law shape — equal steps
 * in raw σ are far from equally meaningful (σ 0.05→0.15 reshapes the curve
 * dramatically; σ 1.0→1.1 barely moves it). The `sigma` slider's *raw input
 * value* is therefore precision `p = 1/σ`, linear in the input element, and
 * converted to/from σ at the UI boundary. `p = 0` is reserved as an explicit
 * sentinel for "uniform picking" (σ = 0), matching `pickingWeightsF`'s own
 * `sigma <= 0` special case — 1/0 is not computed.
 */
export const SIGMA_MIN = 0.05;
export const SIGMA_MAX = 1.5;
export const SIGMA_PRECISION_MAX = 1 / SIGMA_MIN;

function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value));
}

/** σ → slider precision (1/σ), with σ ≤ 0 mapping to the uniform sentinel 0. */
export function sigmaToPrecision(sigma: number): number {
  if (sigma <= 0) return 0;
  return clamp(1 / sigma, 0, SIGMA_PRECISION_MAX);
}

/** Slider precision (1/σ) → σ, with the sentinel 0 mapping back to uniform. */
export function precisionToSigma(precision: number): number {
  if (precision <= 0) return 0;
  return clamp(1 / precision, SIGMA_MIN, SIGMA_MAX);
}

/**
 * Display text for the sigma slider's raw (precision) value — the label
 * already reads "σ (picking)", so this shows the resulting σ number (not
 * precision) to keep the on-screen value meaningful, e.g. "currently 0.35".
 */
export function formatSigmaPrecision(precision: number): string {
  if (precision <= 0) return "uniform (1/σ = 0)";
  return `1/σ = ${precision.toFixed(2)}`;
}

type SliderSpec = {
  id: string;
  label: string;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  group: "physics" | "demand" | "logistics" | "arrival" | "episode" | "pricing";
};

const PRICE_SLIDERS: SliderSpec[] = [
  { id: "p_sell", label: "p_sell", min: 1, max: 10, step: 0.1, format: (v) => `$${v.toFixed(2)}`, group: "pricing" },
  { id: "c_unit", label: "c_unit", min: 0.2, max: 5, step: 0.1, format: (v) => `$${v.toFixed(2)}`, group: "pricing" },
  { id: "c_waste", label: "c_waste", min: 0, max: 5, step: 0.1, format: (v) => `$${v.toFixed(2)}`, group: "pricing" },
  { id: "c_stockout", label: "c_stockout", min: 0, max: 8, step: 0.1, format: (v) => `$${v.toFixed(2)}`, group: "pricing" },
];

const CONFIG_SLIDERS: SliderSpec[] = [
  { id: "eta_ref", label: "η_ref (days)", min: 4, max: 28, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "q10", label: "Q10", min: 1, max: 5, step: 0.1, format: (v) => v.toFixed(1), group: "physics" },
  { id: "t_ref_c", label: "T_ref (°C)", min: -2, max: 8, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "t_store_c", label: "T_store (°C)", min: 0, max: 12, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "demand_mu", label: "demand μ", min: 5, max: 80, step: 1, format: (v) => v.toFixed(0), group: "demand" },
  { id: "demand_vm", label: "demand V/M", min: 1.1, max: 5, step: 0.1, format: (v) => v.toFixed(1), group: "demand" },
  {
    id: "sigma",
    label: "Picking selectivity (1/σ)",
    // Raw input value is precision p = 1/σ, not σ (see comment above);
    // p=0 is the reserved "uniform picking" sentinel, p=SIGMA_PRECISION_MAX
    // corresponds to the most-selective σ=SIGMA_MIN.
    min: 0,
    max: SIGMA_PRECISION_MAX,
    step: 0.1,
    format: formatSigmaPrecision,
    group: "demand",
  },
  { id: "case_size", label: "case size", min: 1, max: 24, step: 1, format: (v) => String(Math.round(v)), group: "logistics" },
  { id: "lead_time", label: "lead time (days)", min: 0, max: 7, step: 1, format: (v) => String(Math.round(v)), group: "logistics" },
  { id: "base_stock", label: "base-stock target", min: 8, max: 160, step: 8, format: (v) => String(Math.round(v)), group: "logistics" },
  {
    id: "spread_scale",
    label: "spread_scale (FIL-11)",
    min: 0.05,
    max: 1.5,
    step: 0.05,
    format: (v) => v.toFixed(2),
    group: "arrival",
  },
  {
    id: "transit_temp_bias_c",
    label: "transit ΔT (°C)",
    min: -2,
    max: 8,
    step: 0.5,
    format: (v) => v.toFixed(1),
    group: "arrival",
  },

  { id: "seed", label: "seed", min: 1, max: 9999, step: 1, format: (v) => String(Math.round(v)), group: "episode" },
];

function tierBadge(id: string): string {
  const meta = PARAM_LABELS[id];
  const tier: ControlTier = meta?.tier ?? "Reset";
  return `<span class="tier-badge tier-badge--${tier.toLowerCase()}">${tier}</span>`;
}

function tuningPlotBlocks(): string {
  return `
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-demand">
          <div class="chart-caption impact-caption">
            Daily demand${infoTipHtml(
              "The actual simulated demand draw for each day, following the day-of-week and weekly calendar shape with random noise on top.",
            )}
          </div>
          <div id="chart-demand-host" class="chart demand-chart-slot" role="img" aria-label="Daily demand over episode days"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-demand-forecast">
          <div class="chart-caption impact-caption">
            Demand forecast${infoTipHtml(
              "Projects daily demand under the mean-demand slider's current setting, without re-simulating any days. Updates immediately, but the simulated history doesn't change until you press Reset.",
            )}
          </div>
          <div id="chart-demand-forecast-host" class="chart demand-chart-slot" role="img" aria-label="Known demand distribution for the next few days"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-picking-variability">
          <div class="chart-caption impact-caption">
            Picking variability shape${infoTipHtml(
              "How strongly the picking exponent biases sales toward fresher units — higher favors fresher stock, zero picks at random. Not FIFO: even old units can occasionally linger unsold.",
            )}
          </div>
          <div id="picking-var-chart" class="chart picking-var-chart" role="img" aria-label="Picking weight curve"></div>
        </div>`;
}

function arrivalPlotBlocks(): string {
  return `
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-arrival-prior">
          <div class="chart-caption impact-caption">
            Arrival freshness prior · receipt rug${infoTipHtml(
              "The expected arrival-freshness distribution for the current corridor, with a rug of actual receipt freshness values from simulated deliveries. The particle filter draws each new lot's freshness from this same distribution.",
            )}
          </div>
          <div id="chart-arrival-prior" class="chart" role="img" aria-label="Arrival freshness prior distribution"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-arrival-shift">
          <div class="chart-caption impact-caption">
            Transit ΔT shift vs baseline${infoTipHtml(
              "Meant to compare the transit-temperature-bias curve against an unbiased baseline, but the bias slider isn't wired into this chart yet (known display gap) — both lines plot the same curve regardless. The bias does apply to the simulated deliveries themselves.",
            )}
          </div>
          <div id="chart-arrival-shift" class="chart" role="img" aria-label="Transit temperature shift"></div>
        </div>`;
}

function physicsPlotBlocks(): string {
  return `
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-arrhenius-temp">
          <div class="chart-caption impact-caption">
            Q10 aging rate vs temperature${infoTipHtml(
              "How much faster freshness decays as the shelf gets warmer. The aging rate scales multiplicatively per 10°C — the default (3.0) triples it per 10°C of warming, not a fixed amount per degree.",
            )}
          </div>
          <div id="chart-arrhenius-temp" class="chart" role="img" aria-label="Q10 aging rate versus store temperature"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-gamma-path">
          <div class="chart-caption impact-caption">
            Gamma freshness mean ± σ until expiry${infoTipHtml(
              "Expected freshness trajectory over time, with a shaded one-standard-deviation band. A hotter storage temperature widens this band as well as steepening the mean line — heat brings more unpredictability along with faster average decay.",
            )}
          </div>
          <div id="chart-gamma-path" class="chart" role="img" aria-label="Unit freshness mean and standard deviation envelope"></div>
        </div>`;
}

function logisticsPlotBlocks(): string {
  return `
        <div class="focus-plot tuning-drawer-slot tuning-drawer-slot--full" data-plot="plot-logistics-calendar">
          <div class="field week-calendar-field">
            <span class="field-label">
              Delivery schedule${infoTipHtml(
                "Click weekdays to set which days deliveries land on; order days are computed automatically as delivery day minus lead time. Takes effect on Reset.",
              )}
            </span>
            <div id="week-calendar" class="week-calendar" role="group" aria-label="Delivery and order weekdays"></div>
            <div class="week-calendar-legend" role="note" aria-label="Calendar legend">
              <span class="week-calendar-legend-item">
                <span class="week-calendar-swatch is-delivery" aria-hidden="true"></span>
                Delivery day
              </span>
              <span class="week-calendar-legend-item">
                <span class="week-calendar-swatch is-order" aria-hidden="true"></span>
                Order day
              </span>
              <span class="week-calendar-legend-item">
                <span class="week-calendar-swatch is-both" aria-hidden="true"></span>
                Both
              </span>
            </div>
            <p class="meta-readonly week-calendar-hint" id="week-calendar-hint" hidden>Reset to apply schedule</p>
          </div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-age-comp">
          <div class="chart-caption impact-caption">
            Historical Freshness Summary${infoTipHtml(
              "On-hand inventory broken into freshness bands, from near-pristine to nearly spoiled. A shelf skewed toward low-freshness bands offers less real protection against demand than the unit count suggests.",
            )}
          </div>
          <div id="chart-age-comp-focus-host" class="chart-host">
            <div id="chart-age-comp-focus" class="chart" role="img" aria-label="On-hand inventory by freshness band preview"></div>
          </div>
        </div>`;
}

function autopilotPlotBlocks(): string {
  return `
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-controller-orders">
          <div class="chart-caption impact-caption">
            Order quantity${infoTipHtml(
              "Preview of each day's order quantity from the active controller policy, enlarged for tuning autopilot parameters.",
            )}
          </div>
          <div id="chart-controller-orders-focus" class="chart" role="img" aria-label="Order quantity preview"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-spoil">
          <div class="chart-caption impact-caption">
            Spoilage${infoTipHtml(
              "Preview of daily units spoiled. Unavailable when waste isn't observed.",
            )}
          </div>
          <div id="chart-spoil-focus" class="chart" role="img" aria-label="Spoilage preview"></div>
        </div>
        <div class="focus-plot tuning-drawer-slot" data-plot="plot-age-comp">
          <div class="chart-caption impact-caption">
            Historical Freshness Summary${infoTipHtml(
              "On-hand inventory broken into freshness bands, from near-pristine to nearly spoiled. A shelf skewed toward low-freshness bands offers less real protection against demand than the unit count suggests.",
            )}
          </div>
          <div id="chart-age-comp-focus-host-autopilot" class="chart-host"></div>
        </div>`;
}

function sliderHtml(spec: SliderSpec): string {
  const meta = PARAM_LABELS[spec.id];
  const label = meta?.label ?? spec.label;
  return `
    <label class="field">
      <span class="field-label">${label}${infoTipHtml(meta?.tooltip ?? spec.label)} ${tierBadge(spec.id)} <span id="val-${spec.id}"></span></span>
      <input type="range" id="${spec.id}" min="${spec.min}" max="${spec.max}" step="${spec.step}" />
    </label>
  `;
}

export type PlayChromeOpts = {
  showTruth?: boolean;
  truthClassTarget?: HTMLElement;
};

/** Persistent order / advance / reset chrome — always visible. */

/** Section-specific knobs — one block visible at a time. */
function mountSectionControlsDom(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<
    ControlsCallbacks,
    | "onEconomicsChange"
    | "onConfigChange"
    | "onControllerChange"
    | "onSetObsScenario"
  >,
  onCaseSizeChange?: (caseSize: number) => void,
  initialController: ControllerControlsState = DEFAULT_CONTROLLER_CONTROLS,
): {
  update: (s: ControlsState) => void;
  showSection: (id: SectionId) => void;
  updateController: (s: ControllerControlsState) => void;
} {
  root.innerHTML = `
    <div class="section-controls">
      <div class="controls-block" data-section="pricing" hidden>
        <p class="hint">Recompute P&amp;L from stored unit history — no re-sim.</p>
        ${PRICE_SLIDERS.map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="physics" hidden>
        <p class="hint">Gamma freshness aging + Q10 temperature shift.</p>
        <p class="meta-readonly">No separate gamma shape knob post f-native migration — aging draws from ModelParams defaults.</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "physics").map(sliderHtml).join("")}
        ${physicsPlotBlocks()}
      </div>
      <div class="controls-block" data-section="demand" hidden>
        <p class="hint">Negative-binomial-ish demand from mean and V/M; 1/σ shapes lot picking spread.</p>
        <div class="demand-controls-sliders">
          ${CONFIG_SLIDERS.filter((s) => s.group === "demand").map(sliderHtml).join("")}
          <p class="meta-readonly" id="play-window-days">Episode window: ${initial.config.window_days} days</p>
          ${CONFIG_SLIDERS.filter((s) => s.group === "episode").map(sliderHtml).join("")}
        </div>
        ${tuningPlotBlocks()}
      </div>
      <div class="controls-block" data-section="logistics" hidden>
        <p class="hint">Case snap, lead time, and stocking targets for daily refill.</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "logistics").map(sliderHtml).join("")}
        ${logisticsPlotBlocks()}
      </div>
      <div class="controls-block" data-section="arrival" hidden>
        <p class="hint">
          MOD-11/18/21: arrival exposure from transit mix + Arrhenius shift.
          Daily lead time stays 1 (no pipeline Gantt).
        </p>
        <div class="field">
          <span class="field-label">Arrival product (MOD-21)${infoTipHtml(
            "The transit lane a delivery travels — its trip duration sets how much freshness a lot has already lost before reaching the shelf. Shorter lanes (e.g. short_haul) deliver fresher stock than longer ones (e.g. long_haul)."
          )}</span>
          <div class="chip-row" id="arrival-chips" role="group" aria-label="Arrival product">
            <button type="button" class="obs-chip arrival-chip" data-arrival="abdella_all" title="Bootstrap all six Abdella shipments">All six</button>
            <button type="button" class="obs-chip arrival-chip" data-arrival="long_haul" title="CA→East long-haul only">Long-haul</button>
            <button type="button" class="obs-chip arrival-chip" data-arrival="short_haul" title="FL short-haul only (tight)">Short-haul</button>
          </div>
        </div>
        ${CONFIG_SLIDERS.filter((s) => s.group === "arrival").map(sliderHtml).join("")}
        ${arrivalPlotBlocks()}
      </div>
      <div class="controls-block" data-section="autopilot" hidden>
        <p class="hint">
          Policy and rollout budgets feed Autopilot / act — physics still needs Reset.
        </p>
        <div class="field">
          <span class="field-label">Policy${infoTipHtml(
            "How the controller turns demand and inventory into an order each day. damped_sw closes a fraction of the gap to a target service level. rollout simulates several candidate order sizes forward and picks the best. constant always orders the same amount, as a baseline."
          )}</span>
          <div class="chip-row" id="policy-chips" role="group" aria-label="Controller policy">
            <button type="button" class="obs-chip policy-chip" data-policy="damped_sw" title="Damped survival-weighted base-stock">damped_sw</button>
            <button type="button" class="obs-chip policy-chip" data-policy="rollout" title="One-step rollout">rollout</button>
            <button type="button" class="obs-chip policy-chip" data-policy="constant" title="Constant order">constant</button>
          </div>
        </div>
        <!-- base_stock policy chip blocked: no backend ActPolicy variant yet (ADR 0117). -->
        <div class="field alpha-rho-field">
          <span class="field-label">α / ρ${infoTipHtml(
            "α is the target service-level quantile the order-up-to level is set to (default 0.9). ρ is the damping factor (default 0.8) that limits how much of the gap to that target is closed each day. Drag the pad: left-right moves α, up-down moves ρ."
          )}</span>
          <div class="alpha-rho-row">
            <svg
              id="alpha-rho-pad"
              class="alpha-rho-pad"
              width="120"
              height="120"
              viewBox="0 0 120 120"
              role="slider"
              aria-label="Alpha and rho tuning pad"
              tabindex="0"
            >
              <rect class="alpha-rho-pad-bg" x="8" y="8" width="104" height="104" rx="4" />
              <line class="alpha-rho-crosshair alpha-rho-crosshair--h" x1="8" y1="60" x2="112" y2="60" />
              <line class="alpha-rho-crosshair alpha-rho-crosshair--v" x1="60" y1="8" x2="60" y2="112" />
              <circle id="alpha-rho-handle" class="alpha-rho-handle" r="6" cx="60" cy="60" />
            </svg>
            <div class="alpha-rho-readout">
              <div>α <span id="val-alpha"></span></div>
              <div>ρ <span id="val-rho"></span></div>
            </div>
          </div>
        </div>
        <label class="field">
          <span class="field-label">H (horizon)${infoTipHtml(
            "How many days ahead the rollout policy simulates when evaluating a candidate order quantity. Longer horizons cost more compute per decision."
          )} <span id="val-H"></span></span>
          <input type="number" id="H" min="1" max="56" step="1" />
        </label>
        <label class="field">
          <span class="field-label">n_rollout_paths${infoTipHtml(
            "How many simulated future paths the rollout policy averages over when scoring each candidate order. More paths reduce noise but cost more compute."
          )} <span id="val-n_rollout_paths"></span></span>
          <input type="number" id="n_rollout_paths" min="1" max="64" step="1" />
        </label>
        <label class="field">
          <span class="field-label">candidate_case_radius${infoTipHtml(
            "How many case-multiples above and below the base order quantity rollout searches — a radius of 1 checks one case up and one case down."
          )} <span id="val-candidate_case_radius"></span></span>
          <input type="number" id="candidate_case_radius" min="0" max="8" step="1" />
        </label>
        <label class="field">
          <span class="field-label">n_particles${infoTipHtml(
            "How many particles the filter uses to track freshness belief. More particles give a smoother belief at the cost of more compute."
          )} <span id="val-n_particles"></span></span>
          <input type="number" id="n_particles" min="16" max="2000" step="16" />
        </label>
        <label class="field">
          <span class="field-label">Autopilot interval (ms)${infoTipHtml(
            "How often Autopilot's timer fires another order-and-advance step. A shorter interval only runs the episode faster — it doesn't change what the controller decides."
          )} <span id="val-intervalMs"></span></span>
          <input type="number" id="intervalMs" min="50" max="10000" step="50" />
        </label>
        ${autopilotPlotBlocks()}
      </div>
    </div>
  `;

  let controllerState: ControllerControlsState = { ...initialController };

  const ALPHA_MIN = 0.5;
  const ALPHA_MAX = 0.99;
  const RHO_MIN = 0.1;
  const RHO_MAX = 1;
  const PAD_PAD = 8;
  const PAD_SIZE = 120;

  function alphaRhoToPad(alpha: number, rho: number): { cx: number; cy: number } {
    const inner = PAD_SIZE - PAD_PAD * 2;
    const cx =
      PAD_PAD + ((alpha - ALPHA_MIN) / (ALPHA_MAX - ALPHA_MIN)) * inner;
    const cy =
      PAD_PAD + (1 - (rho - RHO_MIN) / (RHO_MAX - RHO_MIN)) * inner;
    return { cx, cy };
  }

  function padToAlphaRho(cx: number, cy: number): { alpha: number; rho: number } {
    const inner = PAD_SIZE - PAD_PAD * 2;
    const ax = Math.min(1, Math.max(0, (cx - PAD_PAD) / inner));
    const ry = Math.min(1, Math.max(0, (cy - PAD_PAD) / inner));
    const alpha = ALPHA_MIN + ax * (ALPHA_MAX - ALPHA_MIN);
    const rho = RHO_MIN + (1 - ry) * (RHO_MAX - RHO_MIN);
    return { alpha, rho };
  }

  function syncControlAvailability(channels: SimConfig["obs_channels"]): void {
    for (const spec of [...CONFIG_SLIDERS, ...PRICE_SLIDERS]) {
      const input = root.querySelector(`#${spec.id}`) as HTMLInputElement | null;
      const field = input?.closest(".field") as HTMLElement | null;
      if (!field || !input) continue;
      const avail = controlAvailability(spec.id, channels);
      if (avail === "unavailable") {
        field.hidden = true;
        input.disabled = true;
        continue;
      }
      field.hidden = false;
      if (avail === "dim") {
        field.style.opacity = "0.45";
        input.disabled = true;
      } else {
        field.style.opacity = "";
        input.disabled = false;
      }
    }
  }

  function syncSlider(spec: SliderSpec, value: number): void {
    const el = root.querySelector(`#${spec.id}`) as HTMLInputElement | null;
    const label = root.querySelector(`#val-${spec.id}`) as HTMLElement | null;
    if (!el || !label) return;
    el.value = String(value);
    label.textContent = spec.format(value);
  }

  function syncEconomics(e: Economics): void {
    for (const spec of PRICE_SLIDERS) syncSlider(spec, e[spec.id as keyof Economics]);
  }

  function syncConfig(c: SimConfig, catchingUp = false): void {
    void catchingUp;
    for (const spec of CONFIG_SLIDERS) {
      if (spec.id === "sigma") {
        // Slider's raw value is precision (1/σ), not σ — see SIGMA_* helpers.
        syncSlider(spec, sigmaToPrecision(c.sigma));
        continue;
      }
      const v = c[spec.id as keyof SimConfig];
      if (typeof v === "number") syncSlider(spec, v);
    }
    const copy = SCENARIO_COPY[c.obs_scenario];
    const titleEl = root.querySelector("#obs-scenario-title") as HTMLElement | null;
    const descEl = root.querySelector("#obs-scenario-desc") as HTMLElement | null;
    if (titleEl && copy) titleEl.textContent = copy.title;
    if (descEl && copy) descEl.textContent = copy.description;
    const windowEl = root.querySelector("#play-window-days") as HTMLElement | null;
    if (windowEl) {
      windowEl.textContent = `Episode window: ${c.window_days} days`;
    }
    root.querySelectorAll<HTMLButtonElement>(".arrival-chip").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.arrival === c.arrival_product);
    });
    syncControlAvailability(c.obs_channels);
  }

  function syncController(s: ControllerControlsState): void {
    controllerState = { ...s };
    root.querySelectorAll<HTMLButtonElement>(".policy-chip").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.policy === s.policy);
    });
    const handle = root.querySelector("#alpha-rho-handle") as SVGCircleElement | null;
    const alphaLabel = root.querySelector("#val-alpha") as HTMLElement | null;
    const rhoLabel = root.querySelector("#val-rho") as HTMLElement | null;
    const pos = alphaRhoToPad(s.alpha, s.rho);
    if (handle) {
      handle.setAttribute("cx", String(pos.cx));
      handle.setAttribute("cy", String(pos.cy));
    }
    if (alphaLabel) alphaLabel.textContent = s.alpha.toFixed(2);
    if (rhoLabel) rhoLabel.textContent = s.rho.toFixed(2);
    for (const id of [
      "H",
      "n_rollout_paths",
      "candidate_case_radius",
      "n_particles",
      "intervalMs",
    ] as const) {
      const el = root.querySelector(`#${id}`) as HTMLInputElement;
      el.value = String(s[id]);
      const valLabel = root.querySelector(`#val-${id}`) as HTMLElement | null;
      if (valLabel) valLabel.textContent = String(s[id]);
    }
  }

  for (const spec of PRICE_SLIDERS) {
    const el = root.querySelector(`#${spec.id}`) as HTMLInputElement;
    el.addEventListener("input", () => {
      const value = Number(el.value);
      (root.querySelector(`#val-${spec.id}`) as HTMLElement).textContent =
        spec.format(value);
      cb.onEconomicsChange({ [spec.id]: value });
    });
  }

  for (const spec of CONFIG_SLIDERS) {
    const el = root.querySelector(`#${spec.id}`) as HTMLInputElement | null;
    if (!el) continue;
    el.addEventListener("input", () => {
      const raw = Number(el.value);
      (root.querySelector(`#val-${spec.id}`) as HTMLElement).textContent =
        spec.format(raw);
      if (spec.id === "sigma") {
        // Raw slider value is precision (1/σ); convert before writing config
        // and before feeding the illustrative w(f) curve, which is σ-shaped.
        const sigma = precisionToSigma(raw);
        cb.onConfigChange({ sigma });
        return;
      }
      cb.onConfigChange({ [spec.id]: raw });
      if (spec.id === "case_size") onCaseSizeChange?.(Math.round(raw));
    });
  }

  root.querySelectorAll<HTMLButtonElement>(".arrival-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      cb.onConfigChange({
        arrival_product: btn.dataset.arrival as ArrivalProduct,
      });
    });
  });

  root.querySelectorAll<HTMLButtonElement>(".policy-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const policy = btn.dataset.policy as ControllerPolicy;
      const partial: Partial<ControllerControlsState> = {
        policy,
        intervalMs: defaultIntervalMsForPolicy(policy),
      };
      syncController({ ...controllerState, ...partial });
      cb.onControllerChange?.(partial);
    });
  });

  const alphaRhoPad = root.querySelector("#alpha-rho-pad") as SVGSVGElement;
  let padDragging = false;

  function applyPadPoint(clientX: number, clientY: number): void {
    const rect = alphaRhoPad.getBoundingClientRect();
    const scaleX = PAD_SIZE / rect.width;
    const scaleY = PAD_SIZE / rect.height;
    const cx = (clientX - rect.left) * scaleX;
    const cy = (clientY - rect.top) * scaleY;
    const { alpha, rho } = padToAlphaRho(cx, cy);
    controllerState = { ...controllerState, alpha, rho };
    syncController(controllerState);
    cb.onControllerChange?.({ alpha, rho });
  }

  alphaRhoPad.addEventListener("pointerdown", (ev) => {
    padDragging = true;
    alphaRhoPad.setPointerCapture(ev.pointerId);
    applyPadPoint(ev.clientX, ev.clientY);
  });
  alphaRhoPad.addEventListener("pointermove", (ev) => {
    if (!padDragging) return;
    applyPadPoint(ev.clientX, ev.clientY);
  });
  alphaRhoPad.addEventListener("pointerup", (ev) => {
    padDragging = false;
    alphaRhoPad.releasePointerCapture(ev.pointerId);
  });
  alphaRhoPad.addEventListener("pointerleave", () => {
    padDragging = false;
  });

  for (const id of [
    "H",
    "n_rollout_paths",
    "candidate_case_radius",
    "n_particles",
    "intervalMs",
  ] as const) {
    const el = root.querySelector(`#${id}`) as HTMLInputElement;
    el.addEventListener("change", () => {
      const value = Number(el.value);
      const label = root.querySelector(`#val-${id}`) as HTMLElement | null;
      if (label) label.textContent = String(value);
      controllerState = { ...controllerState, [id]: value };
      cb.onControllerChange?.({ [id]: value });
    });
  }

  syncEconomics(initial.economics);
  syncConfig(initial.config);
  syncController(initialController);

  return {
    update(s) {
      syncEconomics(s.economics);
      syncConfig(s.config, Boolean(s.catchingUp));
    },
    updateController(s) {
      syncController(s);
    },
    showSection(id) {
      root.querySelectorAll<HTMLElement>(".controls-block").forEach((block) => {
        block.hidden = block.dataset.section !== id;
      });
    },
  };
}

export function controlsFromVm(
  vm: ViewModel,
  orderQty: number,
  schedule: ScheduleWire | null = null,
): ControlsState {
  return {
    orderQty,
    economics: vm.economics,
    config: vm.config,
    configDirty: vm.config_dirty,
    episodeDay: vm.episode_day,
    pendingOrder: vm.pending_order,
    schedule,
  };
}

export { mountSectionControls } from "./controlsSectionMount";

export { mountSectionControlsDom };
