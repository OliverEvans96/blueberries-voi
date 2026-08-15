import { useEffect, useState } from "react";

export type VoiReferenceRow = {
  scenario: string;
  metric: string;
  value: number;
};

export type VoiReferenceData = {
  generated_at: string;
  disclaimer: string;
  rows: VoiReferenceRow[];
};

const STUB_URL = "/voi-reference.json";

export function VoiReferencePanel() {
  const [data, setData] = useState<VoiReferenceData | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetch(STUB_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("missing"))))
      .then((json: VoiReferenceData) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (missing) {
    return (
      <div className="voi-reference voi-reference--empty" role="note">
        VOI reference data not available.
      </div>
    );
  }

  if (!data) {
    return <div className="voi-reference voi-reference--loading">Loading…</div>;
  }

  return (
    <section className="voi-reference" aria-label="VOI reference (demo)">
      <p className="voi-reference-disclaimer">{data.disclaimer}</p>
      <p className="voi-reference-meta">
        Generated {new Date(data.generated_at).toLocaleDateString()}
      </p>
      <table className="voi-reference-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={`${row.scenario}-${row.metric}-${i}`}>
              <td>{row.scenario}</td>
              <td>{row.metric}</td>
              <td>{row.value.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
