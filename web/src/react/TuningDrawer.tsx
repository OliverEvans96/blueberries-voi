import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { D3ChartHost } from "./D3ChartHost";
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
                      <button
                        type="button"
                        role="tab"
                        data-section="arrival"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
                      >
                        Arrival
                      </button>
                      <button
                        type="button"
                        role="tab"
                        data-section="physics"
                        aria-controls="section-controls"
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
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
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
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
                        onClick={(e) => onClusterTabClick(e.currentTarget)}
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
                    <div className="chart-caption impact-caption">
                      Daily demand
                      <InfoTip>
                        Shows the actual simulated demand draw for each day
                        of the episode, following the day-of-week and
                        week-to-week calendar shape with random overdispersed
                        noise layered on top. Every ordering policy sees the
                        same underlying calendar mean, so differences in
                        outcome come from freshness information, not from
                        guessing tomorrow's footfall.
                      </InfoTip>
                    </div>
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
                      <InfoTip>
                        Projects what daily demand would look like under the
                        mean-demand slider's current setting, without
                        re-simulating any days. Mean demand is a
                        Preview-tier control: dragging it updates this chart
                        immediately, but the store's actual simulated history
                        stays exactly as it was until you press Reset.
                      </InfoTip>
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
                      <InfoTip>
                        Shows how strongly the picking-weight exponent biases
                        sales toward fresher units: each alive unit gets a
                        lottery ticket count proportional to its freshness
                        raised to this exponent, so a higher value favors the
                        freshest stock more sharply while zero picks
                        uniformly at random. This is not FIFO — shoppers
                        never guarantee picking the oldest punnet, so even
                        tired units can occasionally linger unsold.
                      </InfoTip>
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
                      <span className="field-label">
                        Delivery schedule
                        <InfoTip>
                          Click weekdays in the calendar to set which days
                          deliveries land on; order days are computed
                          automatically as delivery day minus lead time, so
                          shifting delivery days also shifts when orders go
                          out. Changes here don't take effect until you press
                          Reset, since the delivery calendar feeds the
                          simulated arrival schedule from day one.
                        </InfoTip>
                      </span>
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
                    data-plot="plot-age-comp"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      On-hand by freshness band
                      <InfoTip>
                        Shows on-hand inventory broken into freshness bands,
                        from near-pristine to nearly spoiled, over the course
                        of the simulated episode. This is the same per-unit
                        freshness state that effective inventory weights when
                        deciding how much to order — a shelf skewed toward
                        low-freshness bands offers much less real protection
                        against demand than the same unit count would
                        suggest.
                      </InfoTip>
                    </div>
                    <D3ChartHost
                      id="chart-age-comp-focus"
                      className="chart"
                      ariaLabel="On-hand inventory by freshness band preview"
                    />
                  </div>
                  <div
                    className="focus-plot tuning-drawer-slot"
                    data-plot="plot-controller-orders"
                    hidden
                  >
                    <div className="chart-caption impact-caption">
                      Order quantity
                      <InfoTip>
                        Preview of each day's order quantity from the active
                        controller policy — the same series shown in the
                        Outcomes column, enlarged for tuning autopilot
                        parameters.
                      </InfoTip>
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
                    <div className="chart-caption impact-caption">
                      Spoilage
                      <InfoTip>
                        Preview of daily units spoiled — unavailable at the
                        lowest observation rung where waste is not observed.
                      </InfoTip>
                    </div>
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
                      <InfoTip>
                        Shows the distribution of freshness a unit is
                        expected to have the moment it arrives, given the
                        current corridor's transit and temperature
                        assumptions, with a rug of actual receipt freshness
                        values from the simulated deliveries. The particle
                        filter draws each new lot's freshness from this same
                        distribution, conditioned on whatever the active
                        observation rung actually reveals about the trip — a
                        full temperature trace, a pack date, or nothing at
                        all.
                      </InfoTip>
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
                      <InfoTip>
                        Meant to compare the current transit-temperature-bias
                        curve against an unbiased baseline, but the bias
                        slider isn't wired into this chart's data yet (a
                        known display gap) — both lines currently plot the
                        same unbiased curve no matter where the slider is
                        set. The bias does apply to the simulated deliveries
                        themselves, just not to this preview.
                      </InfoTip>
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
                      <InfoTip>
                        Plots the Q10 temperature factor across a range of
                        storage temperatures, showing how much faster
                        freshness decays as the shelf gets warmer. Under the
                        Q10 rule, the aging rate scales multiplicatively per
                        10°C of warming — the default value (3.0) triples
                        the aging rate for every 10°C increase — rather than
                        each degree adding a fixed amount.
                      </InfoTip>
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
                      <InfoTip>
                        Shows the expected freshness trajectory over time,
                        with a shaded band for one standard deviation of
                        spread, under the current gamma aging parameters.
                        Because aging is shape-scaled rather than
                        scale-scaled, a hotter storage temperature widens
                        this band as well as steepening the mean line — heat
                        makes loss events more frequent, not just larger, so
                        higher temperatures bring more day-to-day
                        unpredictability along with faster average decay.
                      </InfoTip>
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
          )}
    </div>
  );
}
