/** Studio presentation flag: reveal sim truth overlays (ADR 0122). */

export const SHOW_TRUTH_STORAGE_KEY = "blueberries-voi-studio-show-truth";

export function loadShowTruth(): boolean {
  try {
    const raw = localStorage.getItem(SHOW_TRUTH_STORAGE_KEY);
    return raw === "true";
  } catch {
    return false;
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
