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
    body: JSON.stringify({
      history: [
        { date: "2026-11-04", level: 280, experience: 1000, experienceRate: "30.125", experienceChange: null, recordStatus: "available" },
        { date: "2026-11-05", level: 280, experience: 1200, experienceRate: "30.500", experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-06", level: 280, experience: 1300, experienceRate: "30.250", experienceChange: 100, recordStatus: "available" }
      ],
      historyStatus: "complete",
      historyStorage: { backend: "postgres", status: "saved" }
    })
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
  expect(desktopAvatar.width).toBeGreaterThanOrEqual(240);
  expect(desktopAvatar.height).toBeGreaterThanOrEqual(240);
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("전투력");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("987,654,321");
  await expect(page.getByRole("button", { name: "관심 캐릭터 등록" })).toBeVisible();
  await expect(page.getByText("주간 일일 평균 경험치")).toBeVisible();
  await expect(page.locator(".history-table thead")).toContainText("경험치 증가량");
  await expect(page.locator(".history-table thead")).not.toContainText("일일 변화");
  const progressRow = page.locator(".history-table tbody tr").filter({ hasText: "2026.11.05" });
  await expect(progressRow.locator(".history-level-progress-change")).toHaveText("+0.375%p");
  await expect(progressRow.locator(".history-level-progress-change")).toHaveClass(/is-positive/);
  await expect(page.getByRole("heading", { name: "캐릭터 상세 정보" })).toBeVisible();
  await expect(page.locator(".game-stat-detail-grade")).toHaveText("레전드리");

  const refreshRequests = [];
  page.on("request", request => {
    if (/\/api\/(character|history)\?/.test(request.url()) &&
        new URL(request.url()).searchParams.get("refresh") === "1") {
      refreshRequests.push(request.url());
    }
  });
  await page.getByRole("button", { name: "공유" }).click();
  await expect(page.getByRole("menu", { name: "공유 및 저장" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "이미지 저장" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "PDF 저장" })).toBeVisible();
  await page.keyboard.press("Escape");
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
  expect(avatar.width).toBeGreaterThanOrEqual(128);
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


test("30-day AI report reuses cache without automatic LLM calls and only regenerates on demand", async ({ page }) => {
  const character = {
    characterName: "기간캐시테스트",
    ocid: "period-cache-test-ocid",
    character_image: null,
    worldName: "크로아",
    job: "아크메이지",
    guildName: null,
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
    { date: "2026-10-20", level: 280, experience: 1000, experienceChange: null, ranking: 12350, recordStatus: "available" },
    { date: "2026-10-21", level: 280, experience: 1200, experienceChange: 200, ranking: 12345, recordStatus: "available" }
  ];
  await page.addInitScript(({ character, history }) => {
    sessionStorage.setItem("mapleGrowthTrackerState", JSON.stringify({
      character,
      history,
      historyRange: 30,
      displayHistory: history,
      periodSummary: {
        days: 30, coveragePercent: 80, confirmedChangeDays: 12,
        averageGrowth: 2000000000000, previousSummary: null
      }
    }));
    if (!sessionStorage.getItem("periodCacheE2eInitialized")) {
      localStorage.removeItem("mapleGrowthTrackerAIResponsesV1");
      sessionStorage.setItem("periodCacheE2eInitialized", "1");
    }
  }, { character, history });

  let aiCalls = 0;
  let submittedPayload = null;
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));
  await page.route("**/api/ai-analysis?*", async route => {
    aiCalls += 1;
    submittedPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        analysis: "[성장 패턴] 기간 분석 테스트 결과입니다.\\n[성장 변화] 선택 기간 기록을 확인했습니다.\\n[레벨업 분석] 확인할 기록이 부족합니다.\\n[성장 전망] 자료가 부족합니다.\\n[AI 코멘트] 테스트 리포트입니다.",
        cacheHit: false,
        growthInsights: {}
      })
    });
  });

  await page.goto("/preview/");
  await expect(page.getByRole("heading", { name: "기간캐시테스트" })).toBeVisible();
  await expect(page.getByText(/최근 30일 분석의 저장 결과가 없습니다/)).toBeVisible();
  await expect.poll(() => aiCalls).toBe(0);

  await page.getByRole("button", { name: "AI 다시 분석" }).click();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(1);
  expect(submittedPayload.analysisContext.periodDays).toBe(30);
  expect(submittedPayload.forceRefresh).toBe(true);
  expect(submittedPayload.history).toHaveLength(2);

  await page.reload();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(1);
});
