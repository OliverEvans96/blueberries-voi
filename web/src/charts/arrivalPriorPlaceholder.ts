/** Placeholder hatch for the arrival prior chart before lazy WASM wire arrives. */
export function renderArrivalPriorPlaceholder(
  container: HTMLElement,
  height = 160,
): void {
  container.replaceChildren();
  container.classList.add("chart-loading-shell", "chart-unavailable");
  container.style.minHeight = `${height}px`;
  const hatch = document.createElement("div");
  hatch.className = "chart-unavailable-hatch";
  hatch.setAttribute("aria-hidden", "true");
  container.appendChild(hatch);
}

/** Clear placeholder styling after the engine wire is rendered. */
export function clearArrivalPriorPlaceholder(container: HTMLElement): void {
  container.classList.remove("chart-loading-shell", "chart-unavailable");
  container.style.removeProperty("min-height");
}
