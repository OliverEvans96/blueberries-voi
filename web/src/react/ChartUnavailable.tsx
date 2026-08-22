export type ChartUnavailableProps = {
  plotId: string;
  caption: string;
};

/** Muted hatch placeholder when a plot slot is unavailable at the active rung. */
export function ChartUnavailable({ plotId, caption }: ChartUnavailableProps) {
  const label = caption || "Chart unavailable.";
  return (
    <div
      className="chart chart-unavailable"
      role="img"
      aria-label={label}
      data-plot-id={plotId}
      data-unavailable="true"
    >
      <div className="chart-unavailable-hatch" data-unavailable-hatch aria-hidden="true" />
      <p className="chart-unavailable-caption">{caption}</p>
    </div>
  );
}
