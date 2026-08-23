import {
  renderDailyDemand,
  renderDemandForecast,
} from "../charts/demandDist";
import type { ViewModelProjector } from "./projector";
import type { ScheduleWire } from "./types";

export type DemandPreviewBindOpts = {
  chartHost: HTMLElement;
  forecastHost?: HTMLElement;
  slider: HTMLInputElement;
  vmSlider?: HTMLInputElement;
  projector: ViewModelProjector;
  schedule?: ScheduleWire | null;
};

function readDemandMu(slider: HTMLInputElement, fallback: number): number {
  const v = Number(slider.value);
  return Number.isFinite(v) ? v : fallback;
}

function readDemandVm(vmSlider: HTMLInputElement | undefined, fallback: number): number {
  if (!vmSlider) return fallback;
  const v = Number(vmSlider.value);
  return Number.isFinite(v) ? v : fallback;
}

/** Wire demand_mu / demand_vm sliders to staged DOW preview (no engine Reset). */
export function bindDemandSliderPreview(opts: DemandPreviewBindOpts): void {
  const { chartHost, forecastHost, slider, vmSlider, projector } = opts;

  const renderPreview = () => {
    const vm = projector.getViewModel();
    const demand_mu = readDemandMu(slider, vm.config.demand_mu);
    const demand_vm = readDemandVm(vmSlider, vm.config.demand_vm);
    const summary = projector.demandSummaryFromConfig({
      demand_mu,
      demand_vm,
    });
    requestAnimationFrame(() => {
      renderDailyDemand(chartHost, vm.history, 160);
      if (forecastHost) {
        renderDemandForecast(
          forecastHost,
          vm.history,
          summary,
          vm.episode_day,
          demand_vm,
          160,
        );
      }
    });
  };

  slider.addEventListener("input", renderPreview);
  vmSlider?.addEventListener("input", renderPreview);
}
