import test from "node:test";
import assert from "node:assert/strict";

import {
    buildGrowthTimeline,
    calculateAverageGrowth,
    calculateGrowthMetrics,
    calculateLevelProgress,
    calculateWeeklyGrowth,
    getDailyGrowth,
    getRankingChange
} from "../static/js/growth.js";

test("average growth includes positive, zero and negative observed changes", () => {
    const history = [
        { date: "2026-11-01", recordStatus: "available", experienceChange: 100 },
        { date: "2026-11-02", recordStatus: "available", experienceChange: 0 },
        { date: "2026-11-03", recordStatus: "available", experienceChange: -20 },
        { date: "2026-11-04", recordStatus: "not_collected", experienceChange: null }
    ];

    assert.equal(calculateAverageGrowth(history), 80 / 3);
    assert.equal(calculateWeeklyGrowth(history), 80);
});

test("latest growth skips uncollected and unconfirmed records", () => {
    const history = [
        { date: "2026-11-01", recordStatus: "available", experienceChange: 250 },
        { date: "2026-11-02", recordStatus: "not_ready", experienceChange: null },
        { date: "2026-11-03", recordStatus: "available", levelUp: true, experienceChange: null }
    ];

    assert.equal(getDailyGrowth(history), 250);
});

test("ranking change uses the latest two valid ranking observations", () => {
    const history = [
        { date: "2026-11-01", ranking: 500 },
        { date: "2026-11-02", ranking: 470 },
        { date: "2026-11-03", ranking: null }
    ];

    assert.equal(getRankingChange(history), 30);
});

test("level progress converts average EXP to percentage points of the current level", () => {
    const progress = calculateLevelProgress(
        { experience: 250, experienceRate: "25.000" },
        50
    );

    assert.equal(progress.currentRate, 25);
    assert.equal(progress.remainingRate, 75);
    assert.equal(progress.estimatedLevelExperience, 1000);
    assert.equal(progress.dailyProgressRate, 5);
});

test("level progress avoids division by zero at 0 percent", () => {
    const progress = calculateLevelProgress(
        { experience: 0, experienceRate: "0.000" },
        50
    );

    assert.equal(progress.currentRate, 0);
    assert.equal(progress.remainingRate, 100);
    assert.equal(progress.estimatedLevelExperience, null);
    assert.equal(progress.dailyProgressRate, null);
});

test("growth timeline contains level-up, best-growth, ranking and latest milestones", () => {
    const history = [
        {
            date: "2026-11-01", recordStatus: "available", level: 280,
            experience: 100, experienceChange: null, ranking: 500, rankingChange: null
        },
        {
            date: "2026-11-02", recordStatus: "available", level: 280,
            experience: 300, experienceChange: 200, ranking: 450, rankingChange: 50
        },
        {
            date: "2026-11-03", recordStatus: "available", level: 281,
            experience: 20, experienceChange: null, levelUp: true, ranking: 430, rankingChange: 20
        }
    ];

    const events = buildGrowthTimeline(history);
    assert.ok(events.some(event => event.type === "level-up" && event.date === "2026-11-03"));
    assert.ok(events.some(event => event.type === "best-growth" && event.date === "2026-11-02"));
    assert.ok(events.some(event => event.type === "ranking" && event.date === "2026-11-02"));
    assert.ok(events.length <= 8);
});

test("growth metrics expose observed-day counts and level-relative pace", () => {
    const character = { level: 280, experience: 250, experienceRate: 25 };
    const history = [
        { date: "2026-11-01", recordStatus: "available", level: 280, experience: 100, experienceChange: null },
        { date: "2026-11-02", recordStatus: "available", level: 280, experience: 200, experienceChange: 100 },
        { date: "2026-11-03", recordStatus: "available", level: 280, experience: 200, experienceChange: 0 },
        { date: "2026-11-04", recordStatus: "available", level: 280, experience: 180, experienceChange: -20 }
    ];

    const metrics = calculateGrowthMetrics(character, history);
    assert.equal(metrics.validGrowthDays, 1);
    assert.equal(metrics.observedChangeDays, 3);
    assert.equal(metrics.zeroGrowthDays, 1);
    assert.equal(metrics.negativeGrowthDays, 1);
    assert.equal(metrics.averageDailyGrowth, 80 / 3);
    assert.equal(metrics.sevenDayGrowth, 80);
    assert.equal(metrics.levelProgress.dailyProgressRate, (80 / 3 / 1000) * 100);
});
