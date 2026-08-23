import { useState, type ReactNode } from "react";
import "../styles/storeTabs.css";

export type StoreChartView = "sales-stockouts" | "freshness-spoilage";

export type StoreChartTabsProps = {
  salesView: ReactNode;
  ageView: ReactNode;
  defaultView?: StoreChartView;
  activeView?: StoreChartView;
  onSelectView?: (view: StoreChartView) => void;
};

export function StoreChartTabs({
  salesView,
  ageView,
  defaultView,
  activeView: controlledActiveView,
  onSelectView,
}: StoreChartTabsProps) {
  const [internalView, setInternalView] = useState<StoreChartView>(
    defaultView ?? "sales-stockouts",
  );

  const isControlled = controlledActiveView !== undefined;
  const activeView = isControlled ? controlledActiveView : internalView;

  const selectView = (view: StoreChartView) => {
    if (!isControlled) {
      setInternalView(view);
    }
    onSelectView?.(view);
  };

  return (
    <div className="store-chart-tabs">
      <div
        role="tablist"
        className="store-chart-tabs-list"
        aria-label="Store charts"
      >
        <button
          type="button"
          role="tab"
          className="store-chart-tabs-tab"
          aria-selected={activeView === "sales-stockouts"}
          onClick={() => selectView("sales-stockouts")}
        >
          Sales & stockouts
        </button>
        <button
          type="button"
          role="tab"
          className="store-chart-tabs-tab"
          aria-selected={activeView === "freshness-spoilage"}
          onClick={() => selectView("freshness-spoilage")}
        >
          Freshness & spoilage
        </button>
      </div>
      <div
        className="store-chart-tabs-panel focus-plot"
        hidden={activeView !== "sales-stockouts" ? true : undefined}
      >
        {salesView}
      </div>
      <div
        className="store-chart-tabs-panel focus-plot"
        hidden={activeView !== "freshness-spoilage" ? true : undefined}
      >
        {ageView}
      </div>
    </div>
  );
}
