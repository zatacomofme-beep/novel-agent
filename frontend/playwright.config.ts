import { defineConfig, devices } from "@playwright/test";

const frontendPort = Number(process.env.PLAYWRIGHT_PORT ?? 3000);
const frontendBaseURL =
  process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${frontendPort}`;
const apiBaseURL =
  process.env.PLAYWRIGHT_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const shouldStartFrontend = process.env.PLAYWRIGHT_SKIP_FRONTEND_SERVER !== "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: frontendBaseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
  webServer: shouldStartFrontend
    ? {
        command:
          `node -e "try{require('fs').rmSync('.next',{recursive:true,force:true})}catch(e){}" ` +
          `&& npm run dev -- --hostname 127.0.0.1 --port ${frontendPort}`,
        cwd: __dirname,
        url: frontendBaseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          ...process.env,
          NEXT_PUBLIC_API_URL: apiBaseURL,
        },
      }
    : undefined,
});
