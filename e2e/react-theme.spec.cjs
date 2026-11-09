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

async function expectReadableText(page, selector) {
  const color = await page.locator(selector).first().evaluate(element => getComputedStyle(element).color);
  const channels = (color.match(/[0-9.]+/g) || []).map(Number);
  expect(channels.length, `${selector} should have a computed text color, got ${color}`).toBeGreaterThanOrEqual(3);
  const average = (channels[0] + channels[1] + channels[2]) / 3;
  expect(average, `${selector} should remain readable on a dark surface, got ${color}`).toBeGreaterThan(120);
}

async function expectDarkSurface(page, selector) {
  const locator = page.locator(selector).first();
  await expect(locator, `Expected surface ${selector} to be visible`).toBeVisible();
  const effectiveBackground = await locator.evaluate(element => {
    const layers = [];
    for (let node = element; node && node !== document.documentElement; node = node.parentElement) {
      const color = getComputedStyle(node).backgroundColor;
      const values = (color.match(/[0-9.]+/g) || []).map(Number);
      if (values.length < 3) continue;
      const alpha = color.startsWith("rgba(") ? values[3] : 1;
      if (alpha > 0) layers.push([values[0], values[1], values[2], alpha]);
    }
    let result = [11, 11, 20];
    for (const [red, green, blue, alpha] of layers.reverse()) {
      result = [
        red * alpha + result[0] * (1 - alpha),
        green * alpha + result[1] * (1 - alpha),
        blue * alpha + result[2] * (1 - alpha)
      ];
    }
    return result;
  });
  const average = effectiveBackground.reduce((sum, channel) => sum + channel, 0) / 3;
  expect(average, `${selector} should resolve to the dark React theme, got ${effectiveBackground.join(", ")}`).toBeLessThan(110);
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
  await expectReadableText(page, "#growth-summary .summary-value");
  await expectDarkSurface(page, "#growth-trend .chart-card");
  await expectDarkSurface(page, "#growth-trend .growth-timeline-section");
  await expectDarkSurface(page, "#growth-trend .growth-timeline-marker");
  await expectDarkSurface(page, "#growth-prediction .prediction-card");
  await expectDarkSurface(page, "#growth-prediction .growth-goal-card");

  const predictionLayout = page.locator("#growth-prediction .growth-prediction-layout");
  const desktopColumns = await predictionLayout.evaluate(element =>
    getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length
  );
  expect(desktopColumns, "prediction and goal should sit in two desktop columns").toBe(2);
  const predictionColumns = await page.locator("#growth-prediction .prediction-grid").evaluate(element =>
    getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length
  );
  expect(predictionColumns, "prediction metrics should use a two-by-two grid").toBe(2);
  await expect(page.locator("#growth-prediction .prediction-value").first()).toHaveCSS("white-space", "nowrap");
  const noMidWordBreakSelectors = [
    "#growth-prediction .prediction-label",
    "#growth-prediction .prediction-note",
    "#growth-prediction .growth-goal-heading h3",
    "#growth-prediction .growth-goal-heading p",
    "#growth-prediction .growth-goal-status",
    "#growth-prediction .growth-goal-pace",
    "#growth-prediction .growth-goal-storage-note",
    "#growth-prediction .growth-goal-notification span"
  ];
  for (const selector of noMidWordBreakSelectors) {
    await expect(page.locator(selector).first(), selector).toHaveCSS("word-break", "keep-all");
    await expect(page.locator(selector).first(), selector).toHaveCSS("overflow-wrap", "normal");
  }
  await expect(page.locator("#growth-prediction .growth-goal-heading h3")).toHaveCSS("white-space", "nowrap");
  await expect(page.locator("#growth-prediction .growth-goal-status")).toHaveCSS("white-space", "nowrap");

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileColumns = await predictionLayout.evaluate(element =>
    getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length
  );
  expect(mobileColumns, "prediction and goal should stack on mobile").toBe(1);
  const mobileOverflow = await page.locator("#growth-prediction").evaluate(element =>
    element.scrollWidth > element.clientWidth
  );
  expect(mobileOverflow, "prediction section should not overflow horizontally on mobile").toBe(false);

  await page.setViewportSize({ width: 320, height: 740 });
  const narrowMetricColumns = await page.locator("#growth-prediction .prediction-grid").evaluate(element =>
    getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length
  );
  expect(narrowMetricColumns, "very narrow screens should use a single metric column").toBe(1);
  const narrowOverflow = await page.locator("#growth-prediction").evaluate(element =>
    element.scrollWidth > element.clientWidth
  );
  expect(narrowOverflow, "prediction section should not overflow at 320px").toBe(false);
  await page.setViewportSize({ width: 1280, height: 900 });

  await page.locator("#growth-trend .history-range-select").selectOption("30");
  await expect(page.locator(".period-summary-section")).toBeVisible();
  await expectDarkSurface(page, ".period-summary-section .period-summary-card");

  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expectDarkSurface(page, "#analytics .ai-analysis-card");

  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(30);
  await expectDarkSurface(page, "#history .history-table thead th");
  await expectDarkSurface(page, "#history .history-table tbody td");
  await expectReadableText(page, "#history .history-table tbody td");

  await page.locator('.mgt-nav a[href="#/details"]').click();
  await expect(page.locator("#details .character-details-section")).toBeVisible();
  await expectDarkSurface(page, "#details .character-details-section");

  await page.locator('.mgt-nav a[href="#/comparison"]').click();
  await expectDarkSurface(page, "#comparison .comparison-card");

  await page.goto("/legacy/");
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(1);
  await expect(page.locator("#searchForm")).toBeVisible();
});
