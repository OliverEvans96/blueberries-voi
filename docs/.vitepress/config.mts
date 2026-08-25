import { defineConfig } from "vitepress";

export default defineConfig({
  title: "Blueberries VOI",
  description:
    "How much is better information about produce freshness worth to a grocery store?",
  base: "/docs/blueberries/",
  cleanUrls: true,
  markdown: {
    math: true,
  },
  themeConfig: {
    nav: [
      { text: "Start here", link: "/" },
      { text: "The store", link: "/store/freshness-not-age" },
      { text: "The ladder", link: "/ladder/channels" },
      { text: "Inference", link: "/inference/why-particle-filter" },
      { text: "Control", link: "/control/newsvendor" },
      { text: "Findings", link: "/findings/does-belief-sharpen" },
      { text: "Studio", link: "/using-it/studio-guide" },
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
          { text: "How fruit ages: the gamma process", link: "/store/gamma-aging" },
          { text: "The cold chain: from truck to door", link: "/store/cold-chain-arrival" },
          { text: "Who buys which punnet", link: "/store/picking" },
          { text: "Spoilage and waste", link: "/store/spoilage-waste" },
          { text: "Demand: a calendar, not a coin", link: "/store/demand-calendar" },
          { text: "One day, in order", link: "/store/one-day-in-order" },
        ],
      },
      {
        text: "What the store can see — the knowledge ladder",
        items: [
          { text: "Three channels, not seven scenarios", link: "/ladder/channels" },
          { text: "The observation scenarios, in a real store", link: "/ladder/observation-scenarios" },
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
          { text: "One filter day, four stages", link: "/inference/one-filter-day" },
          { text: "UPC vs GSIN: refinement, not a different model", link: "/inference/upc-vs-gsin" },
          { text: "Birth freshness: what each observation scenario conditions on", link: "/inference/birth-freshness" },
          { text: "From particles to charts: the wire", link: "/inference/belief-wire" },
        ],
      },
      {
        text: "What the store orders — control",
        items: [
          { text: "Newsvendor in one page", link: "/control/newsvendor" },
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
          { text: "Does information sharpen belief?", link: "/findings/does-belief-sharpen" },
          { text: "Why pack date buys the most", link: "/findings/why-pack-date" },
          { text: "Does sharper belief make money?", link: "/findings/does-money-follow" },
          { text: "Limitations, in one place", link: "/findings/limitations" },
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
        text: "Reference",
        items: [
          { text: "Parameter reference", link: "/reference/parameters" },
          { text: "Rust API (voi_core)", link: "/reference/rust-api" },
        ],
      },
    ],
    socialLinks: [
      { icon: "github", link: "https://github.com/OliverEvans96/blueberries-voi" },
    ],
    search: { provider: "local" },
  },
});
