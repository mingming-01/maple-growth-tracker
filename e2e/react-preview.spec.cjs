const { test, expect } = require("@playwright/test");

test("React dashboard is served at root while the legacy Flask homepage remains available", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(0);
  const reactStylesheet = await page.locator('link[rel="stylesheet"]').evaluateAll(links =>
    links.map(link => link.href).find(href => href.includes("/static/react-preview/assets/")) || null
  );
  expect(reactStylesheet).not.toBeNull();
  const reactCssResponse = await page.request.get(reactStylesheet);
  expect(reactCssResponse.ok()).toBeTruthy();
  const reactCss = await reactCssResponse.text();
  expect(reactCss).toContain(".growth-goal-form");
  expect(reactCss).toContain(".game-equipment-board");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "캐릭터 찾기" })).toBeVisible();
  const moduleScript = await page.locator('script[type="module"]').getAttribute("src");
  expect(moduleScript).toContain("/static/react-preview/assets/");

  await page.goto("/legacy/");
  await expect(page.locator("#searchForm")).toBeVisible();
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(1);

  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#/growth"]')).toBeVisible();
});

test("React preview keeps the existing Flask admin route reachable", async ({ page }) => {
  await page.goto("/admin/login");
  await expect(page.locator('link[rel="stylesheet"][href="/static/style.css"]')).toHaveCount(1);
  await expect(page.locator("form")).toBeVisible();

  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#/admin"]')).toBeVisible();
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
        { date: "2026-11-05", level: 280, experience: 1200, experienceRate: "30.500", experienceChange: 200, experienceRateChange: 0.375, recordStatus: "available" },
        { date: "2026-11-06", level: 280, experience: 1300, experienceRate: "30.250", experienceChange: 100, recordStatus: "available" }
      ],
      historyStatus: "complete",
      metrics: {
        observedChangeDays: 2,
        recordedDays: 3,
        latestDailyGrowth: 100,
        averageDailyGrowth: 150,
        sevenDayGrowth: 300,
        rankingChange: null,
        levelProgress: { currentRate: 35.6, remainingRate: 64.4, dailyProgressRate: 0.25 },
        growthComparison: { direction: "stable", earlierAverage: null, recentAverage: null },
        levelUps: [],
        timeline: [
          { type: "latest", date: "2026-11-06", title: "최근 정상 기록", description: "Lv. 280 · 경험치 1,300", priority: 3 }
        ],
        prediction: null
      },
      periodSummary: {
        startDate: "2026-10-31",
        endDate: "2026-11-06",
        expectedSnapshots: 7,
        availableDays: 3,
        coveragePercent: 42.9,
        confirmedChangeDays: 2,
        averageGrowth: 150,
        growth: 300,
        notReadyDays: 0,
        notCollectedDays: 4,
        unavailableDays: 0,
        levelUpCount: 0,
        levelUpDates: []
      },
      historyStorage: { backend: "postgres", status: "saved" }
    })
  }));
  await page.route("**/api/ai-analysis?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      analysis: [
        "[성장 패턴] 최근 기록에서 성장 흐름을 확인했어요.",
        "[성장 변화] 이전 기록과 비슷한 흐름이에요.",
        "[레벨업 분석] 이번 기간에는 레벨 변화가 확인되지 않았어요.",
        "[성장 전망] 현재 기록을 바탕으로 전망을 살펴볼 수 있어요.",
        "[AI 코멘트] 최근 흐름을 차분히 확인해 보면 좋겠어요."
      ].join("\n"),
      aiGenerated: true,
      aiFallbackUsed: true,
      growthInsights: null,
      periodSummary: null,
      previousPeriodSummary: null
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
      bestCombatPowerObservedAt: "2026-11-08T10:00:00+09:00",
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
  await expect(page.getByTestId("growth-insight")).toBeVisible();
  await expect(page.getByRole("heading", { name: "이번 성장 기록에서 확인한 점" })).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#/analytics"]')).toBeVisible();
  await expect(page.getByText("12,345위")).toBeVisible();
  await expect(page.getByText("6,789위")).toBeVisible();
  await expect(page.getByText("크로아")).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "현재 레벨 경험치 진행률" })).toHaveAttribute("aria-valuenow", "35.6");
  await expect(page.locator(".mgt-character-avatar-frame")).toBeVisible();
  const desktopAvatar = await page.locator(".mgt-character-avatar-frame").boundingBox();
  expect(desktopAvatar.width).toBeGreaterThanOrEqual(128);
  expect(desktopAvatar.height).toBeGreaterThanOrEqual(128);
  await expect(page.getByRole("button", { name: "관심 캐릭터 등록" })).toBeVisible();

  await page.locator('.mgt-nav a[href="#/details"]').click();
  // CharacterDetails loads its data only after entering the dedicated route.
  await expect(page.locator("#details").getByRole("heading", { name: "캐릭터 상세 정보" })).toBeVisible();
  await page.getByRole("heading", { name: "캐릭터 상세 정보" }).scrollIntoViewIfNeeded();
  await expect(page.locator(".game-stat-detail-grade")).toHaveText("레전드리");
  await page.locator('.mgt-nav a[href="#/"]').click();
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("전투력");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("987,654,321");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-best-combat-power']")).toContainText("987,654,321");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-best-combat-power']")).toContainText("2026. 11. 8.");

  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await expect(page.locator("#growth").getByRole("heading", { name: "성장 요약" })).toBeVisible();

  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator(".history-table thead")).toContainText("경험치");
  await expect(page.locator(".history-table thead")).not.toContainText("경험치 증가량");
  await expect(page.locator(".history-table thead tr th")).toHaveCount(5);
  await expect(page.locator(".history-table thead")).not.toContainText("일일 변화");
  const progressRow = page.locator(".history-table tbody tr").filter({ hasText: "2026.11.05" });
  await expect(progressRow.locator(".history-level-progress-change")).toHaveText("+0.375%p");
  await expect(progressRow.locator(".history-level-progress-change")).toHaveClass(/is-positive/);
  await expect(progressRow.locator(".history-experience-value > span")).toHaveText("1,200");
  await expect(progressRow.locator(".history-experience-change")).toHaveText("+0.00조");
  await expect(progressRow.locator(".history-experience-change")).toHaveClass(/is-positive/);
  await expect(progressRow.locator(".history-experience-value")).toHaveAttribute("aria-label", /경험치 증가량/);

  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expect(page.locator("#analytics").getByRole("heading", { name: "AI 성장 리포트" })).toBeVisible();
  await expect(page.getByText("기본 AI 응답이 원활하지 않아 대체 경로로 코멘트를 생성했습니다.", { exact: true })).toBeVisible();
  await expect(page.locator('[data-testid="ai-report-provenance"]')).toHaveCount(0);
  await expect(page.locator("#analytics")).not.toContainText(/Gemini|OpenRouter|nvidia\/|라우팅 제공자|요청 모델/);
  await page.locator('.mgt-nav a[href="#/comparison"]').click();
  await expect(page.locator("#comparison").getByRole("heading", { name: "성장 캐릭터 비교" })).toBeVisible();

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
  expect(avatar.width).toBeGreaterThanOrEqual(88);
});


