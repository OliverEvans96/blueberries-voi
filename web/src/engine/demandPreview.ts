import { renderDemandDist } from "../charts/demandDist";
import type { ViewModelProjector } from "./projector";
// ViewModelProjector.demandSummaryFromConfig is defined on projector.ts
import type { ScheduleWire } from "./types";

export type DemandPreviewBindOpts = {
  chartHost: HTMLElement;
  slider: HTMLInputElement;
  projector: ViewModelProjector;
  schedule?: ScheduleWire | null;
};

/** Wire demand_mu slider to staged DOW preview (no engine Reset). */
export function bindDemandSliderPreview(opts: DemandPreviewBindOpts): void {
  const { chartHost, slider, projector } = opts;

  const onInput = () => {
    const demand_mu = Number(slider.value);
    const vm = projector.getViewModel();
    const summary = projector.demandSummaryFromConfig({
      demand_mu,
      demand_vm: vm.config.demand_vm,
    });
    requestAnimationFrame(() => {
      renderDemandDist(chartHost, summary, opts.schedule ?? vm.schedule, 160);
    });
  };

  slider.addEventListener("input", onInput);
}
