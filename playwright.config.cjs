const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: { timeout: 5000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5000",
    browserName: "chromium",
    headless: true,
  },
  webServer: {
    command: "python scripts/run_e2e_server.py",
    url: "http://127.0.0.1:5000/",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
    env: {
      GROWTH_DATABASE_URL: "",
      FLASK_SECRET_KEY: "maple-growth-e2e-test-secret-32-characters",
      FLASK_COOKIE_SECURE: "false",
    },
  },
});
