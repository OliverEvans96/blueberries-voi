# T-126 qa RED map (storetabs shard)

Shard: `storetabs` — `StoreChartTabs.tsx` (not yet implemented).

## Coverage of acceptance criteria

- Exports `StoreChartView = "sales-stockouts" | "age-spoilage"` and `StoreChartTabsProps` with `salesView`, `ageView`, optional `defaultView`, `activeView`, `onSelectView` → `StoreChartTabs.test.ts` import of `StoreChartTabs` and `StoreChartView` — currently failing: module `./StoreChartTabs` does not exist
- Renders `role="tablist"` with exactly two tabs labelled "Sales & stockouts" and "Age & spoilage"; `aria-selected` reflects active view → `StoreChartTabs.test.ts::renders both tab labels in a tablist`, `controlled: sales-stockouts active…`, `controlled: age-spoilage active…` — currently failing: module missing
- Renders both `salesView` and `ageView` unconditionally; inactive wrapper has `hidden` → `keeps both view subtrees mounted…`, controlled/uncontrolled visibility tests — currently failing: module missing
- Clicking tabs calls `onSelectView` with correct id; uncontrolled internal state updates → `calls onSelectView with the clicked tab id (controlled)`, `uncontrolled: defaults to sales-stockouts…`, `uncontrolled: defaultView selects…` — currently failing: module missing

## Design locked by tests (for implementer)

**Approach:** slot props (`salesView` / `ageView` ReactNode), not baked-in `D3ChartHost` ids inside `StoreChartTabs`. Merge wires `#chart-sales`, `#chart-stockout`, `#chart-history`, `#chart-spoil` as children of those slots.

**Props (verbatim from spec):**

```ts
export type StoreChartView = "sales-stockouts" | "age-spoilage";

export type StoreChartTabsProps = {
  salesView: ReactNode;
  ageView: ReactNode;
  defaultView?: StoreChartView;
  activeView?: StoreChartView;
  onSelectView?: (view: StoreChartView) => void;
};
```

**DOM / visibility:**

- Outer `role="tablist"` with two `<button type="button" role="tab">` elements labelled exactly "Sales & stockouts" and "Age & spoilage".
- Two view wrappers: each renders `{salesView}` or `{ageView}` inside a panel element that is the **direct parent** of the slot root (tests use `getByTestId(...).parentElement` for `hidden` checks).
- Both panels always mounted; inactive panel has HTML `hidden` attribute (`.focus-plot[hidden]` convention); active panel does not.
- Controlled when `activeView` is provided; uncontrolled internal state from `defaultView ?? "sales-stockouts"` when omitted.

## Not covered by tests

- Keyboard Enter/Space activation on tabs — verify manually or extend tests in implement pass; spec requires it but qa shard focused on click + visibility per AC bullet list
- `storeTabs.css` styling — CSS file is implement scope; no source-text assertion in this shard
