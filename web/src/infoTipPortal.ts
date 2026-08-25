/** Shared fixed-position portal for info-tip bubbles (React + vanilla). */

export type InfoTipPositionOpts = {
  /** Right-align the bubble — for triggers near a panel's right edge. */
  alignEnd?: boolean;
  /** Open the bubble upward — for triggers near the bottom of a panel. */
  openUp?: boolean;
};

const GAP_PX = 7;

export function getInfoTipPortalRoot(): HTMLElement | null {
  return document.querySelector(".bv-studio-portal-root");
}

/** Position a bubble with `position: fixed` from a trigger's viewport rect. */
export function positionInfoTipBubble(
  trigger: Element,
  bubble: HTMLElement,
  opts: InfoTipPositionOpts = {},
): void {
  const triggerRect = trigger.getBoundingClientRect();
  bubble.style.position = "fixed";
  bubble.style.zIndex = "1000";
  bubble.style.maxWidth = "260px";

  const prevVisibility = bubble.style.visibility;
  bubble.style.visibility = "hidden";
  const bubbleRect = bubble.getBoundingClientRect();

  let top: number;
  if (opts.openUp) {
    top = triggerRect.top - bubbleRect.height - GAP_PX;
  } else {
    top = triggerRect.bottom + GAP_PX;
  }

  let left: number;
  if (opts.alignEnd) {
    left = triggerRect.right - bubbleRect.width;
  } else {
    left = triggerRect.left;
  }

  bubble.style.top = `${Math.round(top)}px`;
  bubble.style.left = `${Math.round(left)}px`;
  bubble.style.visibility = prevVisibility;
}

type ActiveVanillaTip = {
  trigger: HTMLElement;
  bubble: HTMLElement;
  restoreParent: HTMLElement;
  restoreNext: ChildNode | null;
  alignEnd: boolean;
  openUp: boolean;
};

let activeVanilla: ActiveVanillaTip | null = null;

function readVanillaOpts(wrapper: Element): Pick<InfoTipPositionOpts, "alignEnd" | "openUp"> {
  return {
    alignEnd: wrapper.classList.contains("info-tip--align-end"),
    openUp: wrapper.classList.contains("info-tip--up"),
  };
}

function repositionActiveVanilla(): void {
  if (!activeVanilla) return;
  positionInfoTipBubble(activeVanilla.trigger, activeVanilla.bubble, {
    alignEnd: activeVanilla.alignEnd,
    openUp: activeVanilla.openUp,
  });
}

function closeVanillaTip(): void {
  if (!activeVanilla) return;
  const { bubble, restoreParent, restoreNext } = activeVanilla;
  bubble.classList.remove("info-tip-bubble--portaled", "info-tip-bubble--visible");
  bubble.style.cssText = "";
  if (restoreNext) {
    restoreParent.insertBefore(bubble, restoreNext);
  } else {
    restoreParent.appendChild(bubble);
  }
  activeVanilla = null;
}

function openVanillaTip(trigger: HTMLElement): void {
  if (activeVanilla?.trigger === trigger) {
    repositionActiveVanilla();
    return;
  }
  closeVanillaTip();

  const wrapper = trigger.closest(".info-tip");
  if (!wrapper) return;
  const bubble = wrapper.querySelector<HTMLElement>(".info-tip-bubble");
  if (!bubble) return;

  const portal = getInfoTipPortalRoot();
  if (!portal) return;

  const { alignEnd, openUp } = readVanillaOpts(wrapper);
  const restoreParent = bubble.parentElement;
  if (!restoreParent) return;

  activeVanilla = {
    trigger,
    bubble,
    restoreParent,
    restoreNext: bubble.nextSibling,
    alignEnd: Boolean(alignEnd),
    openUp: Boolean(openUp),
  };

  portal.appendChild(bubble);
  bubble.classList.add("info-tip-bubble--portaled", "info-tip-bubble--visible");
  positionInfoTipBubble(trigger, bubble, { alignEnd, openUp });
}

function isInfoTipTrigger(target: EventTarget | null): target is HTMLElement {
  return (
    target instanceof HTMLElement &&
    target.classList.contains("info-tip-trigger")
  );
}

function onPointerOver(event: Event): void {
  const pointer = event as PointerEvent;
  const from = pointer.relatedTarget;
  const trigger = isInfoTipTrigger(pointer.target)
    ? pointer.target
    : null;
  if (!trigger) return;
  if (from instanceof Node && trigger.contains(from)) return;
  openVanillaTip(trigger);
}

function onPointerOut(event: Event): void {
  const pointer = event as PointerEvent;
  const trigger = isInfoTipTrigger(pointer.target)
    ? pointer.target
    : activeVanilla?.trigger ?? null;
  if (!trigger || activeVanilla?.trigger !== trigger) return;
  const to = pointer.relatedTarget;
  if (to instanceof Node && trigger.contains(to)) return;
  closeVanillaTip();
}

function onFocusIn(event: Event): void {
  const focus = event as FocusEvent;
  const trigger = (focus.target as Element | null)?.closest<HTMLElement>(
    ".info-tip-trigger",
  );
  if (!trigger) return;
  openVanillaTip(trigger);
}

function onFocusOut(event: Event): void {
  const focus = event as FocusEvent;
  if (!activeVanilla) return;
  const next = focus.relatedTarget;
  if (
    next instanceof Node &&
    (activeVanilla.trigger.contains(next) ||
      activeVanilla.bubble.contains(next))
  ) {
    return;
  }
  closeVanillaTip();
}

/**
 * Event-delegated portal for vanilla `infoTipHtml` triggers in controls.ts.
 * Only `.info-tip-trigger` hover/focus — not slider or other controls.
 */
export function initInfoTipPortal(root: ParentNode = document): () => void {
  const host = root instanceof Document ? root : root;
  host.addEventListener("pointerover", onPointerOver);
  host.addEventListener("pointerout", onPointerOut);
  host.addEventListener("focusin", onFocusIn);
  host.addEventListener("focusout", onFocusOut);
  const onReflow = () => repositionActiveVanilla();
  window.addEventListener("scroll", onReflow, true);
  window.addEventListener("resize", onReflow);
  return () => {
    closeVanillaTip();
    host.removeEventListener("pointerover", onPointerOver);
    host.removeEventListener("pointerout", onPointerOut);
    host.removeEventListener("focusin", onFocusIn);
    host.removeEventListener("focusout", onFocusOut);
    window.removeEventListener("scroll", onReflow, true);
    window.removeEventListener("resize", onReflow);
  };
}
