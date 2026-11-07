import { useEffect, useMemo, useRef, useState } from "react";
import Chart from "chart.js/auto";
import { detectLevelUpEvents, buildLevelUpMarkers, buildExperienceChartSeries, dailyGrowthSegmentDash } from "./growthChartData.js";
import {
  getHistoryArchive
} from "../../services/api.js";
import {
  sortHistoryAscending,
  sortHistoryDescending,
  getDailyGrowth,
  calculateAverageGrowth,
  calculateDailyExperienceRateChanges,
  calculateWeeklyGrowth,
  getRankingChange,
  calculatePrediction,
  formatLocalISODate,
  calculateLevelProgress,
  calculateGrowthMetrics,
  buildGrowthTimeline
} from "../../lib/growth.js";
import { readGrowthGoals, saveGrowthGoals, readTrackerState } from "../../lib/storage.js";

function fmt(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const trillion = Number(value) / 1_000_000_000_000;
  if (Math.abs(trillion) >= 100) return trillion.toFixed(0) + "조";
  if (Math.abs(trillion) >= 10) return trillion.toFixed(1) + "조";
  return trillion.toFixed(2) + "조";
}

function signedFmt(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const number = Number(value);
  return (number > 0 ? "+" : number < 0 ? "−" : "") + fmt(Math.abs(number));
}

function localDate(value) {
  if (!value) return "—";
  const parts = String(value).split("-");
  return parts.length === 3 ? parts[0] + "." + parts[1] + "." + parts[2] : String(value);
}

function shiftDate(dateText, amount) {
  const [year, month, day] = String(dateText || "").split("-").map(Number);
  if (!year || !month || !day) return null;
  const date = new Date(Date.UTC(year, month - 1, day + amount));
  return date.toISOString().slice(0, 10);
}

function parseDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) return null;

  return date.getTime();
}

function daysBetween(start, end) {
  const first = parseDate(start);
  const last = parseDate(end);
  return first === null || last === null ? null : Math.round((last - first) / 86400000);
}

async function fetchArchive(days, character, { end = null, collect = false, onProgress = null } = {}) {
  let result = null;
  const totals = { checkedDays: 0, savedRecords: 0, availableRecords: 0, noDataRecords: 0, remainingDays: 0 };
  const batches = collect ? Math.ceil(days / 10) : 1;
  for (let batch = 0; batch < batches; batch += 1) {
    const offset = batch * 10;
    const limit = collect ? Math.min(10, days - offset) : undefined;
    onProgress?.(collect ? `과거 기록 확인 중 · ${Math.min(offset + limit, days)}/${days}일` : "저장된 기간 기록 조회 중...");
    result = await getHistoryArchive(character.ocid, days, {
      end,
      collect,
      characterName: character.characterName,
      worldName: character.worldName,
      offset,
      limit
    });
    const item = result.collection || {};
    totals.checkedDays += Number(item.checkedDays || 0);
    totals.savedRecords += Number(item.savedRecords || 0);
    totals.availableRecords += Number(item.availableRecords || 0);
    totals.noDataRecords += Number(item.noDataRecords || 0);
    totals.remainingDays = Number(item.remainingDays || 0);
    if (!collect || totals.remainingDays === 0) break;
  }
  if (result && collect) result.collectionSummary = totals;
  return result;
}

