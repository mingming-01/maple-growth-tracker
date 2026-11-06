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

  const detailRequests = { stats: 0, union: 0 };
  await page.route(/\/api\/character-details\?/, route => {
    const section = new URL(route.request().url()).searchParams.get("section");
    detailRequests[section] = (detailRequests[section] || 0) + 1;
    const payload = section === "union" ? {
      section: "union",
      status: "available",
      sources: [
        {
          id: "union", label: "유니온 기본 정보", status: "available",
          data: { union_level: 9000, union_grade: "그랜드 마스터 유니온", union_artifact_level: 40 }
        },
        {
          id: "unionStateStat", label: "유니온 스탯", status: "available",
          activePresetNo: 2,
          currentData: { union_state_stat: ["보스 몬스터 공격 시 데미지 +20% 증가"] },
          presets: [
            { number: 1, data: { union_state_stat: ["경험치 획득량 10% 증가", "메소 획득량 5% 증가"] } },
            { number: 2, data: { union_state_stat: ["보스 몬스터 공격 시 데미지 +20% 증가"] } }
          ],
          data: { union_max_point: 9000 }
        },
        {
          id: "unionArtifact", label: "유니온 아티팩트", status: "available",
          currentData: {
            union_artifact_effect: [{ name: "올스탯 증가", level: 10 }],
            union_artifact_crystal: [{
              name: "주황버섯", level: 5, validity_flag: "0", is_expired: false,
              crystal_option_name_1: "버프 지속시간 증가",
              crystal_option_name_2: "크리티컬 데미지 증가",
              crystal_option_name_3: "보스 몬스터 공격 시 데미지 증가"
            }],
            union_artifact_remain_ap: 20
          },
          data: {}
        },
        {
          id: "unionChampion", label: "유니온 챔피언", status: "available",
          currentData: {
            union_champion: [{
              champion_name: "테스트캐릭터", champion_slot: 1, champion_grade: "SSS",
              champion_class: "아크메이지(불,독)",
              champion_badge_info: [{ stat: "보스 몬스터 공격 시 데미지 +1%" }]
            }],
            champion_badge_total_info: [{ stat: "보스 몬스터 공격 시 데미지 +1%" }]
          },
          data: {}
        }
      ]
    } : {
      section: "stats",
      status: "available",
      dataStatus: "current",
      defaultProfile: "current",
      actualPresetNumbers: { equipment: 1, hyperStat: 2, ability: 1, link: 1, union: 2 },
      actualPresetCombinationComplete: true,
      profileRecommendations: {
        boss: { presetNumbers: { equipment: 1, hyperStat: 2, ability: 1, link: 1, union: 2 }, matchedCategories: ["hyperStat", "ability", "union"], score: 12, confidence: "high" },
        hunting: { presetNumbers: { equipment: 2, hyperStat: 1, ability: 2, link: 2, union: 1 }, matchedCategories: ["hyperStat", "union"], score: 8, confidence: "medium" }
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
          presets: [
            { number: 1, purpose: "boss", data: { ability_grade: "레전드리", ability_info: [{ ability_value: "보스 몬스터 공격 시 데미지 +20%" }] } },
            { number: 2, purpose: "hunting", data: { ability_grade: "유니크", ability_info: [{ ability_value: "메소 획득량 +20%" }] } }
          ],
          data: {}
        },
        {
          id: "itemEquipment", label: "장비 프리셋", status: "available", activePresetNo: 1,
          currentData: { item_equipment: [] },
          presets: [
            { number: 1, purpose: "unknown", data: { item_equipment: [{ item_name: "보스 프리셋 장비", item_equipment_slot: "무기" }] } },
            { number: 2, purpose: "unknown", data: { item_equipment: [{ item_name: "사냥 프리셋 장비", item_equipment_slot: "무기" }] } }
          ],
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
          id: "unionStateStat", label: "유니온 스탯", status: "available", activePresetNo: 2,
          currentData: { union_state_stat: ["보스 몬스터 공격 시 데미지 +20% 증가"] },
          presets: [
            { number: 1, purpose: "hunting", data: { union_state_stat: ["경험치 획득량 10% 증가"] } },
            { number: 2, purpose: "boss", data: { union_state_stat: ["보스 몬스터 공격 시 데미지 +20% 증가"] } }
          ],
          data: { union_max_point: 9000 }
        }
      ]
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload)
    });
  });
  await page.goto("/");
  await page.locator("#characterName").fill("프리셋테스트");
  await page.locator("#searchForm button[type='submit']").click();
  await expect(page.locator("#resultSection")).toBeVisible();
  await expect(page.locator("#characterDetailsContent")).toContainText("능력치");
  await expect(page.locator("#characterDetailsContent")).toContainText("현재 적용 중인 실제 전투력");
  expect(detailRequests.stats).toBe(1);

  await expect(page.locator("#characterDetailsContent .game-preset-select")).toHaveCount(4); 
  const hyperPreset = page.locator("#characterDetailsContent .game-preset-select").first();
  await expect(hyperPreset).toHaveValue("2");
  await hyperPreset.selectOption("1");
  await expect(page.locator("#characterDetailsContent")).toContainText("크리티컬 데미지");

  const equipmentPreset = page.locator("#characterDetailsContent .game-preset-select").nth(2);
  await expect(equipmentPreset).toHaveValue("1");
  await equipmentPreset.selectOption("2");
  await expect(page.locator("#characterDetailsContent .game-selected-build-window")).toContainText("사냥 프리셋 장비");

  await page.locator('[data-detail-tab="stats"]').click();
  expect(detailRequests.stats).toBe(1);
  await expect(page.locator("#characterDetailsContent .game-preset-select").first()).toHaveValue("1");
  await expect(page.locator("#characterDetailsContent .game-preset-select").nth(2)).toHaveValue("2");

  await page.locator('[data-detail-tab="union"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("유니온 스탯 투자");
  await expect(page.locator("#characterDetailsContent")).toContainText("주황버섯");
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트캐릭터");
  await expect(page.locator("#characterDetailsContent")).toContainText("SSS");
  await expect(page.locator("#characterDetailsContent .game-union-crystal-monster")).toHaveCount(1);
  await expect(page.locator("#characterDetailsContent .game-union-crystal-order")).toHaveText("01");
  const unionPreset = page.locator("#characterDetailsContent .game-union-state-panel .game-preset-select");
  const unionOptionLabels = await unionPreset.locator("option").allTextContents();
  expect(unionOptionLabels.every(label => !/보스|사냥/.test(label))).toBe(true);
  await expect(unionPreset).toHaveValue("2");
  await unionPreset.selectOption("1");
  await expect(page.locator("#characterDetailsContent")).toContainText("경험치 획득량");
  await expect(page.locator("#characterDetailsContent")).not.toContainText("보스 몬스터 공격 시 데미지 +20% 증가");
  expect(detailRequests.union).toBe(1);
});
