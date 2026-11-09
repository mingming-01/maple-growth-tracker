const { test, expect } = require("@playwright/test");

test("React dashboard is the only public application entry point", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "모험가 찾기" })).toBeVisible();
  const moduleScript = await page.locator('script[type="module"]').getAttribute("src");
  expect(moduleScript).toContain("/static/react-preview/assets/");
  const reactStylesheets = await page.locator('link[rel="stylesheet"]').evaluateAll(links => links.map(link => new URL(link.href).pathname));
  expect(reactStylesheets).not.toContain("/static/style.css");
  const migratedStyleDisplay = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.className = "game-stat-grid";
    document.body.appendChild(probe);
    const display = getComputedStyle(probe).display;
    probe.remove();
    return display;
  });
  expect(migratedStyleDisplay).toBe("grid");

  for (const retiredPath of ["/legacy", "/legacy/", "/preview", "/preview/"]) {
    const response = await page.request.get(retiredPath);
    expect(response.status(), retiredPath).toBe(404);
  }
});

test("React dashboard keeps the existing Flask admin route reachable", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#admin"]')).toBeVisible();
  await expect(page.locator('.mgt-footer a[href="/admin/login"]')).toHaveAttribute("href", "/admin/login");
});

test("React dashboard loads profile data and refreshes only on explicit request", async ({ page }) => {
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
      bestCombatPower: 987654321,
      bestCombatPowerObservedAt: "2026-11-08T10:00:00+09:00"
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
        { id: "stat", label: "주요 스탯", status: "available", combatPower: 876543210, data: { final_stat: [
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

  await page.goto("/");
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
  // CharacterDetails intentionally lazy-loads stats when its section approaches the viewport.
  // Scroll it into view to exercise the same interaction as a real visitor.
  await page.getByRole("heading", { name: "캐릭터 상세 정보" }).scrollIntoViewIfNeeded();
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("전투력");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-combat-power']")).toContainText("876,543,210");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-best-combat-power']")).toContainText("987,654,321");
  await expect(page.locator(".mgt-snapshot-stat[data-testid='profile-best-combat-power']")).toContainText("2026. 11. 8.");
  await expect(page.getByRole("button", { name: "관심 캐릭터 등록" })).toBeVisible();
  await expect(page.getByText("주간 일일 평균 경험치")).toBeVisible();
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
  const aiHeading = page.getByRole("heading", { name: "AI 성장 리포트" });
  const historyHeading = page.getByRole("heading", { name: "날짜별 성장 기록" });
  const aiBeforeHistory = await page.evaluate(() => {
    const ai = [...document.querySelectorAll("h2")].find(node => node.textContent.trim() === "AI 성장 리포트");
    const table = document.querySelector("#history");
    return Boolean(ai && table && (ai.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING));
  });
  expect(aiBeforeHistory).toBe(true);
  await expect(aiHeading).toBeVisible();
  await expect(historyHeading).toBeVisible();
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

  await page.getByRole("button", { name: "관심 캐릭터 등록" }).click();
  await expect(page.locator(".mgt-favorite-card")).toContainText("프리뷰테스트");
  const savedFavorites = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("mapleGrowthTrackerFavorites") || "[]")
  );
  expect(savedFavorites).toHaveLength(1);
  expect(savedFavorites[0].ocid).toBe("react-preview-test-ocid");

  await page.reload();
  await expect(page.locator(".mgt-favorite-card")).toContainText("프리뷰테스트");
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
  await page.goto("/");
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

  await page.goto("/");
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
        cacheHit: false, growthInsights: {}
      })
    });
  });

  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("기간캐시테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "기간캐시테스트" })).toBeVisible();
  await expect.poll(() => aiCalls).toBe(1);
  aiCalls = 0;

  await page.locator(".history-range-control select").selectOption("30");
  const aiReportSection = page.locator(".section").filter({ has: page.getByRole("heading", { name: "AI 성장 리포트" }) });
  await expect(aiReportSection.locator(".section-description")).toContainText("선택한 30일");
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(30);
  await expect(page.locator("#history .history-table tbody tr").first()).toContainText("2026.11.06");
  expect(aiCalls).toBe(0);

  await page.getByRole("button", { name: "AI 다시 분석" }).click();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  expect(aiCalls).toBe(1);
  expect(submittedPayload.analysisContext.periodDays).toBe(30);
  expect(submittedPayload.forceRefresh).toBe(true);
  expect(submittedPayload.history).toHaveLength(30);

  await page.reload();
  await expect(page.getByText("기간 분석 테스트 결과입니다.")).toBeVisible();
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(30);
  expect(aiCalls).toBe(1);

  await page.locator(".history-range-control select").selectOption("7");
  await expect(page.locator("#history .history-table tbody tr")).toHaveCount(3);
  await expect(page.locator("#history .history-table tbody tr").first()).toContainText("2026.11.06");
});


