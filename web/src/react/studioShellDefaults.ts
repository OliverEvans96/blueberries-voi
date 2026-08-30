import { scheduleFromConfig } from "../calendar/weekCalendar";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";

/** Default config for synchronous studio shell placeholders before WASM init. */
export const STUDIO_SHELL_DEFAULT_CONFIG = DEFAULT_SIM_CONFIG;

export const STUDIO_SHELL_DEFAULT_SCHEDULE = scheduleFromConfig(
  STUDIO_SHELL_DEFAULT_CONFIG,
);

export const STUDIO_SHELL_DEFAULT_VM = {
  episode_day: 0,
  window_days: STUDIO_SHELL_DEFAULT_CONFIG.window_days,
  config: STUDIO_SHELL_DEFAULT_CONFIG,
};

/** Default order qty snapped to case size (matches initStudio snapOrder(24)). */
export const STUDIO_SHELL_DEFAULT_ORDER_QTY = 24;

/**
 * Floor for OperatorBar order-q slider max (`#order-range`).
 * SLA stockout chart x-domain is fixed to `[0, ORDER_Q_SLIDER_MIN_MAX]`.
 */
export const ORDER_Q_SLIDER_MIN_MAX = 160;
