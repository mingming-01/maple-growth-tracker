import test from "node:test";
import assert from "node:assert/strict";

import { buildExperienceChartSeries, buildLevelUpMarkers } from "../frontend/src/features/growth/growthChartData.js";

test("places level-up marker on the last known cumulative value when event EXP is missing", () => {
  const records = [
    { date: "2026-09-22", levelUp: false },
    { date: "2026-09-23", levelUp: true },
    { date: "2026-09-24", levelUp: false }
  ];

  assert.deepEqual(
    buildLevelUpMarkers(records, [1.25, null, 1.4]),
    [null, 1.25, null]
  );
});

test("keeps an early level-up marker visible before any cumulative EXP value exists", () => {
  const records = [
    { date: "2026-09-22", levelUp: false },
    { date: "2026-09-23", levelUp: true }
  ];

  assert.deepEqual(buildLevelUpMarkers(records, [null, null]), [null, 0]);
});

test("uses the latest known cumulative value for consecutive level-up events", () => {
  const records = [
    { levelUp: false },
    { levelUp: true },
    { levelUp: true },
    { levelUp: false }
  ];

  assert.deepEqual(
    buildLevelUpMarkers(records, [2.5, null, null, 2.8]),
    [null, 2.5, 2.5, null]
  );
});


test("plots the first day's actual EXP instead of starting cumulative growth at zero", () => {
  const records = [
    { date: "2026-11-02", recordStatus: "available", experience: 1_250_000_000_000, experienceChange: null },
    { date: "2026-11-03", recordStatus: "available", experience: 1_400_000_000_000, experienceChange: 150_000_000_000 },
    { date: "2026-11-04", recordStatus: "available", experience: 1_400_000_000_000, experienceChange: 0 },
    { date: "2026-11-05", recordStatus: "available", experience: 1_550_000_000_000, experienceChange: 150_000_000_000 }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.totalExperience, [1.25, 1.4, 1.4, 1.55]);
  assert.deepEqual(series.dailyGrowth, [null, 0.15, 0, 0.15]);
  assert.deepEqual(series.zeroGrowthDays, [false, false, true, false]);
});

test("does not turn uncollected days into zero EXP or a confirmed zero-growth segment", () => {
  const records = [
    { date: "2026-11-02", recordStatus: "available", experience: 1_250_000_000_000, experienceChange: null },
    { date: "2026-11-03", recordStatus: "not_collected", experience: null, experienceChange: null },
    { date: "2026-11-04", recordStatus: "available", experience: 1_400_000_000_000, experienceChange: null }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.totalExperience, [1.25, null, 1.4]);
  assert.deepEqual(series.dailyGrowth, [null, null, null]);
  assert.deepEqual(series.zeroGrowthDays, [false, false, false]);
});

test("plots level-up dates using the recorded EXP after the level changes", () => {
  const records = [
    { date: "2026-11-02", level: 280, recordStatus: "available", experience: 1_250_000_000_000, experienceChange: null },
    { date: "2026-11-03", level: 281, levelUp: true, recordStatus: "available", experience: 15_000_000, experienceChange: null }
  ];
  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.totalExperience, [1.25, 0.000015]);
  assert.deepEqual(buildLevelUpMarkers(records, series.totalExperience), [null, 0.000015]);
});