function summarizePeriod(history, days) {
  const records = sortHistoryAscending(Array.isArray(history) ? history : []);
  const valid = records.filter(item =>
    (!item.recordStatus || item.recordStatus === "available") &&
    item.experience !== null && item.experience !== undefined &&
    Number.isFinite(Number(item.experience))
  );
  const changes = records.filter(item =>
    (!item.recordStatus || item.recordStatus === "available") &&
    item.experienceChange !== null && item.experienceChange !== undefined &&
    Number.isFinite(Number(item.experienceChange))
  );
  const growth = changes.length ? changes.reduce((sum,item) => sum + Number(item.experienceChange), 0) : null;
  const average = growth === null ? null : growth / changes.length;
  const positive = changes.filter(item => Number(item.experienceChange) > 0);
  const best = positive.reduce((best,item) =>
    !best || Number(item.experienceChange) > Number(best.experienceChange) ? item : best, null);
  const ranked = valid.filter(item => item.ranking !== null && item.ranking !== undefined && Number.isFinite(Number(item.ranking)));
  const levelUps = records.filter((item,index) =>
    item.levelUp === true || (Number(records[index - 1]?.level) < Number(item.level) && Number.isFinite(Number(item.level)))
  );
  return {
    days,
    startDate: records[0]?.date || null,
    endDate: records[records.length - 1]?.date || null,
    growth,
    averageGrowth: average,
    confirmedChangeDays: changes.length,
    bestDailyGrowth: best ? Number(best.experienceChange) : null,
    bestDailyGrowthDate: best?.date || null,
    growthDays: positive.length,
    zeroGrowthDays: changes.filter(item => Number(item.experienceChange) === 0).length,
    negativeGrowthDays: changes.filter(item => Number(item.experienceChange) < 0).length,
    levelUpCount: levelUps.length,
    levelUpDates: levelUps.map(item => item.date),
    rankingChange: ranked.length >= 2 ? Number(ranked[0].ranking) - Number(ranked[ranked.length - 1].ranking) : null,
    availableDays: records.filter(item => item.recordStatus === "available").length,
    notReadyDays: records.filter(item => item.recordStatus === "not_ready").length,
    notCollectedDays: records.filter(item => item.recordStatus === "not_collected").length,
    coveragePercent: records.length ? valid.length / records.length * 100 : 0
  };
}

function ProgressBar({ value, label }) {
  const valid = Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100;
  const percent = valid ? Number(value) : 0;
  return (
    <div className="growth-progress-wrap">
      <div className="growth-progress-heading">
        <span>{label}</span>
        <strong>{valid ? percent.toFixed(3) + "%" : "자료 부족"}</strong>
      </div>
      <div className="growth-progress-track" role="progressbar" aria-label={label}
        aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}>
        <span className="growth-progress-fill" style={{ width: percent + "%" }} />
      </div>
    </div>
  );
}

