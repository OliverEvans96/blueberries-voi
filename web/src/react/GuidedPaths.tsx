import { useEffect, useRef, useState } from "react";
import type { SectionId } from "../sections";
import type { ScenarioId } from "../types";

export type GuidedPath = {
  id: string;
  title: string;
  description: string;
  scenario: ScenarioId;
  section: SectionId;
  autoplayHint?: boolean;
};

export const GUIDED_PATHS: GuidedPath[] = [
  {
    id: "books-baseline",
    title: "Books-only baseline",
    description: "Start at P0 with Play — no daily shrink signal.",
    scenario: "P0",
    section: "play",
  },
  {
    id: "shrink-story",
    title: "Shrink gun story",
    description: "P1 default rung with Belief heatmap.",
    scenario: "P1",
    section: "belief",
  },
  {
    id: "arrival-prior",
    title: "Arrival prior (F2a)",
    description: "Pack-date ASN narrows the arrival-age prior.",
    scenario: "F2a",
    section: "arrival",
    autoplayHint: true,
  },
  {
    id: "rich-receipt",
    title: "Age at receipt (F2)",
    description: "Measured receipt age and sensor noise.",
    scenario: "F2",
    section: "arrival",
  },
];

export type GuidedPathsProps = {
  onSelect: (path: GuidedPath) => void;
};

export function GuidedPaths({ onSelect }: GuidedPathsProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const pick = (path: GuidedPath) => {
    setOpen(false);
    onSelect(path);
  };

  return (
    <div ref={rootRef} className="guided-paths">
      <button
        type="button"
        className="guided-paths-trigger"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        Start here
      </button>
      {open ? (
        <div
          className="guided-paths-popover"
          role="navigation"
          aria-label="Guided paths"
        >
          <ul className="guided-paths-list">
            {GUIDED_PATHS.map((path) => (
              <li key={path.id}>
                <button
                  type="button"
                  className="guided-path-btn"
                  onClick={() => pick(path)}
                >
                  <span className="guided-path-name">{path.title}</span>
                  <span className="guided-path-desc">{path.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
