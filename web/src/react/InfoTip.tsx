import { useId } from "react";
import "../styles/infoTip.css";

export type InfoTipProps = {
  /** Tooltip body — one sentence to one short paragraph. */
  children: string;
  /** Right-align the bubble — for triggers near a panel's right edge. */
  alignEnd?: boolean;
  /** Open the bubble upward — for triggers near the bottom of a panel. */
  openUp?: boolean;
};

/**
 * Small hover/focus info glyph with a CSS-only tooltip bubble (T-161).
 * Mirrors the markup `infoTipHtml` renders for the vanilla tuning-dock
 * controls, so both share `styles/infoTip.css`.
 *
 * The trigger's accessible NAME is a fixed generic string ("More
 * information") rather than the tooltip body, and the body is exposed via
 * `aria-describedby` instead — every other interactive element already has
 * its own accessible name (a heading, a button's label, a group's
 * aria-label), and those names are exactly what test queries and screen
 * readers key off of. Echoing that same text into the info-tip trigger's
 * name made it a duplicate match for `getByRole(..., { name })` /
 * `getByLabelText(...)` queries anywhere the tooltip body happened to
 * mention the nearby control's own name (e.g. "press Reset to..." next to
 * the Reset button).
 */
export function InfoTip({ children, alignEnd, openUp }: InfoTipProps) {
  const bubbleId = useId();
  const className = [
    "info-tip",
    alignEnd && "info-tip--align-end",
    openUp && "info-tip--up",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={className}>
      <button
        type="button"
        className="info-tip-trigger"
        aria-label="More information"
        aria-describedby={bubbleId}
      >
        i
      </button>
      <span id={bubbleId} className="info-tip-bubble" role="tooltip">
        {children}
      </span>
    </span>
  );
}
