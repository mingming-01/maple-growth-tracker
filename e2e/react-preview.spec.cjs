const { test, expect } = require("@playwright/test");

test("React preview is isolated from the existing Flask homepage", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#searchForm")).toBeVisible();

  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "모험가 찾기" })).toBeVisible();
  await expect(page.getByRole("link", { name: "기존 서비스" })).toHaveAttribute("href", "/");
});

test("React preview keeps the existing admin route reachable", async ({ page }) => {
  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.getByRole("link", { name: "관리자" })).toHaveAttribute("href", "/admin/login");
});