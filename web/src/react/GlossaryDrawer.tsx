import { useState } from "react";
import { SCENARIO_COPY } from "../scenarioCopy";
import type { ScenarioId } from "../types";

const GLOSSARY_ENTRIES: { term: string; body: string }[] = [
  {
    term: "Observation scenario",
    body: "Which fields the store manager can see each day — from books-only (P0) to measured age at receipt (F2).",
  },
  ...(["P0", "P1", "F1", "F1s", "F2a", "F2"] as ScenarioId[]).map((id) => ({
    term: `${id} — ${SCENARIO_COPY[id].title}`,
    body: SCENARIO_COPY[id].description,
  })),
  {
    term: "Sim truth overlay",
    body: "Shows hidden simulator state (lot ages, receipt rug) for teaching — orthogonal to the observation ladder.",
  },
  {
    term: "Base-stock",
    body: "Target on-hand inventory the replenishment policy tries to maintain.",
  },
];

export function GlossaryDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="glossary-trigger"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Glossary
      </button>
      {open ? (
        <dialog className="glossary-drawer" open aria-label="Studio glossary">
          <header className="glossary-drawer-head">
            <h2>Glossary</h2>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </header>
          <dl className="glossary-list">
            {GLOSSARY_ENTRIES.map((e) => (
              <div key={e.term} className="glossary-entry">
                <dt>{e.term}</dt>
                <dd>{e.body}</dd>
              </div>
            ))}
          </dl>
        </dialog>
      ) : null}
    </>
  );
}
