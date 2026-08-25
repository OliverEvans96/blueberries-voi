export type ChartLoadingShellProps = {
  className?: string;
};

/** Muted hatch reserved for a chart slot before WASM / first D3 render. */
export function ChartLoadingShell({ className }: ChartLoadingShellProps) {
  const classes = ["chart", "chart-loading-shell", "chart-unavailable", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      data-loading-shell="true"
      data-testid="chart-loading-shell"
      aria-hidden="true"
    >
      <div
        className="chart-unavailable-hatch"
        data-loading-hatch
        aria-hidden="true"
      />
    </div>
  );
}
