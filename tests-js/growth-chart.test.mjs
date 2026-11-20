import test from "node:test";
import assert from "node:assert/strict";

import {
  buildExperienceChartSeries,
  buildLevelUpMarkers,
  detectLevelUpEvents,
  dailyGrowthSegmentDash
} from "../frontend/src/features/growth/growthChartData.js";

test("keeps cumulative EXP continuous across a level-up while daily EXP stays unknown", () => {
  const records = [
    { date: "2026-11-17", level: 298, experience: 1129263590513928, experienceRate: 99.226, experienceChange: null, levelUp: false, recordStatus: "available" },
    { date: "2026-11-18", level: 298, experience: 6175579914147, experienceRate: 0.355, experienceChange: null, levelUp: true, levelUpPreviousLevel: 298, levelUpCurrentLevel: 299, recordStatus: "available" },
    { date: "2026-11-19", level: 299, experience: 34219899249572, experienceRate: 1.969, experienceChange: 28044319335425, levelUp: false, levelUpCatchUp: true, recordStatus: "available" },
    { date: "2026-11-20", level: 299, experience: 50805631039495, experienceRate: 2.924, experienceChange: 16585731789923, levelUp: false, recordStatus: "available" }
  ];

  const series = buildExperienceChartSeries(records);
  assert.deepEqual(detectLevelUpEvents(records), [false, true, false, false]);
  assert.deepEqual(series.cumulative, [
    1129.263590513928,
    1129.263590513928,
    1157.307909849353,
    1173.893641639276
  ]);
  assert.deepEqual(series.daily, [null, null, 28.044319335425, 16.585731789923]);
  assert.deepEqual(
    buildLevelUpMarkers(records, series.cumulative),
    [null, 1129.263590513928, null, null]
  );
});

test("level-up marker uses the last confirmed cumulative value without inventing its daily EXP", () => {
  const series = buildExperienceChartSeries([
    { date: "2026-11-17", recordStatus: "available", experience: 1000, experienceChange: null },
    { date: "2026-11-18", recordStatus: "available", level: 281, experience: 20, experienceChange: null, levelUp: true },
    { date: "2026-11-19", recordStatus: "available", level: 281, experience: 120, experienceChange: 100, levelUp: false }
  ]);
  assert.deepEqual(series.cumulative, [0.000000001, 0.000000001, 0.0000000011]);
  assert.deepEqual(series.daily, [null, null, 0.0000000001]);
  assert.deepEqual(buildLevelUpMarkers([
    { level: 280 }, { level: 281, levelUp: true }, { level: 281, levelUp: false }
  ], series.cumulative), [null, 0.000000001, null]);
});

test("does not turn missing experience records into zero or bridge a missing-date gap", () => {
  const series = buildExperienceChartSeries([
    { date: "2026-11-17", recordStatus: "available", experience: 1000, experienceChange: null },
    { date: "2026-11-18", recordStatus: "not_collected", experience: null, experienceChange: null },
    { date: "2026-11-19", recordStatus: "available", experience: 1500, experienceChange: null }
  ]);
  assert.deepEqual(series.cumulative, [0.000000001, null, null]);
  assert.deepEqual(series.daily, [null, null, null]);
});

test("only zero daily growth is dotted", () => {
  const context = current => ({ p1: { parsed: { y: current } } });
  assert.deepEqual(dailyGrowthSegmentDash(context(120)), []);
  assert.deepEqual(dailyGrowthSegmentDash(context(0)), [2, 4]);
  assert.deepEqual(dailyGrowthSegmentDash(context(80)), []);
});
