import test from "node:test";
import assert from "node:assert/strict";

import {
  buildExperienceChartSeries,
  detectLevelUpEvents,
  levelExperienceSegmentDash,
  dailyGrowthSegmentDash
} from "../frontend/src/features/growth/growthChartData.js";

test("plots level-local EXP and daily EXP independently across a level-up reset", () => {
  const records = [
    { date: "2026-11-17", level: 298, experience: 1129263590513928, experienceRate: 99.226, experienceChange: null, levelUp: false, recordStatus: "available" },
    { date: "2026-11-18", level: 298, experience: 6175579914147, experienceRate: 0.355, experienceChange: 14984259283040, experienceChangeKind: "level_up_reconstructed", experienceChangeLowerBound: 14978524563636, experienceChangeUpperBound: 14989994060239, levelUp: true, levelUpPreviousLevel: 298, levelUpCurrentLevel: 299, recordStatus: "available" },
    { date: "2026-11-19", level: 299, experience: 34219899249572, experienceRate: 1.969, experienceChange: 28044319335425, levelUp: false, levelUpCatchUp: true, recordStatus: "available" },
    { date: "2026-11-20", level: 299, experience: 50805631039495, experienceRate: 2.924, experienceChange: 16585731789923, levelUp: false, recordStatus: "available" }
  ];

  const series = buildExperienceChartSeries(records);
  const events = detectLevelUpEvents(records);
  assert.deepEqual(events, [false, true, false, false]);
  assert.deepEqual(series.experience, [
    1129.263590513928, 6.175579914147, 34.219899249572, 50.805631039495
  ]);
  assert.deepEqual(series.daily, [null, 14.98425928304, 28.044319335425, 16.585731789923]);
  assert.deepEqual(levelExperienceSegmentDash({ p1DataIndex: 1 }, events), [6, 4]);
  assert.deepEqual(levelExperienceSegmentDash({ p1DataIndex: 2 }, events), []);
});

test("keeps level-up EXP point visible and only dashes the segment crossing the level boundary", () => {
  const records = [
    { level: 280, experience: 1000, experienceChange: null, recordStatus: "available" },
    { level: 281, experience: 20, experienceChange: null, levelUp: true, recordStatus: "available" },
    { level: 281, experience: 120, experienceChange: 100, levelUp: false, recordStatus: "available" }
  ];
  const events = detectLevelUpEvents(records);
  const series = buildExperienceChartSeries(records);
  assert.deepEqual(series.experience, [0.000000001, 0.00000000002, 0.00000000012]);
  assert.deepEqual(levelExperienceSegmentDash({ p1DataIndex: 1 }, events), [6, 4]);
  assert.deepEqual(levelExperienceSegmentDash({ p1DataIndex: 2 }, events), []);
  assert.deepEqual(series.daily, [null, null, 0.0000000001]);
});

test("does not turn missing experience records into zero or bridge a missing-date gap", () => {
  const series = buildExperienceChartSeries([
    { date: "2026-11-17", recordStatus: "available", experience: 1000, experienceChange: null },
    { date: "2026-11-18", recordStatus: "not_collected", experience: null, experienceChange: null },
    { date: "2026-11-19", recordStatus: "available", experience: 1500, experienceChange: null }
  ]);
  assert.deepEqual(series.experience, [0.000000001, null, 0.0000000015]);
  assert.deepEqual(series.daily, [null, null, null]);
});

test("only zero daily growth is dotted", () => {
  const context = current => ({ p1: { parsed: { y: current } } });
  assert.deepEqual(dailyGrowthSegmentDash(context(120)), []);
  assert.deepEqual(dailyGrowthSegmentDash(context(0)), [2, 4]);
  assert.deepEqual(dailyGrowthSegmentDash(context(80)), []);
});
