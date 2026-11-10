import assert from "node:assert/strict";
import { test } from "node:test";
import { fetchHistoryArchive } from "../frontend/src/lib/historyCollection.js";

async function withFetch(responses, run) {
  const previousFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    const payload = responses.shift();
    if (!payload) throw new Error("Unexpected API request");
    return {
      ok: true, status: 200, redirected: false,
      headers: { get: name => name.toLowerCase() === "content-type" ? "application/json" : null },
      json: async () => payload
    };
  };
  try { await run(calls); } finally { globalThis.fetch = previousFetch; }
}

test("history collection uses summary-only batches and fetches the full archive once", async () => {
  const character = { ocid: "ocid-1", characterName: "밍득", worldName: "크로아" };
  const batch = remainingDays => ({ collection: { checkedDays: 10, savedRecords: 8, availableRecords: 7, noDataRecords: 1, remainingDays } });
  const archive = { history: [{ date: "2026-11-10", recordStatus: "available" }] };
  await withFetch([batch(20), batch(10), batch(0), archive], async calls => {
    const result = await fetchHistoryArchive(30, character, { collect: true });
    assert.deepEqual(result.history, archive.history);
    assert.deepEqual(result.collectionSummary, { checkedDays: 30, savedRecords: 24, availableRecords: 21, noDataRecords: 3, remainingDays: 0 });
    assert.equal(calls.length, 4);
    for (const [index, offset] of [0, 10, 20].entries()) {
      const query = new URL(calls[index].url, "http://localhost").searchParams;
      assert.equal(query.get("collect"), "1");
      assert.equal(query.get("summary_only"), "1");
      assert.equal(query.get("offset"), String(offset));
      assert.equal(query.get("limit"), "10");
    }
    const finalQuery = new URL(calls[3].url, "http://localhost").searchParams;
    assert.equal(finalQuery.has("collect"), false);
    assert.equal(finalQuery.has("summary_only"), false);
    assert.equal(finalQuery.has("offset"), false);
  });
});

test("history collection stops when the backend reports no remaining days", async () => {
  const character = { ocid: "ocid-2", characterName: "테스트", worldName: "크로아" };
  await withFetch([{ collection: { checkedDays: 10, savedRecords: 10, availableRecords: 10, noDataRecords: 0, remainingDays: 0 } }, { history: [] }], async calls => {
    const result = await fetchHistoryArchive(90, character, { collect: true });
    assert.equal(result.collectionSummary.checkedDays, 10);
    assert.equal(calls.length, 2);
  });
});

test("an existing comparison period is loaded with one non-collection request", async () => {
  const character = { ocid: "ocid-3", characterName: "비교캐릭터", worldName: "크로아" };
  const archive = { history: [{ date: "2026-10-01" }] };
  await withFetch([archive], async calls => {
    const result = await fetchHistoryArchive(30, character, { end: "2026-10-01" });
    assert.deepEqual(result, archive);
    assert.equal(calls.length, 1);
    const query = new URL(calls[0].url, "http://localhost").searchParams;
    assert.equal(query.get("end"), "2026-10-01");
    assert.equal(query.has("collect"), false);
  });
});