test("React hash routes support direct entry, reload, and browser back/forward navigation", async ({ page }) => {
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({
      characterName: "라우트테스트", ocid: "route-test-ocid", character_image: null,
      worldName: "크로아", job: "아크메이지", guildName: null, level: 280,
      experience: 123456, experienceRate: "35.600", ranking: 10,
      worldRanking: 5, jobWorldRanking: 2, jobRanking: 1, rankingDataStatus: "available"
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ history: [], historyStatus: "complete" })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("라우트테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "라우트테스트" })).toBeVisible();

  const detailsMenu = page.locator('.mgt-nav-dropdown').nth(1);
  await detailsMenu.hover();
  await expect(detailsMenu.locator(".mgt-nav-submenu")).toBeVisible();
  await detailsMenu.getByRole("link", { name: "장비", exact: true }).click();
  await expect(page).toHaveURL(/#\/details\?tab=equipment$/);
  await expect(page.locator('[data-detail-tab="equipment"]')).toHaveAttribute("aria-selected", "true");
  const growthMenu = page.locator('.mgt-nav-dropdown').nth(0);
  await growthMenu.hover();
  await expect(detailsMenu.locator(".mgt-nav-submenu")).toBeHidden();
  await expect(growthMenu.locator(".mgt-nav-submenu")).toBeVisible();
  await growthMenu.getByRole("link", { name: "성장 추이", exact: true }).click();
  await expect(page).toHaveURL(/#\/growth\?section=trend$/);
  await expect(page.locator("#growth-trend")).toBeInViewport();

  // The reverse transition must also keep the details submenu from covering growth.
  await detailsMenu.hover();
  await expect(growthMenu.locator(".mgt-nav-submenu")).toBeHidden();
  await expect(detailsMenu.locator(".mgt-nav-submenu")).toBeVisible();
  await detailsMenu.getByRole("link", { name: "스탯", exact: true }).click();
  await expect(page).toHaveURL(/#\/details\?tab=stats$/);
  await expect(page.locator('[data-detail-tab="stats"]')).toHaveAttribute("aria-selected", "true");

  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await expect(page).toHaveURL(/#\/growth$/);
  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page).toHaveURL(/#\/history$/);
  await page.goBack();
  await expect(page).toHaveURL(/#\/growth$/);
  await expect(page.getByTestId("growth-page")).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(/#\/history$/);
  await expect(page.getByTestId("history-page")).toBeVisible();

  await page.goto("/preview/#/details");
  await expect(page.getByTestId("details-page")).toBeVisible();
  await expect(page.locator("#details").getByRole("heading", { name: "캐릭터 상세 정보" })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/#\/details$/);
  await expect(page.getByTestId("details-page")).toBeVisible();
  await expect(page.getByTestId("react-character-search")).toBeVisible();
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
  await page.locator('.mgt-nav a[href="#/admin"]').click();
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


test("AI report loads the server cache on entry and regenerates only on explicit refresh", async ({ page }) => {
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
    { date: "2026-11-04", level: 280, experience: 1000, experienceChange: null, recordStatus: "available" },
    { date: "2026-11-05", level: 280, experience: 1200, experienceChange: 200, recordStatus: "available" },
    { date: "2026-11-06", level: 280, experience: 1300, experienceChange: 100, recordStatus: "available" }
  ];
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(character)
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ history, historyStatus: "complete", historyStorage: { backend: "postgres", status: "saved" } })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));
  await page.route(/\/api\/history\/archive\?/, async route => {
    const url = new URL(route.request().url());
    const days = Number(url.searchParams.get("days"));
    const endDate = url.searchParams.get("end") || "2026-11-06";
    const collecting = url.searchParams.get("collect") === "1";
    const offset = Number(url.searchParams.get("offset") || 0);
    const limit = Number(url.searchParams.get("limit") || 10);
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
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        ocid: character.ocid, days, startDate: records[0].date, endDate: records[records.length - 1].date,
        history: records, availableDays: days, notReadyDays: 0, notCollectedDays: 0,
        collection: collecting ? {
          offset, limit, checkedDays: limit, savedRecords: limit,
          availableRecords: limit, noDataRecords: 0,
          remainingDays: Math.max(0, days - offset - limit)
        } : null,
        storageBackend: "postgres", persistentStorage: true
      })
    });
  });

  let aiCalls = 0;
  let submittedPayload = null;
  await page.route("**/api/ai-analysis?*", async route => {
    aiCalls += 1;
    submittedPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        analysis: "[성장 패턴] 기간 분석 테스트 결과입니다.\\n[성장 변화] 선택 기간 기록을 확인했습니다.\\n[레벨업 분석] 확인할 기록이 부족합니다.\\n[성장 전망] 자료가 부족합니다.\\n[AI 코멘트] 테스트 리포트입니다.",
        cacheHit: false,
        aiGenerated: true,
        growthInsights: {},
        aiFallbackUsed: true
      })
    });
  });

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("기간캐시테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "기간캐시테스트" })).toBeVisible();
  // Opening the AI report checks browser cache, then the server cache; a miss starts generation.
  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  const fallbackNotice = page.getByText(
    "기본 AI 응답이 원활하지 않아 대체 경로로 코멘트를 생성했습니다.",
    { exact: true }
  );
  await expect(fallbackNotice).toBeVisible();
  await expect(page.locator('[data-testid="ai-report-provenance"]')).toHaveCount(0);
  await expect(page.locator("#analytics")).not.toContainText(/Gemini|OpenRouter|sample\\/free-route-model|라우팅 제공자|요청 모델/);
  expect(aiCalls).toBe(1);
  expect(submittedPayload.analysisContext.periodDays).toBe(7);
  expect(submittedPayload.forceRefresh).toBe(false);

  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await page.locator(".history-range-control select").selectOption("30");
  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  const aiReportSection = page.locator(".section").filter({ has: page.getByRole("heading", { name: "AI 성장 리포트" }) });
  await expect(aiReportSection.locator(".section-description")).toContainText("최근 30일");
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(2);
  expect(submittedPayload.analysisContext.periodDays).toBe(30);
  expect(submittedPayload.forceRefresh).toBe(false);
  expect(submittedPayload.history).toHaveLength(30);

  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(30);
  await expect(page.locator("#history .history-table tbody tr").first()).toContainText("2026.11.06");

  // Re-entering the same report reuses the browser cache.
  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  await expect(fallbackNotice).toBeVisible();
  await expect(page.locator("#analytics")).not.toContainText(/Gemini|OpenRouter|sample\\/free-route-model|라우팅 제공자|요청 모델/);
  expect(aiCalls).toBe(2);

  await page.getByRole("button", { name: "다시 분석" }).click();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(3);
  expect(submittedPayload.forceRefresh).toBe(true);

  await page.reload();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(3);

  // Changing the period on the AI page updates the shared period and creates only the missing report.
  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await page.getByLabel("AI 분석 기간").selectOption("90");
  await expect(aiReportSection.locator(".section-description")).toContainText("최근 90일");
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(4);
  expect(submittedPayload.analysisContext.periodDays).toBe(90);
  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(90);
  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await expect(page.locator(".history-range-control select")).toHaveValue("90");

  await page.locator(".history-range-control select").selectOption("7");
  await page.locator('.mgt-nav a[href="#/history"]').click();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(3);
  await expect(page.locator("#history .history-table tbody tr").first()).toContainText("2026.11.06");
});


