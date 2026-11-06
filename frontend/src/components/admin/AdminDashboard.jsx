import { useCallback, useEffect, useState } from "react";

function responseMessage(html, fallback) {
  try {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const message = doc.querySelector(".admin-notice")?.textContent?.trim();
    return message || fallback;
  } catch {
    return fallback;
  }
}

async function fetchAdminLogs(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([,value]) => value !== undefined && value !== null && value !== "")
  );
  const response = await fetch("/admin/api/logs" + (query.size ? "?" + query.toString() : ""), {
    credentials: "same-origin",
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

async function loginAdmin(username, password) {
  const loginPage = await fetch("/admin/login", {
    credentials: "same-origin",
    cache: "no-store"
  });
  if (!loginPage.ok) throw new Error("관리자 로그인 페이지를 불러오지 못했습니다.");
  const html = await loginPage.text();
  const documentNode = new DOMParser().parseFromString(html, "text/html");
  const csrfToken = documentNode.querySelector('input[name="csrf_token"]')?.value;
  if (!csrfToken) {
    throw new Error(responseMessage(html, "CSRF 토큰을 확인할 수 없습니다. 페이지를 새로고침해주세요."));
  }

  const body = new URLSearchParams({
    csrf_token: csrfToken,
    username,
    password
  });
  const response = await fetch("/admin/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    redirect: "follow"
  });
  const resultHtml = await response.text();
  if (!response.ok || !response.redirected || !response.url.endsWith("/admin/logs")) {
    throw new Error(responseMessage(resultHtml, "아이디 또는 비밀번호를 확인해주세요."));
  }

  return fetchAdminLogs();
}

function ResultBadge({ result }) {
  const successful = result === "성공";
  return <span className={"mgt-admin-result-pill " + (successful ? "is-success" : "is-failure")}>{result || "미확인"}</span>;
}

function AdminLogin({ onSuccess }) {
  const [username,setUsername] = useState("");
  const [password,setPassword] = useState("");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("관리자 아이디와 비밀번호를 입력해주세요.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await loginAdmin(username.trim(),password);
      setPassword("");
      onSuccess(data);
    } catch (requestError) {
      setError(requestError.message || "관리자 로그인을 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mgt-admin-login">
      <span className="mgt-eyebrow">OPERATIONS ACCESS</span>
      <h2>관리자 로그인</h2>
      <p>기존 Flask 세션 인증과 CSRF 보호를 사용합니다. 비밀번호는 브라우저 저장소에 보관하지 않습니다.</p>
      <form onSubmit={submit}>
        <label htmlFor="mgt-admin-username">관리자 아이디</label>
        <input id="mgt-admin-username" value={username} onChange={event=>setUsername(event.target.value)} autoComplete="username" maxLength={100} required />
        <label htmlFor="mgt-admin-password">비밀번호</label>
        <input id="mgt-admin-password" type="password" value={password} onChange={event=>setPassword(event.target.value)} autoComplete="current-password" required />
        <button type="submit" className="search-button" disabled={busy}>{busy ? "인증 중..." : "로그인"}</button>
      </form>
      {error && <p className="mgt-admin-error" role="alert">{error}</p>}
    </section>
  );
}

function AdminLogTable({ logs }) {
  return (
    <div className="mgt-admin-table-wrap">
      <table className="mgt-admin-table">
        <thead>
          <tr>
            <th>시간 (KST)</th><th>행동 / 경로</th><th>캐릭터</th><th>비교 대상</th><th>결과</th><th>HTTP / 시간</th><th>오류 분류</th>
          </tr>
        </thead>
        <tbody>
          {logs.length ? logs.map((item,index) => (
            <tr key={String(item.created_at)+String(item.action)+index}>
              <td className="mgt-admin-time">{item.created_at_display || "—"}</td>
              <td><strong>{item.action || "—"}</strong><small>{item.path || "—"}</small></td>
              <td>{item.character_name || "—"}{item.world_name && <small>{item.world_name}</small>}</td>
              <td>{item.comparison_name || "—"}</td>
              <td><ResultBadge result={item.result} /></td>
              <td>{item.status_code ? "HTTP "+item.status_code : "HTTP —"}<small>{item.duration_ms == null ? "—" : item.duration_ms+" ms"}</small></td>
              <td>{item.error_type || "—"}</td>
            </tr>
          )) : <tr><td colSpan={7} className="mgt-admin-empty">조건에 맞는 로그가 없습니다.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function AdminLogs({ initialData, onLogout }) {
  const [data,setData] = useState(initialData);
  const [query,setQuery] = useState("");
  const [action,setAction] = useState("");
  const [result,setResult] = useState("");
  const [dateFrom,setDateFrom] = useState("");
  const [dateTo,setDateTo] = useState("");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");

  const refresh = useCallback(async (filters = {}) => {
    setBusy(true);
    setError("");
    try {
      const next = await fetchAdminLogs(filters);
      setData(next);
    } catch (requestError) {
      if (requestError.message.includes("인증이 필요합니다")) onLogout();
      else setError(requestError.message || "로그를 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  },[onLogout]);

  async function submit(event) {
    event.preventDefault();
    await refresh({q:query,action,result,date_from:dateFrom,date_to:dateTo});
  }

  async function logout() {
    const body = new URLSearchParams({csrf_token:data.csrfToken || ""});
    setBusy(true);
    try {
      await fetch("/admin/logout",{
        method:"POST",
        credentials:"same-origin",
        headers:{"Content-Type":"application/x-www-form-urlencoded"},
        body:body.toString(),
        redirect:"follow"
      });
    } finally {
      setBusy(false);
      onLogout();
    }
  }

  return (
    <div className="mgt-admin-dashboard">
      <div className="mgt-admin-header">
        <div><span className="mgt-eyebrow">MAPLE GROWTH TRACKER / OPERATIONS</span><h2>관리자 로그</h2><p>조회·분석 활동과 API 응답 상태를 확인합니다.</p></div>
        <div className="mgt-admin-header-actions">
          <button type="button" className="export-button" onClick={() => refresh({q:query,action,result,date_from:dateFrom,date_to:dateTo})} disabled={busy}>새로고침</button>
          <button type="button" className="export-button" onClick={logout} disabled={busy}>로그아웃</button>
        </div>
      </div>

      <section className="mgt-admin-overview">
        <div><span className="mgt-eyebrow">LOG STORAGE</span><strong>{data.storageBackend === "postgres" ? "PostgreSQL" : "SQLite"} 로그 저장소</strong><small>{data.storageBackend === "postgres" && !data.storageWarning ? "영구 저장소 연결" : "재배포 후 기록이 사라질 수 있음"}</small></div>
        <div><span className="mgt-eyebrow">SNAPSHOT STORAGE</span><strong>{String(data.snapshotStorageBackend || "unknown").toUpperCase()}</strong><small>캐릭터 데이터 스냅샷 저장소</small></div>
        <div><span className="mgt-eyebrow">TOTAL LOGS</span><strong>{Number(data.totalCount || 0).toLocaleString("ko-KR")}</strong><small>검색 결과 {data.displayedCount} / 전체 {data.totalCount}건</small></div>
      </section>

      {(data.storageWarning || data.snapshotStorageWarning) && (
        <p className="mgt-admin-warning" role="status">{[data.storageWarning,data.snapshotStorageWarning].filter(Boolean).join(" ")}</p>
      )}
      <section className="mgt-admin-filter">
        <div><h3>로그 검색</h3><p>캐릭터명, 행동, 경로, HTTP 상태 또는 오류 분류를 검색합니다.</p></div>
        <form onSubmit={submit}>
          <label>검색어<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="캐릭터명 또는 오류 검색" /></label>
          <label>행동<select value={action} onChange={event=>setAction(event.target.value)}><option value="">모든 행동</option>{data.actionOptions.map(value=><option key={value} value={value}>{value}</option>)}</select></label>
          <label>결과<select value={result} onChange={event=>setResult(event.target.value)}><option value="">전체 결과</option><option value="성공">성공</option><option value="실패">실패</option></select></label>
          <label>시작일 (한국 시간)<input type="date" value={dateFrom} onChange={event=>setDateFrom(event.target.value)} /></label>
          <label>종료일 (한국 시간)<input type="date" value={dateTo} onChange={event=>setDateTo(event.target.value)} /></label>
          <div className="mgt-admin-filter-actions"><button className="search-button" type="submit" disabled={busy}>검색</button><button className="export-button" type="button" onClick={()=>{setQuery("");setAction("");setResult("");setDateFrom("");setDateTo("");refresh({});}} disabled={busy}>초기화</button></div>
        </form>
      </section>
      {error && <p className="mgt-admin-error" role="alert">{error}</p>}
      {busy && <p className="mgt-admin-loading" role="status">로그를 불러오고 있습니다...</p>}
      {!busy && <AdminLogTable logs={data.logs || []} />}
      {(data.totalCount || 0) > 500 && <p className="mgt-admin-note">검색 결과가 500건을 초과해 최신 500건만 표시합니다. 필터를 추가해 범위를 좁혀보세요.</p>}
    </div>
  );
}

export default function AdminDashboard({ onBack }) {
  const [data,setData] = useState(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState("");
  const [authenticated,setAuthenticated] = useState(false);

  const onLogout = useCallback(() => {
    setAuthenticated(false);
    setData(null);
    setError("");
  },[]);

  useEffect(() => {
    let cancelled = false;
    fetchAdminLogs()
      .then(result => {
        if (!cancelled) {
          setData(result);
          setAuthenticated(true);
        }
      })
      .catch(requestError => {
        if (!cancelled) {
          setAuthenticated(false);
          if (!requestError.message.includes("인증이 필요합니다")) setError(requestError.message);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  },[]);

  return (
    <section className="mgt-admin-root">
      <div className="mgt-admin-back-row">
        <button type="button" className="export-button" onClick={onBack}>← 대시보드로 돌아가기</button>
      </div>
      {loading ? <div className="mgt-loading" role="status"><span /> 관리자 세션을 확인하고 있습니다.</div>
        : authenticated && data ? <AdminLogs initialData={data} onLogout={onLogout} />
        : <AdminLogin onSuccess={result=>{setData(result);setAuthenticated(true);setError("");}} />}
      {error && !authenticated && <p className="mgt-admin-error" role="alert">{error}</p>}
    </section>
  );
}