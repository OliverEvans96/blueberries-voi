import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { D3ChartHost } from "./D3ChartHost";
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

  const openDrawer = () => setOpen(true);
  const closeDrawer = () => setOpen(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    try {
      if (typeof dialog.showModal === "function" && !dialog.open) {
        dialog.showModal();
      } else if (!dialog.hasAttribute("open")) {
        dialog.setAttribute("open", "");
      }
    } catch {
      dialog.setAttribute("open", "");
    }
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

      {open
        ? createPortal(
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
                      >
                        Demand
                      </button>
                      <button
                        type="button"
                        role="tab"
                        data-section="arrival"
                        aria-controls="section-controls"
                      >
                        Arrival
                      </button>
                      <button
                        type="button"
                        role="tab"
                        data-section="physics"
                        aria-controls="section-controls"
                      >
                        Physics
                      </button>
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
                      >
                        Logistics
                      </button>
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
                      >
                        Autopilot
                      </button>
                    </div>
                  </div>
                </nav>
                <button type="button" onClick={closeDrawer} aria-label="Close">
                  ×
                </button>
              </header>

              <div className="tuning-drawer-body">
                <div className="focus-header tuning-drawer-slot tuning-drawer-slot--full">
                  <h2 id="focus-title">Demand</h2>
                  <p className="focus-blurb" id="focus-blurb" />
                </div>

                <div
                  className="tuning-drawer-slot"
                  data-slot="controls"
                >
                  <div id="section-controls" className="tuning-drawer-controls" />
                </div>

                <div
                  className="focus-plots tuning-plots tuning-drawer-plots"
                  data-slot="plots"
                >
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-demand"
                    hidden
                  >
                    <div className="chart-caption impact-caption">Daily demand</div>
                    <div
                      id="chart-demand-host"
                      className="chart demand-chart-slot"
                      role="img"
                      aria-label="Daily demand over episode days"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-demand-forecast"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Demand forecast
                    </div>
                    <div
                      id="chart-demand-forecast-host"
                      className="chart demand-chart-slot"
                      role="img"
                      aria-label="Known demand distribution for the next few days"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-picking-variability"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Picking variability shape
                    </div>
                    <div
                      id="picking-var-chart"
                      className="chart picking-var-chart"
                      role="img"
                      aria-label="Picking weight curve"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot tuning-drawer-slot--full"
                    data-plot="plot-logistics-calendar"
                    hidden
                  >
                    <div className="field week-calendar-field">
                      <span className="field-label">Delivery schedule</span>
                      <div
                        id="week-calendar"
                        className="week-calendar"
                        role="group"
                        aria-label="Delivery and order weekdays"
                      />
                      <div
                        className="week-calendar-legend"
                        role="note"
                        aria-label="Calendar legend"
                      >
                        <span className="week-calendar-legend-item">
                          <span
                            className="week-calendar-swatch is-delivery"
                            aria-hidden="true"
                          />
                          Delivery day
                        </span>
                        <span className="week-calendar-legend-item">
                          <span
                            className="week-calendar-swatch is-order"
                            aria-hidden="true"
                          />
                          Order day
                        </span>
                        <span className="week-calendar-legend-item">
                          <span
                            className="week-calendar-swatch is-both"
                            aria-hidden="true"
                          />
                          Both
                        </span>
                      </div>
                      <p
                        className="meta-readonly week-calendar-hint"
                        id="week-calendar-hint"
                        hidden
                      >
                        Reset to apply schedule
                      </p>
                    </div>
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-inventory"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Effective inventory preview
                    </div>
                    <D3ChartHost
                      id="chart-inventory-focus"
                      className="chart"
                      ariaLabel="Inventory versus base stock target preview"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-controller-orders"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Order quantity
                    </div>
                    <D3ChartHost
                      id="chart-controller-orders-focus"
                      className="chart"
                      ariaLabel="Order quantity preview"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-spoil"
                    hidden
                  >
                    <div className="chart-caption impact-caption">Spoilage</div>
                    <D3ChartHost
                      id="chart-spoil-focus"
                      className="chart"
                      ariaLabel="Spoilage preview"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-arrival-prior"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Arrival freshness prior · receipt rug
                    </div>
                    <D3ChartHost
                      id="chart-arrival-prior"
                      className="chart"
                      ariaLabel="Arrival freshness prior distribution"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-arrival-shift"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Transit ΔT shift vs baseline
                    </div>
                    <D3ChartHost
                      id="chart-arrival-shift"
                      className="chart"
                      ariaLabel="Transit temperature shift"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-arrhenius-temp"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Q10 aging rate vs temperature
                    </div>
                    <D3ChartHost
                      id="chart-arrhenius-temp"
                      className="chart"
                      ariaLabel="Q10 aging rate versus store temperature"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-gamma-path"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Gamma freshness mean ± σ until expiry
                    </div>
                    <D3ChartHost
                      id="chart-gamma-path"
                      className="chart"
                      ariaLabel="Unit freshness mean and standard deviation envelope"
                    />
                  </div>
                </div>
              </div>
            </dialog>,
            portalTarget,
          )
        : null}
    </div>
  );
}
