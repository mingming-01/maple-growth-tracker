import test from "node:test";
import assert from "node:assert/strict";

import {
  buildExperienceChartSeries,
  detectLevelUpEvents,
  levelExperienceSegmentColor,
  dailyGrowthSegmentDash
} from "../frontend/src/features/growth/growthChartData.js";

test("plots raw level-local EXP on the reset date and daily EXP separately", () => {
  const records = [
    { date: "2026-11-17", level: 298, experience: 1129263590513928, experienceRate: 99.226, experienceChange: null, levelUp: false, recordStatus: "available" },
    { date: "2026-11-18", level: 298, experience: 6175579914147, experienceRate: 0.355, experienceChange: null, levelUp: true, levelUpCurrentLevel: 299, recordStatus: "available" },
    { date: "2026-11-19", level: 299, experience: 34219899249572, experienceRate: 1.969, experienceChange: 28044319335425, levelUp: false, levelUpCatchUp: true, recordStatus: "available" },
    { date: "2026-11-20", level: 299, experience: 50805631039495, experienceRate: 2.924, experienceChange: 16585731789923, levelUp: false, recordStatus: "available" }
  ];

  const series = buildExperienceChartSeries(records);
  assert.deepEqual(detectLevelUpEvents(records), [false, true, false, false]);
  assert.deepEqual(series.experience, [
    1129.263590513928, 6.175579914147, 34.219899249572, 50.805631039495
  ]);
  assert.deepEqual(series.daily, [null, null, 28.044319335425, 16.585731789923]);
});

test("hides only the line entering a level-up point while preserving its raw EXP point", () => {
  const events = [false, true, false];
  assert.equal(levelExperienceSegmentColor({ p1DataIndex: 1 }, events), "transparent");
  assert.equal(levelExperienceSegmentColor({ p1DataIndex: 2 }, events), "#36a2eb");
});

test("does not turn missing experience records into zero", () => {
  const series = buildExperienceChartSeries([
    { date: "2026-11-17", recordStatus: "available", experience: 1000, experienceChange: null },
    { date: "2026-11-18", recordStatus: "not_collected", experience: null, experienceChange: null },
    { date: "2026-11-19", recordStatus: "available", experience: 1500, experienceChange: null }
  ]);
  assert.deepEqual(series.experience, [0.000000000001, null, 0.0000000000015]);
  assert.deepEqual(series.daily, [null, null, null]);
});

test("only zero daily growth is dotted", () => {
  const context = current => ({ p1: { parsed: { y: current } } });
  assert.deepEqual(dailyGrowthSegmentDash(context(120)), []);
  assert.deepEqual(dailyGrowthSegmentDash(context(0)), [2, 4]);
  assert.deepEqual(dailyGrowthSegmentDash(context(80)), []);
});
