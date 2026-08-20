/** Minimum horizontal space (px) a single day-index tick label needs to avoid colliding with its neighbor. */
const MIN_TICK_SPACING_PX = 28;

/**
 * Thin day-index ticks to fit the available width, so density scales down as
 * episode length grows instead of capping out at a fixed "every other" rule.
 * Always keeps the last day so the axis doesn't lose its right edge.
 */
export function pickDayTicks(
  days: readonly number[],
  innerWidthPx: number,
): number[] {
  if (days.length <= 1) return [...days];
  const pxPerDay = innerWidthPx / days.length;
  const step = Math.max(1, Math.ceil(MIN_TICK_SPACING_PX / Math.max(pxPerDay, 1)));
  const picked = days.filter((_, i) => i % step === 0);
  const last = days[days.length - 1]!;
  // Anchor the true last day without appending a cramped extra tick: moving the
  // final stepped tick rightward can only widen (never shrink) its gap from the
  // tick before it.
  if (picked.length > 0) picked[picked.length - 1] = last;
  else picked.push(last);
  return picked;
}
