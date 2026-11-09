async function requestResponse(path, options = {}) {
  return fetch(path, {
    credentials: "same-origin",
    ...options
  });
}

async function requestJson(path, options = {}) {
  const response = await requestResponse(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers
    },
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    // Keep the caller-facing fallback when the server does not return JSON.
  }

  if (!response.ok) {
    const error = new Error(payload.error || "요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.");
    error.status = response.status;
    const retryAfter = Number(
      payload.retryAfterSeconds ?? payload.retryAfter ?? response.headers.get("Retry-After")
    );
    if (Number.isFinite(retryAfter) && retryAfter > 0) {
      error.retryAfterSeconds = Math.ceil(retryAfter);
      if (response.status === 429) {
        const totalMinutes = Math.ceil(error.retryAfterSeconds / 60);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        const retryLabel = hours > 0
          ? (minutes > 0 ? `${hours}시간 ${minutes}분` : `${hours}시간`)
          : `${Math.max(1, minutes)}분`;
        error.message += ` (약 ${retryLabel} 후 다시 시도할 수 있습니다.)`;
      }
    }
    throw error;
  }

  return payload;
}

function selectAiMetricsForPeriod(metrics, analysisContext) {
  const periodDays = Number(analysisContext?.periodDays || 7);
  if (![30, 90].includes(periodDays)) return metrics;

  // 장기 리포트에는 최근 7일의 집계 지표를 섞지 않고,
  // 최근 속도 기준 예측과 현재 레벨 진행률만 전달한다.
  const levelProgress = metrics?.levelProgress || {};
  return {
    prediction: metrics?.prediction ?? null,
    levelProgress: {
      ...(levelProgress.currentRate !== undefined ? { currentRate: levelProgress.currentRate } : {}),
      ...(levelProgress.remainingRate !== undefined ? { remainingRate: levelProgress.remainingRate } : {})
    }
  };
}

export function getCharacter(name, { refresh = true, signal } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/character?" + params.toString(), { signal, cache: "no-store" });
}

export function getHistory(name, { refresh = true, ocid, signal } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  if (ocid) params.set("ocid", String(ocid));
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/history?" + params.toString(), { signal, cache: "no-store" });
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
  if (options.summaryOnly) params.set("summary_only", "1");
  return requestJson("/api/history/archive?" + params.toString(), {
    signal: options.signal,
    cache: "no-store"
  });
}

export function getCharacterDetails(ocid, section, { refresh = false, signal } = {}) {
  const params = new URLSearchParams({
    ocid: String(ocid || ""),
    section: String(section || "")
  });
  if (refresh) params.set("refresh", "1");
  return requestJson("/api/character-details?" + params.toString(), {
    signal,
    cache: refresh ? "no-store" : "default"
  });
}

export function postAiAnalysis(name, metrics, history = [], analysisContext = {}, { signal, forceRefresh = false } = {}) {
  const params = new URLSearchParams({ name: String(name || "").trim() });
  const periodMetrics = selectAiMetricsForPeriod(metrics, analysisContext);
  return requestJson("/api/ai-analysis?" + params.toString(), {
    method: "POST",
    body: JSON.stringify({ metrics: periodMetrics, history, analysisContext, forceRefresh }),
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


function responseMessage(html, fallback) {
  try {
    const documentNode = new DOMParser().parseFromString(html, "text/html");
    return documentNode.querySelector(".admin-notice")?.textContent?.trim() || fallback;
  } catch {
    return fallback;
  }
}

export async function getAdminLogs(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
  const response = await requestResponse("/admin/api/logs" + (query.size ? "?" + query.toString() : ""), {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });
  const contentType = response.headers.get("content-type") || "";
  if (response.redirected || !contentType.includes("application/json")) {
    throw new Error("관리자 인증이 필요합니다. 아이디와 비밀번호로 로그인해주세요.");
  }
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "관리자 로그를 불러오지 못했습니다.");
  return payload;
}

export async function loginAdmin(username, password) {
  const loginPage = await requestResponse("/admin/login", { cache: "no-store" });
  if (!loginPage.ok) throw new Error("관리자 로그인 페이지를 불러오지 못했습니다.");
  const html = await loginPage.text();
  const documentNode = new DOMParser().parseFromString(html, "text/html");
  const csrfToken = documentNode.querySelector('input[name="csrf_token"]')?.value;
  if (!csrfToken) throw new Error(responseMessage(html, "CSRF 토큰을 확인할 수 없습니다. 페이지를 새로고침해주세요."));
  const body = new URLSearchParams({ csrf_token: csrfToken, username, password });
  const response = await requestResponse("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    redirect: "follow"
  });
  const resultHtml = await response.text();
  if (!response.ok || !response.redirected || !response.url.endsWith("/admin/logs")) {
    throw new Error(responseMessage(resultHtml, "아이디 또는 비밀번호를 확인해주세요."));
  }
  return getAdminLogs();
}

export async function logoutAdmin(csrfToken) {
  return requestResponse("/admin/logout", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrf_token: csrfToken || "" }).toString(),
    redirect: "follow"
  });
}
