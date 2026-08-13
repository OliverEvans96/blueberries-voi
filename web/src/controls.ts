import type {
  ArrivalProduct,
  Economics,
  ScenarioId,
  SimConfig,
  ViewModel,
} from "./types";
import type { SectionId } from "./sections";
import { defaultIntervalMsForPolicy } from "./autopilotLoop";

/** Locked chip copy (ADR 0110 / T-089). */
const SCENARIO_COPY: Record<
  ScenarioId,
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
    description: "Narrows the arrival-age prior only.",
  },
  F2: {
    title: "Age at receipt",
    description: "Measured age at receipt plus rich lot maps.",
  },
};

export type ControlsCallbacks = {
  onOrderChange: (qty: number) => void;
  onAdvance: () => void;
  onReset: () => void;
  onAutopilotPlay?: () => void;
  onAutopilotPause?: () => void;
  onEconomicsChange: (partial: Partial<Economics>) => void;
  onConfigChange: (partial: Partial<SimConfig>) => void;
  onControllerChange?: (partial: Partial<ControllerControlsState>) => void;
};

export type ControlsState = {
  orderQty: number;
  economics: Economics;
  config: SimConfig;
  configDirty: boolean;
  episodeDay: number;
  pendingOrder: number;
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

function snap(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  const cs = Math.max(1, Math.round(caseSize));
  return Math.round(qty / cs) * cs;
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
  { id: "beta", label: "β (Weibull shape)", min: 0.8, max: 4, step: 0.1, format: (v) => v.toFixed(1), group: "physics" },
  { id: "eta_ref", label: "η_ref (days)", min: 4, max: 28, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "q10", label: "Q10", min: 1, max: 5, step: 0.1, format: (v) => v.toFixed(1), group: "physics" },
  { id: "t_ref_c", label: "T_ref (°C)", min: -2, max: 8, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "t_store_c", label: "T_store (°C)", min: 0, max: 12, step: 0.5, format: (v) => v.toFixed(1), group: "physics" },
  { id: "sigma", label: "σ (picking)", min: 0, max: 1.5, step: 0.05, format: (v) => v.toFixed(2), group: "physics" },
  { id: "demand_mu", label: "demand μ", min: 5, max: 80, step: 1, format: (v) => v.toFixed(0), group: "demand" },
  { id: "demand_vm", label: "demand V/M", min: 1.1, max: 5, step: 0.1, format: (v) => v.toFixed(1), group: "demand" },
  { id: "case_size", label: "case size", min: 1, max: 24, step: 1, format: (v) => String(Math.round(v)), group: "logistics" },
  { id: "base_stock", label: "base-stock target", min: 8, max: 160, step: 8, format: (v) => String(Math.round(v)), group: "logistics" },
  { id: "starting_inv", label: "starting inventory", min: 0, max: 160, step: 8, format: (v) => String(Math.round(v)), group: "logistics" },
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
  {
    id: "f2a_transit_sd",
    label: "F2a transit SD",
    min: 0.1,
    max: 2,
    step: 0.05,
    format: (v) => v.toFixed(2),
    group: "arrival",
  },
  {
    id: "sensor_sigma",
    label: "sensor σ (age)",
    min: 0,
    max: 1.5,
    step: 0.05,
    format: (v) => v.toFixed(2),
    group: "arrival",
  },
  { id: "seed", label: "seed", min: 1, max: 9999, step: 1, format: (v) => String(Math.round(v)), group: "episode" },
];

function sliderHtml(spec: SliderSpec): string {
  return `
    <label class="field">
      <span class="field-label">${spec.label} <span id="val-${spec.id}"></span></span>
      <input type="range" id="${spec.id}" min="${spec.min}" max="${spec.max}" step="${spec.step}" />
    </label>
  `;
}

/** Persistent order / advance / reset chrome — always visible. */
export function mountPlayChrome(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<
    ControlsCallbacks,
    | "onOrderChange"
    | "onAdvance"
    | "onReset"
    | "onAutopilotPlay"
    | "onAutopilotPause"
  >,
): {
  update: (s: ControlsState) => void;
  setOrderFromCaseChange: (qty: number, caseSize: number) => void;
  setAutopilotRunning: (running: boolean) => void;
} {
  root.innerHTML = `
    <div class="play-chrome">
      <label class="field">
        <span class="field-label">Order quantity <em id="case-em">(case ${initial.config.case_size})</em></span>
        <div class="order-row">
          <input type="range" id="order-range" min="0" max="160" step="${initial.config.case_size}" value="${initial.orderQty}" />
          <input type="number" id="order-num" min="0" max="320" step="${initial.config.case_size}" value="${initial.orderQty}" />
        </div>
      </label>
      <div class="btn-row btn-row-play">
        <button type="button" class="btn-advance" id="btn-advance">Advance day</button>
        <button type="button" class="btn-autopilot" id="btn-autopilot-play" aria-label="Autopilot Play">Autopilot Play</button>
        <button type="button" class="btn-autopilot" id="btn-autopilot-pause" aria-label="Autopilot Pause" disabled>Autopilot Pause</button>
        <button type="button" class="btn-reset" id="btn-reset">Reset episode</button>
      </div>
      <p class="hint" id="autopilot-hint">
        While Autopilot is running, Advance is disabled — pause Autopilot to step manually.
      </p>
      <div class="meta-line" id="order-meta"></div>
      <div class="dirty-banner" id="dirty-banner" hidden>
        Config edited — new days use it; <strong>Reset</strong> regenerates history from seed.
      </div>
    </div>
  `;

  const orderRange = root.querySelector("#order-range") as HTMLInputElement;
  const orderNum = root.querySelector("#order-num") as HTMLInputElement;
  const caseEm = root.querySelector("#case-em") as HTMLElement;
  const meta = root.querySelector("#order-meta") as HTMLElement;
  const dirtyBanner = root.querySelector("#dirty-banner") as HTMLElement;
  const btnAdvance = root.querySelector("#btn-advance") as HTMLButtonElement;
  const btnAutopilotPlay = root.querySelector(
    "#btn-autopilot-play",
  ) as HTMLButtonElement;
  const btnAutopilotPause = root.querySelector(
    "#btn-autopilot-pause",
  ) as HTMLButtonElement;
  let caseSize = initial.config.case_size;
  let autopilotRunning = false;

  function syncOrderInputs(qty: number, cs: number): void {
    caseSize = cs;
    const snapped = snap(qty, cs);
    orderRange.step = String(cs);
    orderNum.step = String(cs);
    orderRange.max = String(Math.max(160, cs * 20));
    orderRange.value = String(snapped);
    orderNum.value = String(snapped);
    caseEm.textContent = `(case ${cs})`;
  }

  function setOrder(raw: number): void {
    const snapped = snap(raw, caseSize);
    syncOrderInputs(snapped, caseSize);
    cb.onOrderChange(snapped);
  }

  function setAutopilotRunning(running: boolean): void {
    autopilotRunning = running;
    // Advance disabled while Autopilot runs (T-100 open question pick).
    btnAdvance.disabled = running;
    btnAutopilotPlay.disabled = running;
    btnAutopilotPause.disabled = !running;
  }

  orderRange.addEventListener("input", () => setOrder(Number(orderRange.value)));
  orderNum.addEventListener("change", () => setOrder(Number(orderNum.value)));
  btnAdvance.addEventListener("click", () => {
    if (autopilotRunning) return;
    cb.onAdvance();
  });
  btnAutopilotPlay.addEventListener("click", () => {
    cb.onAutopilotPlay?.();
  });
  btnAutopilotPause.addEventListener("click", () => {
    cb.onAutopilotPause?.();
  });
  (root.querySelector("#btn-reset") as HTMLButtonElement).addEventListener(
    "click",
    () => cb.onReset(),
  );

  syncOrderInputs(initial.orderQty, initial.config.case_size);
  meta.textContent = `Episode day ${initial.episodeDay} · pending inbound ${initial.pendingOrder} units`;
  dirtyBanner.hidden = !initial.configDirty;
  setAutopilotRunning(false);

  return {
    update(s) {
      syncOrderInputs(s.orderQty, s.config.case_size);
      meta.textContent = `Episode day ${s.episodeDay} · pending inbound ${s.pendingOrder} units`;
      dirtyBanner.hidden = !s.configDirty;
    },
    setOrderFromCaseChange(qty, cs) {
      syncOrderInputs(qty, cs);
      cb.onOrderChange(snap(qty, cs));
    },
    setAutopilotRunning,
  };
}

/** Section-specific knobs — one block visible at a time. */
export function mountSectionControls(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<
    ControlsCallbacks,
    "onEconomicsChange" | "onConfigChange" | "onControllerChange"
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
      <div class="controls-block" data-section="play">
        <p class="hint">Seed reshapes the episode on Reset. Advance to step the store.</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "episode").map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="pricing" hidden>
        <p class="hint">Recompute P&amp;L from stored unit history — no re-sim.</p>
        ${PRICE_SLIDERS.map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="physics" hidden>
        <p class="hint">Weibull spoilage + Q10 temperature shift (fake).</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "physics").map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="demand" hidden>
        <p class="hint">Negative-binomial-ish demand from mean and V/M.</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "demand").map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="logistics" hidden>
        <p class="hint">Case snap and stocking targets for daily refill.</p>
        ${CONFIG_SLIDERS.filter((s) => s.group === "logistics").map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="arrival" hidden>
        <p class="hint">
          MOD-11/18/21: arrival age from transit mix + Arrhenius shift.
          Daily lead time stays 1 (no pipeline Gantt).
        </p>
        <div class="field">
          <span class="field-label">Arrival product (MOD-21)</span>
          <div class="chip-row" id="arrival-chips" role="group" aria-label="Arrival product">
            <button type="button" class="obs-chip arrival-chip" data-arrival="abdella_all" title="Bootstrap all six Abdella shipments">All six</button>
            <button type="button" class="obs-chip arrival-chip" data-arrival="long_haul" title="CA→East long-haul only">Long-haul</button>
            <button type="button" class="obs-chip arrival-chip" data-arrival="short_haul" title="FL short-haul only (tight)">Short-haul</button>
          </div>
        </div>
        ${CONFIG_SLIDERS.filter((s) => s.group === "arrival").map(sliderHtml).join("")}
      </div>
      <div class="controls-block" data-section="belief" hidden>
        <p class="hint">Observation richness changes belief blur vs truth lots.</p>
        <div class="field">
          <span class="field-label">Observation scenario</span>
          <div class="chip-row" id="obs-chips" role="group" aria-label="Observation scenario">
            <button type="button" class="obs-chip" data-obs="P0" title="Books only">P0</button>
            <button type="button" class="obs-chip" data-obs="P1" title="Shrink gun">P1</button>
            <button type="button" class="obs-chip" data-obs="F1" title="Lot ID at POS">F1</button>
            <button type="button" class="obs-chip" data-obs="F1s" title="Lot ID on shrink">F1s</button>
            <button type="button" class="obs-chip" data-obs="F2a" title="Pack date on ASN">F2a</button>
            <button type="button" class="obs-chip" data-obs="F2" title="Age at receipt">F2</button>
          </div>
          <div class="obs-scenario-copy" id="obs-scenario-copy">
            <strong class="obs-scenario-title" id="obs-scenario-title"></strong>
            <p class="obs-scenario-desc" id="obs-scenario-desc"></p>
          </div>
        </div>
      </div>
      <div class="controls-block" data-section="controller" hidden>
        <p class="hint">
          Policy and rollout budgets feed Autopilot / act — physics still needs Reset.
        </p>
        <div class="field">
          <span class="field-label">Policy</span>
          <div class="chip-row" id="policy-chips" role="group" aria-label="Controller policy">
            <button type="button" class="obs-chip policy-chip" data-policy="damped_sw" title="Damped survival-weighted base-stock">damped_sw</button>
            <button type="button" class="obs-chip policy-chip" data-policy="rollout" title="One-step rollout">rollout</button>
            <button type="button" class="obs-chip policy-chip" data-policy="constant" title="Constant order">constant</button>
          </div>
        </div>
        <label class="field">
          <span class="field-label">α <span id="val-alpha"></span></span>
          <input type="range" id="alpha" min="0.5" max="0.99" step="0.01" />
        </label>
        <label class="field">
          <span class="field-label">ρ <span id="val-rho"></span></span>
          <input type="range" id="rho" min="0.1" max="1" step="0.05" />
        </label>
        <label class="field">
          <span class="field-label">H (horizon) <span id="val-H"></span></span>
          <input type="number" id="H" min="1" max="56" step="1" />
        </label>
        <label class="field">
          <span class="field-label">n_rollout_paths <span id="val-n_rollout_paths"></span></span>
          <input type="number" id="n_rollout_paths" min="1" max="64" step="1" />
        </label>
        <label class="field">
          <span class="field-label">candidate_case_radius <span id="val-candidate_case_radius"></span></span>
          <input type="number" id="candidate_case_radius" min="0" max="8" step="1" />
        </label>
        <label class="field">
          <span class="field-label">n_particles <span id="val-n_particles"></span></span>
          <input type="number" id="n_particles" min="16" max="2000" step="16" />
        </label>
        <label class="field">
          <span class="field-label">Autopilot interval (ms) <span id="val-intervalMs"></span></span>
          <input type="number" id="intervalMs" min="50" max="10000" step="50" />
        </label>
      </div>
    </div>
  `;

  let controllerState: ControllerControlsState = { ...initialController };

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

  function syncConfig(c: SimConfig): void {
    for (const spec of CONFIG_SLIDERS) {
      const v = c[spec.id as keyof SimConfig];
      if (typeof v === "number") syncSlider(spec, v);
    }
    root.querySelectorAll<HTMLButtonElement>(".obs-chip[data-obs]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.obs === c.obs_scenario);
    });
    const copy = SCENARIO_COPY[c.obs_scenario];
    const titleEl = root.querySelector("#obs-scenario-title") as HTMLElement | null;
    const descEl = root.querySelector("#obs-scenario-desc") as HTMLElement | null;
    if (titleEl && copy) titleEl.textContent = copy.title;
    if (descEl && copy) descEl.textContent = copy.description;
    root.querySelectorAll<HTMLButtonElement>(".arrival-chip").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.arrival === c.arrival_product);
    });
  }

  function syncController(s: ControllerControlsState): void {
    controllerState = { ...s };
    root.querySelectorAll<HTMLButtonElement>(".policy-chip").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.policy === s.policy);
    });
    const alphaEl = root.querySelector("#alpha") as HTMLInputElement;
    const rhoEl = root.querySelector("#rho") as HTMLInputElement;
    alphaEl.value = String(s.alpha);
    rhoEl.value = String(s.rho);
    (root.querySelector("#val-alpha") as HTMLElement).textContent =
      s.alpha.toFixed(2);
    (root.querySelector("#val-rho") as HTMLElement).textContent = s.rho.toFixed(2);
    for (const id of [
      "H",
      "n_rollout_paths",
      "candidate_case_radius",
      "n_particles",
      "intervalMs",
    ] as const) {
      const el = root.querySelector(`#${id}`) as HTMLInputElement;
      el.value = String(s[id]);
      const label = root.querySelector(`#val-${id}`) as HTMLElement | null;
      if (label) label.textContent = String(s[id]);
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
      const value = Number(el.value);
      (root.querySelector(`#val-${spec.id}`) as HTMLElement).textContent =
        spec.format(value);
      cb.onConfigChange({ [spec.id]: value });
      if (spec.id === "case_size") onCaseSizeChange?.(Math.round(value));
    });
  }

  root.querySelectorAll<HTMLButtonElement>(".obs-chip[data-obs]").forEach((btn) => {
    btn.addEventListener("click", () => {
      cb.onConfigChange({ obs_scenario: btn.dataset.obs as ScenarioId });
    });
  });

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

  const alphaInput = root.querySelector("#alpha") as HTMLInputElement;
  alphaInput.addEventListener("input", () => {
    const alpha = Number(alphaInput.value);
    (root.querySelector("#val-alpha") as HTMLElement).textContent =
      alpha.toFixed(2);
    controllerState = { ...controllerState, alpha };
    cb.onControllerChange?.({ alpha });
  });
  const rhoInput = root.querySelector("#rho") as HTMLInputElement;
  rhoInput.addEventListener("input", () => {
    const rho = Number(rhoInput.value);
    (root.querySelector("#val-rho") as HTMLElement).textContent = rho.toFixed(2);
    controllerState = { ...controllerState, rho };
    cb.onControllerChange?.({ rho });
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
      syncConfig(s.config);
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
): ControlsState {
  return {
    orderQty,
    economics: vm.economics,
    config: vm.config,
    configDirty: vm.config_dirty,
    episodeDay: vm.episode_day,
    pendingOrder: vm.pending_order,
  };
}
