import "./styles/infoTip.css";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export type InfoTipHtmlOpts = {
  /** Right-align the bubble — for triggers near a panel's right edge. */
  alignEnd?: boolean;
  /** Open the bubble upward — for triggers near the bottom of a panel. */
  openUp?: boolean;
};

let nextBubbleId = 0;

/**
 * HTML-string counterpart to `InfoTip.tsx` for the vanilla template-string
 * DOM built by `mountSectionControlsDom` (controls.ts) — same markup and
 * `styles/infoTip.css` classes, so both render identically (T-161).
 *
 * The trigger's accessible NAME is the fixed generic string "More
 * information"; the body is exposed via `aria-describedby` instead — see
 * the longer comment in InfoTip.tsx for why (it keeps the tooltip body from
 * colliding with name-based queries/assistive-tech lookups aimed at the
 * control the tooltip sits next to).
 */
export function infoTipHtml(text: string, opts: InfoTipHtmlOpts = {}): string {
  const safe = escapeHtml(text);
  const bubbleId = `info-tip-bubble-${nextBubbleId++}`;
  const className = [
    "info-tip",
    opts.alignEnd && "info-tip--align-end",
    opts.openUp && "info-tip--up",
  ]
    .filter(Boolean)
    .join(" ");
  return `<span class="${className}"><button type="button" class="info-tip-trigger" aria-label="More information" aria-describedby="${bubbleId}">i</button><span id="${bubbleId}" class="info-tip-bubble" role="tooltip">${safe}</span></span>`;
}
