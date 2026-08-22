import type { SectionId } from "./sections";

export type StudioChapter = {
  id: string;
  title: string;
  sectionIds: SectionId[];
};

export const STUDIO_CHAPTERS: StudioChapter[] = [
  {
    id: "operate",
    title: "Operate",
    sectionIds: ["economics", "autopilot"],
  },
  {
    id: "understand",
    title: "Understand",
    sectionIds: ["demand", "arrival"],
  },
  {
    id: "tune",
    title: "Tune",
    sectionIds: ["physics", "logistics", "pricing"],
  },
];

export function chapterForSection(sectionId: SectionId): StudioChapter | undefined {
  return STUDIO_CHAPTERS.find((ch) => ch.sectionIds.includes(sectionId));
}
