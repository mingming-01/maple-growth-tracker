const { test, expect } = require("@playwright/test");

test("메인 프로필 갱신 후 열린 상세 스탯도 최신 전투력을 다시 조회한다", async ({ page }) => {
  let currentPower = "987654321";
  let detailRequestCount = 0;

  await page.route("**/api/character?*", async route => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("refresh") === "1") {
      currentPower = "999999999";
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        characterName: "동기화검증",
        ocid: "phase1-combat-power-sync-ocid",
        character_image: null,
        worldName: "크로아",
        job: "아크메이지(불,독)",
        guildName: null,
        level: 280,
        experience: 123456789,
        experienceRate: "35.600",
        ranking: 1,
        worldRanking: 2,
        jobWorldRanking: 3,
        jobRanking: 4,
        rankingDataStatus: "available",
        currentCombatPower: currentPower,
        bestCombatPower: Number(currentPower),
        bestCombatPowerObservedAt: "2026-11-10T10:00:00+09:00"
      })
    });
  });

  await page.route("**/api/history?*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ history: [], historyStatus: "complete" })
  }));

  await page.route("**/api/character-details?*", async route => {
    detailRequestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        section: "stats",
        status: "available",
        sources: [{
          id: "stat",
          label: "주요 스탯",
          status: "available",
          combatPower: currentPower,
          data: {
            final_stat: [
              { stat_name: "전투력", stat_value: currentPower },
              { stat_name: "STR", stat_value: "45000" }
            ]
          }
        }]
      })
    });
  });

  await page.goto("/preview/");
  await page.getByLabel("캐릭터명").fill("동기화검증");
  await page.getByRole("button", { name: /캐릭터 조회/ }).click();
  await expect(page.getByRole("heading", { name: "동기화검증" })).toBeVisible();

  await page.locator('.mgt-nav a[href="#/details"]').click();
  await page.locator("#details").getByRole("heading", { name: "캐릭터 상세 정보" }).scrollIntoViewIfNeeded();
  await expect(page.locator(".game-power-value")).toContainText("987,654,321");
  await expect.poll(() => detailRequestCount).toBe(1);

  await page.getByRole("button", { name: "최신 정보 다시 조회" }).click();
  await expect.poll(() => detailRequestCount).toBe(2);
  await expect(page.locator(".game-power-value")).toContainText("999,999,999");
});
