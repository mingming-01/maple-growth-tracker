const { test, expect } = require("@playwright/test");

test("mobile touch opens item tooltips without clipped detail panels", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  page.setDefaultNavigationTimeout(10000);

  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "상세정보확장테스트", ocid: "mobile-details-expanded-ocid",
      worldName: "크로아", job: "아크메이지", level: 280,
      experience: 123456, experienceRate: "41.250",
      ranking: 10, worldRanking: 20, jobWorldRanking: 30, jobRanking: 40,
      rankingDataStatus: "available"
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ history: [], historyStatus: "complete" })
  }));
  await page.route("**/api/character-details?*", route => {
    const section = new URL(route.request().url()).searchParams.get("section");
    const sources = section === "symbols" ? [{
      id: "symbolEquipment", label: "심볼", status: "available",
      currentData: { symbol: [
        {
          symbol_name: "아케인심볼: 소멸의 여로", symbol_level: 20,
          symbol_force: 300, symbol_description: "심볼 설명 터치 확인",
          symbol_str: "500", symbol_require_growth_count: 100,
          symbol_growth_count: 50
        },
        {
          symbol_name: "그랜드 어센틱 심볼: 테스트", symbol_level: 10,
          symbol_force: 500,
          symbol_description: "경험치 획득량 +5%, 아이템 드롭률 +10%, 메소 획득량 +10%",
          symbol_int: "800", symbol_require_growth_count: 100,
          symbol_growth_count: 40
        }
      ] }, data: {}
    }] : section === "equipment" ? [
      {
        id: "itemEquipment", label: "장비", status: "available",
        activePresetNo: 1,
        currentData: { item_equipment: [
          {
            item_name: "테스트 무기", item_equipment_slot: "무기", item_equipment_part: "무기",
            item_icon: "https://example.com/weapon.png",
            starforce: "22", equipment_level_increase: 10,
            potential_option_grade: "레전드리", additional_potential_option_grade: "에픽",
            item_total_option: {
              str: "500", dex: "20", attack_power: "350",
              boss_damage: "40", ignore_monster_armor: "20"
            },
            item_base_option: { base_equipment_level: 250, base_equipment_job: ["마법사"], attack_power: "200" },
            item_etc_option: { attack_power: "50" },
            item_add_option: { attack_power: "60" },
            item_starforce_option: { attack_power: "40" },
            potential_option_1: "보스 몬스터 공격 시 데미지 +40%",
            additional_potential_option_1: "공격력 +12%"
          },
          {
            item_name: "리스트레인트 링 4레벨", item_equipment_slot: "반지 1",
            item_equipment_part: "반지", item_icon: "https://example.com/ring1.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] }
          },
          {
            item_name: "컨티뉴어스 링 4레벨", item_equipment_slot: "반지 2",
            item_equipment_part: "반지", item_icon: "https://example.com/ring2.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] }
          },
          {
            item_name: "테스트 얼굴 장식", item_equipment_slot: "얼굴장식",
            item_equipment_part: "얼굴장식", item_icon: "https://example.com/face.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] },
            starforce: "0"
          }
        ] },
        presets: [{ number: 1, data: { item_equipment: [
          {
            item_name: "테스트 무기", item_equipment_slot: "무기", item_equipment_part: "무기",
            item_icon: "https://example.com/weapon.png",
            starforce: "22", equipment_level_increase: 10,
            potential_option_grade: "레전드리", additional_potential_option_grade: "에픽",
            item_total_option: {
              str: "500", dex: "20", attack_power: "350",
              boss_damage: "40", ignore_monster_armor: "20"
            },
            item_base_option: { base_equipment_level: 250, base_equipment_job: ["마법사"], attack_power: "200" },
            item_etc_option: { attack_power: "50" },
            item_add_option: { attack_power: "60" },
            item_starforce_option: { attack_power: "40" },
            potential_option_1: "보스 몬스터 공격 시 데미지 +40%",
            additional_potential_option_1: "공격력 +12%"
          },
          {
            item_name: "리스트레인트 링 4레벨", item_equipment_slot: "반지 1",
            item_equipment_part: "반지", item_icon: "https://example.com/ring1.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] }
          },
          {
            item_name: "컨티뉴어스 링 4레벨", item_equipment_slot: "반지 2",
            item_equipment_part: "반지", item_icon: "https://example.com/ring2.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] }
          },
          {
            item_name: "테스트 얼굴 장식", item_equipment_slot: "얼굴장식",
            item_equipment_part: "얼굴장식", item_icon: "https://example.com/face.png",
            item_base_option: { base_equipment_level: 150, base_equipment_job: ["전 직업"] },
            starforce: "0"
          }
        ] } }], data: {}
      },
      {
        id: "characterAppearance", label: "헤어·성형·피부", status: "available",
        currentData: {
          character_hair: { hair_name: "테스트 헤어", base_color: "검정" },
          character_face: { face_name: "테스트 성형", base_color: "갈색" },
          character_skin_name: "뽀송 피부"
        }, data: {}
      },
      {
        id: "androidEquipment", label: "안드로이드", status: "available",
        currentData: { android_name: "싱크로이드 9", android_icon: "https://example.com/android.png",
          android_grade: "레전드리", android_gender: "여성", android_ear_sensor: "미적용" }, data: {}
      },
      { id: "setEffect", label: "세트 효과", status: "available",
        currentData: { set_effect: [{ set_name: "테스트 세트", total_set_count: 4 }] }, data: {} },
      {
        id: "cashItemEquipment", label: "캐시 장비 및 외형 프리셋", status: "available",
        activePresetNo: 1,
        currentData: {
          character_look_mode: "COORDINATION",
          cash_item_equipment_base: [{ cash_item_name: "테스트 캐시 장비", cash_item_equipment_part: "모자",
            cash_item_icon: "https://example.com/cash-hat.png" }]
        },
        presets: [{ number: 1, data: { cash_item_equipment: [
          { cash_item_name: "테스트 캐시 장비", cash_item_equipment_part: "모자",
            cash_item_icon: "https://example.com/cash-hat.png" }
        ] } }], data: {}
      },
      {
        id: "petEquipment", label: "펫 정보", status: "available",
        currentData: {
          pet_1_name: "테스트 펫", pet_1_nickname: "밍펫",
          pet_1_icon: "https://example.com/pet.png",
          pet_1_equipment: [{ item_name: "펫 장비 테스트" }],
          pet_1_auto_skill: [{ skill_name: "펫 자동 줍기" }]
        }, data: {}
      }
    ] : section === "union" ? [
      { id: "union", label: "유니온 기본 정보", status: "available",
        data: { union_level: 9000, union_grade: "그랜드 마스터 유니온" } },
      { id: "unionChampion", label: "유니온 챔피언", status: "available",
        currentData: {
          union_champion: [{
            champion_name: "챔피언 테스트", champion_grade: "SSS", champion_slot: 1,
            champion_class: "아크메이지(썬,콜)", character_class: "아크메이지(썬,콜)",
            character_level: 298, character_image: "https://example.com/champion.png",
            champion_badge_info: [
              { stat: "보스 몬스터 공격 시 데미지 +1%" },
              { stat: "크리티컬 데미지 +1%" },
              { stat: "경험치 획득량 +1%" },
              { stat: "아이템 드롭률 +1%" },
              { stat: "메소 획득량 +1%" }
            ]
          }],
          champion_badge_total_info: [{ stat: "보스 몬스터 공격 시 데미지 +1%" }]
        }, data: {}
      }
    ] : section === "skills" ? [{
      id: "skill6", label: "6차 스킬", status: "available",
      data: { character_skill: [{
        skill_name: "테스트 6차 스킬", skill_level: 30,
        skill_icon: "https://example.com/skill.png",
        skill_description: "스킬 설명 터치 확인",
        skill_effect: "스킬 효과 터치 확인"
      }] }
    }] : [{
      id: "stat", label: "스탯", status: "available",
      combatPower: "123456", data: { final_stat: [{ stat_name: "STR", stat_value: "10000" }] }
    }];
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ section, status: "available", sources })
    });
  });

  try {
    await page.goto("/preview/");
    await page.getByLabel("캐릭터명").fill("상세정보확장테스트");
    await page.getByRole("button", { name: /캐릭터 조회/ }).tap();
    await expect(page.getByRole("heading", { name: "상세정보확장테스트" })).toBeVisible();

    await expect(page.getByText("프리셋 조합 추천")).toHaveCount(0);
    await page.locator('[data-detail-tab="symbols"]').tap();
    const symbol = page.getByRole("button", { name: "아케인심볼: 소멸의 여로 상세 정보" });
    await expect(symbol).toBeVisible();
    await symbol.tap();
    const tooltip = page.locator("body > .game-floating-tooltip");
    await expect(tooltip).toContainText("심볼 설명 터치 확인");
    await expect(tooltip).toContainText("포스 +300");
    await expect(tooltip).toContainText("STR +500");
    await expect(symbol.locator(".game-symbol-growth")).toHaveText("MAX");
    const grandSymbol = page.locator(".game-symbol-tile").filter({ hasText: "그랜드 어센틱 심볼: 테스트" });
    await expect(grandSymbol).toContainText("경험치 5%");
    await expect(grandSymbol).toContainText("드롭률 10%");
    await expect(grandSymbol).toContainText("메획 10%");
    await symbol.tap();
    await expect(tooltip).toHaveCount(0);
    await symbol.tap();
    await expect(tooltip).toContainText("심볼 설명 터치 확인");
    let bounds = await tooltip.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(391);

    await page.locator(".mgt-topbar").tap();
    await expect(tooltip).toHaveCount(0);

    await page.locator('[data-detail-tab="equipment"]').tap();
    const weapon = page.locator('.equipment-game-slot[data-slot="weapon"]');
    await expect(weapon).toBeVisible();
    await weapon.tap();
    const equipmentTooltip = page.locator("body > .game-floating-tooltip");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-star")).toHaveText("★ 22");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-icon")).toBeVisible();
    await expect(equipmentTooltip).toContainText("요구 레벨 Lv. 250 (+10)");
    await expect(equipmentTooltip).toContainText("합계 · 기본 · 스타포스 · 주문서 · 추옵");
    await expect(equipmentTooltip).toContainText("착용 직업 마법사");
    await expect(equipmentTooltip).toContainText("무기 · 무기");
    await expect(equipmentTooltip).toContainText("STR");
    await expect(equipmentTooltip).toContainText("+500");
    await expect(equipmentTooltip).toContainText("공격력");
    await expect(equipmentTooltip).toContainText("+350");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-stat small.is-base")).toContainText("기본 200");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-stat small.is-starforce")).toContainText("스타포스 40");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-stat small.is-scroll")).toContainText("주문서 50");
    await expect(equipmentTooltip.locator(".game-equipment-tooltip-stat small.is-bonus")).toContainText("추옵 60");
    await expect(equipmentTooltip).toContainText("잠재능력");
    await expect(equipmentTooltip).toContainText("보스 몬스터 공격 시 데미지 +40%");
    await expect(equipmentTooltip).toContainText("에디셔널 잠재 옵션");
    await expect(equipmentTooltip).toContainText("공격력 +12%");
    await expect(equipmentTooltip).not.toHaveCSS("overflow-y", "auto");
    const tooltipBounds = await equipmentTooltip.boundingBox();
    expect(tooltipBounds.y + tooltipBounds.height).toBeLessThanOrEqual(844);

    await expect(page.locator(".game-set-effects")).toContainText("테스트 세트");
    await expect(page.locator(".game-set-effects .game-stat-detail-card")).toHaveCount(0);
    const faceSlot = page.locator('.equipment-game-slot[data-slot="face"]');
    await expect(faceSlot.locator(".equipment-game-star")).toHaveCount(0);
    await faceSlot.tap();
    await expect(page.locator("body > .game-floating-tooltip .game-equipment-tooltip-star")).toHaveCount(0);
    await page.locator(".mgt-topbar").tap();
    const seedRing = page.locator('.equipment-game-slot[data-slot="ring1"]');
    await seedRing.tap();
    await expect(page.locator("body > .game-floating-tooltip")).toContainText("시드링 구성");
    await expect(page.locator("body > .game-floating-tooltip")).toContainText("리스트레인트 링 4레벨 · Lv. 4");
    await expect(page.locator("body > .game-floating-tooltip")).toContainText("컨티뉴어스 링 4레벨 · Lv. 4");
    await page.locator(".mgt-topbar").tap();

    await page.getByRole("tab", { name: "치장" }).tap();
    await expect(page.getByText("착용 모드 · COORDINATION")).toBeVisible();
    await expect(page.getByText("테스트 캐시 장비")).toBeVisible();
    await expect(page.getByText("뽀송 피부")).toBeVisible();
    await page.getByRole("tab", { name: "펫" }).tap();
    await expect(page.getByText("밍펫")).toBeVisible();
    await expect(page.getByText("펫 장비 테스트")).toBeVisible();
    await page.getByRole("tab", { name: "장비" }).tap();
    await page.locator('.equipment-game-slot[data-slot="android"]').tap();
    const androidTooltip = page.locator("body > .game-floating-tooltip");
    await expect(androidTooltip).toContainText("싱크로이드 9");
    await expect(androidTooltip).toContainText("레전드리");
    await expect(androidTooltip).toContainText("여성");

    await page.locator(".mgt-topbar").tap();
    await page.locator('[data-detail-tab="skills"]').tap();
    const skill = page.locator(".game-sixth-skill-tile[data-tooltip-trigger='true']");
    await expect(skill).toBeVisible();
    await skill.tap();
    await expect(page.locator("body > .game-floating-tooltip")).toContainText("스킬 설명 터치 확인");

    await page.locator(".mgt-topbar").tap();
    await page.locator('[data-detail-tab="union"]').tap();
    const championCard = page.locator(".game-union-champion-card");
    await expect(championCard).toContainText("챔피언 테스트");
    const championAvatar = championCard.locator(".game-union-champion-avatar-preview");
    const avatarBounds = await championAvatar.boundingBox();
    expect(avatarBounds.width).toBeGreaterThanOrEqual(110);
    await championAvatar.tap();
    const championTooltip = page.locator("body > .game-floating-tooltip");
    await expect(championTooltip).toContainText("직업 · 아크메이지(썬,콜)");
    await expect(championTooltip).toContainText("레벨 · Lv. 298");
    await expect(championTooltip.locator("img")).toHaveCount(0);
    await page.locator(".mgt-topbar").tap();

    const crest = championCard.locator(".game-union-champion-crest").first();
    await crest.tap();
    const crestTooltip = page.locator("body > .game-floating-tooltip");
    await expect(crestTooltip).toContainText("보스 몬스터 공격 시 데미지 +1%");
    await expect(crestTooltip.locator("img")).toHaveCount(0);

    const scrollState = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight
    }));
    expect(scrollState.scrollHeight).toBeGreaterThan(scrollState.viewportHeight);
  } finally {
    await context.close().catch(() => {});
  }
});
