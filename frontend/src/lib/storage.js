export const STORAGE_KEYS = Object.freeze({
  state: "mapleGrowthTrackerState",
  favorites: "mapleGrowthTrackerFavorites",
  goals: "mapleGrowthTrackerGoals",
  ai: "mapleGrowthTrackerAIResponsesV1"
});

const MAX_FAVORITES = 30;
const MAX_AI_ENTRIES = 40;
const DEFAULT_AI_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const AI_TTL_BY_TYPE = Object.freeze({
  // 30·90일 성장 리포트는 단기 기록 변동에 흔들리지 않도록 7일간 재사용한다.
  "growth-report-v3": 7 * 24 * 60 * 60 * 1000
});

function getAiTtl(type) {
  return AI_TTL_BY_TYPE[type] || DEFAULT_AI_TTL_MS;
}

function readJson(storage, key, fallback) {
  try {
    const raw = storage?.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(storage, key, value) {
  try {
    storage?.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function readTrackerState() {
  return readJson(globalThis.sessionStorage, STORAGE_KEYS.state, null);
}

export function saveTrackerState(patch) {
  const previous = readTrackerState() || {};
  return writeJson(globalThis.sessionStorage, STORAGE_KEYS.state, {
    ...previous,
    ...patch
  });
}

export function readFavorites() {
  const saved = readJson(globalThis.localStorage, STORAGE_KEYS.favorites, []);
  if (!Array.isArray(saved)) return [];
  return saved
    .filter(item => item && typeof item.name === "string" && item.name.trim())
    .map(item => ({
      ocid: typeof item.ocid === "string" ? item.ocid : "",
      name: item.name.trim(),
      worldName: typeof item.worldName === "string" ? item.worldName : ""
    }))
    .slice(0, MAX_FAVORITES);
}

export function saveFavorites(favorites) {
  return writeJson(globalThis.localStorage, STORAGE_KEYS.favorites,
    (Array.isArray(favorites) ? favorites : []).slice(0, MAX_FAVORITES));
}

export function favoriteKey(item) {
  return item?.ocid
    ? "ocid:" + item.ocid
    : "name:" + String(item?.name || "") + ":" + String(item?.worldName || "");
}

export function readGrowthGoals() {
  const value = readJson(globalThis.localStorage, STORAGE_KEYS.goals, {});
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function saveGrowthGoals(goals) {
  return writeJson(globalThis.localStorage, STORAGE_KEYS.goals, goals || {});
}

export function hashSignature(value) {
  let hash = 2166136261;
  const source = String(value);
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16);
}

export function readAIEntries() {
  const entries = readJson(globalThis.localStorage, STORAGE_KEYS.ai, []);
  if (!Array.isArray(entries)) return [];
  const now = Date.now();
  return entries.filter(item =>
    item &&
    typeof item.signature === "string" &&
    typeof item.analysis === "string" &&
    Number.isFinite(item.savedAt) &&
    now - item.savedAt <= getAiTtl(item.type)
  ).slice(0, MAX_AI_ENTRIES);
}

export function getCachedAI(type, signature) {
  const entries = readAIEntries();
  const key = type + ":" + hashSignature(signature);
  const entry = entries.find(item =>
    item.type === type && item.key === key && item.signature === signature
  );
  if (!entry) return null;
  entry.lastUsedAt = Date.now();
  writeJson(globalThis.localStorage, STORAGE_KEYS.ai, entries);
  return {
    analysis: entry.analysis,
    growthInsights: entry.growthInsights || null
  };
}

export function saveCachedAI(type, signature, analysis, growthInsights = null) {
  if (!analysis) return;
  const entries = readAIEntries();
  const key = type + ":" + hashSignature(signature);
  const now = Date.now();
  const next = entries.filter(item => !(item.type === type && item.key === key));
  next.unshift({
    type,
    key,
    signature,
    analysis,
    growthInsights,
    savedAt: now,
    lastUsedAt: now
  });
  writeJson(globalThis.localStorage, STORAGE_KEYS.ai, next.slice(0, MAX_AI_ENTRIES));
}

export function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(stableStringify).join(",") + "]";
  return "{" + Object.keys(value).sort().map(key =>
    JSON.stringify(key) + ":" + stableStringify(value[key])
  ).join(",") + "}";
}

export const MAX_FAVORITE_CHARACTERS = MAX_FAVORITES;