import { STUDIO_CHAPTERS } from "../chapters";
import { STUDIO_SECTIONS } from "../sections";
import { D3ChartHost } from "./D3ChartHost";
import { GlossaryDrawer } from "./GlossaryDrawer";
import { GuidedPaths } from "./GuidedPaths";
import { ShortcutHelp } from "./ShortcutHelp";
import { VoiReferencePanel } from "./VoiReferencePanel";

/** Static studio shell — three-zone layout (T-124 / ADR 0128). */
export function StudioLayout() {
  return (
    <div className="shell studio">
      <header className="hero">
        <div className="hero-top">
          <div className="brand">Cold Case Ledger</div>
          <div className="hero-tools">
            <GlossaryDrawer />
            <ShortcutHelp />
            <span
              id="engine-status"
              className="engine-status"
              data-status="loading"
              role="status"
              aria-live="polite"
            >
              <span className="engine-status-dot" aria-hidden="true" />
              <span className="engine-status-label">Loading</span>
            </span>
          </div>
        </div>
        <h1>Blueberry inventory studio</h1>
        <p className="lede">
          Walk one idea at a time — order the store, then explore Operate,
          Understand, and Tune chapters to see how each knob teaches through its
          plots.
        </p>
        <div id="insight-strip-host" className="insight-strip-host" />
      </header>

      <div className="studio-layout studio-layout--three-zone">
        <main className="store">
          <section className="panel panel-stage" id="linked-charts">
            <div className="panel-head">
              <h2>The store</h2>
              <span className="panel-note" id="hover-note">
                Hover a day to highlight it everywhere
              </span>
            </div>
            <div id="day-inspector-host" className="day-inspector-host" />
            <div className="legend-inline store-legend">
              <span className="chip chip-sales">Sales</span>
              <span className="chip chip-lots">Lots (size ∝ qty)</span>
              <span className="chip chip-spoil">Spoilage</span>
              <span className="chip chip-missed">Missed</span>
            </div>
            <div className="chart-stack">
              <div className="chart-caption">Units sold</div>
              <D3ChartHost
                id="chart-sales"
                className="chart"
                ariaLabel="Units sold by day"
              />
              <div className="chart-caption">Missed sales</div>
              <D3ChartHost
                id="chart-stockout"
                className="chart"
                ariaLabel="Missed sales by day"
              />
              <div className="chart-caption" data-truth-caption="lots">
                Lots · day × age
              </div>
              <D3ChartHost
                id="chart-history"
                className="chart"
                ariaLabel="Inventory lots by day and age"
              />
              <div className="chart-caption">Units spoiled</div>
              <D3ChartHost
                id="chart-spoil"
                className="chart"
                ariaLabel="Units spoiled by day"
              />
            </div>
          </section>
        </main>

        <aside className="focus-column">
          <div className="focus-row">
            <nav className="section-nav panel" aria-label="Studio sections">
              {STUDIO_CHAPTERS.map((chapter) => (
                <div key={chapter.id} className="chapter-group" data-chapter={chapter.id}>
                  <div className="chapter-label">{chapter.title}</div>
                  {chapter.sectionIds.map((sectionId) => {
                    const s = STUDIO_SECTIONS.find((x) => x.id === sectionId)!;
                    const i = STUDIO_SECTIONS.findIndex((x) => x.id === sectionId);
                    return (
                      <button
                        key={s.id}
                        type="button"
                        className="section-nav-item"
                        data-section={s.id}
                        data-index={String(i)}
                      >
                        <span className="section-nav-index">{i + 1}</span>
                        <span className="section-nav-text">
                          <span className="section-nav-label">{s.label}</span>
                          <span className="section-nav-blurb">{s.blurb}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
              <p className="section-nav-hint">Keys 1–8 or ← →</p>
            </nav>

            <section className="panel focus-pane" id="focus-pane">
              <div className="focus-header">
                <h2 id="focus-title">Play</h2>
                <p className="focus-blurb" id="focus-blurb" />
              </div>
              <div id="guided-paths-host" className="guided-paths-host">
                <GuidedPaths onSelect={() => undefined} />
              </div>
              <div id="section-controls" />
              <div className="focus-plots">
                <div className="focus-plot" data-plot="plot-sales-demand" hidden>
                  <div className="chart-caption impact-caption">Sales vs demand</div>
                  <D3ChartHost
                    id="chart-sales-demand"
                    className="chart"
                    ariaLabel="Sales versus demand"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-pnl" hidden>
                  <details className="ledger-expand">
                    <summary className="chart-caption impact-caption">
                      Full ledger (cumulative revenue · cost · profit)
                    </summary>
                    <D3ChartHost
                      id="chart-pnl-series"
                      className="chart"
                      ariaLabel="Cumulative profit and loss"
                    />
                  </details>
                </div>
                <div className="focus-plot" data-plot="plot-survival" hidden>
                  <div className="chart-caption impact-caption">Survival + lot rug</div>
                  <D3ChartHost
                    id="chart-survival"
                    className="chart"
                    ariaLabel="Survival curve and lot rug"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-demand" hidden>
                  <div className="chart-caption impact-caption">
                    DOW demand · protection 3 / 3 / 4
                  </div>
                  <D3ChartHost
                    id="chart-demand"
                    className="chart"
                    ariaLabel="Day of week demand profile"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-inventory" hidden>
                  <div className="chart-caption impact-caption">
                    Inventory vs base-stock
                  </div>
                  <D3ChartHost
                    id="chart-inventory"
                    className="chart"
                    ariaLabel="Inventory versus base stock target"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-age-comp" hidden>
                  <div className="chart-caption impact-caption">On-hand by age band</div>
                  <D3ChartHost
                    id="chart-age-comp"
                    className="chart"
                    ariaLabel="On-hand inventory by age band"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-arrival-prior" hidden>
                  <div className="chart-caption impact-caption">
                    Arrival-age prior · receipt rug
                  </div>
                  <D3ChartHost
                    id="chart-arrival-prior"
                    className="chart"
                    ariaLabel="Arrival age prior distribution"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-arrival-shift" hidden>
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
                  className="focus-plot"
                  data-plot="plot-belief-age-marginal"
                  hidden
                >
                  <div className="chart-caption impact-caption">Age marginal</div>
                  <D3ChartHost
                    id="chart-belief-age-marginal"
                    className="chart"
                    ariaLabel="Belief age marginal"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-belief-lg" hidden>
                  <div
                    className="chart-caption impact-caption"
                    data-truth-caption="belief-lg"
                  >
                    Belief heatmap
                  </div>
                  <D3ChartHost
                    id="chart-belief-lg"
                    className="chart"
                    ariaLabel="Belief heatmap age by count"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-controller-orders" hidden>
                  <div className="chart-caption impact-caption">Order quantity</div>
                  <D3ChartHost
                    id="chart-controller-orders"
                    className="chart"
                    ariaLabel="Controller order quantities"
                  />
                </div>
              </div>
              <div className="voi-reference-host">
                <VoiReferencePanel />
              </div>
            </section>
          </div>
        </aside>

        <div className="decision-rail-column">
          <div id="play-chrome" hidden />
          <div className="pnl-chrome" hidden>
            <D3ChartHost id="chart-pnl-totals" ariaLabel="Episode profit and loss totals" />
            <div className="chart-caption impact-caption">Cumulative PnL</div>
            <D3ChartHost
              id="chart-pnl-spark"
              className="chart"
              ariaLabel="Cumulative profit sparkline"
            />
          </div>
          <div id="decision-rail-host" />
        </div>
      </div>

      <div id="studio-error" className="studio-error" hidden role="alert" />
      <footer className="foot" id="studio-footer" />
    </div>
  );
}