function GoalPanel({ character, metrics, history }) {
  const [goal, setGoal] = useState(null);
  const [targetDate, setTargetDate] = useState("");
  const [notifications, setNotifications] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState(false);
  const key = String(character.ocid || "");
  const today = formatLocalISODate(new Date());
  const currentLevel = Number(character.level);
  const currentRate = Number(String(character.experienceRate ?? "").replace("%",""));
  const validRate = Number.isFinite(currentRate) && currentRate >= 0 && currentRate <= 100;

  useEffect(() => {
    const saved = readGrowthGoals()[key] || null;
    setGoal(saved);
    setTargetDate(saved?.targetDate || formatLocalISODate(new Date(Date.now() + 7 * 86400000)));
    setNotifications(saved?.notificationsEnabled === true);
    setFeedback("");
  }, [key]);

  useEffect(() => {
    if (!goal || !Number.isFinite(currentLevel)) return;
    const previous = Number(goal.lastObservedLevel ?? goal.startLevel);
    const levelUp = Number.isFinite(previous) && currentLevel > previous;
    const completed = currentLevel >= Number(goal.targetLevel) && !goal.completedAt;
    if (!levelUp && !completed) return;
    const nextGoal = {
      ...goal,
      lastObservedLevel: currentLevel,
      completedAt: completed ? new Date().toISOString() : goal.completedAt
    };
    const all = readGrowthGoals();
    all[key] = nextGoal;
    saveGrowthGoals(all);
    setGoal(nextGoal);
    if (nextGoal.notificationsEnabled && "Notification" in window && Notification.permission === "granted") {
      try {
        new Notification(completed ? "성장 목표 달성" : "새로운 레벨업", {
          body: completed
            ? `${character.characterName} 캐릭터가 목표 레벨 Lv.${goal.targetLevel}을 달성했습니다.`
            : `${character.characterName} 캐릭터가 Lv.${currentLevel}로 레벨업했습니다.`,
          tag: "maple-growth-goal-" + key
        });
      } catch { /* Browser notification failure does not affect saved goal state. */ }
    }
    setFeedback(completed ? `Lv. ${goal.targetLevel} 목표를 달성했습니다.` : `Lv. ${currentLevel} 레벨업을 확인했습니다.`);
  }, [goal, currentLevel, key, character.characterName]);

  async function saveGoal(event) {
    event.preventDefault();
    setError(false);
    if (!key || !Number.isFinite(currentLevel)) {
      setError(true);
      setFeedback("캐릭터 식별 정보 또는 레벨을 확인할 수 없습니다.");
      return;
    }
    if (parseDate(targetDate) === null || daysBetween(today,targetDate) < 0) {
      setError(true);
      setFeedback("오늘 이후의 올바른 목표 날짜를 선택해주세요.");
      return;
    }
    let notificationsEnabled = false;
    let notice = "";
    if (notifications) {
      if (!("Notification" in window)) notice = "이 브라우저는 알림을 지원하지 않습니다.";
      else {
        let permission = Notification.permission;
        if (permission === "default") {
          try { permission = await Notification.requestPermission(); } catch { permission = "denied"; }
        }
        notificationsEnabled = permission === "granted";
        if (!notificationsEnabled) notice = "브라우저 알림 권한이 없어 사이트 내 목표 상태만 표시합니다.";
      }
    }
    const previous = readGrowthGoals()[key] || null;
    const startingNew = !previous || previous.completedAt || currentLevel >= Number(previous.targetLevel);
    const next = {
      ocid: key,
      characterName: character.characterName || "",
      worldName: character.worldName || "",
      startLevel: startingNew ? currentLevel : Number(previous.startLevel),
      startExperienceRate: startingNew ? (validRate ? currentRate : null) : previous.startExperienceRate,
      targetLevel: startingNew ? currentLevel + 1 : Number(previous.targetLevel),
      targetDate,
      lastObservedLevel: currentLevel,
      notificationsEnabled,
      createdAt: startingNew ? new Date().toISOString() : previous.createdAt,
      completedAt: null
    };
    const all = readGrowthGoals();
    all[key] = next;
    if (!saveGrowthGoals(all)) {
      setError(true);
      setFeedback("브라우저 저장소에 목표를 저장하지 못했습니다.");
      return;
    }
    setGoal(next);
    setFeedback(notice || `Lv. ${next.targetLevel} 목표를 ${targetDate}로 저장했습니다.`);
  }

  function clearGoal() {
    const all = readGrowthGoals();
    delete all[key];
    if (!saveGrowthGoals(all)) {
      setError(true);
      setFeedback("목표를 해제하지 못했습니다.");
      return;
    }
    setGoal(null);
    setFeedback("성장 목표를 해제했습니다.");
    setError(false);
  }

  const completed = !!goal && (goal.completedAt || currentLevel >= Number(goal.targetLevel));
  const startLevel = Number(goal?.startLevel);
  const startRate = Number(goal?.startExperienceRate);
  let progress = null;
  if (goal && completed) progress = 100;
  else if (goal && currentLevel === startLevel && validRate && Number.isFinite(startRate) && startRate >= 0 && startRate < 100) {
    progress = Math.max(0, Math.min(100, ((currentRate - startRate) / (100 - startRate)) * 100));
  }
  const daysRemaining = goal ? daysBetween(today, goal.targetDate) : null;
  const requiredRate = daysRemaining > 0 && validRate ? Math.max(0,100-currentRate)/daysRemaining : null;
  const observedRate = metrics.levelProgress?.dailyProgressRate;

  return (
    <section className="growth-goal-card" aria-labelledby="growth-goal-title">
      <div className="growth-goal-heading">
        <div>
          <span className="growth-goal-kicker">PERSONAL GOAL</span>
          <h3 id="growth-goal-title">다음 레벨 목표</h3>
          <p>목표 날짜를 정하고 실제 관측 성장 속도와 비교합니다.</p>
        </div>
        <span className="growth-goal-status">{!goal ? "목표 미설정" : completed ? "목표 달성" : daysRemaining < 0 ? "목표일 경과" : "진행 중"}</span>
      </div>
      {goal && (
        <div className="growth-goal-progress-panel">
          <div className="growth-goal-progress-heading"><span>목표 진척률</span><strong>{progress === null ? "진척률 자료 부족" : progress.toFixed(1)+"%"}</strong></div>
          <div className="growth-goal-progress-track" role="progressbar" aria-label="다음 레벨 목표 진척률" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress ?? 0}>
            <span className="growth-goal-progress-fill" style={{width:(progress ?? 0)+"%"}} />
          </div>
          <p className="growth-goal-pace">
            {completed ? `목표 레벨 Lv. ${goal.targetLevel}을 확인했습니다.`
              : daysRemaining === null ? "목표 날짜 형식을 확인할 수 없습니다."
              : daysRemaining < 0 ? "목표 날짜가 지났습니다. 날짜를 변경해 목표를 이어가세요."
              : daysRemaining === 0 ? "목표일이 오늘입니다. 현재 경험치 진행률을 확인하세요."
              : requiredRate === null ? `목표일까지 ${daysRemaining}일 남았습니다. 현재 진행률 자료가 부족합니다.`
              : Number.isFinite(observedRate) && observedRate > 0
                ? `목표일까지 ${daysRemaining}일 · 필요 ${requiredRate.toFixed(4)}%p/일 · 최근 관측 ${observedRate.toFixed(4)}%p/일. ${observedRate >= requiredRate ? "현재 속도면 목표에 도달할 수 있습니다." : "목표를 맞추려면 성장 속도를 높여야 합니다."}`
                : `목표일까지 ${daysRemaining}일 · 필요 진척 ${requiredRate.toFixed(4)}%p/일. 비교할 성장 기록이 부족합니다.`}
          </p>
        </div>
      )}
      <form className="growth-goal-form" onSubmit={saveGoal}>
        <div className="growth-goal-fields">
          <div className="growth-goal-target"><span>목표 레벨</span><strong>Lv. {goal?.targetLevel || currentLevel + 1}</strong></div>
          <label className="growth-goal-date-label">목표 날짜
            <input type="date" required min={today} value={targetDate} onChange={event => setTargetDate(event.target.value)} />
          </label>
        </div>
        <label className="growth-goal-notification">
          <input type="checkbox" checked={notifications} onChange={event => setNotifications(event.target.checked)} />
          <span>레벨업 또는 목표 달성 시 브라우저 알림 받기</span>
        </label>
        <div className="growth-goal-actions">
          <button type="submit" className="growth-goal-save-button">{goal ? completed ? "다음 목표 설정" : "목표일 변경" : "목표 설정"}</button>
          {goal && <button type="button" className="growth-goal-clear-button" onClick={clearGoal}>목표 해제</button>}
        </div>
      </form>
      {feedback && <p className={"growth-goal-feedback " + (error ? "is-error" : "")} role="status">{feedback}</p>}
      <p className="growth-goal-storage-note">목표는 기존과 동일하게 캐릭터 OCID 기준 브라우저 저장소에 보관됩니다. 기기 간 동기화는 지원하지 않습니다. 브라우저 알림은 사이트가 열려 있고 캐릭터를 다시 조회할 때 감지됩니다.</p>
    </section>
  );
}

