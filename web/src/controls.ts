import type { Economics, ViewModel } from "./types";

export type ControlsCallbacks = {
  onOrderChange: (qty: number) => void;
  onAdvance: () => void;
  onEconomicsChange: (partial: Partial<Economics>) => void;
};

export type ControlsState = {
  orderQty: number;
  caseSize: number;
  economics: Economics;
  episodeDay: number;
  pendingOrder: number;
};

function snap(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  return Math.round(qty / caseSize) * caseSize;
}

export function mountControls(
  root: HTMLElement,
  initial: ControlsState,
  cb: ControlsCallbacks,
): { update: (s: ControlsState) => void } {
  root.innerHTML = `
    <div class="controls">
      <div class="controls-block">
        <div class="block-title">Ordering</div>
        <label class="field">
          <span class="field-label">Order quantity <em>(case ${initial.caseSize})</em></span>
          <div class="order-row">
            <input type="range" id="order-range" min="0" max="96" step="${initial.caseSize}" value="${initial.orderQty}" />
            <input type="number" id="order-num" min="0" max="192" step="${initial.caseSize}" value="${initial.orderQty}" />
          </div>
        </label>
        <button type="button" class="btn-advance" id="btn-advance">Advance day</button>
        <div class="meta-line" id="order-meta"></div>
      </div>
      <div class="controls-block">
        <div class="block-title">Pricing levers</div>
        <p class="hint">Recompute P&amp;L from stored unit history — no re-sim.</p>
        <label class="field">
          <span class="field-label">p_sell <span id="val-p_sell"></span></span>
          <input type="range" id="p_sell" min="1" max="10" step="0.1" />
        </label>
        <label class="field">
          <span class="field-label">c_unit <span id="val-c_unit"></span></span>
          <input type="range" id="c_unit" min="0.2" max="5" step="0.1" />
        </label>
        <label class="field">
          <span class="field-label">c_waste <span id="val-c_waste"></span></span>
          <input type="range" id="c_waste" min="0" max="5" step="0.1" />
        </label>
        <label class="field">
          <span class="field-label">c_stockout <span id="val-c_stockout"></span></span>
          <input type="range" id="c_stockout" min="0" max="8" step="0.1" />
        </label>
      </div>
    </div>
  `;

  const orderRange = root.querySelector("#order-range") as HTMLInputElement;
  const orderNum = root.querySelector("#order-num") as HTMLInputElement;
  const btn = root.querySelector("#btn-advance") as HTMLButtonElement;
  const meta = root.querySelector("#order-meta") as HTMLElement;

  const priceIds = ["p_sell", "c_unit", "c_waste", "c_stockout"] as const;

  function syncOrderInputs(qty: number, caseSize: number): void {
    const snapped = snap(qty, caseSize);
    orderRange.step = String(caseSize);
    orderNum.step = String(caseSize);
    orderRange.value = String(snapped);
    orderNum.value = String(snapped);
  }

  function syncEconomics(e: Economics): void {
    for (const id of priceIds) {
      const el = root.querySelector(`#${id}`) as HTMLInputElement;
      const label = root.querySelector(`#val-${id}`) as HTMLElement;
      el.value = String(e[id]);
      label.textContent = `$${e[id].toFixed(2)}`;
    }
  }

  function syncMeta(s: ControlsState): void {
    meta.textContent = `Episode day ${s.episodeDay} · pending inbound ${s.pendingOrder} units`;
  }

  function setOrder(raw: number, caseSize: number): void {
    const snapped = snap(raw, caseSize);
    syncOrderInputs(snapped, caseSize);
    cb.onOrderChange(snapped);
  }

  orderRange.addEventListener("input", () => {
    setOrder(Number(orderRange.value), Number(orderRange.step) || 12);
  });
  orderNum.addEventListener("change", () => {
    setOrder(Number(orderNum.value), Number(orderNum.step) || 12);
  });
  btn.addEventListener("click", () => cb.onAdvance());

  for (const id of priceIds) {
    const el = root.querySelector(`#${id}`) as HTMLInputElement;
    el.addEventListener("input", () => {
      const value = Number(el.value);
      (root.querySelector(`#val-${id}`) as HTMLElement).textContent =
        `$${value.toFixed(2)}`;
      cb.onEconomicsChange({ [id]: value });
    });
  }

  syncOrderInputs(initial.orderQty, initial.caseSize);
  syncEconomics(initial.economics);
  syncMeta(initial);

  return {
    update(s: ControlsState) {
      syncOrderInputs(s.orderQty, s.caseSize);
      syncEconomics(s.economics);
      syncMeta(s);
    },
  };
}

export function controlsFromVm(
  vm: ViewModel,
  orderQty: number,
): ControlsState {
  return {
    orderQty,
    caseSize: vm.case_size,
    economics: vm.economics,
    episodeDay: vm.episode_day,
    pendingOrder: vm.pending_order,
  };
}
