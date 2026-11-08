import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import { getCharacter, getHistory } from "./services/api.js";
import CharacterDetails from "./components/character/CharacterDetails.jsx";
import AdminDashboard from "./components/admin/AdminDashboard.jsx";
import GrowthDashboard from "./features/growth/GrowthDashboard.jsx";
import { AIReport, GrowthComparison } from "./features/analytics/AnalyticsAndComparison.jsx";
import {
  readTrackerState,
  saveTrackerState,
  readFavorites,
  saveFavorites,
  favoriteKey,
  readGrowthGoals,
  MAX_FAVORITE_CHARACTERS
} from "./lib/storage.js";
import {
  calculateAverageGrowth,
  calculateLevelProgress,
  sortHistoryAscending
} from "./lib/growth.js";

const WORLD_LOGOS = {
  "스카니아":"/static/images/worlds/SCANIA.PNG",
  "베라":"/static/images/worlds/BERA.PNG",
  "루나":"/static/images/worlds/LUNA.png",
  "제니스":"/static/images/worlds/ZENITH.png",
  "크로아":"/static/images/worlds/CROA.png",
  "유니온":"/static/images/worlds/UNION.png",
  "엘리시움":"/static/images/worlds/ELYSIUM.png",
  "이노시스":"/static/images/worlds/ENOSIS.png",
  "레드":"/static/images/worlds/RED.png",
  "오로라":"/static/images/worlds/AURORA.PNG",
  "아케인":"/static/images/worlds/ARCANE.png",
  "노바":"/static/images/worlds/NOVA.png",
  "에오스":"/static/images/worlds/EOS.png",
  "헬리오스":"/static/images/worlds/HELIOS.png",
  "챌린저스":"/static/images/worlds/CHALLENGERS.png"
};

function formatNumber(value) {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("ko-KR");
}

function formatRate(value) {
  const number = Number(String(value ?? "").replace("%",""));
  return Number.isFinite(number) && number >= 0 && number <= 100 ? number : null;
}

function rankingFallback(status, label) {
  if (status === "not_ready") return "당일 집계 전";
  if (status === "unavailable") return "조회 실패";
  if (status === "partial") return "일부 조회 실패";
  if (status === "empty") return "최근 집계자료 없음";
  return label || "랭킹 자료 없음";
}

function RankingItem({ label, value, status }) {
  return (
    <div className="ranking-item">
      <span>{label}</span>
      <strong>{value === null || value === undefined || value === "" ? rankingFallback(status) : formatNumber(value) + "위"}</strong>
      {value === null || value === undefined || value === "" ? <small>현재 순위 미확인</small> : <small>Nexon 랭킹 API</small>}
    </div>
  );
}