function PeriodSummary({ summary, previous, label }) {
  if (!summary) return null;
  const comparisonPercent = previous?.averageGrowth !== null && previous?.averageGrowth !== undefined &&
    summary.averageGrowth !== null && previous.averageGrowth !== 0
    ? (summary.averageGrowth - previous.averageGrowth) / Math.abs(previous.averageGrowth) * 100
    : null;
  const cells = [
    ["기간 증가량",fmt(summary.growth),summary.confirmedChangeDays + "개 연속 관측 구간"],
    ["관측 일 평균",fmt(summary.averageGrowth),summary.confirmedChangeDays + "개 구간 기준"],
    ["랭킹 변화",summary.rankingChange === null ? "자료 부족" : (summary.rankingChange > 0 ? "▲ " + summary.rankingChange + "위 상승" : summary.rankingChange < 0 ? "▼ " + Math.abs(summary.rankingChange) + "위 하락" : "변화 없음"),"첫 기록과 마지막 기록 비교"],
    ["직전 기간 대비",comparisonPercent === null ? "비교 자료 부족" : (comparisonPercent > 0 ? "+" : "") + comparisonPercent.toFixed(1) + "%",previous ? "직전 동일 기간의 관측 평균과 비교" : "직전 기간 자료 없음"],
    ["기록 충실도",summary.availableDays + " / " + summary.days + "일",`API 미제공 ${summary.notReadyDays}일 · 미수집 ${summary.notCollectedDays}일`],
    ["기간 최고 성장",fmt(summary.bestDailyGrowth),summary.bestDailyGrowthDate ? localDate(summary.bestDailyGrowthDate) : "확인된 성장 기록 없음"],
    ["성장 활동일",summary.growthDays + "일",`정체 ${summary.zeroGrowthDays}일 · 감소 ${summary.negativeGrowthDays}일`],
    ["레벨업",summary.levelUpCount + "회",summary.levelUpDates.length ? summary.levelUpDates.map(localDate).join(" · ") : "기간 내 레벨업 기록 없음"]
  ];
  return (
    <section className="period-summary-section">
      <div className="period-summary-heading">
        <div><h3>기간별 성장 요약</h3><p>{label} · {localDate(summary.startDate)} ~ {localDate(summary.endDate)} · 기록 {summary.coveragePercent.toFixed(0)}%</p></div>
        <span className={"period-summary-badge " + (summary.coveragePercent < 70 ? "is-warning" : "")}>기록 {summary.coveragePercent.toFixed(0)}%</span>
      </div>
      <div className="period-summary-grid react-period-grid">
        {cells.map(([title,value,detail]) => (
          <article className="period-summary-card" key={title}>
            <span className="period-summary-label">{title}</span>
            <strong className="period-summary-value">{value}</strong>
            <span className="period-summary-detail">{detail}</span>
          </article>
        ))}
      </div>
      <p className="period-summary-footnote">
        평균은 실제 변화량이 확인된 날짜 간 구간 기준입니다. 미수집 날짜는 0으로 간주하지 않으며, 레벨업 경계의 경험치 초기화는 증가량으로 계산하지 않습니다.
      </p>
    </section>
  );
}

