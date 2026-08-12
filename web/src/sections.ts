export type SectionId =
  | "play"
  | "pricing"
  | "physics"
  | "demand"
  | "logistics"
  | "belief";

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
    id: "play",
    label: "Play",
    blurb: "Run the store day by day. Watch inventory age, sales, and spoilage unfold.",
    plotIds: ["plot-belief", "plot-sales-demand"],
    controlSection: "play",
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
    blurb: "Weibull quality and cold-chain temps shape how long lots survive.",
    plotIds: ["plot-survival"],
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
    id: "belief",
    label: "Belief",
    blurb: "Observation richness tightens or loosens the age×count posterior vs truth.",
    plotIds: ["plot-belief-lg"],
    controlSection: "belief",
  },
];

export const SECTION_STORAGE_KEY = "blueberries-voi-studio-section";

export function loadSection(): SectionId {
  try {
    const raw = localStorage.getItem(SECTION_STORAGE_KEY);
    if (STUDIO_SECTIONS.some((s) => s.id === raw)) return raw as SectionId;
  } catch {
    /* ignore */
  }
  return "play";
}

export function saveSection(id: SectionId): void {
  try {
    localStorage.setItem(SECTION_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}
