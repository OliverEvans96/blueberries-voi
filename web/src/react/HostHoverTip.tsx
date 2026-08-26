import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type ReactElement,
} from "react";
import { createPortal } from "react-dom";
import {
  positionInfoTipBubble,
  resolveInfoTipPortalTarget,
} from "../infoTipPortal";
import "../styles/infoTip.css";

export type HostHoverTipProps = {
  /** Tooltip body — one sentence to one short paragraph. */
  tip: string;
  /** Right-align the bubble — for triggers near a panel's right edge. */
  alignEnd?: boolean;
  /** Open the bubble upward — for triggers near the bottom of a panel. */
  openUp?: boolean;
  children: ReactElement<{
    onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
    onMouseLeave?: (event: MouseEvent<HTMLElement>) => void;
    onFocus?: (event: FocusEvent<HTMLElement>) => void;
    onBlur?: (event: FocusEvent<HTMLElement>) => void;
  }>;
};

/**
 * Tooltip on host hover/focus — no separate "i" glyph. The host keeps its own
 * accessible name; the tip is exposed via `aria-describedby`.
 */
export function HostHoverTip({
  tip,
  alignEnd,
  openUp,
  children,
}: HostHoverTipProps) {
  const bubbleId = useId();
  const hostRef = useRef<HTMLElement | null>(null);
  const bubbleRef = useRef<HTMLSpanElement | null>(null);
  const [open, setOpen] = useState(false);

  const updatePosition = useCallback(() => {
    const host = hostRef.current;
    const bubble = bubbleRef.current;
    if (host && bubble && open) {
      positionInfoTipBubble(host, bubble, { alignEnd, openUp });
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

  const setHostRef = (node: HTMLElement | null) => {
    hostRef.current = node;
  };

  const child = isValidElement(children)
    ? cloneElement(children, {
        ref: setHostRef,
        "aria-describedby": bubbleId,
        onMouseEnter: (event: MouseEvent<HTMLElement>) => {
          children.props.onMouseEnter?.(event);
          setOpen(true);
        },
        onMouseLeave: (event: MouseEvent<HTMLElement>) => {
          children.props.onMouseLeave?.(event);
          setOpen(false);
        },
        onFocus: (event: FocusEvent<HTMLElement>) => {
          children.props.onFocus?.(event);
          setOpen(true);
        },
        onBlur: (event: FocusEvent<HTMLElement>) => {
          children.props.onBlur?.(event);
          setOpen(false);
        },
      } as Record<string, unknown>)
    : children;

  const portalRoot = open ? resolveInfoTipPortalTarget(hostRef.current) : null;
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
            {tip}
          </span>,
          portalRoot,
        )
      : null;

  return (
    <>
      {child}
      {bubble}
    </>
  );
}
