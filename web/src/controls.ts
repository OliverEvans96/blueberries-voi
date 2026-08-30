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
import { DEFAULT_OBS_CHANNELS } from "./obsMask";
import { tunedControllerFor } from "./perChannelTuning";

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

/**
 * ADR 0099 dialed browser budgets + CTL-01 defaults. `alpha`/`rho` start at
 * the per-channel Ax-tuned values for Studio's own default observation
 * channels (`DEFAULT_OBS_CHANNELS`, i.e. `upc|on|none`) — see
 * `perChannelTuning.ts`. Whenever observation channels change, `studioLogic`
 * re-syncs `alpha`/`rho` to that channel's own tuning rather than leaving a
 * single shared pair in place across every channel (2026-08-30: a shared
 * pair was found to flatten the belief-accuracy-vs-profit relationship even
 * when each channel's belief accuracy differed cleanly — see
 * `.team/plans/2026-08-30-particle-filter-collapse-fix.md`).
 */
export const DEFAULT_CONTROLLER_CONTROLS: ControllerControlsState = {
  policy: "damped_sw",
  ...tunedControllerFor(DEFAULT_OBS_CHANNELS),
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

function fieldLabelHtml(
  label: string,
  tip: string,
  opts?: { valueId?: string; tierId?: string },
): string {
  const tier = opts?.tierId ? ` ${tierBadge(opts.tierId)}` : "";
  const value = opts?.valueId ? ` <span id="val-${opts.valueId}"></span>` : "";
  return `<span class="field-label"><span class="field-label-main">${label}${infoTipHtml(tip)}${tier}</span>${value}</span>`;
}

function slidersByIds(ids: string[]): string {
  const idSet = new Set(ids);
  return CONFIG_SLIDERS.filter((s) => idSet.has(s.id)).map(sliderHtml).join("");
}

type TuningChartGroupOpts = {
  plotId: string;
  caption: string;
  tip: string;
  ariaLabel: string;
  fullWidth?: boolean;
  slidersHtml?: string;
  chartInnerHtml: string;
};

function tuningChartGroup(opts: TuningChartGroupOpts): string {
  const fullClass = opts.fullWidth ? " tuning-drawer-slot--full" : "";
  const sliders = opts.slidersHtml
    ? `<div class="tuning-chart-group-sliders">${opts.slidersHtml}</div>`
    : "";
  return `
    <div class="tuning-chart-group">
      <div class="focus-plot tuning-drawer-slot${fullClass}" data-plot="${opts.plotId}">
        <div class="chart-caption impact-caption">
          ${opts.caption}${infoTipHtml(opts.tip)}
        </div>
        ${opts.chartInnerHtml}
      </div>
      ${sliders}
    </div>`;
}

function demandChartGroups(): string {
  return `
        ${tuningChartGroup({
          plotId: "plot-demand-forecast",
          caption: "Demand forecast",
          tip: "Projects daily demand under the mean-demand slider's current setting, without re-simulating any days. Updates immediately, but the simulated history doesn't change until you press Reset.",
          ariaLabel: "Known demand distribution for the next few days",
          chartInnerHtml:
            '<div id="chart-demand-forecast-host" class="chart demand-chart-slot" role="img" aria-label="Known demand distribution for the next few days"></div>',
          slidersHtml: slidersByIds(["demand_mu", "demand_vm"]),
        })}
        ${tuningChartGroup({
          plotId: "plot-picking-variability",
          caption: "Picking variability shape",
          tip: "How strongly the picking exponent biases sales toward fresher units — higher favors fresher stock, zero picks at random. Not FIFO: even old units can occasionally linger unsold.",
          ariaLabel: "Picking weight curve",
          chartInnerHtml:
            '<div id="picking-var-chart" class="chart picking-var-chart" role="img" aria-label="Picking weight curve"></div>',
          slidersHtml: slidersByIds(["sigma"]),
        })}`;
}

function arrivalChartGroups(): string {
  return `
        ${tuningChartGroup({
          plotId: "plot-arrival-prior",
          caption: "Arrival freshness prior · receipt rug",
          tip: "The expected arrival-freshness distribution for the current corridor, with a rug of actual receipt freshness values from simulated deliveries. The particle filter draws each new lot's freshness from this same distribution.",
          ariaLabel: "Arrival freshness prior distribution",
          chartInnerHtml:
            '<div class="chart-arrival-prior-slot"><div id="chart-arrival-prior" class="chart" role="img" aria-label="Arrival freshness prior distribution"></div><div id="chart-arrival-prior-overlay" class="chart-arrival-loading-overlay" hidden aria-live="polite"><span class="engine-status-dot" aria-hidden="true"></span><span class="chart-arrival-loading-label">Loading arrival prior…</span></div></div>',
          slidersHtml: slidersByIds(["spread_scale"]),
        })}
        ${tuningChartGroup({
          plotId: "plot-arrival-shift",
          caption: "Transit ΔT shift vs baseline",
          tip: "Compares the transit-temperature-bias curve against an unbiased baseline. The bias slider reshapes the displayed shift curve and applies to simulated deliveries.",
          ariaLabel: "Transit temperature shift",
          chartInnerHtml:
            '<div id="chart-arrival-shift" class="chart" role="img" aria-label="Transit temperature shift"></div>',
          slidersHtml: slidersByIds(["transit_temp_bias_c"]),
        })}`;
}

function physicsChartGroups(): string {
  return `
        ${tuningChartGroup({
          plotId: "plot-arrhenius-temp",
          caption: "Q10 aging rate vs temperature",
          tip: "How much faster freshness decays as the shelf gets warmer. The aging rate scales multiplicatively per 10°C — the default (2.0) doubles it per 10°C of warming, not a fixed amount per degree.",
          ariaLabel: "Q10 aging rate versus store temperature",
          chartInnerHtml:
            '<div id="chart-arrhenius-temp" class="chart" role="img" aria-label="Q10 aging rate versus store temperature"></div>',
          slidersHtml: slidersByIds(["q10", "t_ref_c", "t_store_c"]),
        })}
        ${tuningChartGroup({
          plotId: "plot-gamma-path",
          caption: "Gamma freshness mean ± σ until expiry",
          tip: "Expected freshness trajectory over time, with a shaded one-standard-deviation band. A hotter storage temperature widens this band as well as steepening the mean line — heat brings more unpredictability along with faster average decay.",
          ariaLabel: "Unit freshness mean and standard deviation envelope",
          chartInnerHtml:
            '<div id="chart-gamma-path" class="chart" role="img" aria-label="Unit freshness mean and standard deviation envelope"></div>',
          slidersHtml: slidersByIds(["eta_ref"]),
        })}`;
}

function logisticsCalendarGroup(): string {
  return `
    <div class="tuning-chart-group">
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
      <div class="tuning-chart-group-sliders">
        ${slidersByIds(["lead_time", "case_size"])}
      </div>
    </div>`;
}

function logisticsAgeCompGroup(): string {
  return tuningChartGroup({
    plotId: "plot-age-comp",
    caption: "Historical Freshness Summary",
    tip: "On-hand inventory broken into freshness bands, from near-pristine to nearly spoiled. A shelf skewed toward low-freshness bands offers less real protection against demand than the unit count suggests.",
    ariaLabel: "On-hand inventory by freshness band preview",
    chartInnerHtml: `<div id="chart-age-comp-focus-host" class="chart-host">
            <div id="chart-age-comp-focus" class="chart" role="img" aria-label="On-hand inventory by freshness band preview"></div>
          </div>`,
  });
}

function autopilotAlphaRhoSliders(): string {
  return `
        <label class="field" id="alpha-field">
          ${fieldLabelHtml(
            "α (service level)",
            "Target service-level quantile for protection demand F⁻¹(α). Higher α raises the order-up-to target.",
            { valueId: "alpha" },
          )}
          <input type="range" id="alpha" min="0.5" max="0.99" step="0.01" />
        </label>
        <label class="field" id="rho-field">
          ${fieldLabelHtml(
            "ρ (damping)",
            "Fraction of the gap to the target closed each order day. Lower ρ dampens orders; higher ρ closes the gap faster.",
            { valueId: "rho" },
          )}
          <input type="range" id="rho" min="0.5" max="2" step="0.01" />
        </label>
        <p class="meta-readonly alpha-rho-disabled-hint" id="alpha-rho-disabled-hint" hidden>
          Constant policy — α / ρ apply to damped_sw only.
        </p>`;
}

function autopilotChartGroup(): string {
  return tuningChartGroup({
    plotId: "plot-damped-sw-demo",
    caption: "Protection-interval demand",
    tip: "Histogram of total demand over the current protection window. Vertical lines mark the α service target F⁻¹(α) and the case-rounded order q = caseRound(ρ·max(0, F⁻¹(α) − Ĩ)). Updates as you move α and ρ.",
    ariaLabel: "Damped survival-weighted controller demo",
    fullWidth: true,
    chartInnerHtml:
      '<div id="chart-damped-sw-demo" class="chart damped-sw-demo-slot" role="img" aria-label="Damped survival-weighted controller demo"></div>',
    slidersHtml: autopilotAlphaRhoSliders(),
  });
}

function sliderHtml(spec: SliderSpec): string {
  const meta = PARAM_LABELS[spec.id];
  const label = meta?.label ?? spec.label;
  return `
    <label class="field">
      ${fieldLabelHtml(label, meta?.tooltip ?? spec.label, {
        valueId: spec.id,
        tierId: spec.id,
      })}
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
        <p class="hint">η_ref sets θ; heat scales event rate via φ on gamma shape (γ(k·φ, θ)).</p>
        <p class="meta-readonly">No separate gamma shape knob post f-native migration — aging draws from ModelParams defaults.</p>
        ${physicsChartGroups()}
      </div>
      <div class="controls-block" data-section="demand" hidden>
        <p class="hint">Negative-binomial-ish demand from mean and V/M; 1/σ shapes lot picking spread.</p>
        ${slidersByIds(["seed"])}
        ${demandChartGroups()}
        <p class="meta-readonly" id="play-window-days">Episode window: ${initial.config.window_days} days</p>
      </div>
      <div class="controls-block" data-section="logistics" hidden>
        <p class="hint">Case snap, lead time, and stocking targets for daily refill.</p>
        ${logisticsCalendarGroup()}
        ${logisticsAgeCompGroup()}
      </div>
      <div class="controls-block" data-section="arrival" hidden>
        <p class="hint">
          MOD-11/18/21: arrival exposure from transit mix + Arrhenius shift.
          Daily lead time stays 1 (no pipeline Gantt).
        </p>
        <div class="field">
          ${fieldLabelHtml(
            "Arrival corridor (MOD-21)",
            "Abdella corridor mixture (abdella_mix): each delivery draws short_haul (60%) or long_haul (40%) for trip duration and temperature. Illustrative leaf lanes are not exposed as separate studio chips.",
          )}
          <div class="chip-row" id="arrival-chips" role="group" aria-label="Arrival corridor">
            <button type="button" class="obs-chip arrival-chip" data-arrival="abdella_mix" title="Abdella short/long corridor blend (60/40)">Abdella mix</button>
          </div>
        </div>
        ${arrivalChartGroups()}
      </div>
      <div class="controls-block" data-section="autopilot" hidden>
        <p class="hint">
          damped_sw α / ρ feed Autopilot / act — physics still needs Reset.
        </p>
        <div class="field">
          ${fieldLabelHtml(
            "Policy",
            "How the controller turns demand and inventory into an order each day. damped_sw closes a fraction of the gap to a target service level. constant always orders the same amount, as a baseline.",
          )}
          <div class="chip-row" id="policy-chips" role="group" aria-label="Controller policy">
            <button type="button" class="obs-chip policy-chip" data-policy="damped_sw" title="Damped survival-weighted base-stock">damped_sw</button>
            <button type="button" class="obs-chip policy-chip" data-policy="sla_pb" title="Window SLA Poisson-binomial fast path">sla_pb</button>
            <button type="button" class="obs-chip policy-chip" data-policy="sla_mc" title="Window SLA Monte Carlo oracle">sla_mc</button>
            <button type="button" class="obs-chip policy-chip" data-policy="constant" title="Constant order">constant</button>
          </div>
        </div>
        <!-- base_stock policy chip blocked: no backend ActPolicy variant yet (ADR 0117). -->
        <!-- rollout chip + budgets hidden in UI; ControllerControlsState defaults still pass through act. -->
        <label class="field">
          ${fieldLabelHtml(
            "n_particles",
            "How many particles the filter uses to track freshness belief. More particles give a smoother belief at the cost of more compute.",
            { valueId: "n_particles" },
          )}
          <input type="number" id="n_particles" min="16" max="2000" step="16" />
        </label>
        <label class="field">
          ${fieldLabelHtml(
            "Autopilot interval (ms)",
            "How often Autopilot's timer fires another order-and-advance step. A shorter interval only runs the episode faster — it doesn't change what the controller decides.",
            { valueId: "intervalMs" },
          )}
          <input type="number" id="intervalMs" min="50" max="10000" step="50" />
        </label>
        ${autopilotChartGroup()}
      </div>
    </div>
  `;

  let controllerState: ControllerControlsState = { ...initialController };

  function syncAlphaRhoAvailability(policy: ControllerPolicy): void {
    const disabled = policy === "constant";
    for (const id of ["alpha", "rho"] as const) {
      const input = root.querySelector(`#${id}`) as HTMLInputElement | null;
      const field = root.querySelector(`#${id}-field`) as HTMLElement | null;
      if (input) input.disabled = disabled;
      if (field) field.style.opacity = disabled ? "0.45" : "";
    }
    const hint = root.querySelector("#alpha-rho-disabled-hint") as HTMLElement | null;
    if (hint) hint.hidden = !disabled;
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
    syncAlphaRhoAvailability(s.policy);
    const alphaEl = root.querySelector("#alpha") as HTMLInputElement | null;
    const rhoEl = root.querySelector("#rho") as HTMLInputElement | null;
    const alphaLabel = root.querySelector("#val-alpha") as HTMLElement | null;
    const rhoLabel = root.querySelector("#val-rho") as HTMLElement | null;
    if (alphaEl) alphaEl.value = String(s.alpha);
    if (rhoEl) rhoEl.value = String(s.rho);
    if (alphaLabel) alphaLabel.textContent = s.alpha.toFixed(2);
    if (rhoLabel) rhoLabel.textContent = s.rho.toFixed(2);
    for (const id of ["n_particles", "intervalMs"] as const) {
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

  for (const id of ["alpha", "rho"] as const) {
    const el = root.querySelector(`#${id}`) as HTMLInputElement;
    el.addEventListener("input", () => {
      const value = Number(el.value);
      const label = root.querySelector(`#val-${id}`) as HTMLElement | null;
      if (label) {
        label.textContent = value.toFixed(2);
      }
      controllerState = { ...controllerState, [id]: value };
      cb.onControllerChange?.({ [id]: value });
    });
  }

  for (const id of ["n_particles", "intervalMs"] as const) {
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
