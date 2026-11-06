const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ page }) => {
  // E2E는 브라우저에 서드파티 CDN 접속을 요구하지 않는다.
  await page.route("https://cdn.jsdelivr.net/**", route => route.abort());
});

test("home page renders and validates an empty character search", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#searchForm")).toBeVisible();
  await expect(page.getByRole("heading", { name: "MAPLE GROWTH TRACKER" }).first()).toBeVisible();
  await expect(page.locator("#favoriteEmpty")).toBeVisible();

  await page.locator("#searchForm button[type='submit']").click();
  await expect(page.locator("#errorMessage")).toBeVisible();
  await expect(page.locator("#errorMessage")).toContainText("캐릭터명을 입력해주세요.");
});

test("admin logs require an authenticated session", async ({ page }) => {
  await page.goto("/admin/logs");
  await expect(page).toHaveURL(/\/admin\/login$/);
  await expect(page.locator("form")).toBeVisible();
  await expect(page.locator("input[name='csrf_token']")).toHaveValue(/.+/);
});