export default function GrowthDashboard({ character, history, onHistoryChange, onPersist }) {
  const initialState = readTrackerState() || {};
  const initialRange = [7,30,90].includes(Number(initialState.historyRange)) ? Number(initialState.historyRange) : 7;
  const [range, setRange] = useState(initialRange);
  const [displayHistory, setDisplayHistory] = useState(
    initialRange === 7 || !Array.isArray(initialState.displayHistory) ? history || [] : initialState.displayHistory
  );
  const [rangeStatus, setRangeStatus] = useState(initialState.historyRangeStatus || null);
  const [periodSummary, setPeriodSummary] = useState(initialState.periodSummary || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progressText, setProgressText] = useState("");
  const [chartVersion, setChartVersion] = useState(0);
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const saved = readTrackerState() || {};
    const savedRange = [7,30,90].includes(Number(saved.historyRange)) ? Number(saved.historyRange) : 7;
    setRange(savedRange);
    setDisplayHistory(savedRange === 7 || !Array.isArray(saved.displayHistory) ? history || [] : saved.displayHistory);
    setRangeStatus(saved.historyRangeStatus || null);
    setPeriodSummary(saved.periodSummary || null);
    setError("");
    setProgressText("");
  }, [character.ocid]);

  const prediction = useMemo(() => calculatePrediction(character, history || []), [character, history]);
  const metrics = useMemo(() => calculateGrowthMetrics(character, history || [], prediction), [character, history, prediction]);
  const levelProgress = metrics.levelProgress;
  const timeline = useMemo(() => buildGrowthTimeline(displayHistory, 8), [displayHistory]);
  const progressRateChanges = useMemo(
    () => calculateDailyExperienceRateChanges(displayHistory),
    [displayHistory]
  );

  useEffect(() => {
    if (!canvasRef.current) return undefined;
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }
    const sorted = sortHistoryAscending(displayHistory);
    if (!sorted.length) return undefined;
    const { daily, cumulative } = buildExperienceChartSeries(sorted);
    // The history API provides daily levels rather than a levelUp flag.
    // Detect level changes locally so the yellow star is drawn on actual events.
    const levelUpEvents = detectLevelUpEvents(sorted);
    const levelUps = buildLevelUpMarkers(sorted, cumulative);
    chartRef.current = new Chart(canvasRef.current.getContext("2d"), {
      type: "line",
      data: {
        labels: sorted.map(item => String(item.date || "").slice(5)),
        datasets: [
          { label:"총 경험치 증가량",data:cumulative,yAxisID:"experience",borderColor:"#36a2eb",backgroundColor:"#36a2eb",borderWidth:3,tension:0,pointRadius:3,pointHoverRadius:6,fill:false },
          { label:"일일 경험치 증가량",data:daily,yAxisID:"dailyGrowth",borderColor:"#ff6384",backgroundColor:"#ff6384",borderWidth:2,segment:{borderDash:dailyGrowthSegmentDash},tension:0,pointRadius:2,pointHoverRadius:5,fill:false },
          { label:"레벨업",data:levelUps,yAxisID:"experience",showLine:false,pointStyle:"star",pointRadius:8,pointHoverRadius:10,pointBackgroundColor:"#f5c542",borderWidth:0 }
        ]
      },
      options: {
        responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:"index"},
        plugins:{legend:{display:true},tooltip:{callbacks:{
          label(context) {
            if (context.dataset.label === "레벨업") {
              const current = sorted[context.dataIndex];
              const previous = sorted.slice(0, context.dataIndex).reverse()
                .find(item => item?.level !== null && item?.level !== undefined && Number.isFinite(Number(item.level)));
              return "⭐ 레벨업 · Lv. " + (previous?.level ?? "—") + " → " + (current?.level ?? "—");
            }
            return context.parsed.y === null ? "" : context.dataset.label + ": " + context.parsed.y.toFixed(2) + "조";
          }
        }}},
        scales:{
          x:{type:"category",ticks:{
            autoSkip:false,maxRotation:0,minRotation:0,
            callback(value,index) {
              const item = sorted[index];
              const isLevelUp = levelUpEvents[index] === true;
              if (index % 3 !== 0 && !isLevelUp) return "";
              const label = String(item?.date || "").slice(5);
              return isLevelUp ? label + " ★" : label;
            }
          }},
          experience:{type:"linear",position:"left",title:{display:true,text:"총 경험치 증가량"},ticks:{callback:value=>Number(value).toFixed(0)+"조"}},
          dailyGrowth:{type:"linear",position:"right",beginAtZero:true,title:{display:true,text:"일일 경험치 증가량"},grid:{drawOnChartArea:false},ticks:{callback:value=>Number(value).toFixed(0)+"조"}}
        }
      }
    });
    return () => {
      if (chartRef.current) chartRef.current.destroy();
      chartRef.current = null;
    };
  }, [displayHistory, chartVersion]);

  async function changeRange(nextRange) {
    const days = [7,30,90].includes(Number(nextRange)) ? Number(nextRange) : 7;
    setBusy(true);
    setError("");
    try {
      if (days === 7) {
        setRange(7);
        setDisplayHistory(history || []);
        setRangeStatus(null);
        setPeriodSummary(null);
        onPersist?.({historyRange:7,displayHistory:history || [],historyRangeStatus:null,periodSummary:null});
      } else {
        const current = await fetchArchive(days,character,{
          collect:true,
          onProgress:setProgressText
        });
        let previous = null;
        const previousEnd = shiftDate(current.startDate,-1);
        if (previousEnd) {
          try { previous = await fetchArchive(days,character,{end:previousEnd,collect:false}); } catch { previous = null; }
        }
        const summary = summarizePeriod(current.history || [],days);
        summary.startDate = current.startDate || summary.startDate;
        summary.endDate = current.endDate || summary.endDate;
        setRange(days);
        setDisplayHistory(current.history || []);
        setPeriodSummary(summary);
        setRangeStatus({
          availableDays:current.availableDays || 0,
          notReadyDays:current.notReadyDays || 0,
          notCollectedDays:current.notCollectedDays || 0,
          collection:current.collectionSummary || null
        });
        onPersist?.({
          historyRange:days,displayHistory:current.history || [],
          historyRangeStatus:{
            availableDays:current.availableDays || 0,
            notReadyDays:current.notReadyDays || 0,
            notCollectedDays:current.notCollectedDays || 0,
            collection:current.collectionSummary || null
          },
          periodSummary:summary
        });
        const priorSummary = previous ? summarizePeriod(previous.history || [],days) : null;
        setPeriodSummary({ ...summary, previousSummary:priorSummary });
      }
      setChartVersion(value => value + 1);
      setProgressText("");
    } catch (requestError) {
      setError(requestError.message || "성장 기록을 불러오지 못했습니다.");
      setProgressText("");
    } finally {
      setBusy(false);
    }
  }

  const daily = getDailyGrowth(history || []);
  const weekly = calculateWeeklyGrowth(history || []);
  const average = calculateAverageGrowth(history || []);
  const rankChange = getRankingChange(history || []);
  const percent = Number(String(character.experienceRate ?? "").replace("%",""));
  const remaining = Number.isFinite(percent) ? Math.max(0,100-percent) : null;

  return (
    <div className="growth-dashboard">
      <section className="section">
        <div className="section-header">
          <h2 className="section-title">성장 요약</h2>
          <p className="section-description">실제 기록이 확인된 날짜 간 경험치 변화만 집계합니다.</p>
        </div>
        <div className="summary-grid">
          <div className="summary-card"><div className="summary-label">최근 확인된 성장량</div><div className="summary-value">{signedFmt(daily)}</div></div>
          <div className="summary-card"><div className="summary-label">랭킹 변화</div><div className="summary-value">{rankChange === null ? "자료 부족" : rankChange > 0 ? "▲ "+rankChange : rankChange < 0 ? "▼ "+Math.abs(rankChange) : "변동 없음"}</div></div>
          <div className="summary-card"><div className="summary-label">최근 7일 성장</div><div className="summary-value">{signedFmt(weekly)}</div></div>
          <div className="summary-card"><div className="summary-label">관측 일 평균</div><div className="summary-value">{fmt(average)}</div></div>
        </div>
      </section>

      <section className="section">
        <div className="section-header history-chart-header">
          <div><h2 className="section-title">성장 추이</h2><p className="section-description">첫날의 실제 경험치를 기준으로 한 총 경험치 증가량과 일일 경험치 증가량, 레벨업을 표시합니다.</p></div>
          <label className="history-range-control">기록 범위
            <select className="history-range-select" value={range} onChange={event => changeRange(Number(event.target.value))} disabled={busy}>
              <option value="7">최근 7일</option><option value="30">저장 기록 30일</option><option value="90">저장 기록 90일</option>
            </select>
          </label>
        </div>
        <p className="history-range-notice" role="status">
          {busy ? progressText || "기록을 불러오고 있습니다..." : range === 7
            ? `최근 7일 API 정상 기록 ${(history || []).filter(item=>item.recordStatus==="available").length}일`
            : `최근 ${range}일 · 정상 ${rangeStatus?.availableDays ?? 0}일 · API 미제공 ${rangeStatus?.notReadyDays ?? 0}일 · 미수집 ${rangeStatus?.notCollectedDays ?? 0}일`}
        </p>
        {error && !busy && <p className="history-range-notice is-warning" role="alert">{error}</p>}
        {periodSummary && range !== 7 && <PeriodSummary summary={periodSummary} previous={periodSummary.previousSummary} label={`최근 ${range}일`} />}
        <div className="chart-card"><div className="chart-wrapper"><canvas ref={canvasRef} aria-label="기간별 성장 추이 그래프" /></div></div>
        <section className="growth-timeline-section">
          <div className="growth-timeline-heading"><h3>주요 성장 타임라인</h3><p>선택 기간에서 확인된 레벨업과 성장·랭킹 기록입니다.</p></div>
          <ol className="growth-timeline-list">
            {timeline.length ? timeline.map((event,index) => (
              <li className={"growth-timeline-item is-"+event.type} key={event.type+event.date+index}>
                <span className="growth-timeline-marker" aria-hidden="true" />
                <div className="growth-timeline-body">
                  <time className="growth-timeline-date">{localDate(event.date)}</time>
                  <strong className="growth-timeline-title">{event.title}</strong>
                  <p className="growth-timeline-description">{event.description}</p>
                </div>
              </li>
            )) : <li className="growth-timeline-empty">기록이 쌓이면 레벨업과 주요 성장 기록이 표시됩니다.</li>}
          </ol>
        </section>
      </section>

      <section className="section">
        <div className="section-header"><h2 className="section-title">성장 예측</h2><p className="section-description">최근 관측 성장 속도를 기준으로 다음 레벨업을 예상합니다.</p></div>
        <div className="prediction-card">
          <div className="prediction-grid">
            <div className="prediction-item"><div className="prediction-label">다음 레벨까지</div><div className="prediction-value">{prediction?.requiredExp == null ? "자료 부족" : fmt(prediction.requiredExp) + " (" + prediction.currentRate.toFixed(3) + "%)"}</div></div>
            <div className="prediction-item"><div className="prediction-label">예상 소요</div><div className="prediction-value">{Number.isFinite(prediction?.days) ? "약 "+prediction.days.toFixed(1)+"일" : "자료 부족"}</div></div>
            <div className="prediction-item"><div className="prediction-label">예상 레벨업</div><div className="prediction-value">{prediction?.date ? localDate(formatLocalISODate(prediction.date)) : "자료 부족"}</div></div>
            <div className="prediction-item"><div className="prediction-label">최근 평균</div><div className="prediction-value">{prediction?.averageGrowth > 0 ? fmt(prediction.averageGrowth) : "자료 부족"}</div></div>
          </div>
          <p className="prediction-note">최근 관측 평균 획득량이 유지된다는 가정의 추정치입니다. API가 제공하지 않은 날짜나 레벨업 경계는 임의로 채우지 않습니다.</p>
        </div>
        <GoalPanel character={character} metrics={metrics} history={history || []} />
      </section>

      <section className="section">
        <div className="section-header"><h2 className="section-title">날짜별 성장 기록</h2><p className="section-description">선택한 기간의 경험치 진행률과 랭킹 변화입니다. API가 진행률을 제공하지 않은 날짜는 추정하지 않고 비워 둡니다.</p></div>
        <div className="history-card">
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead><tr><th>날짜</th><th>랭킹</th><th>레벨</th><th>경험치</th><th>경험치 증가량</th><th>레벨 진행률</th></tr></thead>
              <tbody>
                {sortHistoryDescending(displayHistory).map(item => {
                  const rate = item.experienceRate == null
                    ? null
                    : Number(String(item.experienceRate).replace("%",""));
                  const rateChange = progressRateChanges[item.date];
                  const validRate = Number.isFinite(rate) && rate >= 0 && rate <= 100;
                  return (
                    <tr key={item.date}>
                      <td>{localDate(item.date)}</td>
                      <td>{item.ranking == null ? "—" : Number(item.ranking).toLocaleString("ko-KR")+"위"}</td>
                      <td>{item.level == null ? "—" : "Lv. "+item.level}</td>
                      <td className="history-experience-value">{item.experience == null ? "—" : Number(item.experience).toLocaleString("ko-KR")}</td>
                      <td className={"history-growth-value " + (Number(item.experienceChange) > 0 ? "is-positive" : Number(item.experienceChange) < 0 ? "is-negative" : "")}>{item.experienceChange == null ? "—" : signedFmt(item.experienceChange)}</td>
                      <td>
                        {validRate ? (
                          <span className="history-level-progress-cell">
                            <span>{rate.toFixed(3)}%</span>
                            {Number.isFinite(rateChange) && (
                              <small className={"history-level-progress-change " + (
                                rateChange > 0 ? "is-positive" : rateChange < 0 ? "is-negative" : "is-neutral"
                              )}>
                                {rateChange > 0 ? "+" : rateChange < 0 ? "−" : ""}{Math.abs(rateChange).toFixed(3)}%p
                              </small>
                            )}
                          </span>
                        ) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!displayHistory.length && <p className="history-range-notice">성장 기록이 없습니다.</p>}
        </div>
      </section>
    </div>
  );
}