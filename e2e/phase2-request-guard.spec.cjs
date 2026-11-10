const { test, expect } = require("@playwright/test");

test("API 요청 보호 변경 후에도 React 시작 화면과 기본 내비게이션이 유지된다", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "캐릭터 찾기" })).toBeVisible();
  await expect(page.locator(".mgt-nav")).toBeVisible();
});
