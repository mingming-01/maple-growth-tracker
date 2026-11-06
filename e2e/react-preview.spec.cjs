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

test("React preview renders a character using the existing Flask API contract", async ({ page }) => {
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리뷰테스트",
      character_image: null,
      worldName: "크로아",
      job: "아크메이지(불,독)",
      guildName: "테스트길드",
      level: 280,
      experience: 123456789,
      experienceRate: "35.600",
      ranking: 12345,
      worldRanking: 6789,
      jobWorldRanking: 123,
      jobRanking: 456,
      bestCombatPower: 987654321
    })
  }));

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("프리뷰테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();

  await expect(page.getByRole("heading", { name: "프리뷰테스트" })).toBeVisible();
  await expect(page.getByText("12,345위")).toBeVisible();
  await expect(page.getByText("크로아 · 아크메이지(불,독) · 테스트길드")).toBeVisible();
});
