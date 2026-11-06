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
    const payload = section === "symbols" ? {
      section: "symbols",
      status: "available",
      sources: [{
        id: "symbolEquipment", label: "심볼", status: "available",
        currentData: { symbol: [{
          symbol_name: "테스트 그랜드 어센틱심볼", symbol_level: 11,
          symbol_growth_count: 0, symbol_require_growth_count: null,
          symbol_force: 150, symbol_str: 15000, symbol_dex: 15000,
          symbol_int: 15000, symbol_luk: 15000, symbol_hp: 450000,
          symbol_description: "최대 레벨에 도달한 심볼"
        }] },
        data: {}
      }]
    } : section === "equipment" ? {
      section: "equipment",
      status: "available",
      sources: [
        {
          id: "characterAppearance", label: "헤어·성형·피부", status: "available",
          currentData: {
            character_hair: { hair_name: "테스트 헤어" },
            character_face: { face_name: "테스트 성형" },
            character_skin_name: "뽀송 피부"
          },
          data: {}
        },
        {
          id: "itemEquipment", label: "장비", status: "available", activePresetNo: 1,
          currentData: {
            item_equipment: [
              { item_name: "테스트 무기", item_equipment_slot: "무기", item_icon: "https://example.com/weapon.png" },
              { item_name: "테스트 보조무기", item_equipment_slot: "보조무기", item_icon: "https://example.com/subweapon.png" }
            ]
          },
          presets: [{ number: 1, data: { item_equipment: [
            { item_name: "테스트 무기", item_equipment_slot: "무기", item_icon: "https://example.com/weapon.png" },
            { item_name: "테스트 보조무기", item_equipment_slot: "보조무기", item_icon: "https://example.com/subweapon.png" }
          ] } }],
          data: {}
        },
        {
          id: "androidEquipment", label: "안드로이드", status: "available",
          currentData: {
            android_name: "테스트 안드로이드",
            android_icon: "",
            android_grade: "레전드리",
            android_gender: "여성",
            android_hair: { hair_name: "테스트 안드로이드 헤어", base_color: "검정" },
            android_face: { face_name: "테스트 안드로이드 성형", base_color: "갈색" },
            android_skin_name: "테스트 안드로이드 피부"
          },
          data: {}
        },
        {
          id: "setEffect", label: "세트 효과", status: "available",
          currentData: { set_effect: [] }, data: {}
        }
      ]
    } : section === "skills" ? {
      section: "skills",
      status: "available",
      sources: [
        {
          id: "skill6", label: "6차 스킬", status: "available",
          data: { character_skill: [{
            skill_name: "테스트 6차 스킬", skill_level: 1,
            skill_description: "6차 스킬 설명"
          }] }
        },
        {
          id: "hexaMatrix", label: "HEXA 코어", status: "available",
          data: { character_hexa_core_equipment: [{
            hexa_core_type: "강화 코어", hexa_core_name: "테스트 HEXA 코어",
            hexa_core_level: 10, linked_skill: [{ hexa_skill_id: "테스트 6차 스킬" }]
          }] }
        },
        {
          id: "hexaStat", label: "HEXA 스탯", status: "available",
          data: {
            character_hexa_stat_core: [{
              slot_id: "0", main_stat_name: "크리티컬 데미지", main_stat_level: 10,
              sub_stat_name_1: "보스 데미지", sub_stat_level_1: 5,
              sub_stat_name_2: "방어율 무시", sub_stat_level_2: 5, stat_grade: "레어"
            }],
            character_hexa_stat_core_2: [{
              slot_id: "1", main_stat_name: "보스 데미지", main_stat_level: 8,
              sub_stat_name_1: "크리티컬 데미지", sub_stat_level_1: 4,
              sub_stat_name_2: "공격력", sub_stat_level_2: 4, stat_grade: "레어"
            }],
            character_hexa_stat_core_3: [{
              slot_id: "2", main_stat_name: "방어율 무시", main_stat_level: 6,
              sub_stat_name_1: "보스 데미지", sub_stat_level_1: 3,
              sub_stat_name_2: "공격력", sub_stat_level_2: 3, stat_grade: "레어"
            }]
          }
        }
      ]
    } : section === "union" ? {
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
              champion_class: "아크메이지(불,독)", character_image: "https://example.com/champion.png",
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

  await expect(page.locator("#characterDetailsContent .game-preset-select")).toHaveCount(2);
  await expect(page.locator("#characterDetailsContent .game-profile-window")).toHaveCount(0);
  await expect(page.locator("#characterDetailsContent .game-stat-detail-card-header .game-preset-select")).toHaveCount(2);
  await expect(page.locator("#characterDetailsContent .game-stat-grid")).toContainText("STR");
  await expect(page.locator("#characterDetailsContent")).toContainText("어빌리티");
  await expect(page.locator("#characterDetailsContent")).toContainText("하이퍼 스탯");
  await expect(page.locator("#characterDetailsContent .game-selected-build-window")).toHaveCount(0);
  await expect(page.locator("#characterDetailsContent")).not.toContainText("보스 프리셋 장비");

  const abilityPreset = page.locator("#characterDetailsContent .game-stat-detail-card-header .game-preset-select").nth(0);
  await expect(abilityPreset).toHaveValue("1");
  await abilityPreset.selectOption("2");
  const hyperPreset = page.locator("#characterDetailsContent .game-stat-detail-card-header .game-preset-select").nth(1);
  await expect(hyperPreset).toHaveValue("2");
  await hyperPreset.selectOption("1");
  await page.locator('[data-detail-tab="stats"]').click();
  expect(detailRequests.stats).toBe(1);
  await expect(page.locator("#characterDetailsContent .game-stat-detail-card-header .game-preset-select").nth(0)).toHaveValue("2");
  await expect(page.locator("#characterDetailsContent .game-stat-detail-card-header .game-preset-select").nth(1)).toHaveValue("1");

  await page.locator('[data-detail-tab="symbols"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트 그랜드 어센틱심볼");
  const maxSymbol = page.locator("#characterDetailsContent .game-symbol-tile");
  await maxSymbol.hover();
  await expect(maxSymbol.locator(".game-hover-tooltip")).toContainText("성장량 MAX");
  await expect(maxSymbol.locator(".game-hover-tooltip")).toContainText("포스 +150");
  await expect(maxSymbol.locator(".game-hover-tooltip")).toContainText("STR +15,000");
  await expect(maxSymbol.locator(".game-hover-tooltip")).toContainText("HP +450,000");

  await page.locator('[data-detail-tab="equipment"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트 헤어");
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트 성형");
  await expect(page.locator("#characterDetailsContent")).toContainText("뽀송 피부");
  const androidSlot = page.locator('#characterDetailsContent [data-slot="android"]');
  await expect(androidSlot).toContainText("테스트 안드로이드");
  await androidSlot.hover();
  const androidTooltip = androidSlot.locator(".game-hover-tooltip");
  await expect(androidTooltip).toBeVisible();
  await expect(androidTooltip).toContainText("헤어 · 테스트 안드로이드 헤어");
  await expect(androidTooltip).toContainText("성형 · 테스트 안드로이드 성형");
  await expect(androidTooltip).toContainText("피부 · 테스트 안드로이드 피부");
  await expect(page.locator('#characterDetailsContent [data-slot="weapon"]')).toContainText("테스트 무기");
  await expect(page.locator('#characterDetailsContent [data-slot="subweapon"]')).toContainText("테스트 보조무기");
  const expectedSlots = {
    ring4: ["4", "1"], pendant1: ["4", "2"], hair: ["4", "3"],
    faceStyle: ["4", "4"], skin: ["4", "5"], shoulder: ["4", "6"], medal: ["4", "7"],
    belt: ["5", "1"], pendant2: ["5", "2"], weapon: ["5", "3"],
    subweapon: ["5", "4"], emblem: ["5", "5"], android: ["5", "6"], heart: ["5", "7"]
  };
  for (const [slot, [row, column]] of Object.entries(expectedSlots)) {
    const element = page.locator(`#characterDetailsContent [data-slot="${slot}"]`);
    await expect(element).toHaveCSS("grid-row-start", row);
    await expect(element).toHaveCSS("grid-column-start", column);
  }

  await page.locator('[data-detail-tab="skills"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트 6차 스킬");
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트 HEXA 코어");
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-columns")).toHaveCount(1);
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-column")).toHaveCount(3);
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-column-title")).toHaveText(["HEXA 1", "HEXA 2", "HEXA 3"]);
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-entry .game-hover-tooltip")).toHaveCount(0);
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-columns")).toContainText("크리티컬 데미지");
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-columns")).toContainText("보스 데미지");
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-columns")).toContainText("방어율 무시");
  await expect(page.locator("#characterDetailsContent .game-hexa-stat-columns")).not.toContainText("슬롯 1");

  await page.locator('[data-detail-tab="union"]').click();
  await expect(page.locator("#characterDetailsContent")).toContainText("유니온 스탯 투자");
  await expect(page.locator("#characterDetailsContent")).toContainText("주황버섯");
  await expect(page.locator("#characterDetailsContent")).toContainText("테스트캐릭터");
  await expect(page.locator("#characterDetailsContent")).toContainText("SSS");
  await expect(page.locator("#characterDetailsContent .game-union-champion-avatar-wrap")).toHaveCount(0);
  await expect(page.locator("#characterDetailsContent .game-champion-hover-tooltip img")).toHaveCount(1);
  const championCard = page.locator("#characterDetailsContent .game-union-champion-card");
  await championCard.hover();
  await expect(championCard.locator(".game-champion-hover-tooltip")).toBeVisible();
  await expect(championCard.locator(".game-champion-hover-tooltip img")).toHaveCSS("width", "248px");
  await expect(page.locator("#characterDetailsContent .game-union-crystal-grid")).toHaveCSS("grid-template-columns", /repeat\(3,/);
  await expect(page.locator("#characterDetailsContent .game-union-champion-grid")).toHaveCSS("grid-template-columns", /repeat\(3,/);
  await expect(page.locator("#characterDetailsContent .game-union-crystal-monster")).toHaveCount(0);
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


test("character detail tabs remain in one horizontal row on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator("#resultSection").evaluate(element => { element.hidden = false; });
  await page.locator("#characterDetailsSection").evaluate(element => { element.hidden = false; });
  const tabs = page.locator(".detail-tabs");
  await expect(tabs).toBeVisible();
  const layout = await tabs.evaluate(element => {
    const children = Array.from(element.children).map(child => child.getBoundingClientRect());
    return {
      flexWrap: getComputedStyle(element).flexWrap,
      overflowX: getComputedStyle(element).overflowX,
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
      childTops: children.map(rect => Math.round(rect.top))
    };
  });
  expect(layout.flexWrap).toBe("nowrap");
  expect(layout.overflowX).toBe("auto");
  expect(new Set(layout.childTops).size).toBe(1);
  expect(layout.scrollWidth).toBeGreaterThan(layout.clientWidth);
});
