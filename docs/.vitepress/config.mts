import { defineConfig } from "vitepress";

import { markdownFigures } from "./markdown-figures";

export default defineConfig({
  title: "Blueberries VOI",
  description:
    "How much is better information about produce freshness worth to a grocery store?",
  base: "/docs/blueberries/",
  cleanUrls: true,
  markdown: {
    math: true,
    config: (md) => {
      markdownFigures(md);
    },
  },
  themeConfig: {
    siteTitle: false,
    nav: [
      { text: "Start here", link: "/" },
      { text: "The store", link: "/store/freshness-not-age" },
      { text: "The ladder", link: "/ladder/channels" },
      { text: "Inference", link: "/inference/why-particle-filter" },
      { text: "Control", link: "/control/newsvendor" },
      { text: "Findings", link: "/findings/does-belief-sharpen" },
      { text: "Studio", link: "/using-it/studio-guide" },
      { text: "Rust API", link: "/api/rust/index.html" },
    ],
    sidebar: [
      {
        text: "Start here",
        items: [
          { text: "What this is", link: "/" },
          { text: "The store in five minutes", link: "/start-here/five-minutes" },
          { text: "Notation and glossary", link: "/start-here/glossary" },
        ],
      },
      {
        text: "The store — physics and ground truth",
        items: [
          { text: "Freshness, not age", link: "/store/freshness-not-age" },
          { text: "How fruit loses freshness — the gamma process", link: "/store/gamma-aging" },
          { text: "Cold-Chain Arrival Model", link: "/store/cold-chain-arrival" },
          { text: "Who buys which punnet", link: "/store/picking" },
          { text: "Spoilage and waste", link: "/store/spoilage-waste" },
          { text: "Demand: a calendar, not a coin", link: "/store/demand-calendar" },
          { text: "One day, in order", link: "/store/one-day-in-order" },
        ],
      },
      {
        text: "What the store can see — the knowledge ladder",
        items: [
          { text: "Observation channels", link: "/ladder/channels" },
          { text: "The observation ladder", link: "/ladder/observation-scenarios" },
          {
            text: "No channel ever observes freshness",
            link: "/ladder/no-channel-observes-freshness",
          },
        ],
      },
      {
        text: "What the store believes — inference",
        items: [
          { text: "Why a particle filter", link: "/inference/why-particle-filter" },
          { text: "What one particle is", link: "/inference/what-one-particle-is" },
          { text: "UPC vs LGTIN", link: "/inference/upc-vs-lgtin" },
        ],
      },
      {
        text: "What the store orders — control",
        items: [
          { text: "The newsvendor problem", link: "/control/newsvendor" },
          { text: "Why not the textbook fractile", link: "/control/why-not-textbook-fractile" },
          { text: "Effective inventory", link: "/control/effective-inventory" },
          { text: "The ordering rule", link: "/control/ordering-rule" },
          { text: "Protection demand under a calendar", link: "/control/protection-demand" },
        ],
      },
      {
        text: "What it's worth — economics and the experiment",
        items: [
          { text: "Profit accounting", link: "/economics/profit-accounting" },
          { text: "Same weather, different glasses", link: "/economics/crn-seeding" },
          { text: "The VOI metric", link: "/economics/voi-metric" },
        ],
      },
      {
        text: "Findings — honestly",
        items: [
          { text: "Does belief actually sharpen as you climb the ladder?", link: "/findings/does-belief-sharpen" },
          { text: "Why a pack date does so much", link: "/findings/why-pack-date" },
          { text: "Does the money follow?", link: "/findings/does-money-follow" },
          { text: "Limitations", link: "/findings/limitations" },
        ],
      },
      {
        text: "Using it",
        items: [
          { text: "The studio, guided", link: "/using-it/studio-guide" },
          { text: "Run it locally", link: "/using-it/run-locally" },
        ],
      },
      {
        text: "Appendix",
        items: [
          { text: "Model parameters", link: "/reference/parameters" },
          { text: "Rust API (voi_core)", link: "/reference/rust-api" },
          { text: "The Belief Wire", link: "/inference/belief-wire" },
          { text: "Birth Freshness by Observation Scenario", link: "/inference/birth-freshness" },
          { text: "One Filter Day", link: "/inference/one-filter-day" },
          { text: "Window service-level ordering", link: "/control/window-service-level" },
        ],
      },
    ],
    socialLinks: [
      { icon: "github", link: "https://github.com/OliverEvans96/blueberries-voi" },
    ],
    search: { provider: "local" },
  },
});
