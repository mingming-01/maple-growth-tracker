import test from "node:test";
import assert from "node:assert/strict";

import { buildLevelUpMarkers } from "../frontend/src/features/growth/growthChartData.js";

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
