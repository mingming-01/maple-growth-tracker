async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers
    },
    ...options
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    // Keep the caller-facing fallback when the server does not return JSON.
  }

  if (!response.ok) {
    throw new Error(payload.error || "요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.");
  }

  return payload;
}

export function getCharacter(name, { refresh = false, signal } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/character?" + params.toString(), { signal });
}

export function getHistory(name, { refresh = false, signal } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/history?" + params.toString(), { signal });
}

export function getHistoryArchive(ocid, days = 30, options = {}) {
  const params = new URLSearchParams({
    ocid: String(ocid || ""),
    days: String(days)
  });
  if (options.end) params.set("end", options.end);
  if (options.collect) params.set("collect", "1");
  if (options.characterName) params.set("character_name", options.characterName);
  if (options.worldName) params.set("world_name", options.worldName);
  if (options.offset !== undefined) params.set("offset", String(options.offset));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  return requestJson("/api/history/archive?" + params.toString(), {
    signal: options.signal
  });
}

export function getCharacterDetails(ocid, section, { refresh = false, signal } = {}) {
  const params = new URLSearchParams({
    ocid: String(ocid || ""),
    section: String(section || "")
  });
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/character-details?" + params.toString(), { signal });
}

export function postAiAnalysis(name, metrics, { signal } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  return requestJson("/api/ai-analysis?" + params.toString(), {
    method: "POST",
    body: JSON.stringify({ metrics }),
    signal
  });
}

export function postAiComparison(primary, comparison, { signal } = {}) {
  return requestJson("/api/ai-comparison", {
    method: "POST",
    body: JSON.stringify({ primary, comparison }),
    signal
  });
}