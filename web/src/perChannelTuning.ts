import type { ObsChannels } from "./types";

/**
 * Per-channel `damped_sw` `(alpha, rho)`, independently Ax-tuned against each
 * channel's own real closed-loop belief (particle filter at `n_particles=200`,
 * not the oracle belief a single shared retune would use) — see
 * `notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb`'s per-channel
 * section and `outputs/damped_sw_alpha_bo_per_channel.json`. Values below are
 * the K=30-seed, 25-trial-per-channel run (properly de-noised; an earlier
 * K=4-seed pass showed BO overfitting and was discarded — see
 * `.team/plans/2026-08-30-particle-filter-collapse-fix.md`).
 *
 * Regenerate this file by hand from `outputs/damped_sw_alpha_bo_per_channel.json`
 * whenever that notebook is re-run; there's no build-time sync (T-163-era
 * scripts copy fonts/CSS, not arbitrary data — see `scripts/copy-lib-assets.mjs`),
 * so keeping the values inline as a TS constant is what guarantees they reach
 * the published `@oliverevans96/blueberries-voi-studio` bundle (and from there
 * the personal-website embed) rather than depending on a runtime fetch of a
 * file that may not be copied into `dist-lib`.
 */
export type ChannelTuning = { alpha: number; rho: number };

export const PER_CHANNEL_TUNING: Record<string, ChannelTuning> = {
  "gsin|off|none": { alpha: 0.8071589220265128, rho: 1.394628748377438 },
  "gsin|off|pack_date": { alpha: 0.8442973276444823, rho: 1.2777455488434784 },
  "gsin|off|temperature_history": { alpha: 0.793295164558508, rho: 1.2963693999365884 },
  "gsin|on|none": { alpha: 0.6954157752332277, rho: 1.6260255076922476 },
  "gsin|on|pack_date": { alpha: 0.7819331431293843, rho: 1.3782009127639303 },
  "gsin|on|temperature_history": { alpha: 0.7960607826645429, rho: 1.3747979103936117 },
  "upc|off|none": { alpha: 0.6530923499888022, rho: 1.5911718315868328 },
  "upc|off|pack_date": { alpha: 0.8308848716092779, rho: 1.3994280218508455 },
  "upc|off|temperature_history": { alpha: 0.735492293554861, rho: 1.462916084653586 },
  "upc|on|none": { alpha: 0.7897616529555731, rho: 1.2505105594860244 },
  "upc|on|pack_date": { alpha: 0.8812298530063483, rho: 1.2789064276626447 },
  "upc|on|temperature_history": { alpha: 0.7960100194522467, rho: 1.5112963166894722 },
};

/** `ObsChannels` -> the exact key `PER_CHANNEL_TUNING` is indexed by. */
export function channelTuningKey(channels: ObsChannels): string {
  const waste = channels.scan_waste ? "on" : "off";
  return `${channels.code_type}|${waste}|${channels.delivery_history}`;
}

/**
 * Looks up the tuned `(alpha, rho)` for a channel combination. Falls back to
 * `upc|on|none` (Studio's own default channels, `DEFAULT_OBS_CHANNELS` in
 * `obsMask.ts`) if the combination is somehow missing — the table is meant to
 * cover the full 12-cell factorial (`code_type x scan_waste x delivery_history`),
 * so a miss here would indicate a real key-construction bug, not a legitimately
 * absent entry.
 */
export function tunedControllerFor(channels: ObsChannels): ChannelTuning {
  const key = channelTuningKey(channels);
  return (
    PER_CHANNEL_TUNING[key] ?? PER_CHANNEL_TUNING["upc|on|none"]!
  );
}
