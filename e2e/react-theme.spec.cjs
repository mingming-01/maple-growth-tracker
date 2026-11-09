const { test, expect } = require("@playwright/test");

async function installFixtures(page) {
  const character = {
    characterName: "테마검증",
    ocid: "theme-boundary-test-ocid",
    character_image: null,
    worldName: "크로아",
    job: "아크메이지(불,독)",
    guildName: "테스트",
    level: 280,
    experience: 123456789,
    experienceRate: "35.600",
    ranking: 12345,
    worldRanking: 6789,
    jobWorldRanking: 123,
    jobRanking: 456,
    rankingDataStatus: "available"
  };
  const history = [
    { date: "2026-11-04", level: 280, experience: 1000, experienceRate: "35.100", experienceChange: null, recordStatus: "available" },
    { date: "2026-11-05", level: 280, experience: 1200, experienceRate: "35.300", experienceChange: 200, recordStatus: "available" },
    { date: "2026-11-06", level: 280, experience: 1400, experienceRate: "35.600", experienceChange: 200, recordStatus: "available" }
  ];

  await page.route("**/api/character?*", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(character)
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      history,
      historyStatus: "complete",
      historyStorage: { backend: "postgres", status: "saved" }
    })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));
  await page.route("**/api/history/archive?*", async route => {
    const url = new URL(route.request().url());
    const days = Number(url.searchParams.get("days") || 30);
    const endDate = url.searchParams.get("end") || "2026-11-06";
    const collecting = url.searchParams.get("collect") === "1";
    const offset = Number(url.searchParams.get("offset") || 0);
    const limit = Number(url.searchParams.get("limit") || days);
    const [year, month, day] = endDate.split("-").map(Number);
    const endUtc = Date.UTC(year, month - 1, day);
    const records = Array.from({ length: days }, (_, index) => ({
      date: new Date(endUtc - (days - index - 1) * 86400000).toISOString().slice(0, 10),
      ranking: 5000 - index,
      level: 280,
      experience: 1000000 + index * 1000,
      experienceChange: index === 0 ? null : 1000,
      recordStatus: "available",
      levelUp: false
    }));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ocid: character.ocid,
        days,
        startDate: records[0].date,
        endDate: records[records.length - 1].date,
        history: records,
        availableDays: days,
        notReadyDays: 0,
        notCollectedDays: 0,
        collection: collecting ? {
          offset,
          limit,
          checkedDays: limit,
          savedRecords: limit,
          availableRecords: limit,
          noDataRecords: 0,
          remainingDays: Math.max(0, days - offset - limit)
        } : null,
        storageBackend: "postgres",
        persistentStorage: true
      })
    });
  });
  return character;
}

async function expectDarkSurface(page, selector) {
  const locator = page.locator(selector).first();
  await expect(locator, `Expected surface ${selector} to be visible`).toBeVisible();
  const backgroundColor = await locator.evaluate(element => getComputedStyle(element).backgroundColor);
  const channels = (backgroundColor.match(/[0-9.]+/g) || []).map(Number);
  expect(channels.length, `${selector} should have a computed background, got ${backgroundColor}`).toBeGreaterThanOrEqual(3);
  const alpha = backgroundColor.startsWith("rgba(") ? channels[3] : 1;
  expect(alpha, `${selector} should not be transparent`).toBeGreaterThan(0.5);
  const average = (channels[0] + channels[1] + channels[2]) / 3;
  expect(average, `${selector} should use the dark React theme, got ${backgroundColor}`).toBeLessThan(110);
}

test("React routes use the purple-dark theme while the legacy page keeps its stylesheet", async ({ page }) => {
  await installFixtures(page);
  await page.goto("/");
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(0);
  await page.getByLabel("캐릭터명").fill("테마검증");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "테마검증" })).toBeVisible();

  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await expect(page.locator("#growth-summary .summary-card").first()).toBeVisible();
  await expectDarkSurface(page, "#growth-summary .summary-card");
  await expectDarkSurface(page, "#growth-trend .chart-card");
  await expectDarkSurface(page, "#growth-trend .growth-timeline-section");
  await expectDarkSurface(page, "#growth-prediction .growth-goal-card");

  await page.locator("#growth-trend .history-range-select").selectOption("30");
  await expect(page.locator(".period-summary-section")).toBeVisible();
  await expectDarkSurface(page, ".period-summary-section .period-summary-card");

  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expectDarkSurface(page, "#analytics .ai-analysis-card");

  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(30);
  await expectDarkSurface(page, "#history .history-table thead th");
  await expectDarkSurface(page, "#history .history-table tbody td");

  await page.locator('.mgt-nav a[href="#/details"]').click();
  await expect(page.locator("#details .character-details-section")).toBeVisible();
  await expectDarkSurface(page, "#details .character-details-section");

  await page.locator('.mgt-nav a[href="#/comparison"]').click();
  await expectDarkSurface(page, "#comparison .comparison-card");

  await page.goto("/legacy/");
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(1);
  await expect(page.locator("#searchForm")).toBeVisible();
});
