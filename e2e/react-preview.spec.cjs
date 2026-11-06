const { test, expect } = require("@playwright/test");

test("React preview is isolated from the existing Flask homepage", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#searchForm")).toBeVisible();

  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('[data-testid="react-character-search"]')).toBeVisible();
  await expect(page.getByRole("heading", { name: "모험가 찾기" })).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#growth"]')).toBeVisible();
});

test("React preview keeps the existing Flask admin route reachable", async ({ page }) => {
  await page.goto("/preview/");
  await expect(page.locator('[data-testid="react-preview-ready"]')).toBeVisible();
  await expect(page.locator('.mgt-nav a[href="#admin"]')).toBeVisible();
  await expect(page.locator('.mgt-footer a[href="/admin/login"]')).toHaveAttribute("href", "/admin/login");
});

test("React preview refreshes ranking data and restores the full-size profile progress UI", async ({ page }) => {
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
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  const characterRequest = await characterRequestPromise;
  expect(new URL(characterRequest.url()).searchParams.get("refresh")).toBe("1");

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


test("React admin panel logs in through Flask session and filters protected operations logs", async ({ page }) => {
  let authenticated = false;
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
    if (!authenticated) {
      await route.fulfill({
        status: 302,
        headers: { location: "/admin/login" },
        body: ""
      });
      return;
    }
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

  await page.route(/\/admin\/login(?:\?.*)?$/, async route => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "text/html",
        body: '<form><input type="hidden" name="csrf_token" value="e2e-csrf-token"></form>'
      });
      return;
    }
    authenticated = true;
    await route.fulfill({
      status: 302,
      headers: { location: "/admin/logs" },
      body: ""
    });
  });
  await page.route(/\/admin\/logs(?:\?.*)?$/, route => route.fulfill({
    status: 200,
    contentType: "text/html",
    body: "<html><body>Legacy admin fallback</body></html>"
  }));
  await page.route("**/admin/logout", route => {
    authenticated = false;
    return route.fulfill({ status: 302, headers: { location: "/admin/login" }, body: "" });
  });

  await page.goto("/preview/");
  await page.locator('.mgt-nav a[href="#admin"]').click();
  await expect(page.getByRole("heading", { name: "관리자 로그인" })).toBeVisible();
  await page.getByLabel("관리자 아이디").fill("admin");
  await page.getByLabel("비밀번호").fill("test-password");
  let adminLogsResponse = null;
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname === "/admin/api/logs" && response.status() === 200) {
      adminLogsResponse = response;
    }
  });
  await page.getByRole("button", { name: "로그인" }).click();

  await expect(page.getByRole("heading", { name: "관리자 로그" })).toBeVisible();
  await expect.poll(() => Boolean(adminLogsResponse)).toBe(true);
  const logsPayload = await adminLogsResponse.json();
  expect(logsPayload.logs.map(item => item.character_name)).toContain("밍득");
  expect(logsPayload.logs.map(item => item.error_type)).toContain("http_5xx");
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "밍득" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "http_5xx" })).toBeVisible();

  await page.getByLabel("검색어").fill("테스트캐릭터");
  await page.getByRole("button", { name: "검색" }).click();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "테스트캐릭터" })).toBeVisible();
  await expect(page.locator(".mgt-admin-table tbody tr").filter({ hasText: "밍득" })).toHaveCount(0);

  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("heading", { name: "관리자 로그인" })).toBeVisible();
});
