import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { InfoTip } from "./InfoTip";
import "../styles/tuningDrawer.css";

export type TuningDrawerProps = {
  /** Portal host under the studio mount (T-142 embed scoping). */
  portalContainerRef?: RefObject<HTMLElement | null>;
  /** Controlled open state — when set, external trigger is expected. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Hide built-in gear trigger (title bar hosts #tuning-drawer-trigger). */
  hideTrigger?: boolean;
  /** Close reference drawer when this drawer opens. */
  onOpen?: () => void;
};

export function TuningDrawer({
  portalContainerRef,
  open: openProp,
  onOpenChange,
  hideTrigger = false,
  onOpen,
}: TuningDrawerProps = {}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = openProp ?? internalOpen;
  const dialogRef = useRef<HTMLDialogElement>(null);
  const scopeRef = useRef<HTMLDivElement>(null);

  const setOpen = (next: boolean) => {
    if (onOpenChange) onOpenChange(next);
    else setInternalOpen(next);
    if (next) onOpen?.();
  };

  const selectClusterTab = (tab: HTMLButtonElement) => {
    const root = tab.closest(".tuning-dock-tabs");
    if (!root) return;
    root.querySelectorAll<HTMLButtonElement>("[data-section]").forEach((el) => {
      const selected = el === tab;
      el.setAttribute("aria-selected", selected ? "true" : "false");
      el.tabIndex = selected ? 0 : -1;
    });
  };

  const openDrawer = () => setOpen(true);
  const closeDrawer = () => setOpen(false);
  const onClusterTabClick = (tab: HTMLButtonElement) => selectClusterTab(tab);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      try {
        if (typeof dialog.showModal === "function" && !dialog.open) {
          dialog.showModal();
        } else if (!dialog.hasAttribute("open")) {
          dialog.setAttribute("open", "");
        }
      } catch {
        dialog.setAttribute("open", "");
      }
    } else {
      try {
        if (dialog.open && typeof dialog.close === "function") {
          dialog.close();
        }
      } catch {
        /* jsdom <dialog> may lack close() */
      }
      dialog.removeAttribute("open");
    }
  }, [open]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!open) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeDrawer();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    const trigger = document.querySelector("#tuning-drawer-trigger");
    if (!trigger || hideTrigger) return;
    const onClick = () => openDrawer();
    trigger.addEventListener("click", onClick);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    return () => trigger.removeEventListener("click", onClick);
  }, [hideTrigger, open]);

  useEffect(() => {
    const trigger = document.querySelector("#tuning-drawer-trigger");
    if (trigger) trigger.setAttribute("aria-expanded", open ? "true" : "false");
  }, [open]);

  const portalTarget =
    portalContainerRef?.current ??
    scopeRef.current?.closest(".bv-studio") ??
    document.body;

  return (
    <div className="tuning-drawer-root" ref={scopeRef}>
      {!hideTrigger ? (
        <button
          type="button"
          id="tuning-drawer-trigger"
          className="tuning-drawer-trigger"
          aria-label="Simulation parameters"
          aria-expanded={open ? "true" : "false"}
          aria-controls="tuning-drawer"
          onClick={() => (open ? closeDrawer() : openDrawer())}
        />
      ) : null}

      {createPortal(
            <dialog
              ref={dialogRef}
              id="tuning-drawer"
              className="tuning-drawer"
              aria-modal="true"
              aria-label="Simulation parameters"
              onClose={() => setOpen(false)}
              onClick={(e) => {
                if (e.target === dialogRef.current) closeDrawer();
              }}
            >
              <header className="tuning-drawer-head">
                <nav
                  className="tuning-dock-tabs"
                  role="tablist"
                  aria-label="Tuning clusters"
                >
                  <div className="tuning-cluster" role="presentation">
                    <span className="tuning-cluster-label">Sim params</span>
                    <div className="tuning-cluster-tabs">
                      <button
                        type="button"
                        role="tab"
                        data-section="demand"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Demand
                      </button>
                      <InfoTip>
                        Sets the average daily demand level and how much
                        random variability rides on top of the day-of-week
                        and week-to-week calendar shape. It's split from
                        Arrival and Physics because demand determines how
                        many customers show up, not how fresh any unit is —
                        every ordering policy sees the same demand calendar,
                        so this cluster only affects the sales side of the
                        simulation.
                      </InfoTip>
                      <button
                        type="button"
                        role="tab"
                        data-section="arrival"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Arrival
                      </button>
                      <InfoTip>
                        Sets the cold-chain corridor a delivery travels
                        through — transit duration, mean temperature, and how
                        much units vary within one pallet — which together
                        determine each unit's freshness the moment it arrives
                        on the shelf. It's split from Physics because Arrival
                        governs a single trip's outcome before a unit is ever
                        shelved, while Physics governs the daily aging that
                        happens afterward, even though both draw from the
                        same gamma decay law.
                      </InfoTip>
                      <button
                        type="button"
                        role="tab"
                        data-section="physics"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Physics
                      </button>
                      <InfoTip alignEnd>
                        Sets the daily in-store aging process: reference
                        shelf life, the Q10 temperature sensitivity, and
                        store temperature, which together determine how fast
                        a unit's freshness decays once it's on the shelf.
                        It's grouped apart from Arrival because these knobs
                        control ongoing shelf-life physics rather than the
                        one-time transit that sets a unit's freshness at
                        receipt.
                      </InfoTip>
                    </div>
                  </div>
                  <div className="tuning-cluster" role="presentation">
                    <span className="tuning-cluster-label">Logistics</span>
                    <div className="tuning-cluster-tabs">
                      <button
                        type="button"
                        role="tab"
                        data-section="logistics"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Logistics
                      </button>
                      <InfoTip alignEnd>
                        Sets the delivery calendar, case size, and lead time
                        that determine how much stock the store carries and
                        how it gets refilled (the base-stock target here only
                        moves a chart reference line, not the live
                        controller). It's kept separate from Autopilot
                        because Logistics defines the physical constraints
                        ordering has to work within — Autopilot decides how
                        aggressively the ordering rule reacts to what's
                        currently on the shelf.
                      </InfoTip>
                    </div>
                  </div>
                  <div className="tuning-cluster" role="presentation">
                    <span className="tuning-cluster-label">Autopilot</span>
                    <div className="tuning-cluster-tabs">
                      <button
                        type="button"
                        role="tab"
                        data-section="autopilot"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Autopilot
                      </button>
                      <InfoTip alignEnd>
                        Sets the automated ordering policy's parameters: how
                        aggressively the damped base-stock rule closes the
                        gap between the demand target and effective
                        inventory, plus the rollout search budget layered on
                        top. It's split from Logistics because Autopilot
                        controls decision-making — when and how much to
                        order — while Logistics controls the physical
                        constraints that decision has to work within.
                      </InfoTip>
                    </div>
                  </div>
                </nav>
                <button type="button" onClick={closeDrawer} aria-label="Close">
                  ×
                </button>
              </header>

              <div className="tuning-drawer-body">
                <div className="focus-header tuning-drawer-slot">
                  <h2 id="focus-title">Demand</h2>
                  <p className="focus-blurb" id="focus-blurb" />
                </div>

                <div
                  id="section-controls"
                  className="tuning-drawer-controls"
                />
              </div>
            </dialog>,
            portalTarget,
          )}
    </div>
  );
}
