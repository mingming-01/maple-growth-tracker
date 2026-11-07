const { test, expect } = require("@playwright/test");

test("React dashboard is served at root while the legacy Flask homepage remains available", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "모험가 찾기" })).toBeVisible();
  const moduleScript = await page.locator('script[type="module"]').getAttribute("src");
  expect(moduleScript).toContain("/static/react-preview/assets/");

  await page.goto("/legacy/");
  await expect(page.locator("#searchForm")).toBeVisible();

  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#growth"]')).toBeVisible();
});

test("React preview keeps the existing Flask admin route reachable", async ({ page }) => {
  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#admin"]')).toBeVisible();
  await expect(page.locator('.mgt-footer a[href="/admin/login"]')).toHaveAttribute("href", "/admin/login");
});

test("React preview loads profile data and refreshes only on explicit request", async ({ page }) => {
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "프리뷰테스트",
      ocid: "react-preview-test-ocid",
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
      rankingDataStatus: "available",
      bestCombatPower: 987654321
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ history: [], historyStatus: "complete", historyStorage: { backend: "postgres", status: "saved" } })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      section: "stats",
      status: "available",
      defaultProfile: "current",
      profileRecommendations: {
        boss: { confidence: "medium", score: 5, presetNumbers: { equipment: 1, ability: 1, hyperStat: 1, link: 1, union: 1 } },
        hunting: { confidence: "low", score: 0, presetNumbers: { equipment: 1, ability: 1, hyperStat: 1, link: 1, union: 1 } }
      },
      actualPresetNumbers: { equipment: 1, ability: 1, hyperStat: 1, link: 1, union: 1 },
      bestCombatPower: 987654321,
      sources: [
        { id: "stat", label: "주요 스탯", status: "available", combatPower: 987654321, data: { final_stat: [
          { stat_name: "전투력", stat_value: "987654321" },
          { stat_name: "STR", stat_value: "45000" },
          { stat_name: "크리티컬 데미지", stat_value: "95.00%" }
        ] } },
        { id: "ability", label: "어빌리티", status: "available", activePresetNo: 1, presets: [{ number: 1, data: { ability_grade: "레전드리", ability_info: [{ ability_grade: "레전드리", ability_value: "보스 몬스터 공격 시 데미지 20%" }] } }], data: {} },
        { id: "hyperStat", label: "하이퍼 스탯", status: "available", activePresetNo: 1, presets: [{ number: 1, data: { hyper_stat: [{ stat_type: "크리티컬 데미지", stat_level: 10, stat_increase: "10%" }] } }], data: {} },
        { id: "itemEquipment", label: "장비 프리셋", status: "available", activePresetNo: 1, presets: [{ number: 1, data: { item_equipment: [] } }], data: {} },
        { id: "linkSkill", label: "링크 스킬 프리셋", status: "available", activePresetNo: 1, presets: [{ number: 1, data: { character_link_skill: [] } }], data: {} },
        { id: "unionStateStat", label: "유니온 스탯", status: "available", activePresetNo: 1, presets: [{ number: 1, data: { union_state_stat: [] } }], data: {} }
      ]
    })
  }));

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("프리뷰테스트");
  const characterRequestPromise = page.waitForRequest(request =>
    request.url().includes("/api/character?") && request.method() === "GET"
  );
  const historyRequestPromise = page.waitForRequest(request =>
    request.url().includes("/api/history?") && request.method() === "GET"
  );
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  const characterRequest = await characterRequestPromise;
  const historyRequest = await historyRequestPromise;
  expect(new URL(characterRequest.url()).searchParams.get("refresh")).toBeNull();
  expect(new URL(historyRequest.url()).searchParams.get("refresh")).toBeNull();

  await expect(page.getByRole("heading", { name: "프리뷰테스트" })).toBeVisible();
  await expect(page.getByText("12,345위")).toBeVisible();
  await expect(page.getByText("6,789위")).toBeVisible();
  await expect(page.getByText("크로아")).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "현재 레벨 경험치 진행률" })).toHaveAttribute("aria-valuenow", "35.6");
  await expect(page.locator(".mgt-character-avatar-frame")).toBeVisible();
  const desktopAvatar = await page.locator(".mgt-character-avatar-frame").boundingBox();
  expect(desktopAvatar.width).toBeGreaterThanOrEqual(200);
  expect(desktopAvatar.height).toBeGreaterThanOrEqual(200);
  await expect(page.getByRole("heading", { name: "캐릭터 상세 정보" })).toBeVisible();
  await expect(page.locator(".game-stat-detail-grade")).toHaveText("레전드리");

  const refreshRequests = [];
  page.on("request", request => {
    if (/\/api\/(character|history)\?/.test(request.url()) &&
        new URL(request.url()).searchParams.get("refresh") === "1") {
      refreshRequests.push(request.url());
    }
  });
  await page.getByRole("button", { name: "최신 정보 다시 조회" }).click();
  await expect.poll(() => refreshRequests.length).toBe(2);
});

