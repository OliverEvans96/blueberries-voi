/** Studio presentation flag: reveal sim truth overlays (ADR 0125). */

export const SHOW_TRUTH_STORAGE_KEY = "bv-studio:show-truth";

export function loadShowTruth(): boolean {
  try {
    const raw = localStorage.getItem(SHOW_TRUTH_STORAGE_KEY);
    // Default to true for cockpit grid to show truth overlay by default
    return raw !== "false";
  } catch {
    return true;
  }
}

export function saveShowTruth(value: boolean): void {
  try {
    localStorage.setItem(SHOW_TRUTH_STORAGE_KEY, value ? "true" : "false");
  } catch {
    /* ignore */
  }
}

export function truthLots<T>(show: boolean, lots: readonly T[]): T[] {
  return show ? [...lots] : [];
}
