import { defineConfig, devices } from "@playwright/test";

// E2E suite for the sovereign-agent-fleet ui/ control surface.
// Drives REAL behavior against the live fleet/api control plane on :8788.
// No mocks: HALLUCINATION must read BLOCKED, beats must pass, the D17
// approval console must produce a genuine human_sig. The UI itself holds
// zero authority — these tests assert it only reads + triggers.

const UI_URL = process.env.UI_BASE ?? "http://127.0.0.1:3002";
const FLEET_API = process.env.FLEET_API ?? "http://127.0.0.1:8788";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: UI_URL,
    trace: "retain-on-failure",
    // Local browsers were installed into the project's node_modules.
    launchOptions: { args: ["--no-sandbox"] },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Build + serve the production bundle. The dev server's Turbopack HMR
  // returns 403 on static chunks to headless Chromium (HMR websocket
  // handshake fails), which prevents client hydration. `next start` serves
  // chunks correctly, so e2e exercises the real built UI.
  webServer: {
    command: "npm run build && npm run start",
    url: UI_URL,
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});

export { UI_URL, FLEET_API };
