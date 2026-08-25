import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PW_PORT ?? 5180);

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
    headless: true,
  },

  projects: [
    {
      name: "chromium",
      // Mobile-only specs run under the "mobile" project below instead —
      // they assert on a phone-width layout the desktop project never sees.
      testIgnore: /\.mobile\.spec\.ts$/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
      },
    },
    {
      name: "mobile",
      testMatch: /\.mobile\.spec\.ts$/,
      use: {
        ...devices["iPhone 13"],
      },
    },
  ],

  webServer: {
    // Production preview — dev-mode StrictMode can skip mounting operator bar / panes.
    command: `npm run preview -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    env: {
      ...process.env,
      PW_E2E: "1",
    },
  },
});
