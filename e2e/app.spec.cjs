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

test("character details load lazily and default to the API active preset", async ({ page }) => {
  await page.addInitScript(() => {
    window.Chart = class {
      destroy() {}
      update() {}
    };
  });

  const timestamp = "2026-11-06T04:00:00+09:00";
  await page.route(/\/api\/character\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리셋테스트",
      worldName: "크로아",
      job: "전사",
      guildName: "테스트",
      level: 200,
      experience: 300,
      experienceRate: "30.000",
      ranking: 1,
      worldRanking: 1,
      jobWorldRanking: 1,
      jobRanking: 1,
      ocid: "preset-test-ocid",
      rankingDataStatus: "available",
      dataStatus: "current",
      dataAsOf: timestamp
    })
  }));
  await page.route(/\/api\/history\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리셋테스트",
      worldName: "크로아",
      level: 200,
      history: [
        { date: "2026-11-05", ranking: 2, level: 200, experience: 200, experienceChange: null, recordStatus: "available" },
        { date: "2026-11-06", ranking: 1, level: 200, experience: 300, experienceChange: 100, recordStatus: "available" }
      ],
      historyStatus: "complete",
      historyStorage: { backend: "sqlite", status: "saved", savedRecords: 2 },
      dataStatus: "current",
      dataAsOf: timestamp
    })
  }));
  await page.route(/\/api\/ai-analysis/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ analysis: "[성장 패턴] 테스트", cacheHit: false })
  }));

  let detailRequests = 0;
  await page.route(/\/api\/character-details\?/, route => {
    detailRequests += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        section: "stats",
        status: "available",
        dataStatus: "current",
        sources: [
          {
            id: "stat",
            label: "주요 스탯",
            status: "available",
            combatPower: "123456",
            activePresetNo: null,
            presets: [],
            data: { final_stat: [{ stat_name: "전투력", stat_value: "123456" }] }
          },
          {
            id: "hyperStat",
            label: "하이퍼 스탯",
            status: "available",
            activePresetNo: 2,
            presets: [
              { number: 1, data: { hyper_stat_preset_1: [{ stat_type: "크리티컬 데미지", stat_level: 5 }] } },
              { number: 2, data: { hyper_stat_preset_2: [{ stat_type: "보스 데미지", stat_level: 10 }] } }
            ],
            data: {}
          }
        ]
      })
    });
  });

  await page.goto("/");
  await page.locator("#characterName").fill("프리셋테스트");
  await page.locator("#searchForm button[type='submit']").click();
  await expect(page.locator("#resultSection")).toBeVisible();
  expect(detailRequests).toBe(0);

  await page.locator('[data-detail-tab="stats"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("주요 스탯");
  await expect(page.locator("#characterDetailsContent")).toContainText("현재 적용 상태 전투력");
  const presetSelect = page.locator("#characterDetailsContent .detail-preset-select").first();
  await expect(presetSelect).toHaveValue("2");
  await presetSelect.selectOption("1");
  await expect(page.locator("#characterDetailsContent")).toContainText("크리티컬 데미지");
  expect(detailRequests).toBe(1);
});
