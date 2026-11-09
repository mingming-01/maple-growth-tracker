import { useCallback, useEffect, useMemo, useState } from "react";
import { getCharacter, getHistory, getHistoryArchive, postAiAnalysis, postAiComparison } from "../../services/api.js";
import {
  calculatePrediction,
  calculateGrowthMetrics,
  calculateLevelProgress,
  calculateAverageGrowth,
  calculateWeeklyGrowth,
  getDailyGrowth,
  getRankingChange,
  sortHistoryAscending
} from "../../lib/growth.js";
import { getCachedAI, saveCachedAI, stableStringify } from "../../lib/storage.js";

function formatNumber(value) {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "자료 부족";
  return Number(value).toLocaleString("ko-KR");
}

function formatTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const n = Number(value) / 1_000_000_000_000;
  return (Math.abs(n) >= 100 ? n.toFixed(0) : Math.abs(n) >= 10 ? n.toFixed(1) : n.toFixed(2)) + "조";
}

function signedTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const n = Number(value);
  return (n > 0 ? "+" : n < 0 ? "−" : "") + formatTrillion(Math.abs(n));
}

function parseAnalysis(analysis) {
  const sections = {
    growthPattern: "",
    growthChange: "",
    levelUp: "",
    growthOutlook: "",
    judgement: ""
  };
  const aliases = new Map([
    ["성장 패턴", "growthPattern"],
    ["성장 변화", "growthChange"],
    ["성장 분석", "growthChange"],
    ["레벨업 분석", "levelUp"],
    ["레벨업", "levelUp"],
    ["성장 전망", "growthOutlook"],
    ["AI 코멘트", "judgement"],
    ["AI 판단", "judgement"]
  ]);
  const source = String(analysis || "");
  const headings = Array.from(source.matchAll(/\[([^\]]+)\]/g));

  if (!headings.length) {
    if (source.trim()) sections.judgement = source.trim();
    return sections;
  }

  headings.forEach((match, index) => {
    const key = aliases.get(String(match[1] || "").trim());
    if (!key) return;
    const bodyStart = match.index + match[0].length;
    const bodyEnd = headings[index + 1]?.index ?? source.length;
    const body = source.slice(bodyStart, bodyEnd).trim();
    if (body) sections[key] = body;
  });

  return sections;
}

function buildReportSignature(character, history, metrics, analysisContext = {}) {
  return stableStringify({
    name:character.characterName,
    ocid:character.ocid,
    level:character.level,
    experience:character.experience,
    experienceRate:character.experienceRate,
    ranking:character.ranking,
    history,
    metrics,
    analysisContext
  });
}


