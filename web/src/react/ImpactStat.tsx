export type ImpactStatProps = {
  label: string;
  absolute: number;
  percent: number;
  /** Optional override for percent display (e.g. "12.5% of demand"). */
  percentCaption?: string;
};

export function ImpactStat({
  label,
  absolute,
  percent,
  percentCaption,
}: ImpactStatProps) {
  const pctText =
    percentCaption ??
    `${(percent * 100).toFixed(1)}% of cumulative ${label.includes("missed") ? "demand" : "orders"}`;

  return (
    <p
      className="impact-stat"
      data-testid="impact-stat"
      data-impact-label={label}
    >
      <strong className="impact-stat-label">{label}:</strong>{" "}
      <span className="impact-stat-value">
        {absolute} units ({pctText})
      </span>
    </p>
  );
}
