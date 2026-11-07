import test from "node:test";
import assert from "node:assert/strict";

import {
  detectLevelUpEvents,
  buildLevelUpMarkers,
  buildExperienceChartSeries,
  dailyGrowthSegmentDash
} from "../frontend/src/features/growth/growthChartData.js";

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

test("does not invent a chart coordinate before any cumulative EXP value exists", () => {
  const records = [
    { date: "2026-09-22", levelUp: false },
    { date: "2026-09-23", levelUp: true }
  ];

  assert.deepEqual(buildLevelUpMarkers(records, [null, null]), [null, null]);
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

test("detects level-up days by comparing the recorded level when no flag is supplied", () => {
  const records = [
    { date: "2026-11-01", level: 280 },
    { date: "2026-11-02", level: 280 },
    { date: "2026-11-03", level: 281 },
    { date: "2026-11-04", level: null },
    { date: "2026-11-05", level: 282 },
    { date: "2026-11-06", level: 282, levelUp: true }
  ];

  assert.deepEqual(detectLevelUpEvents(records), [false, false, true, false, true, true]);
  assert.deepEqual(
    buildLevelUpMarkers(records, [1, 1.2, null, null, 1.25, null]),
    [null, null, 1.2, null, 1.25, 1.25]
  );
});

test("anchors total EXP growth to the first calendar day's actual EXP", () => {
  const records = [
    { date: "2026-11-02", recordStatus: "available", experience: 1_000_000_000_000, experienceChange: null },
    { date: "2026-11-03", recordStatus: "available", experience: 1_250_000_000_000, experienceChange: 250_000_000_000 },
    { date: "2026-11-04", recordStatus: "available", experience: 1_250_000_000_000, experienceChange: 0 },
    { date: "2026-11-05", recordStatus: "available", experience: 1_750_000_000_000, experienceChange: 500_000_000_000 },
    { date: "2026-11-06", recordStatus: "available", experience: 2_000_000_000_000, experienceChange: 250_000_000_000 },
    { date: "2026-11-07", recordStatus: "available", experience: 2_100_000_000_000, experienceChange: 100_000_000_000 },
    { date: "2026-11-08", recordStatus: "available", experience: 2_300_000_000_000, experienceChange: 200_000_000_000 }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.cumulative, [1, 1.25, 1.25, 1.75, 2, 2.1, 2.3]);
  assert.deepEqual(series.daily, [null, 0.25, 0, 0.5, 0.25, 0.1, 0.2]);
});

test("does not shift the baseline to the first later observed date", () => {
  const records = [
    { date: "2026-11-02", recordStatus: "not_ready", experience: null, experienceChange: null },
    { date: "2026-11-03", recordStatus: "available", experience: 1_250_000_000_000, experienceChange: null },
    { date: "2026-11-04", recordStatus: "available", experience: 1_500_000_000_000, experienceChange: 250_000_000_000 }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.cumulative, [null, null, null]);
  assert.deepEqual(series.daily, [null, null, 0.25]);
});

test("keeps unknown days blank instead of converting them to zero growth", () => {
  const records = [
    { date: "2026-11-02", recordStatus: "available", experience: 1_000_000_000_000, experienceChange: null },
    { date: "2026-11-03", recordStatus: "available", experience: 1_100_000_000_000, experienceChange: 100_000_000_000 },
    { date: "2026-11-04", recordStatus: "not_collected", experience: null, experienceChange: null },
    { date: "2026-11-05", recordStatus: "available", experience: 1_300_000_000_000, experienceChange: null },
    { date: "2026-11-06", recordStatus: "available", experience: 1_450_000_000_000, experienceChange: 150_000_000_000 }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.cumulative, [1, 1.1, null, null, null]);
  assert.deepEqual(series.daily, [null, 0.1, null, null, 0.15]);
});

test("dashes only the daily EXP segment whose current day has zero growth", () => {
  const context = current => ({ p1: { parsed: { y: current } } });

  assert.deepEqual(dailyGrowthSegmentDash(context(120)), []);
  assert.deepEqual(dailyGrowthSegmentDash(context(0)), [2, 4]);
  assert.deepEqual(dailyGrowthSegmentDash(context(80)), []);
});

test("carries the last known total across a level-up without inventing cross-level EXP", () => {
  const records = [
    { date: "2026-11-02", level: 280, recordStatus: "available", experience: 1_000_000_000_000, experienceChange: null },
    { date: "2026-11-03", level: 280, recordStatus: "available", experience: 1_100_000_000_000, experienceChange: 100_000_000_000 },
    { date: "2026-11-04", level: 281, recordStatus: "available", experience: 20_000_000, experienceChange: null },
    { date: "2026-11-05", level: 281, recordStatus: "available", experience: 120_000_000, experienceChange: 100_000_000 }
  ];

  const series = buildExperienceChartSeries(records);

  assert.deepEqual(series.cumulative, [1, 1.1, 1.1, 1.1001]);
  assert.equal(series.daily[2], null);
});
