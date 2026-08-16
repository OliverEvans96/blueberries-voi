export type SectionId =
  | "economics"
  | "pricing"
  | "physics"
  | "demand"
  | "logistics"
  | "arrival"
  | "observation"
  | "autopilot";

export type StudioSection = {
  id: SectionId;
  label: string;
  blurb: string;
  /** Chart container ids to show/render in the focus pane */
  plotIds: string[];
  /** Control block data-section attribute */
  controlSection: string;
};

export const STUDIO_SECTIONS: StudioSection[] = [
  {
    id: "economics",
    label: "Economics",
    blurb:
      "Revenue, cost, and profit drivers — P&L recomputes from stored units without re-simulating physics.",
    plotIds: ["plot-sales-demand", "plot-pnl"],
    controlSection: "economics",
  },
  {
    id: "pricing",
    label: "Pricing",
    blurb: "Retune money without re-simulating physics — P&L recomputes from stored units.",
    plotIds: ["plot-pnl"],
    controlSection: "pricing",
  },
  {
    id: "physics",
    label: "Physics",
    blurb: "Gamma freshness aging and cold-chain temps shape how long lots stay sellable.",
    plotIds: [],
    controlSection: "physics",
  },
  {
    id: "demand",
    label: "Demand",
    blurb: "Mean and variability set how often you stock out or over-cover.",
    plotIds: ["plot-demand"],
    controlSection: "demand",
  },
  {
    id: "logistics",
    label: "Logistics",
    blurb: "Case size and base-stock set how you refill the cooler each day.",
    plotIds: ["plot-inventory", "plot-age-comp"],
    controlSection: "logistics",
  },
  {
    id: "arrival",
    label: "Arrival",
    blurb:
      "Transit assumptions set freshness at receipt — the identification signal for relative quality.",
    plotIds: ["plot-arrival-prior", "plot-arrival-shift"],
    controlSection: "arrival",
  },
  {
    id: "observation",
    label: "Observation",
    blurb:
      "Knowledge changes what the store sees, so future orders can change. Use the decision rail to switch observation rungs.",
    plotIds: [],
    controlSection: "observation",
  },
  {
    id: "autopilot",
    label: "Autopilot",
    blurb:
      "Policy and rollout budgets for Autopilot — orders alongside on-hand vs target.",
    plotIds: ["plot-controller-orders", "plot-inventory"],
    controlSection: "autopilot",
  },
];

export const SECTION_STORAGE_KEY = "blueberries-voi-studio-section";

const LEGACY_SECTION_IDS: Record<string, SectionId> = {
  play: "demand",
  belief: "observation",
  controller: "autopilot",
};

export function loadSection(): SectionId {
  try {
    const raw = localStorage.getItem(SECTION_STORAGE_KEY);
    if (raw && STUDIO_SECTIONS.some((s) => s.id === raw)) {
      return raw as SectionId;
    }
    if (raw && raw in LEGACY_SECTION_IDS) {
      return LEGACY_SECTION_IDS[raw]!;
    }
  } catch {
    /* ignore */
  }
  return "demand";
}

export function saveSection(id: SectionId): void {
  try {
    localStorage.setItem(SECTION_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}
