const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ page }) => {
  await page.route("https://cdn.jsdelivr.net/**", route => route.abort());
});

test("empty character search is disabled in the React dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.getByRole("button", { name: /캐릭터 조회/ })).toBeDisabled();
});

test("admin logs require an authenticated session", async ({ page }) => {
  await page.goto("/admin/logs");
  await expect(page).toHaveURL(/\/admin\/login$/);
  await expect(page.locator("form")).toBeVisible();
  await expect(page.locator("input[name='csrf_token']")).toHaveValue(/.+/);
});
