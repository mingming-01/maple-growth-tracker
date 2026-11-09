import assert from "node:assert/strict";
import { test } from "node:test";
import { getCachedAI, saveCachedAI, STORAGE_KEYS } from "../frontend/src/lib/storage.js";

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

test("AI report cache expires after the period-specific retention window", () => {
  const previousStorage = globalThis.localStorage;
  const previousNow = Date.now;
  const storage = new MemoryStorage();
  globalThis.localStorage = storage;

  const day = 24 * 60 * 60 * 1000;
  const retention = [
    ["growth-report-7d", 6 * 60 * 60 * 1000],
    ["growth-report-30d", 7 * day],
    ["growth-report-90d", 30 * day]
  ];

  let now = 1_800_000_000_000;
  Date.now = () => now;

  try {
    for (const [type, ttl] of retention) {
      const signature = "character-ocid:" + type;
      saveCachedAI(type, signature, "saved report");

      assert.equal(getCachedAI(type, signature)?.analysis, "saved report");

      now += ttl;
      assert.equal(getCachedAI(type, signature)?.analysis, "saved report");

      now += 1;
      assert.equal(getCachedAI(type, signature), null);
      now -= ttl + 1;
    }

    const stored = JSON.parse(storage.getItem(STORAGE_KEYS.ai) || "[]");
    assert.equal(stored.length, 0);
  } finally {
    Date.now = previousNow;
    if (previousStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previousStorage;
  }
});
