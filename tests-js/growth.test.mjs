import test from "node:test";
import assert from "node:assert/strict";

import {
    buildGrowthTimeline,
    calculateAverageGrowth,
    calculateDailyExperienceRateChanges,
    calculateGrowthMetrics,
    calculatePrediction,
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

test("daily level progress change compares only consecutive dates within the same level", () => {
    const history = [
        { date: "2026-11-01", level: 280, recordStatus: "available", experienceRate: "10.000" },
        { date: "2026-11-02", level: 280, recordStatus: "available", experienceRate: "10.750" },
        { date: "2026-11-03", level: 280, recordStatus: "available", experienceRate: "10.750" },
        { date: "2026-11-04", level: 281, levelUp: true, recordStatus: "available", experienceRate: "0.125" },
        { date: "2026-11-05", level: 281, recordStatus: "available", experienceRate: "0.625" },
        { date: "2026-11-07", level: 281, recordStatus: "available", experienceRate: "1.000" },
        { date: "2026-11-08", level: 281, recordStatus: "not_collected", experienceRate: null },
        { date: "2026-11-09", level: 281, recordStatus: "available", experienceRate: "1.500" },
        { date: "2026-11-10", level: 281, recordStatus: "available", experienceRate: "0.250" }
    ];

    assert.deepEqual(calculateDailyExperienceRateChanges(history), {
        "2026-11-02": 0.75,
        "2026-11-03": 0,
        "2026-11-05": 0.5
    });
    // A negative same-level delta is treated as an inconsistent/corrected
    // snapshot, not as a legitimate decrease in MapleStory EXP progress.
    assert.equal(calculateDailyExperienceRateChanges(history)["2026-11-10"], undefined);
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


test("future and invalid snapshots are excluded from growth metrics and timeline", () => {
    const formatDate = value => {
        const year = value.getFullYear();
        const month = String(value.getMonth() + 1).padStart(2, "0");
        const day = String(value.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    };
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const todayDate = formatDate(today);
    const history = [
        { date: formatDate(yesterday), recordStatus: "available", level: 280, experience: 1000, experienceChange: 100 },
        { date: todayDate, recordStatus: "available", level: 280, experience: 1100, experienceChange: 100 },
        { date: formatDate(tomorrow), recordStatus: "available", level: 281, experience: 999999, experienceChange: 999000, levelUp: true },
        { date: "2026-02-30", recordStatus: "available", level: 282, experience: 1999999, experienceChange: 999000, levelUp: true }
    ];

    const metrics = calculateGrowthMetrics(
        { level: 280, experience: 1100, experienceRate: 50 },
        history
    );

    assert.equal(metrics.observedChangeDays, 2);
    assert.equal(metrics.recordedDays, 2);
    assert.equal(metrics.averageDailyGrowth, 100);
    assert.ok(metrics.timeline.every(event => event.date <= todayDate));
    assert.ok(metrics.timeline.every(event => event.date !== "2026-02-30"));
});

test("level-up forecast is withheld when recent observed intervals are insufficient", () => {
    const today = new Date();
    const dates = [4, 3, 2, 1].map(daysAgo => {
        const value = new Date(today);
        value.setDate(value.getDate() - daysAgo);
        const year = value.getFullYear();
        const month = String(value.getMonth() + 1).padStart(2, "0");
        const day = String(value.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    });
    const history = dates.map((date, index) => ({
        date,
        recordStatus: "available",
        level: 280,
        experience: 1000 + index * 100,
        experienceChange: index === 0 ? null : 100
    }));

    assert.equal(
        calculatePrediction(
            { level: 280, experience: 1400, experienceRate: 50 },
            history
        ),
        null
    );
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
