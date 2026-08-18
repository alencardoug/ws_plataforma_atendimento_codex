import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 60_000,
  fullyParallel: false,
  // Every e2e/*.spec.ts file drives the same live backend/Postgres/operator
  // capacity (max 4 active conversations) — they were never designed to run
  // as separate concurrent workers against that shared state (found while
  // adding v3.spec.ts: default worker parallelism across files produced
  // capacity/TRUNCATE-lock races between files, not a product regression).
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chrome",
      use: { launchOptions: { executablePath: "/usr/bin/google-chrome" } },
    },
  ],
});