test("mobile dashboard stays within the viewport and keeps the report before history", async ({ page }) => {
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
  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("모바일진단");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "모바일진단" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "날짜별 성장 기록" })).toBeVisible();

  const measurements = [];
  for (const width of [360, 390, 412]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForTimeout(100);
    const measurement = await page.evaluate(() => {
      const viewport = document.documentElement.clientWidth;
      const root = {
        innerWidth: window.innerWidth,
        clientWidth: viewport,
        documentScrollWidth: document.documentElement.scrollWidth,
        bodyScrollWidth: document.body.scrollWidth
      };
      const majorSelectors = [
        ".mgt-app-shell", ".mgt-page-content", ".mgt-result-content",
        "#character", "#details", "#growth", "#analytics",
        ".mgt-profile-shell", ".character-details-section",
        ".react-equipment-board", ".growth-dashboard",
        ".history-card", ".history-table-wrapper", ".history-table"
      ];
      const major = Object.fromEntries(majorSelectors.map(selector => {
        const element = document.querySelector(selector);
        if (!element) return [selector, null];
        const rect = element.getBoundingClientRect();
        return [selector, {
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth
        }];
      }));
      const offenders = [...document.querySelectorAll("body *")].map(element => {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) return null;
        let clipped = false;
        for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
          const overflowX = getComputedStyle(parent).overflowX;
          if (["auto", "scroll", "hidden", "clip"].includes(overflowX)) {
            clipped = true;
            break;
          }
        }
        return {
          tag: element.tagName.toLowerCase(),
          id: element.id || "",
          className: typeof element.className === "string" ? element.className : "",
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          clippedByAncestor: clipped
        };
      }).filter(item => item && !item.clippedByAncestor &&
        (item.left < -1 || item.right > viewport + 1))
        .sort((a, b) => Math.max(b.right - viewport, -b.left) - Math.max(a.right - viewport, -a.left))
        .slice(0, 12);
      return { ...root, major, offenders };
    });
    measurements.push({ viewport: width, ...measurement });
  }
  for (const measurement of measurements) {
    expect(
      measurement.documentScrollWidth,
      `document overflow at ${measurement.viewport}px: ${JSON.stringify(measurement.offenders)}`
    ).toBe(measurement.clientWidth);
    expect(measurement.bodyScrollWidth).toBe(measurement.clientWidth);
    expect(measurement.major["#character"].right).toBeLessThanOrEqual(measurement.viewport + 1);
    expect(measurement.major["#details"].right).toBeLessThanOrEqual(measurement.viewport + 1);
    expect(measurement.major["#growth"].right).toBeLessThanOrEqual(measurement.viewport + 1);
    expect(measurement.major["#analytics"].right).toBeLessThanOrEqual(measurement.viewport + 1);
    expect(measurement.major[".history-table-wrapper"].scrollWidth)
      .toBeLessThanOrEqual(measurement.major[".history-table-wrapper"].clientWidth + 1);
  }
});

