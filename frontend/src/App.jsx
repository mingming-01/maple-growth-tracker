import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCharacter, getHistory } from "./services/api.js";
import AdminDashboard from "./components/admin/AdminDashboard.jsx";
import CharacterOverview from "./features/home/CharacterOverview.jsx";
import FavoriteCharacters from "./features/home/FavoriteCharacters.jsx";
import GrowthHome from "./features/home/GrowthHome.jsx";
import {
  readTrackerState,
  saveTrackerState,
  readFavorites,
  saveFavorites,
  favoriteKey,
  MAX_FAVORITE_CHARACTERS
} from "./lib/storage.js";

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
        historyResult = await getHistory(target,{refresh,ocid:nextCharacter.ocid});
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
      const { default: html2canvas } = await import("html2canvas");
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
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf")
      ]);
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

        <FavoriteCharacters favorites={favorites} current={character} onOpen={item => searchName(item.name)} onRemove={removeFavorite} />

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
              <GrowthHome
                character={character}
                history={history}
                onStatsLoaded={onStatsLoaded}
                onHistoryChange={setHistory}
                onAnalysisPeriodChange={setAnalysisPeriod}
                onPersist={persistPatch}
                analysisPeriod={analysisPeriod}
                comparisonState={comparisonState}
              />
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
