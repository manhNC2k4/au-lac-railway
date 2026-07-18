import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:3000",
    locale: "vi-VN",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000/booking",
    reuseExistingServer: true,
    timeout: 120_000,
    env: { API_SERVER_URL: process.env.API_SERVER_URL ?? "http://127.0.0.1:8000" },
  },
});
