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

test("character details automatically open the game-style stat window", async ({ page }) => {
  await page.addInitScript(() => {
    window.Chart = class { destroy() {} update() {} };
  });

  const timestamp = "2026-11-06T04:00:00+09:00";
  await page.route(/\/api\/character\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리셋테스트", worldName: "크로아", job: "전사", guildName: "테스트",
      level: 200, experience: 300, experienceRate: "30.000",
      ranking: 1, worldRanking: 1, jobWorldRanking: 1, jobRanking: 1,
      ocid: "preset-test-ocid", rankingDataStatus: "available",
      dataStatus: "current", dataAsOf: timestamp
    })
  }));
  await page.route(/\/api\/history\?/, route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리셋테스트", worldName: "크로아", level: 200,
      history: [
        { date: "2026-11-05", ranking: 2, level: 200, experience: 200, experienceChange: null, recordStatus: "available" },
        { date: "2026-11-06", ranking: 1, level: 200, experience: 300, experienceChange: 100, recordStatus: "available" }
      ],
      historyStatus: "complete", historyStorage: { backend: "sqlite", status: "saved", savedRecords: 2 },
      dataStatus: "current", dataAsOf: timestamp
    })
  }));
  await page.route(/\/api\/ai-analysis/, route => route.fulfill({
    status: 200, contentType: "application/json",
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
        defaultProfile: "current",
        actualPresetNumbers: { equipment: 1, hyperStat: 2, ability: 1, link: 1, union: 1 },
        actualPresetCombinationComplete: true,
        profileRecommendations: {
          boss: { presetNumbers: { equipment: 1, hyperStat: 2, ability: 1, link: 1, union: 1 }, matchedCategories: ["equipment", "hyperStat", "link"], score: 12, confidence: "high" },
          hunting: { presetNumbers: { equipment: 2, hyperStat: 1, ability: 2, link: 2, union: 2 }, matchedCategories: ["equipment", "hyperStat"], score: 8, confidence: "medium" }
        },
        sources: [
          {
            id: "stat", label: "주요 스탯", status: "available", combatPower: "123456",
            activePresetNo: null, presets: [],
            data: { final_stat: [
              { stat_name: "STR", stat_value: "12000" },
              { stat_name: "전투력", stat_value: "123456" }
            ] }
          },
          {
            id: "hyperStat", label: "하이퍼 스탯", status: "available", activePresetNo: 2,
            currentData: { hyper_stat: [{ stat_type: "보스 데미지", stat_level: 10 }] },
            presets: [
              { number: 1, purpose: "hunting", data: { hyper_stat: [{ stat_type: "크리티컬 데미지", stat_level: 5 }] } },
              { number: 2, purpose: "boss", data: { hyper_stat: [{ stat_type: "보스 데미지", stat_level: 10 }] } }
            ],
            data: {}
          },
          {
            id: "ability", label: "어빌리티", status: "available", activePresetNo: 1,
            currentData: { ability_info: [{ ability_value: "보스 몬스터 공격 시 데미지 +20%" }] },
            presets: [{ number: 1, purpose: "boss", data: { ability_info: [{ ability_value: "보스 몬스터 공격 시 데미지 +20%" }] } }],
            data: {}
          },
          {
            id: "itemEquipment", label: "장비 프리셋", status: "available", activePresetNo: 1,
            currentData: { item_equipment: [] },
            presets: [{ number: 1, purpose: "unknown", data: { item_equipment: [] } }],
            data: {}
          },
          {
            id: "linkSkill", label: "링크 스킬 프리셋", status: "available", activePresetNo: 1,
            currentData: { character_link_skill: [], character_owned_link_skill: null },
            presets: [{
              number: 1, purpose: "boss",
              data: {
                character_link_skill: [{ skill_name: "소울 컨트랙트", skill_level: 2 }],
                character_owned_link_skill: { skill_name: "데몬스 퓨리", skill_level: 2 }
              }
            }],
            data: {}
          },
          {
            id: "unionRaider", label: "유니온 프리셋", status: "available", activePresetNo: 1,
            presets: [{ number: 1, purpose: "unknown", data: { union_raider: {}, union_block: {} } }],
            currentData: {}, data: {}
          }
        ]
      })
    });
  });

  await page.goto("/");
  await page.locator("#characterName").fill("프리셋테스트");
  await page.locator("#searchForm button[type='submit']").click();
  await expect(page.locator("#resultSection")).toBeVisible();
  await expect(page.locator("#characterDetailsContent")).toContainText("능력치");
  await expect(page.locator("#characterDetailsContent")).toContainText("현재 적용 중인 실제 전투력");
  expect(detailRequests).toBe(1);

  const hyperPreset = page.locator("#characterDetailsContent .game-preset-select").first();
  await expect(hyperPreset).toHaveValue("2");
  await hyperPreset.selectOption("1");
  await expect(page.locator("#characterDetailsContent")).toContainText("크리티컬 데미지");

  await page.locator('[data-detail-tab="stats"]').click();
  expect(detailRequests).toBe(1);
});