test("React profile keeps a readable avatar and progress bar on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "모바일테스트",
      character_image: null,
      worldName: "크로아",
      job: "아크메이지",
      guildName: null,
      level: 280,
      experience: 100000,
      experienceRate: "42.125",
      ranking: 1,
      worldRanking: 2,
      jobWorldRanking: 3,
      jobRanking: 4,
      rankingDataStatus: "available"
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({history:[],historyStatus:"complete"})
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({section:"stats",status:"available",sources:[]})
  }));
  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("모바일테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("progressbar", { name: "현재 레벨 경험치 진행률" })).toBeVisible();
  await expect(page.locator(".mgt-character-avatar-frame")).toBeVisible();
  const avatar = await page.locator(".mgt-character-avatar-frame").boundingBox();
  expect(avatar.width).toBeGreaterThanOrEqual(110);
});


test("React admin panel renders and filters session-protected operations logs", async ({ page }) => {
  const logs = [
    {
      created_at: "2026-11-06T09:00:00+00:00",
      created_at_display: "2026-11-06 (금) 18:00:00 KST",
      action: "캐릭터 조회",
      character_name: "밍득",
      world_name: "크로아",
      comparison_name: null,
      result: "성공",
      path: "/api/character",
      status_code: 200,
      duration_ms: 45,
      error_type: null
    },
    {
      created_at: "2026-11-06T08:00:00+00:00",
      created_at_display: "2026-11-06 (금) 17:00:00 KST",
      action: "성장 기록 조회",
      character_name: "테스트캐릭터",
      world_name: "루나",
      comparison_name: null,
      result: "실패",
      path: "/api/history",
      status_code: 503,
      duration_ms: 300,
      error_type: "http_5xx"
    }
  ];

  await page.route(/\/admin\/api\/logs(?:\?.*)?$/, async route => {
    const url = new URL(route.request().url());
    const q = (url.searchParams.get("q") || "").toLowerCase();
    const result = url.searchParams.get("result") || "";
    const action = url.searchParams.get("action") || "";
    const filtered = logs.filter(item => {
      const matchesQuery = !q || [item.action,item.character_name,item.world_name,item.path,item.error_type]
        .some(value => String(value || "").toLowerCase().includes(q));
      return matchesQuery && (!result || item.result === result) && (!action || item.action === action);
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        logs: filtered,
        totalCount: filtered.length,
        displayedCount: filtered.length,
        actionOptions: ["캐릭터 조회","성장 기록 조회"],
        storageBackend: "postgres",
        storageWarning: "",
        snapshotStorageBackend: "postgres",
        snapshotStorageWarning: "",
        csrfToken: "e2e-csrf-token"
      })
    });
  });

  await page.route("**/admin/logout", route => route.fulfill({
    status: 200,
    contentType: "text/plain",
    body: "logged out"
  }));

  await page.goto("/preview/");
  await page.locator('.mgt-nav a[href="#admin"]').click();
  await expect(page.getByRole("heading", { name: "관리자 로그" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "밍득" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "http_5xx" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "밍득" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "http_5xx" })).toBeVisible();

  await page.getByLabel("검색어").fill("테스트캐릭터");
  await page.getByRole("button", { name: "검색" }).click();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "테스트캐릭터" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "밍득" })).toHaveCount(0);

  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("heading", { name: "관리자 로그인" })).toBeVisible();
});


test("mobile touch opens item tooltips without clipped detail panels", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });
  const page = await context.newPage();

  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "터치테스트", ocid: "mobile-tooltip-ocid",
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
          symbol_growth_count: 100
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
    await page.getByLabel("캐릭터명").fill("터치테스트");
    await page.getByRole("button", { name: /캐릭터 조회/ }).tap();
    await expect(page.getByRole("heading", { name: "터치테스트" })).toBeVisible();

    await page.locator('[data-detail-tab="symbols"]').tap();
    const symbol = page.locator(".game-symbol-tile[data-tooltip-trigger='true']");
    await expect(symbol).toBeVisible();
    await symbol.tap();
    const tooltip = page.locator("body > .game-floating-tooltip");
    await expect(tooltip).toContainText("심볼 설명 터치 확인");
    await expect(symbol.locator(".game-symbol-growth")).toHaveText("MAX");
    await expect(page.locator(".game-symbol-tile").filter({ hasText: "그랜드 어센틱 심볼: 테스트" }))
      .toContainText("경험치 5%");
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

    const faceSlot = page.locator('.equipment-game-slot[data-slot="face"]');
    await expect(faceSlot.locator(".equipment-game-star")).toHaveCount(0);
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
    await context.close();
  }
});