test("React character details exposes all migrated tabs and loads each section on demand", async ({ page }) => {
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "상세탭검증",
      ocid: "react-detail-tabs-ocid",
      character_image: null,
      worldName: "크로아",
      job: "아크메이지",
      level: 280,
      experience: 123456,
      experienceRate: "35.600",
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
    body: JSON.stringify({ history: [], historyStatus: "complete" })
  }));
  await page.route("**/api/character-details?*", route => {
    const url = new URL(route.request().url());
    const section = url.searchParams.get("section") || "stats";
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ section, status: "available", sources: [] })
    });
  });

  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("상세탭검증");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  const heading = page.getByRole("heading", { name: "캐릭터 상세 정보" });
  await expect(heading).toBeVisible();
  const initialStatsResponse = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.pathname === "/api/character-details" &&
      url.searchParams.get("section") === "stats";
  });
  await heading.scrollIntoViewIfNeeded();
  await initialStatsResponse;
  const detailTabs = page.getByLabel("캐릭터 상세 정보 구분");
  await expect(detailTabs.getByRole("tab", { name: "스탯" })).toHaveAttribute("aria-selected", "true");

  const tabs = [
    ["장비", "equipment"],
    ["심볼", "symbols"],
    ["6차 / HEXA", "skills"],
    ["링크 스킬", "link"],
    ["유니온", "union"]
  ];

  for (const [label, section] of tabs) {
    const tab = detailTabs.getByRole("tab", { name: label });
    const response = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === "/api/character-details" &&
        url.searchParams.get("section") === section;
    });
    await tab.click();
    await response;
    await expect(tab).toHaveAttribute("aria-selected", "true");
  }
});


test("React AI report preserves its data-evidence explanation across reloads", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const timestamp = "2026-11-06T04:00:00+09:00";
  await page.route("**/api/character?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "근거테스트", worldName: "크로아", job: "전사", guildName: "테스트",
      level: 280, experience: 1300, experienceRate: "30.000",
      ranking: 1, worldRanking: 1, jobWorldRanking: 1, jobRanking: 1,
      ocid: "evidence-test-ocid", rankingDataStatus: "available",
      dataStatus: "current", dataAsOf: timestamp
    })
  }));
  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      characterName: "근거테스트", worldName: "크로아", level: 280,
      history: [
        { date: "2026-10-31", ranking: 7, level: 280, experience: 100, experienceChange: null, recordStatus: "available" },
        { date: "2026-11-01", ranking: 6, level: 280, experience: 300, experienceChange: 200, recordStatus: "available" },
        { date: "2026-11-02", ranking: null, level: null, experience: null, experienceChange: null, recordStatus: "not_ready" },
        { date: "2026-11-03", ranking: 5, level: 280, experience: 700, experienceChange: 400, recordStatus: "available" },
        { date: "2026-11-04", ranking: null, level: null, experience: null, experienceChange: null, recordStatus: "not_collected" },
        { date: "2026-11-05", ranking: 4, level: 280, experience: 1000, experienceChange: 300, recordStatus: "available" },
        { date: "2026-11-06", ranking: 3, level: 280, experience: 1300, experienceChange: 300, recordStatus: "available" }
      ],
      historyStatus: "complete",
      historyStorage: { backend: "postgres", status: "saved", savedRecords: 5 },
      dataStatus: "current", dataAsOf: timestamp
    })
  }));
  await page.route("**/api/ai-analysis?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      analysis: "[성장 패턴] 최근 성장 흐름이 개선됐습니다.\\n[성장 변화] 주말에 성장이 집중됐습니다.\\n[레벨업 분석] 확인된 레벨업은 없습니다.\\n[성장 전망] 현재 자료를 참고하세요.\\n[AI 코멘트] 기록을 이어가세요.",
      cacheHit: false,
      growthInsights: {
        basis: {
          referenceDate: "2026-11-06",
          periodStartDate: "2026-10-24",
          periodEndDate: "2026-11-06",
          snapshotStartDate: "2026-10-23",
          expectedSnapshots: 15,
          availableSnapshots: 10,
          missingSnapshots: 5,
          coveragePercent: 66.7,
          dataQuality: "medium",
          dataQualityLabel: "보통"
        },
        recentPeriod: { validGrowthIntervals: 5 },
        previousPeriod: { validGrowthIntervals: 4 },
        weekOverWeek: { status: "available", averageDailyGrowthChangePercent: 12.5, direction: "increase" },
        weekdayWeekend: { status: "available", weekendSharePercent: 44.2 }
      }
    })
  }));

  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("근거테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
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
  await expect(page.getByTestId("ai-analysis-evidence")).toContainText("10 / 15일");
});

