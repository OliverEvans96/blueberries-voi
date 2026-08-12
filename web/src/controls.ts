import type {
  ArrivalProduct,
  Economics,
  ObsScenario,
  SimConfig,
  ViewModel,
} from "./types";
import type { SectionId } from "./sections";

export type ControlsCallbacks = {
  onOrderChange: (qty: number) => void;
  onAdvance: () => void;
  onReset: () => void;
  onEconomicsChange: (partial: Partial<Economics>) => void;
  onConfigChange: (partial: Partial<SimConfig>) => void;
};

export type ControlsState = {
  orderQty: number;
  economics: Economics;
  config: SimConfig;
  configDirty: boolean;
  episodeDay: number;
  pendingOrder: number;
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
  cb: Pick<ControlsCallbacks, "onOrderChange" | "onAdvance" | "onReset">,
): {
  update: (s: ControlsState) => void;
  setOrderFromCaseChange: (qty: number, caseSize: number) => void;
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
      <div class="btn-row">
        <button type="button" class="btn-advance" id="btn-advance">Advance day</button>
        <button type="button" class="btn-reset" id="btn-reset">Reset episode</button>
      </div>
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
  let caseSize = initial.config.case_size;

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

  orderRange.addEventListener("input", () => setOrder(Number(orderRange.value)));
  orderNum.addEventListener("change", () => setOrder(Number(orderNum.value)));
  (root.querySelector("#btn-advance") as HTMLButtonElement).addEventListener(
    "click",
    () => cb.onAdvance(),
  );
  (root.querySelector("#btn-reset") as HTMLButtonElement).addEventListener(
    "click",
    () => cb.onReset(),
  );

  syncOrderInputs(initial.orderQty, initial.config.case_size);
  meta.textContent = `Episode day ${initial.episodeDay} · pending inbound ${initial.pendingOrder} units`;
  dirtyBanner.hidden = !initial.configDirty;

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
  };
}

/** Section-specific knobs — one block visible at a time. */
export function mountSectionControls(
  root: HTMLElement,
  initial: ControlsState,
  cb: Pick<ControlsCallbacks, "onEconomicsChange" | "onConfigChange">,
  onCaseSizeChange?: (caseSize: number) => void,
): { update: (s: ControlsState) => void; showSection: (id: SectionId) => void } {
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
            <button type="button" class="obs-chip" data-obs="P0" title="Noisy / weak obs">P0</button>
            <button type="button" class="obs-chip" data-obs="P1" title="Standard obs">P1</button>
            <button type="button" class="obs-chip" data-obs="P2" title="Sharp / informative obs">P2</button>
          </div>
        </div>
      </div>
    </div>
  `;

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
    root.querySelectorAll<HTMLButtonElement>(".arrival-chip").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.arrival === c.arrival_product);
    });
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
      cb.onConfigChange({ obs_scenario: btn.dataset.obs as ObsScenario });
    });
  });

  root.querySelectorAll<HTMLButtonElement>(".arrival-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      cb.onConfigChange({
        arrival_product: btn.dataset.arrival as ArrivalProduct,
      });
    });
  });

  syncEconomics(initial.economics);
  syncConfig(initial.config);

  return {
    update(s) {
      syncEconomics(s.economics);
      syncConfig(s.config);
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
