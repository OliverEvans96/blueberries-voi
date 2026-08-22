import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { scenarioDescription, scenarioTitle } from "../scenarioCopy";
import type { ScenarioId } from "../types";
import "../styles/referenceDrawer.css";

const GLOSSARY_ENTRIES: { term: string; body: string }[] = [
  {
    term: "Observation scenario",
    body: "Which fields the store manager can see each day — from books-only (P0) to measured age at receipt (F2).",
  },
  ...(["P0", "P1", "F1", "F1s", "F2a", "F2"] as ScenarioId[]).map((id) => ({
    term: `${id} — ${scenarioTitle(id)}`,
    body: scenarioDescription(id),
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

const SHORTCUTS = [
  { keys: "1–7", action: "Jump to studio section" },
  { keys: "← →", action: "Previous / next section" },
  { keys: "↑ ↓", action: "Previous / next section" },
  { keys: "?", action: "Open this help" },
  { keys: "T", action: "Toggle sim truth overlay (when focused)" },
];

type ReferenceTab = "glossary" | "voi" | "shortcuts";

type VoiReferenceRow = {
  scenario: string;
  metric: string;
  value: number;
};

type VoiReferenceData = {
  generated_at: string;
  disclaimer: string;
  rows: VoiReferenceRow[];
};

const STUB_URL = "/voi-reference.json";

function VoiReferenceContent() {
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

export type ReferenceDrawerProps = {
  /** Portal host under the studio mount (T-142 embed scoping). */
  portalContainerRef?: RefObject<HTMLElement | null>;
  /** Hide visible trigger buttons — open via keyboard shortcut only. */
  hideTriggers?: boolean;
};

export function ReferenceDrawer({
  portalContainerRef,
  hideTriggers = false,
}: ReferenceDrawerProps = {}) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ReferenceTab>("glossary");
  const [voiMounted, setVoiMounted] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const openDrawer = (tab: ReferenceTab) => {
    if (tab === "voi") setVoiMounted(true);
    setActiveTab(tab);
    setOpen(true);
  };

  const closeDrawer = () => setOpen(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    try {
      if (typeof dialog.showModal === "function" && !dialog.open) {
        dialog.showModal();
      } else if (!dialog.hasAttribute("open")) {
        dialog.setAttribute("open", "");
      }
    } catch {
      dialog.setAttribute("open", "");
    }
  }, [open]);

  const scopeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!document.querySelector(".bv-studio")) return;
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (event.key === "?") {
        event.preventDefault();
        if (open && activeTab === "shortcuts") {
          closeDrawer();
        } else {
          setActiveTab("shortcuts");
          setOpen(true);
        }
      }

      if (event.key === "Escape" && open) {
        closeDrawer();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, activeTab]);

  const selectTab = (tab: ReferenceTab) => {
    if (tab === "voi") setVoiMounted(true);
    setActiveTab(tab);
  };

  const portalTarget =
    portalContainerRef?.current ??
    scopeRef.current?.closest(".bv-studio") ??
    document.body;

  return (
    <div
      className={`reference-drawer-root${hideTriggers ? " reference-drawer-root--headless" : ""}`}
      ref={scopeRef}
    >
      <button
        type="button"
        className="reference-drawer-trigger reference-drawer-trigger--glossary"
        onClick={() => openDrawer("glossary")}
      >
        Glossary
      </button>
      <button
        type="button"
        className="reference-drawer-trigger reference-drawer-trigger--voi"
        onClick={() => openDrawer("voi")}
      >
        VOI reference
      </button>
      <button
        type="button"
        className="reference-drawer-trigger reference-drawer-trigger--shortcuts"
        onClick={() => openDrawer("shortcuts")}
      >
        Shortcuts
      </button>

      {open
        ? createPortal(
            <dialog
              ref={dialogRef}
              className="reference-drawer"
              aria-label="Studio reference"
              onClose={() => setOpen(false)}
            >
              <header className="reference-drawer-head">
                <nav
                  role="tablist"
                  aria-label="Reference sections"
                  className="reference-drawer-tabs"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "glossary"}
                    onClick={() => selectTab("glossary")}
                  >
                    Glossary
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "voi"}
                    onClick={() => selectTab("voi")}
                  >
                    VOI reference
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "shortcuts"}
                    onClick={() => selectTab("shortcuts")}
                  >
                    Shortcuts
                  </button>
                </nav>
                <button type="button" onClick={closeDrawer} aria-label="Close">
                  ×
                </button>
              </header>

              <div className="reference-drawer-panel">
                {activeTab === "glossary" ? (
                  <dl className="glossary-list">
                    {GLOSSARY_ENTRIES.map((e) => (
                      <div key={e.term} className="glossary-entry">
                        <dt>{e.term}</dt>
                        <dd>{e.body}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}

                {activeTab === "voi" && voiMounted ? <VoiReferenceContent /> : null}

                {activeTab === "shortcuts" ? (
                  <ul className="shortcut-list">
                    {SHORTCUTS.map((s) => (
                      <li key={s.keys}>
                        <kbd>{s.keys}</kbd> {s.action}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </dialog>,
            portalTarget,
          )
        : null}
    </div>
  );
}