export function AIReport({ character, history, analysisHistory = history, periodDays = 7, periodSummary = null, onPeriodSelect }) {
  const [analysis,setAnalysis] = useState("");
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const [periodChanging,setPeriodChanging] = useState(false);

  const metrics = useMemo(() => {
    const prediction = calculatePrediction(character,history || []);
    return calculateGrowthMetrics(character,history || [],prediction);
  },[character,history]);

  const run = useCallback(async ({ force = false, allowGenerate = true } = {}) => {
    if (!character?.characterName || !Array.isArray(history) || !Array.isArray(analysisHistory)) return;
    setLoading(true);
    setError("");
    const analysisContext = { periodDays:[7,30,90].includes(Number(periodDays)) ? Number(periodDays) : 7, periodSummary:periodSummary || null };
    // 분석에 실제 전달되는 캐릭터·기록·지표·기간 요약 전체를 캐시 키에 포함한다.
    // 캐시 버전을 올려 과거에 기간/캐릭터만으로 저장된 장기 리포트를 재사용하지 않는다.
    const signature = stableStringify({
      // 캐시 키는 실제 분석 요청에 영향을 주는 값만 사용한다.
      // CharacterDetails가 비동기로 추가하는 전투력 등 분석 입력이 아닌 필드는 제외한다.
      cacheVersion: 3,
      characterName: character.characterName,
      history: analysisHistory,
      metrics,
      analysisContext
    });
    const cacheType = analysisContext.periodDays > 7 ? "growth-report-long-v2" : "growth-report-v4";
    const cached = !force ? getCachedAI(cacheType,signature) : null;
    if (cached?.analysis) {
      setAnalysis(cached.analysis);
      setNotice(analysisContext.periodDays > 7 ? `최근 ${analysisContext.periodDays}일 분석의 저장 결과를 재사용했습니다.` : "");
      setLoading(false);
      return;
    }
    if (!allowGenerate && !force) {
      setAnalysis("");
      setNotice(`최근 ${analysisContext.periodDays}일 분석의 저장 결과가 없습니다. 새 분석은 'AI 다시 분석'을 눌렀을 때만 생성됩니다.`);
      setLoading(false);
      return;
    }
    setNotice("");
    try {
      const result = await postAiAnalysis(character.characterName,metrics,analysisHistory,analysisContext,{forceRefresh:force});
      if (!result.analysis) throw new Error("AI 분석 결과가 비어 있습니다.");
      setAnalysis(result.analysis);
      setNotice("");
      saveCachedAI(cacheType,signature,result.analysis,result.growthInsights || null);
    } catch (requestError) {
      setError(requestError.message || "AI 성장 분석을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  },[character,history,analysisHistory,metrics,periodDays,periodSummary]);

  useEffect(() => {
    setAnalysis("");
    setError("");
    // 모든 기간은 저장된 캐시만 확인한다. AI 요청은 사용자가 버튼을 눌렀을 때만 실행한다.
    run({ allowGenerate: false });
  },[run,periodDays]);

  async function handlePeriodChange(event) {
    const nextDays = Number(event.target.value);
    if (!onPeriodSelect || nextDays === Number(periodDays)) return;
    setPeriodChanging(true);
    setError("");
    setNotice(`최근 ${nextDays}일 성장 기록을 불러오고 있습니다...`);
    try {
      await onPeriodSelect(nextDays);
    } catch (requestError) {
      setError(requestError.message || "선택한 기간의 성장 기록을 불러오지 못했습니다.");
      setNotice("");
    } finally {
      setPeriodChanging(false);
    }
  }

  const sections = useMemo(() => parseAnalysis(analysis),[analysis]);

  return (
    <section className="section">
      <div className="section-header">
        <h2 className="section-title">AI 성장 리포트</h2>
        <p className="section-description">선택한 {periodDays}일의 실제 저장 기록을 바탕으로 변화와 흐름을 정리했습니다.</p>
      </div>
      <div className="ai-analysis-card">
        {periodDays > 7 && periodSummary && <div className="ai-analysis-period-evidence" data-testid="ai-analysis-period-evidence">
          <strong>분석 근거 · 최근 {periodDays}일</strong>
          <div className="ai-analysis-period-grid">
            <span>기록 충실도 <b>{Number.isFinite(Number(periodSummary.coveragePercent)) ? Number(periodSummary.coveragePercent).toFixed(1)+"%" : "자료 부족"}</b></span>
            <span>확인된 성장 구간 <b>{periodSummary.confirmedChangeDays ?? 0}일</b></span>
            <span>평균 일일 성장량 <b>{periodSummary.averageGrowth == null ? "자료 부족" : (Number(periodSummary.averageGrowth)/1_000_000_000_000).toFixed(2)+"조"}</b></span>
            <span>직전 동일 기간 평균 <b>{periodSummary.previousSummary?.averageGrowth == null ? "자료 부족" : (Number(periodSummary.previousSummary.averageGrowth)/1_000_000_000_000).toFixed(2)+"조"}</b></span>
          </div>
        </div>}
        <div className="ai-analysis-actions">
          <label className="ai-analysis-period-control">
            <span>분석 기간</span>
            <select value={periodDays} onChange={handlePeriodChange} disabled={periodChanging || loading} aria-label="AI 분석 기간">
              <option value="7">최근 7일</option>
              <option value="30">최근 30일</option>
              <option value="90">최근 90일</option>
            </select>
          </label>
          <button className="export-button" type="button" onClick={() => run({force:Boolean(analysis),allowGenerate:true})} disabled={loading || periodChanging}>
            {loading ? "분석 중..." : analysis ? "다시 분석" : "AI 분석 시작"}
          </button>
        </div>
        {loading && <div className="ai-analysis-loading" role="status">성장 기록을 살펴보고 있습니다...</div>}
        {error && <div className="ai-analysis-error" role="alert">{error}</div>}
        {analysis && !loading && (
          <div className="ai-analysis-result">
            {[
              ["성장 패턴",sections.growthPattern],
              ["성장 변화",sections.growthChange],
              ["레벨업 분석",sections.levelUp],
              ["성장 전망",sections.growthOutlook],
              ["AI 코멘트",sections.judgement]
            ].map(([label,value]) => (
              <div className="ai-analysis-item" key={label}>
                <div className="ai-analysis-label">{label}</div>
                <div className="ai-analysis-text">{value || "이 항목에 해당하는 설명이 없습니다."}</div>
              </div>
            ))}

          </div>
        )}
        {!analysis && !loading && !error && (
          <div className="ai-analysis-empty" data-testid="ai-analysis-empty">
            <strong>{character?.characterName ? `최근 ${periodDays}일 AI 리포트가 아직 없습니다.` : "먼저 캐릭터를 조회해주세요."}</strong>
            <p>{character?.characterName ? "선택한 기간의 성장 기록을 확인한 뒤, AI 분석 시작을 누르면 리포트를 생성합니다." : "캐릭터를 조회하면 해당 캐릭터의 성장 기록을 바탕으로 분석할 수 있습니다."}</p>
          </div>
        )}
      </div>
    </section>
  );
}

async function fetchArchive(days,character,onProgress) {
  let result = null;
  const summary = {checkedDays:0,savedRecords:0,availableRecords:0,noDataRecords:0,remainingDays:0};
  for (let offset=0;offset<days;offset+=10) {
    const limit = Math.min(10,days-offset);
    onProgress?.(`${character.characterName} · ${Math.min(offset+limit,days)}/${days}일 확인`);
    result = await getHistoryArchive(character.ocid,days,{
      collect:true,
      characterName:character.characterName,
      worldName:character.worldName,
      offset,
      limit
    });
    const batch = result.collection || {};
    summary.checkedDays += Number(batch.checkedDays || 0);
    summary.savedRecords += Number(batch.savedRecords || 0);
    summary.availableRecords += Number(batch.availableRecords || 0);
    summary.noDataRecords += Number(batch.noDataRecords || 0);
    summary.remainingDays = Number(batch.remainingDays || 0);
    if (summary.remainingDays === 0) break;
  }
  if (result) result.collectionSummary = summary;
  return result;
}

function comparisonSummary(history,days) {
  const records = sortHistoryAscending(history || []);
  const changes = records.filter(item =>
    (!item.recordStatus || item.recordStatus === "available") &&
    item.experienceChange !== null && item.experienceChange !== undefined &&
    Number.isFinite(Number(item.experienceChange))
  );
  const total = changes.length ? changes.reduce((sum,item) => sum + Number(item.experienceChange),0) : null;
  const ranked = records.filter(item => item.ranking !== null && item.ranking !== undefined && Number.isFinite(Number(item.ranking)));
  const available = records.filter(item => item.recordStatus === "available").length;
  return {
    days,
    growth:total,
    average:total === null ? null : total / changes.length,
    rankingChange:ranked.length >= 2 ? Number(ranked[0].ranking)-Number(ranked[ranked.length-1].ranking) : null,
    availableDays:available,
    coverage:records.length ? available/records.length*100 : 0,
    notReady:records.filter(item=>item.recordStatus==="not_ready").length,
    notCollected:records.filter(item=>item.recordStatus==="not_collected").length
  };
}

function ComparisonCharacterCard({ title, character, history }) {
  const prediction = calculatePrediction(character,history || []);
  const metrics = calculateGrowthMetrics(character,history || [],prediction);
  const values = [
    ["레벨","Lv. "+formatNumber(character.level)],
    ["레벨 내 진행률",character.experienceRate == null ? "자료 부족" : Number(character.experienceRate).toFixed(3)+"%"],
    ["최근 성장량",signedTrillion(metrics.latestDailyGrowth)],
    ["평균 성장량",formatTrillion(metrics.averageDailyGrowth)],
    ["현재 레벨 기준 일일 진척",metrics.levelProgress?.dailyProgressRate == null ? "자료 부족" : metrics.levelProgress.dailyProgressRate.toFixed(4)+"%p"],
    ["최근 7일 성장",signedTrillion(metrics.sevenDayGrowth)],
    ["랭킹 변화",metrics.rankingChange == null ? "자료 부족" : (metrics.rankingChange > 0 ? "▲ " : metrics.rankingChange < 0 ? "▼ " : "")+formatNumber(Math.abs(metrics.rankingChange))],
    ["예상 레벨업",metrics.prediction?.estimatedDate || "자료 부족"]
  ];
  return (
    <article className="comparison-character-card">
      <h3 className="comparison-name">{title} · {character.characterName || "캐릭터"}</h3>
      <div className="comparison-stat-grid">
        {values.map(([label,value]) => (
          <div className="comparison-stat" key={label}><span>{label}</span><strong>{value}</strong></div>
        ))}
      </div>
      <p className="comparison-period-detail">{character.worldName || "월드 정보 없음"} · {character.job || "직업 정보 없음"}</p>
    </article>
  );
}

export function GrowthComparison({ character, history, initialState, onSave }) {
  const [name,setName] = useState(initialState?.character?.characterName || "");
  const [other,setOther] = useState(initialState?.character || null);
  const [otherHistory,setOtherHistory] = useState(initialState?.history || []);
  const [analysis,setAnalysis] = useState(initialState?.aiAnalysis || "");
  const [days,setDays] = useState(Number(initialState?.periodDays) === 90 ? 90 : 30);
  const [period,setPeriod] = useState(initialState?.periodSummary || null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const [periodBusy,setPeriodBusy] = useState(false);

  useEffect(() => {
    setName(initialState?.character?.characterName || "");
    setOther(initialState?.character || null);
    setOtherHistory(initialState?.history || []);
    setAnalysis(initialState?.aiAnalysis || "");
    setDays(Number(initialState?.periodDays) === 90 ? 90 : 30);
    setPeriod(initialState?.periodSummary || null);
  },[character.ocid]);

  const primaryPrediction = calculatePrediction(character,history || []);
  const primaryMetrics = calculateGrowthMetrics(character,history || [],primaryPrediction);
  const secondaryMetrics = other ? calculateGrowthMetrics(other,otherHistory || []) : null;

  async function loadPeriod(secondary,selectedDays) {
    setPeriodBusy(true);
    setNotice(`최근 ${selectedDays}일 비교 기록을 확인하고 있습니다...`);
    try {
      const [first,second] = await Promise.all([
        fetchArchive(selectedDays,character,setNotice),
        fetchArchive(selectedDays,secondary,setNotice)
      ]);
      const firstSummary = comparisonSummary(first.history,selectedDays);
      const secondSummary = comparisonSummary(second.history,selectedDays);
      const result = {days:selectedDays,primary:firstSummary,secondary:secondSummary};
      setPeriod(result);
      setNotice(`최근 ${selectedDays}일의 실제 저장 기록을 비교했습니다.`);
      return result;
    } catch (requestError) {
      setNotice(requestError.message || "기간 비교 기록을 불러오지 못했습니다.");
      setPeriod(null);
      return null;
    } finally {
      setPeriodBusy(false);
    }
  }

  async function runComparison(event) {
    event.preventDefault();
    const query = name.trim();
    if (!query) { setError("비교할 캐릭터명을 입력해주세요."); return; }
    if (query.toLocaleLowerCase() === character.characterName.toLocaleLowerCase()) {
      setError("같은 캐릭터는 비교할 수 없습니다."); return;
    }
    setBusy(true);
    setError("");
    setPeriod(null);
    setAnalysis("");
    try {
      const [secondCharacter,secondHistory] = await Promise.all([
        getCharacter(query,{refresh:true}),
        getHistory(query,{refresh:true})
      ]);
      if (String(secondCharacter.characterName).toLowerCase() === String(character.characterName).toLowerCase()) {
        throw new Error("같은 캐릭터는 비교할 수 없습니다.");
      }
      const historyItems = secondHistory.history || [];
      const secondPrediction = calculatePrediction(secondCharacter,historyItems);
      const secondMetrics = calculateGrowthMetrics(secondCharacter,historyItems,secondPrediction);
      setOther(secondCharacter);
      setOtherHistory(historyItems);
      const periodResult = await loadPeriod(secondCharacter,days);

      const signature = stableStringify({
        primary:{character,metrics:primaryMetrics,history},
        comparison:{character:secondCharacter,metrics:secondMetrics,history:historyItems}
      });
      const cached = getCachedAI("growth-comparison-v1",signature);
      let comparisonReport = cached?.analysis || "";
      if (comparisonReport) {
        setAnalysis(comparisonReport);
        setNotice("저장된 비교 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다.");
      } else {
        const result = await postAiComparison(
          {character,metrics:primaryMetrics,history},
          {character:secondCharacter,metrics:secondMetrics,history:historyItems}
        );
        comparisonReport = result.analysis || "분석 결과가 없습니다.";
        setAnalysis(comparisonReport);
        saveCachedAI("growth-comparison-v1",signature,comparisonReport);
        setNotice(result.cacheHit
          ? "서버에 저장된 비교 분석을 재사용했습니다."
          : "새 비교 분석을 생성했습니다.");
      }
      onSave?.({
        comparison:{
          character:secondCharacter,
          history:historyItems,
          metrics:secondMetrics,
          aiAnalysis:comparisonReport,
          periodDays:days,
          periodSummary:periodResult,
          periodError:periodResult ? "" : "기간별 비교 기록을 불러오지 못했습니다."
        }
      });
    } catch (requestError) {
      setError(requestError.message || "성장 비교를 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function changePeriod(value) {
    const selectedDays = Number(value) === 90 ? 90 : 30;
    setDays(selectedDays);
    if (!other) return;
    const result = await loadPeriod(other,selectedDays);
    onSave?.({comparison:{character:other,history:otherHistory,metrics:secondaryMetrics,aiAnalysis:analysis,periodDays:selectedDays,periodSummary:result,periodError:result ? "" : notice}});
  }

  return (
    <section className="section">
      <div className="section-header"><h2 className="section-title">성장 캐릭터 비교</h2><p className="section-description">두 캐릭터의 최근 성장 지표와 동일 기간 저장 기록을 비교합니다.</p></div>
      <div className="comparison-card">
        <form className="comparison-form" onSubmit={runComparison}>
          <label className="comparison-input-label" htmlFor="react-comparison-name">비교할 캐릭터</label>
          <input id="react-comparison-name" className="search-input" value={name} onChange={event=>setName(event.target.value)} placeholder="캐릭터명을 입력하세요" autoComplete="off" />
          <button id="react-comparison-button" className="search-button" type="submit" disabled={busy}>{busy ? "비교 중..." : "성장 비교"}</button>
        </form>
        {error && <div className="error-message" role="alert">{error}</div>}
        {notice && <p className="comparison-period-notice" role="status">{notice}</p>}
        {busy && <div className="loading-message" role="status">두 캐릭터의 최신 데이터와 성장 기록을 조회하고 있습니다...</div>}
        {other && !busy && (
          <div className="comparison-result">
            <div className="comparison-grid">
              <ComparisonCharacterCard title="기준 캐릭터" character={character} history={history || []} />
              <ComparisonCharacterCard title="비교 캐릭터" character={other} history={otherHistory || []} />
            </div>
            <section className="comparison-period-section">
              <div className="comparison-period-heading">
                <div><h3>기간별 성장 비교</h3><p>양쪽 모두 같은 날짜 범위의 저장 기록을 비교합니다.</p></div>
                <label className="comparison-period-control">비교 기간
                  <select className="history-range-select" value={days} onChange={event=>changePeriod(event.target.value)} disabled={periodBusy}>
                    <option value="30">최근 30일</option><option value="90">최근 90일</option>
                  </select>
                </label>
              </div>
              {period ? (
                <div className="comparison-period-grid">
                  {[[character.characterName,period.primary],[other.characterName,period.secondary]].map(([title,item])=>(
                    <article className="comparison-period-character-card" key={title}>
                      <h4 className="comparison-period-name">{title}</h4>
                      <div className="comparison-period-stat"><span>확인된 경험치 증가</span><strong>{formatTrillion(item.growth)}</strong></div>
                      <div className="comparison-period-stat"><span>기록 기준 1일 평균</span><strong>{formatTrillion(item.average)}</strong></div>
                      <div className="comparison-period-stat"><span>랭킹 변화</span><strong>{item.rankingChange == null ? "자료 부족" : (item.rankingChange > 0 ? "▲ " : item.rankingChange < 0 ? "▼ " : "")+formatNumber(Math.abs(item.rankingChange))+"위"}</strong></div>
                      <div className="comparison-period-stat"><span>기록 충실도</span><strong>{item.availableDays} / {item.days}일</strong></div>
                      <p className="comparison-period-detail">API 미제공 {item.notReady}일 · 미수집 {item.notCollected}일</p>
                    </article>
                  ))}
                </div>
              ) : <p className="comparison-period-verdict">기간별 저장 기록을 아직 불러오지 않았습니다.</p>}
              <p className="comparison-period-notice">경험치 증가량은 연속 관측된 날짜 간 변화만 합산합니다. 결측 날짜는 0으로 계산하지 않습니다.</p>
            </section>
            <div className="comparison-ai">
              <h3>AI 성장 비교 분석</h3>
              {analysis ? <div className="comparison-ai-text">{analysis}</div> : <p className="comparison-ai-text">AI 비교 분석 결과가 없습니다.</p>}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}