test("mobile route pages stay within the viewport at common device widths", async ({ page }) => {
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "모바일진단",
      ocid: "mobile-layout-diagnostic",
      character_image: null,
      worldName: "크로아",
      job: "아크메이지(불,독)",
      guildName: "테스트길드",
      level: 280,
      experience: 123456789012345,
      experienceRate: "42.125",
      ranking: 12345,
      worldRanking: 6789,
      jobWorldRanking: 123,
      jobRanking: 456,
      rankingDataStatus: "available"
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      history: [
        { date: "2026-11-02", level: 280, experience: 1000, experienceRate: "39.000", experienceChange: null, recordStatus: "available" },
        { date: "2026-11-03", level: 280, experience: 1200, experienceRate: "39.500", experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-04", level: 280, experience: 1300, experienceRate: "40.000", experienceChange: 100, recordStatus: "available" },
        { date: "2026-11-05", level: 280, experience: 1500, experienceRate: "40.750", experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-06", level: 280, experience: 1700, experienceRate: "41.250", experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-07", level: 280, experience: 1900, experienceRate: "41.750", experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-08", level: 280, experience: 2100, experienceRate: "42.125", experienceChange: 200, recordStatus: "available" }
      ],
      historyStatus: "complete",
      historyStorage: { backend: "postgres", status: "saved" }
    })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));
  await page.route("**/api/ai-analysis?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      analysis: "[성장 패턴] 모바일 레이아웃 진단",
      cacheHit: true,
      growthInsights: {}
    })
  }));

  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("모바일진단");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "모바일진단" })).toBeVisible();
  await expect(page.getByTestId("growth-insight")).toBeVisible();

  const measurements = [];
  for (const route of ["overview", "growth", "details", "analytics", "history", "comparison"]) {
    const href = route === "overview" ? "#/" : `#/${route}`;
    await page.locator(`.mgt-nav a[href="${href}"]`).click();
    for (const width of [360, 390, 412]) {
      await page.setViewportSize({ width, height: 844 });
      await page.waitForTimeout(80);
      const measurement = await page.evaluate(() => {
        const viewport = document.documentElement.clientWidth;
        const content = document.querySelector(".mgt-result-content");
        const pageContent = document.querySelector(".mgt-growth-page-content") ||
          document.querySelector(".mgt-growth-home-top") ||
          document.querySelector(".mgt-growth-page-index");
        const historyTable = document.querySelector(".history-table-wrapper");
        return {
          viewport,
          documentScrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth,
          contentRight: content?.getBoundingClientRect().right ?? null,
          pageRight: pageContent?.getBoundingClientRect().right ?? null,
          historyScrollWidth: historyTable?.scrollWidth ?? null,
          historyClientWidth: historyTable?.clientWidth ?? null
        };
      });
      measurements.push({ route, width, ...measurement });
    }
  }
  for (const measurement of measurements) {
    expect(
      measurement.documentScrollWidth,
      `document overflow on ${measurement.route} at ${measurement.width}px`
    ).toBe(measurement.viewport);
    expect(measurement.bodyScrollWidth).toBe(measurement.viewport);
    expect(measurement.contentRight).toBeLessThanOrEqual(measurement.viewport + 1);
    if (measurement.pageRight !== null) {
      expect(measurement.pageRight).toBeLessThanOrEqual(measurement.viewport + 1);
    }
    if (measurement.historyScrollWidth !== null) {
      expect(measurement.historyScrollWidth).toBeLessThanOrEqual(measurement.historyClientWidth + 1);
    }
  }
});

