import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  getInfoTipPortalRoot,
  positionInfoTipBubble,
} from "../infoTipPortal";
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
 * Small hover/focus info glyph with a portaled tooltip bubble (T-161).
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
/** True on a device with no real hover (touch) — where tap must substitute
 * for the hover/focus that already opens the tip on desktop. */
function hasNoHover(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(hover: none)").matches
  );
}

export function InfoTip({ children, alignEnd, openUp }: InfoTipProps) {
  const bubbleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const className = [
    "info-tip",
    alignEnd && "info-tip--align-end",
    openUp && "info-tip--up",
  ]
    .filter(Boolean)
    .join(" ");

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    const bubble = bubbleRef.current;
    if (trigger && bubble && open) {
      positionInfoTipBubble(trigger, bubble, { alignEnd, openUp });
    }
  }, [open, alignEnd, openUp]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const onReflow = () => updatePosition();
    window.addEventListener("scroll", onReflow, true);
    window.addEventListener("resize", onReflow);
    return () => {
      window.removeEventListener("scroll", onReflow, true);
      window.removeEventListener("resize", onReflow);
    };
  }, [open, updatePosition]);

  // Tap-to-toggle for touch devices, which have no real hover state to open
  // the tip and no "leave" event to close it. Closing on an outside tap
  // covers both the tap-opened case and (harmlessly) the hover-opened one.
  useEffect(() => {
    if (!open) return;
    const onOutside = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (triggerRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onOutside);
    return () => document.removeEventListener("pointerdown", onOutside);
  }, [open]);

  const portalRoot = getInfoTipPortalRoot();
  const bubble =
    open && portalRoot
      ? createPortal(
          <span
            id={bubbleId}
            ref={bubbleRef}
            className={[
              "info-tip-bubble",
              "info-tip-bubble--portaled",
              "info-tip-bubble--visible",
              alignEnd && "info-tip--align-end",
              openUp && "info-tip--up",
            ]
              .filter(Boolean)
              .join(" ")}
            role="tooltip"
          >
            {children}
          </span>,
          portalRoot,
        )
      : null;

  return (
    <span className={className}>
      <button
        type="button"
        ref={triggerRef}
        className="info-tip-trigger"
        aria-label="More information"
        aria-describedby={bubbleId}
        onMouseEnter={() => {
          if (!hasNoHover()) setOpen(true);
        }}
        onMouseLeave={() => {
          if (!hasNoHover()) setOpen(false);
        }}
        onFocus={() => {
          if (!hasNoHover()) setOpen(true);
        }}
        onBlur={() => {
          if (!hasNoHover()) setOpen(false);
        }}
        onClick={() => {
          // Hover/focus already open this on desktop; only toggle here on a
          // device with no real hover, so a mouse click doesn't fight hover.
          if (!hasNoHover()) return;
          setOpen((wasOpen) => !wasOpen);
        }}
      >
        i
      </button>
      {bubble}
    </span>
  );
}
