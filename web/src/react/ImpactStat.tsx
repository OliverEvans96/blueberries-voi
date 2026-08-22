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
    <div
      className="impact-stat"
      data-testid="impact-stat"
      data-impact-label={label}
    >
      <div className="impact-stat-head">
        <span className="impact-stat-label">{label}</span>
        <span className="impact-stat-abs">{absolute}</span>
      </div>
      <div className="impact-stat-pct">{pctText}</div>
    </div>
  );
}