test("React next-level goal persists and completes when refreshed character reaches its target", async ({ page }) => {
  let characterLookups = 0;
  await page.route("**/api/character?*", route => {
    characterLookups += 1;
    const level = characterLookups === 1 ? 280 : 281;
    const experienceRate = characterLookups === 1 ? "30.000" : "0.000";
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        characterName: "목표테스트", worldName: "크로아", job: "전사", guildName: "테스트",
        level, experience: 10000, experienceRate,
        ranking: 1, worldRanking: 1, jobWorldRanking: 1, jobRanking: 1,
        ocid: "growth-goal-test-ocid", rankingDataStatus: "available",
        dataStatus: "current", dataAsOf: "2026-11-06T04:00:00+09:00"
      })
    });
  });
  let historyLookups = 0;
  await page.route("**/api/history?*", route => {
    historyLookups += 1;
    const latestLevel = historyLookups === 1 ? 280 : 281;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        characterName: "목표테스트", worldName: "크로아", level: latestLevel,
        history: [
          { date: "2026-11-05", ranking: 2, level: 280, experience: 9000, experienceChange: null, recordStatus: "available" },
          { date: "2026-11-06", ranking: 1, level: latestLevel, experience: 10000, experienceChange: latestLevel === 280 ? 1000 : null, levelUp: latestLevel === 281, recordStatus: "available" }
        ],
        historyStatus: "complete",
        historyStorage: { backend: "postgres", status: "saved", savedRecords: 2 },
        dataStatus: "current", dataAsOf: "2026-11-06T04:00:00+09:00"
      })
    });
  });
  await page.route("**/api/ai-analysis?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ analysis: "[성장 패턴] 기록을 확인했습니다.", cacheHit: false, growthInsights: null })
  }));
  await page.route("**/api/character-details?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ section: "stats", status: "available", sources: [] })
  }));

  await page.goto("/");
  await page.getByLabel("캐릭터명").fill("목표테스트");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  const goal = page.locator(".growth-goal-card");
  await expect(goal.getByRole("heading", { name: "다음 레벨 목표" })).toBeVisible();
  await expect(goal.locator(".growth-goal-target")).toContainText("Lv. 281");
  await goal.getByLabel("목표 날짜").fill("2099-12-31");
  await goal.getByRole("button", { name: "목표 설정" }).click();
  await expect(goal.locator(".growth-goal-status")).toHaveText("진행 중");
  const savedGoals = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("mapleGrowthTrackerGoals") || "{}")
  );
  expect(savedGoals["growth-goal-test-ocid"].targetLevel).toBe(281);
  expect(savedGoals["growth-goal-test-ocid"].targetDate).toBe("2099-12-31");

  await page.getByRole("button", { name: "최신 정보 다시 조회" }).click();
  await expect(goal.locator(".growth-goal-status")).toHaveText("목표 달성");
  await expect(goal.getByRole("status")).toContainText("목표를 달성했습니다");
  const completedGoals = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("mapleGrowthTrackerGoals") || "{}")
  );
  expect(completedGoals["growth-goal-test-ocid"].completedAt).toBeTruthy();

  await page.reload();
  await expect(page.locator(".growth-goal-card .growth-goal-status")).toHaveText("목표 달성");
});