test("React AI report restores evidence details from cache", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "근거테스트",
      ocid: "evidence-test-ocid",
      worldName: "크로아",
      job: "전사",
      guildName: "테스트",
      level: 280,
      experience: 1300,
      experienceRate: "30.000",
      ranking: 1,
      worldRanking: 1,
      jobWorldRanking: 1,
      jobRanking: 1,
      rankingDataStatus: "available"
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      history: [
        { date: "2026-11-04", level: 280, experience: 700, experienceRate: "29.500", experienceChange: null, recordStatus: "available" },
        { date: "2026-11-05", level: 280, experience: 1000, experienceRate: "29.750", experienceChange: 300, recordStatus: "available" },
        { date: "2026-11-06", level: 280, experience: 1300, experienceRate: "30.000", experienceChange: 300, recordStatus: "available" }
      ],
      historyStatus: "complete",
      historyStorage: { backend: "postgres", status: "saved" }
    })
  }));
  await page.route("**/api/ai-analysis?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      analysis: "[성장 패턴] 최근 성장 흐름이 개선됐습니다.\\n[AI 코멘트] 기록을 이어가세요.",
      cacheHit: false,
      growthInsights: {
        basis: {
          referenceDate: "2026-11-06",
          expectedSnapshots: 15,
          availableSnapshots: 10,
          coveragePercent: 66.7,
          dataQualityLabel: "보통"
        },
        weekOverWeek: { status: "available", averageDailyGrowthChangePercent: 12.5 },
        weekdayWeekend: { status: "available", weekendSharePercent: 44.2 }
      }
    })
  }));

  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("근거테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await page.locator('.mgt-nav a[href="#/analytics"]').click();

  const evidence = page.getByTestId("ai-analysis-evidence");
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText("AI 분석 기준 및 데이터 충실도");
  await expect(evidence).toContainText("2026.11.06");
  await expect(evidence).toContainText("10 / 15일");
  await expect(evidence).toContainText("보통 · 66.7%");
  await expect(evidence).toContainText("12.5%");
  await expect(evidence).toContainText("44.2%");
  const bounds = await evidence.evaluate(element => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, viewportWidth: window.innerWidth };
  });
  expect(bounds.left).toBeGreaterThanOrEqual(0);
  expect(bounds.right).toBeLessThanOrEqual(bounds.viewportWidth);

  await page.reload();
  const cachedEvidence = page.getByTestId("ai-analysis-evidence");
  await expect(cachedEvidence).toBeVisible();
  await expect(cachedEvidence).toContainText("10 / 15일");
});