function RankingStatus({ character }) {
  const status = character.rankingDataStatus;
  const rankingDate = character.rankingDate
    ? new Date(character.rankingDate + "T00:00:00+09:00").toLocaleDateString("ko-KR")
    : "";
  const dateNote = rankingDate ? " 집계 기준일 · " + rankingDate + "." : "";
  const warnings = Array.isArray(character.rankingWarnings) ? character.rankingWarnings : [];

  if (status === "available" && [character.ranking,character.worldRanking,character.jobWorldRanking,character.jobRanking].some(value => value !== null && value !== undefined)) {
    return <p className="mgt-ranking-status is-success">Nexon 공개 랭킹 데이터입니다.{dateNote}</p>;
  }

  const message = status === "not_ready"
    ? "오늘 날짜의 랭킹 집계가 아직 준비되지 않았습니다. 잠시 후 최신 정보 다시 조회를 눌러 확인해주세요."
    : status === "unavailable"
      ? "Nexon 랭킹 API 요청에 실패했습니다. 캐릭터 기본 정보는 정상 조회됐으며, 최신 정보 다시 조회로 재시도할 수 있습니다."
      : status === "partial"
        ? "일부 랭킹만 확인됐습니다. 확인된 순위만 표시하고 누락된 값은 임의로 채우지 않았습니다."
        : status === "empty"
          ? "최근 3일의 공개 랭킹 응답에 이 캐릭터의 순위가 없습니다. 집계 대상 외 캐릭터이거나 랭킹 데이터가 아직 제공되지 않았을 수 있습니다."
          : "현재 응답에서 랭킹을 확인하지 못했습니다. 최신 정보 다시 조회를 눌러 다시 확인해주세요.";

  return (
    <div className="mgt-ranking-status is-warning" role="status">
      <p>{message}{dateNote}</p>
      {warnings.length > 0 && <small>{warnings.join(" ")}</small>}
      {character.rankingApiDiagnostics && Object.keys(character.rankingApiDiagnostics).length > 0 && (
        <details className="mgt-ranking-diagnostics">
          <summary>랭킹 API 응답 상세</summary>
          <div>
            {Object.entries(character.rankingApiDiagnostics).map(([key, item]) => (
              <span key={key}>
                {({ranking:"종합",worldRanking:"월드",jobWorldRanking:"직업·월드",jobRanking:"직업"})[key] || key}
                {" · HTTP "}{item.statusCode ?? "응답 없음"}
                {" · 항목 "}{item.returnedEntries ?? "확인 불가"}건
                {item.errorCode ? " · " + item.errorCode : ""}
                {item.errorMessage ? " · " + item.errorMessage : ""}
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function CharacterProfile({ character, history }) {
  const rate = formatRate(character.experienceRate);
  const weeklyHistory = sortHistoryAscending(history || []).slice(-7);
  const average = calculateAverageGrowth(weeklyHistory);
  const progress = calculateLevelProgress(character,average);
  const logo = WORLD_LOGOS[character.worldName];
  return (
    <section className="mgt-profile-shell" aria-label="캐릭터 프로필">
      <div className="mgt-profile-main">
        <div className="mgt-character-identity">
          <div className="mgt-character-avatar-frame">
            {character.character_image
              ? <img className="mgt-character-avatar" src={character.character_image}
                  alt={character.characterName + " 캐릭터 아바타"}
                  referrerPolicy="no-referrer" />
              : <span className="mgt-avatar-fallback">M</span>}
          </div>
          <div className="mgt-character-copy">
            <span className="mgt-eyebrow">CHARACTER PROFILE</span>
            <h2>{character.characterName || "이름 정보 없음"}</h2>
            <div className="mgt-character-meta">
              {logo && <img src={logo} alt="" className="mgt-world-logo" />}
              <span>{character.worldName || "월드 정보 없음"}</span>
              <span>Lv. {formatNumber(character.level)}</span>
              <span>{character.job || "직업 정보 없음"}</span>
              <span>{character.guildName || "길드 없음"}</span>
            </div>
          </div>
        </div>
        <div className="mgt-profile-progress">
          <div className="mgt-progress-top">
            <div><span className="mgt-stat-label">현재 레벨 진행률</span><strong>{rate === null ? "자료 부족" : rate.toFixed(3)+"%"}</strong></div>
            <span className="mgt-progress-remaining">{rate === null ? "경험치 진행률 미제공" : "다음 레벨까지 "+(100-rate).toFixed(3)+"%"}</span>
          </div>
          <div className="mgt-exp-track" role="progressbar" aria-label="현재 레벨 경험치 진행률"
            aria-valuemin="0" aria-valuemax="100" aria-valuenow={rate ?? 0}>
            <span className="mgt-exp-fill" style={{width:(rate ?? 0)+"%"}} />
          </div>
          <p className="mgt-progress-note">
            {progress?.dailyProgressRate != null
              ? "최근 관측 평균 +" + progress.dailyProgressRate.toFixed(4) + "%p / 일"
              : "성장 기록이 쌓이면 실제 관측 경험치를 이용해 일일 진척률을 계산합니다."}
          </p>
        </div>
      </div>
      <div className="mgt-profile-side">
        <div className="mgt-eyebrow">CHARACTER SNAPSHOT</div>
        <div className="mgt-snapshot-stat"><span>현재 경험치</span><strong>{formatNumber(character.experience)}</strong></div>
        <div className="mgt-snapshot-stat"><span>주간 일일 평균 경험치</span><strong>{average === null ? "자료 부족" : formatTrillion(average)}</strong></div>
        <div className="mgt-snapshot-stat" data-testid="profile-combat-power">
          <span>전투력</span><strong>{character.currentCombatPower == null ? "상세 정보 조회 대기" : formatNumber(character.currentCombatPower)}</strong>
        </div>
      </div>
      <div className="mgt-ranking-panel">
        <div className="mgt-ranking-heading">
          <div><span className="mgt-eyebrow">RANKING</span><h3>캐릭터 랭킹</h3></div>
          <span>공개 랭킹 API</span>
        </div>
        <div className="mgt-ranking-grid">
          <RankingItem label="종합 랭킹" value={character.ranking} status={character.rankingDataStatus} />
          <RankingItem label="월드 랭킹" value={character.worldRanking} status={character.rankingDataStatus} />
          <RankingItem label="직업 · 월드" value={character.jobWorldRanking} status={character.rankingDataStatus} />
          <RankingItem label="직업 전체" value={character.jobRanking} status={character.rankingDataStatus} />
        </div>
        <RankingStatus character={character} />
      </div>
    </section>
  );
}

function formatTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const n = Number(value) / 1_000_000_000_000;
  return (Math.abs(n) >= 100 ? n.toFixed(0) : Math.abs(n) >= 10 ? n.toFixed(1) : n.toFixed(2)) + "조";
}

function FavoritesPanel({ favorites, current, onOpen, onRemove }) {
  return (
    <section className="mgt-favorites-panel">
      <div className="mgt-section-heading">
        <div><span className="mgt-eyebrow">FAVORITES</span><h2>관심 캐릭터</h2></div>
        <span>{favorites.length} / {MAX_FAVORITE_CHARACTERS}명</span>
      </div>
      {favorites.length ? (
        <div className="mgt-favorites-list">
          {favorites.map(item => {
            const goal = item.ocid ? readGrowthGoals()[item.ocid] : null;
            return (
              <article className="mgt-favorite-card" key={favoriteKey(item)}>
                <button type="button" className="mgt-favorite-open" onClick={() => onOpen(item)}>
                  <span className="mgt-favorite-star">★</span>
                  <span className="mgt-favorite-details">
                    <strong>{item.name}</strong>
                    <small>{item.worldName || "월드 정보 없음"}</small>
                    {goal && <small className="mgt-favorite-goal">{goal.completedAt ? `목표 Lv.${goal.targetLevel} 달성` : `목표 Lv.${goal.targetLevel}`}</small>}
                  </span>
                </button>
                <button type="button" className="mgt-favorite-remove" aria-label={item.name+" 관심 목록에서 제거"} onClick={() => onRemove(item)}>×</button>
              </article>
            );
          })}
        </div>
      ) : <p className="mgt-favorites-empty">관심 캐릭터를 등록하면 이곳에서 빠르게 다시 조회할 수 있습니다.</p>}
      {current && <p className="mgt-favorites-note">관심 캐릭터 목록은 기존 브라우저 저장 데이터와 공유됩니다.</p>}
    </section>
  );
}

function App() {
  const restored = useMemo(() => readTrackerState(), []);
  const [name,setName] = useState(restored?.character?.characterName || "");
  const [character,setCharacter] = useState(restored?.character || null);
  const [history,setHistory] = useState(Array.isArray(restored?.history) ? restored.history : []);
  const [analysisPeriod,setAnalysisPeriod] = useState(() => ({ days:[7,30,90].includes(Number(restored?.historyRange)) ? Number(restored.historyRange) : 7, history:Array.isArray(restored?.displayHistory) ? restored.displayHistory : (Array.isArray(restored?.history) ? restored.history : []), summary:restored?.periodSummary || null }));
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  const [historyWarning,setHistoryWarning] = useState("");
  const [lastSearched,setLastSearched] = useState("");
  const [favorites,setFavorites] = useState(() => readFavorites());
  const [favoriteFeedback,setFavoriteFeedback] = useState("");
  const [exporting,setExporting] = useState("");
  const [shareOpen,setShareOpen] = useState(false);
  const [view,setView] = useState(() => window.location.hash === "#admin" ? "admin" : "dashboard");
  const [comparisonState,setComparisonState] = useState(restored?.comparison || null);
  const resultRef = useRef(null);

  useEffect(() => {
    const syncView = () => setView(window.location.hash === "#admin" ? "admin" : "dashboard");
    window.addEventListener("hashchange",syncView);
    return () => window.removeEventListener("hashchange",syncView);
  },[]);

  useEffect(() => {
    if (!shareOpen) return undefined;
    const closeOnOutsideClick = event => {
      if (!event.target?.closest?.(".mgt-share-menu-wrap")) setShareOpen(false);
    };
    const closeOnEscape = event => {
      if (event.key === "Escape") setShareOpen(false);
    };
    document.addEventListener("pointerdown",closeOnOutsideClick);
    document.addEventListener("keydown",closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown",closeOnOutsideClick);
      document.removeEventListener("keydown",closeOnEscape);
    };
  },[shareOpen]);

  const isFavorite = useMemo(() => {
    if (!character) return false;
    const current = {ocid:String(character.ocid || ""),name:character.characterName,worldName:character.worldName || ""};
    return favorites.some(item => favoriteKey(item) === favoriteKey(current));
  },[favorites,character]);

  useEffect(() => {
    if (!character) return;
    saveTrackerState({character,history});
  },[character,history]);

  const persistPatch = useCallback(patch => {
    saveTrackerState(patch);
    if (Object.prototype.hasOwnProperty.call(patch || {}, "comparison")) {
      setComparisonState(patch.comparison || null);
    }
  },[]);

  function openAdmin(event) {
    event?.preventDefault?.();
    if (window.location.hash !== "#admin") window.location.hash = "admin";
    setView("admin");
  }

  function closeAdmin() {
    window.history.replaceState(null,"",window.location.pathname + window.location.search);
    setView("dashboard");
  }

  const onStatsLoaded = useCallback(data => {
    setCharacter(previous => {
      if (!previous) return previous;
      const statSource = Array.isArray(data?.sources)
        ? data.sources.find(source => source?.id === "stat")
        : null;
      const currentCombatPower = statSource?.combatPower ?? data?.combatPower ?? null;
      const next = {
        ...previous,
        currentCombatPower: currentCombatPower ?? previous.currentCombatPower ?? null
      };
      saveTrackerState({character:next});
      return next;
    });
  },[]);

  async function searchName(query, { refresh = false } = {}) {
    const target = String(query || "").trim();
    if (!target || loading) return;
    setName(target);
    setLoading(true);
    setError("");
    setHistoryWarning("");
    setLastSearched("");
    try {
      const nextCharacter = await getCharacter(target,{refresh});
      let historyResult;
      try {
        historyResult = await getHistory(target,{refresh});
      } catch (historyError) {
        historyResult = {history:[],dataStatus:"unavailable",historyStatus:"unavailable"};
        setHistoryWarning(historyError.message || "성장 기록을 조회하지 못했습니다. 캐릭터 기본 정보는 표시합니다.");
      }
      const records = Array.isArray(historyResult.history) ? historyResult.history : [];
      nextCharacter.historyStatus = historyResult.historyStatus || null;
      nextCharacter.historyDataStatus = historyResult.dataStatus || null;
      nextCharacter.historyDataAsOf = historyResult.dataAsOf || null;
      nextCharacter.historyStorage = historyResult.historyStorage || null;
      setCharacter(nextCharacter);
      setHistory(records);
      setAnalysisPeriod({days:7,history:records,summary:null});
      setComparisonState(null);
      setLastSearched(new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"}));
      saveTrackerState({
        character:nextCharacter,
        history:records,
        aiAnalysis:null,
        aiInsights:null,
        comparison:null,
        historyRange:7,
        displayHistory:records,
        historyRangeStatus:null,
        periodSummary:null
      });
    } catch (requestError) {
      setError(requestError.message || "캐릭터 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(event) {
    event.preventDefault();
    await searchName(name);
  }

  async function refreshCurrent() {
    if (character?.characterName) await searchName(character.characterName,{refresh:true});
  }

  function toggleFavorite() {
    if (!character) return;
    const current = {
      ocid:String(character.ocid || ""),
      name:character.characterName,
      worldName:character.worldName || ""
    };
    const exists = favorites.some(item => favoriteKey(item) === favoriteKey(current));
    const next = exists
      ? favorites.filter(item => favoriteKey(item) !== favoriteKey(current))
      : [current,...favorites].slice(0,MAX_FAVORITE_CHARACTERS);
    if (!exists && favorites.length >= MAX_FAVORITE_CHARACTERS) {
      setFavoriteFeedback(`관심 캐릭터는 최대 ${MAX_FAVORITE_CHARACTERS}명까지 저장할 수 있습니다.`);
      return;
    }
    if (!saveFavorites(next)) {
      setFavoriteFeedback("브라우저 저장소를 사용할 수 없어 관심 캐릭터를 저장하지 못했습니다.");
      return;
    }
    setFavorites(next);
    setFavoriteFeedback(exists ? `${current.name} 캐릭터를 관심 목록에서 제거했습니다.` : `${current.name} 캐릭터를 관심 목록에 저장했습니다.`);
  }

  function removeFavorite(item) {
    const next = favorites.filter(saved => favoriteKey(saved) !== favoriteKey(item));
    if (!saveFavorites(next)) {
      setFavoriteFeedback("관심 캐릭터를 제거하지 못했습니다.");
      return;
    }
    setFavorites(next);
    setFavoriteFeedback(item.name+" 캐릭터를 관심 목록에서 제거했습니다.");
  }

  async function exportImage() {
    if (!resultRef.current) return;
    setExporting("image");
    try {
      const canvas = await html2canvas(resultRef.current,{
        backgroundColor:"#10101a",
        scale:2,
        useCORS:true,
        ignoreElements:element => element.dataset?.exportIgnore === "true"
      });
      const link = document.createElement("a");
      link.download = "maple-growth-"+(character?.characterName || "character")+".png";
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch (exportError) {
      setError(exportError.message || "이미지 저장 중 오류가 발생했습니다.");
    } finally {
      setExporting("");
    }
  }

  async function exportPdf() {
    if (!resultRef.current) return;
    setExporting("pdf");
    try {
      const canvas = await html2canvas(resultRef.current,{
        backgroundColor:"#10101a",
        scale:2,
        useCORS:true,
        ignoreElements:element => element.dataset?.exportIgnore === "true"
      });
      const imageData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({orientation:"portrait",unit:"mm",format:"a4"});
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 10;
      const availableWidth = pageWidth - margin * 2;
      const imageHeight = canvas.height * availableWidth / canvas.width;
      let heightLeft = imageHeight;
      let position = margin;
      pdf.addImage(imageData,"PNG",margin,position,availableWidth,imageHeight);
      heightLeft -= pageHeight - margin * 2;
      while (heightLeft > 0) {
        position = -(imageHeight - heightLeft) + margin;
        pdf.addPage();
        pdf.addImage(imageData,"PNG",margin,position,availableWidth,imageHeight);
        heightLeft -= pageHeight - margin * 2;
      }
      pdf.save("maple-growth-"+(character?.characterName || "character")+".pdf");
    } catch (exportError) {
      setError(exportError.message || "PDF 저장 중 오류가 발생했습니다.");
    } finally {
      setExporting("");
    }
  }

  return (
    <div className="mgt-app-shell" data-testid="react-preview-ready">
      <header className="mgt-topbar">
        <a className="mgt-brand" href="/" aria-label="Maple Growth Tracker 메인">
          <span className="mgt-brand-mark">M</span>
          <span>MAPLE <b>GROWTH</b></span>
        </a>
        <nav className="mgt-nav" aria-label="주요 메뉴">
          {view === "dashboard" ? <>
            <a href="#character">캐릭터</a>
            <a href="#details">스펙</a>
            <a href="#growth">성장 기록</a>
            <a href="#analytics">AI 분석</a>
          </> : <a href="#dashboard" onClick={event=>{event.preventDefault();closeAdmin();}}>대시보드</a>}
          <a href="#admin" onClick={openAdmin}>관리자</a>
        </nav>
      </header>

      <main className="mgt-page-content">
        {view === "admin" ? <AdminDashboard onBack={closeAdmin} /> : <>
        <section className="mgt-hero">
          <div>
            <div className="mgt-hero-label"><span /> CHARACTER GROWTH DASHBOARD</div>
            <h1>모험가의 성장을<br /><em>기록하고 분석하다.</em></h1>
            <p>Nexon Open API 기반의 캐릭터 정보, 성장 통계, 스펙과 프리셋을 하나의 대시보드에서 확인하세요.</p>
          </div>
          <div className="mgt-hero-ornament" aria-hidden="true">
            <span className="mgt-orbit mgt-orbit-one" />
            <span className="mgt-orbit mgt-orbit-two" />
            <span className="mgt-orbit-core">M</span>
            <i>✦</i><b>✧</b>
          </div>
        </section>

        <FavoritesPanel favorites={favorites} current={character} onOpen={item => searchName(item.name)} onRemove={removeFavorite} />

        <section className="mgt-search-panel" aria-labelledby="mgt-search-title">
          <div className="mgt-search-heading">
            <div><span className="mgt-eyebrow">CHARACTER SEARCH</span><h2 id="mgt-search-title">모험가 찾기</h2></div>
            <span className="mgt-api-indicator"><i /> NEXON OPEN API</span>
          </div>
          <form className="mgt-search-form" onSubmit={handleSearch} data-testid="react-character-search">
            <label className="sr-only" htmlFor="react-character-name">캐릭터명</label>
            <input id="react-character-name" value={name} onChange={event=>setName(event.target.value)}
              placeholder="조회할 캐릭터명을 입력하세요" autoComplete="off" maxLength={30} />
            <button type="submit" disabled={loading || !name.trim()}>{loading ? "조회 중..." : "캐릭터 조회"} <span>→</span></button>
          </form>
          <div className="mgt-search-footnote">넥슨 Open API에서 최신 공개 데이터를 다시 조회합니다.</div>
          {error && <p className="mgt-error" role="alert">{error}</p>}
          {favoriteFeedback && <p className="mgt-feedback" role="status">{favoriteFeedback}</p>}
          {historyWarning && <p className="mgt-warning" role="status">{historyWarning}</p>}
        </section>

        {loading && <div className="mgt-loading" role="status"><span /> 캐릭터 정보를 불러오고 있습니다.</div>}

        {character && (
          <>
            <div className="mgt-result-toolbar">
              <span><i /> 조회 완료{lastSearched ? " · "+lastSearched : ""}</span>
              <div className="mgt-export-actions" data-export-ignore="true">
                <button type="button"
                  className={"mgt-icon-action mgt-favorite-icon-button " + (isFavorite ? "is-saved" : "")}
                  onClick={toggleFavorite} aria-pressed={isFavorite}
                  aria-label={isFavorite ? "관심 캐릭터 해제" : "관심 캐릭터 등록"}
                  title={isFavorite ? "관심 캐릭터 해제" : "관심 캐릭터 등록"}>
                  <span aria-hidden="true">{isFavorite ? "★" : "☆"}</span>
                </button>
                <button type="button" className="mgt-icon-action" onClick={refreshCurrent}
                  disabled={loading} aria-label="최신 정보 다시 조회" title="최신 정보 다시 조회">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M20 7v5h-5M4 17v-5h5" />
                    <path d="M6.2 9A7 7 0 0 1 18 6.5L20 12M4 12l2 5.5A7 7 0 0 0 17.8 15" />
                  </svg>
                </button>
                <div className="mgt-share-menu-wrap">
                  <button type="button" className="mgt-icon-action" onClick={() => setShareOpen(open => !open)}
                    aria-label="공유" aria-haspopup="menu" aria-expanded={shareOpen} title="공유">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                      <path d="m8.7 10.7 6.6-4.4M8.7 13.3l6.6 4.4" />
                    </svg>
                  </button>
                  {shareOpen && (
                    <div className="mgt-share-menu" role="menu" aria-label="공유 및 저장">
                      <button type="button" role="menuitem" onClick={() => { setShareOpen(false); exportImage(); }} disabled={!!exporting}>
                        <span aria-hidden="true">▧</span> {exporting === "image" ? "이미지 저장 중..." : "이미지 저장"}
                      </button>
                      <button type="button" role="menuitem" onClick={() => { setShareOpen(false); exportPdf(); }} disabled={!!exporting}>
                        <span aria-hidden="true">▤</span> {exporting === "pdf" ? "PDF 생성 중..." : "PDF 저장"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div ref={resultRef} className="mgt-result-content">
              <div id="character">
                <CharacterProfile character={character} history={history} />
              </div>
              <div id="details">
                <CharacterDetails ocid={character.ocid} onStatsLoaded={onStatsLoaded} />
              </div>
              <div id="growth">
                <GrowthDashboard character={character} history={history} onHistoryChange={setHistory} onAnalysisPeriodChange={setAnalysisPeriod} onPersist={persistPatch} />
              </div>
              <div id="analytics">
                <AIReport character={character} history={history} analysisHistory={analysisPeriod.history || history} periodDays={analysisPeriod.days} periodSummary={analysisPeriod.summary} />
                <GrowthComparison
                  character={character}
                  history={history}
                  initialState={comparisonState}
                  onSave={persistPatch}
                />
              </div>
            </div>
          </>
        )}

        {!character && !loading && (
          <section className="mgt-empty-state">
            <span className="mgt-empty-emblem">✧</span>
            <span className="mgt-eyebrow">YOUR ADVENTURE LOG</span>
            <h2>성장 기록을 시작해 보세요.</h2>
            <p>캐릭터를 조회하면 프로필, 실시간 공개 랭킹, 장비·능력치, 성장 기록과 AI 분석이 표시됩니다.</p>
          </section>
        )}

        </>}
        <footer className="mgt-footer">
          <span>MAPLE GROWTH TRACKER</span>
          <span>Powered by NEXON Open API · Flask · React</span>
          <a href="/admin/login">레거시 관리자 로그인</a>
        </footer>
      </main>
    </div>
  );
}

export default App;