test("React growth chart configures level-up EXP markers and timeline", async ({ page }) => {
  const timestamp = "2026-11-20T08:45:00+09:00";
  const character = {
    characterName: "레벨업검증", ocid: "level-up-chart-ai-e2e",
    character_image: null, worldName: "크로아", job: "아델", guildName: null,
    level: 299, experience: 50805631039495, experienceRate: "2.924",
    ranking: 12345, rankingDataStatus: "available", dataStatus: "current", dataAsOf: timestamp
  };
  const history = [
    { date: "2026-11-14", level: 298, experience: 1094349410488372, experienceRate: 94.825, experienceChange: null, levelUp: false, recordStatus: "available" },
    { date: "2026-11-15", level: 298, experience: 1103053861914765, experienceRate: 96.177, experienceChange: 8704451426393, levelUp: false, recordStatus: "available" },
    { date: "2026-11-16", level: 298, experience: 1118748264632899, experienceRate: 97.143, experienceChange: 15694402718134, levelUp: false, recordStatus: "available" },
    { date: "2026-11-17", level: 298, experience: 1129263590513928, experienceRate: 99.226, experienceChange: 10515325881029, levelUp: false, recordStatus: "available" },
    { date: "2026-11-18", level: 298, experience: 6175579914147, experienceRate: 0.355, experienceChange: null, levelUp: true, levelUpPreviousLevel: 298, levelUpCurrentLevel: 299, recordStatus: "available" },
    { date: "2026-11-19", level: 299, experience: 34219899249572, experienceRate: 1.969, experienceChange: 28044319335425, levelUp: false, levelUpCatchUp: true, recordStatus: "available" },
    { date: "2026-11-20", level: 299, experience: 50805631039495, experienceRate: 2.924, experienceChange: 16585731789923, levelUp: false, recordStatus: "available" }
  ];

  await page.route("**/api/character?*", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(character)
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({
      characterName: character.characterName, worldName: character.worldName,
      history, historyStatus: "complete",
      metrics: {
        observedChangeDays: 5, recordedDays: 7,
        latestDailyGrowth: 16585731789923,
        averageDailyGrowth: 15908846230180.8,
        sevenDayGrowth: 79544231150904, rankingChange: null,
        levelProgress: { currentRate: 2.924, remainingRate: 97.076, dailyProgressRate: 1.2845 },
        growthComparison: { direction: "increased", earlierAverage: 1000, recentAverage: 2000 },
        levelUps: [{ date: "2026-11-18", previousLevel: 298, currentLevel: 299 }],
        timeline: [
          { type: "level-up", date: "2026-11-18", title: "Lv. 299 달성", description: "Lv. 298에서 레벨업 · 당일 경험치 증가량 미확인", priority: 0 },
          { type: "latest", date: "2026-11-20", title: "최근 정상 기록", description: "Lv. 299 · 경험치 50,805,631,039,495", priority: 3 }
        ],
        prediction: {
          currentLevel: 299, nextLevel: 300, currentExperience: 50805631039495,
          currentRate: 2.924, remainingRate: 97.076,
          estimatedTotalExp: 1737538681241279, requiredExp: 1686733050201784,
          requiredExpEstimated: true, requiredExpMethod: "experience_rate_reverse_estimate",
          averageGrowth: 22315025562674, experienceSamples: 2,
          averageDailyProgressRate: 1.2845, progressSamples: 2,
          confidence: "initial", days: 75.5873232349398, date: "2027-02-04",
          estimatedDays: 75.5873232349398, estimatedDate: "2027-02-04",
          observationDate: "2026-11-20", method: "experience_rate_reverse_estimate"
        }
      },
      periodSummary: {
        startDate: "2026-11-14", endDate: "2026-11-20", expectedSnapshots: 7,
        availableDays: 7, coveragePercent: 100, confirmedChangeDays: 5,
        averageGrowth: 15908846230180.8, growth: 79544231150904,
        notReadyDays: 0, notCollectedDays: 0, unavailableDays: 0,
        levelUpCount: 1, levelUpDates: ["2026-11-18"]
      }
    })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));

  let submittedPayload = null;
  await page.route("**/api/ai-analysis?*", async route => {
    submittedPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        analysis: "[성장 패턴] 확인된 다섯 구간의 일일 변화가 있습니다.\\n[성장 변화] 레벨업 경계는 제외하고 새 레벨 내부의 관측 증가량을 반영했습니다.\\n[레벨업 분석] 11월 18일에 298레벨에서 299레벨로 올라갔어요.\\n[성장 전망] 관측된 진행률을 기준으로 초기 전망을 계산했습니다.\\n[AI 코멘트] 다음 기록에서도 같은 레벨의 변화를 이어서 비교해 보세요.",
        cacheHit: false, growthInsights: {}
      })
    });
  });

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill(character.characterName);
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: character.characterName })).toBeVisible();
  await page.locator('.mgt-nav a[href="#/growth"]').click();
  await expect(page.locator("#growth-trend canvas[aria-label='기간별 성장 추이 그래프']")).toBeVisible();

  const canvas = page.locator("#growth-trend canvas[aria-label='기간별 성장 추이 그래프']");
  const pinkPixelCount = () => canvas.evaluate(element => {
    const ctx = element.getContext("2d");
    const { data } = ctx.getImageData(0, 0, element.width, element.height);
    let pink = 0;
    for (let offset = 0; offset < data.length; offset += 4) {
      const red = data[offset], green = data[offset + 1], blue = data[offset + 2], alpha = data[offset + 3];
      if (alpha > 160 && red > 210 && green < 150 && blue > 90 && blue < 190) pink += 1;
    }
    return pink;
  });
  await expect.poll(pinkPixelCount).toBeGreaterThan(30);
  const markerState = await canvas.evaluate(async element => {
    const chartModuleUrl = performance.getEntriesByType("resource")
      .map(entry => entry.name)
      .find(url => /\/static\/react-preview\/assets\/auto-[^/]+\.js(?:\?.*)?$/.test(url));
    if (!chartModuleUrl) return { error: "chart_module_not_loaded" };

    const { default: Chart } = await import(chartModuleUrl);
    const chart = Chart.getChart(element);
    if (!chart) return { error: "chart_instance_not_found" };

    const markerIndex = chart.data.labels.findIndex(label => String(label) === "11-18");
    const point = markerIndex >= 0 ? chart.getDatasetMeta(0).data[markerIndex] : null;
    const position = point?.getProps?.(["x", "y"], true) || null;
    const area = chart.chartArea;
    return {
      markerIndex,
      color: point?.options?.backgroundColor ?? null,
      style: point?.options?.pointStyle ?? null,
      radius: point?.options?.radius ?? null,
      skipped: point?.skip ?? null,
      x: position?.x ?? null,
      y: position?.y ?? null,
      chartArea: area ? { left: area.left, right: area.right, top: area.top, bottom: area.bottom } : null
    };
  });
  expect(markerState.error).toBeUndefined();
  expect(markerState.markerIndex).toBe(4);
  expect(markerState.color).toBe("#f5c542");
  expect(markerState.style).toBe("star");
  expect(markerState.radius).toBe(7);
  expect(markerState.skipped).toBe(false);
  expect(markerState.x).toBeGreaterThan(markerState.chartArea.left);
  expect(markerState.x).toBeLessThan(markerState.chartArea.right);
  expect(markerState.y).toBeGreaterThanOrEqual(markerState.chartArea.top);
  expect(markerState.y).toBeLessThanOrEqual(markerState.chartArea.bottom);

  await expect(page.locator("#growth-timeline .growth-timeline-item.is-level-up")).toHaveCount(1);
  await expect(page.locator("#growth-timeline")).toContainText("2026.11.18");
  await expect(page.locator("#growth-timeline")).toContainText("당일 경험치 증가량 미확인");
  await expect(page.locator("#growth-trend .history-range-notice")).toContainText("레벨업 1일 · 당일 일일 EXP 증가량 미확인");
  await expect(page.locator("#growth-prediction .prediction-item").nth(0).locator(".prediction-value")).toHaveText("1687조");
  await expect(page.locator("#growth-prediction .prediction-item").nth(1).locator(".prediction-value")).toHaveText("약 75.6일");
  await expect(page.locator("#growth-prediction .prediction-item").nth(2).locator(".prediction-value")).toHaveText("2027.02.04");
  await expect(page.locator("#growth-prediction .prediction-item").nth(3).locator(".prediction-value")).toHaveText("22.3조");
  await expect(page.locator("#growth-prediction .prediction-note")).toContainText("2개 일일 EXP 변화량 평균");
  await expect(page.locator("#growth-prediction .prediction-note")).not.toContainText("추정");
  await expect(page.locator("#growth-prediction .prediction-note")).not.toContainText("역산");

  await page.locator('.mgt-nav a[href="#/analytics"]').click();
  await expect(page.getByText("11월 18일에 298레벨에서 299레벨로 올라갔어요.")).toBeVisible();
  expect(submittedPayload).not.toBeNull();
  const resetDay = submittedPayload.history.find(item => item.date === "2026-11-18");
  const catchUpDay = submittedPayload.history.find(item => item.date === "2026-11-19");
  const latestDay = submittedPayload.history.find(item => item.date === "2026-11-20");
  expect(resetDay.experienceChange).toBeNull();
  expect(resetDay.levelUp).toBe(true);
  expect(catchUpDay.experienceChange).toBe(28044319335425);
  expect(catchUpDay.levelUpCatchUp).toBe(true);
  expect(latestDay.experienceChange).toBe(16585731789923);
});
