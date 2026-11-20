import { useEffect, useRef, useState } from "react";
import { detectLevelUpEvents, buildExperienceChartSeries, dailyGrowthSegmentDash, cumulativeGrowthSegmentDash } from "./growthChartData.js";
import { fetchHistoryArchive } from "../../lib/historyCollection.js";
import { sortHistoryAscending, sortHistoryDescending, formatLocalISODate } from "../../lib/growth.js";
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

function createLevelUpStarPlugin(levelUpEvents) {
  return {
    id: "growthLevelUpStars",
    afterDatasetsDraw(chart) {
      const meta = chart.getDatasetMeta(0);
      const xScale = chart.scales.x;
      if (!meta?.data?.length || !xScale) return;
      const { ctx } = chart;
      let lastKnownY = null;
      ctx.save();
      levelUpEvents.forEach((isLevelUp, index) => {
        const point = meta.data[index];
        if (!point) return;
        const position = point.getProps(["x", "y"], true);
        const pointIsKnown = !point.skip && Number.isFinite(position.y);
        if (!isLevelUp) {
          if (pointIsKnown) lastKnownY = position.y;
          return;
        }

        // If EXP across the level boundary is unknown, keep the star on the
        // event date and align it to the last measured cumulative value.
        const x = xScale.getPixelForValue(index);
        const y = pointIsKnown ? position.y : lastKnownY;
        if (!Number.isFinite(x) || !Number.isFinite(y)) return;

        const outerRadius = 9;
        const innerRadius = 4;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(-Math.PI / 2);
        ctx.beginPath();
        for (let vertex = 0; vertex < 10; vertex += 1) {
          const radius = vertex % 2 === 0 ? outerRadius : innerRadius;
          const angle = vertex * Math.PI / 5;
          const px = Math.cos(angle) * radius;
          const py = Math.sin(angle) * radius;
          if (vertex === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fillStyle = "#f5c542";
        ctx.strokeStyle = "#805b00";
        ctx.lineWidth = 1.25;
        ctx.fill();
        ctx.stroke();
        ctx.restore();
        if (pointIsKnown) lastKnownY = position.y;
      });
      ctx.restore();
    }
  };
}

export async function loadGrowthPeriod(character, days, onProgress = null) {
  const normalizedDays = [30, 90].includes(Number(days)) ? Number(days) : 7;
  if (!character?.ocid || normalizedDays === 7) {
    throw new Error("기간별 성장 기록을 불러올 수 없습니다.");
  }
  const current = await fetchHistoryArchive(normalizedDays, character, {
    collect: true,
    onProgress
  });
  let previous = null;
  const previousEnd = shiftDate(current.startDate, -1);
  if (previousEnd) {
    try {
      previous = await fetchHistoryArchive(normalizedDays, character, { end: previousEnd, collect: false });
    } catch {
      previous = null;
    }
  }
  const summary = current.periodSummary
    ? {
        ...current.periodSummary,
        days: current.periodSummary.expectedSnapshots ?? normalizedDays,
        startDate: current.periodSummary.startDate || current.startDate || null,
        endDate: current.periodSummary.endDate || current.endDate || null,
        previousSummary: previous?.periodSummary || null
      }
    : null;
  return {
    days: normalizedDays,
    history: current.history || [],
    metrics: current.metrics || null,
    summary,
    rangeStatus: {
      availableDays: current.availableDays || 0,
      notReadyDays: current.notReadyDays || 0,
      notCollectedDays: current.notCollectedDays || 0,
      collection: current.collectionSummary || null
    }
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
      setFeedback("이 브라우저에 목표를 저장하지 못했어요.");
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
  const observedRate = metrics?.levelProgress?.dailyProgressRate;

  return (
    <section className="growth-goal-card" aria-labelledby="growth-goal-title">
      <div className="growth-goal-heading">
        <div>
          <span className="growth-goal-kicker">PERSONAL GOAL</span>
          <h3 id="growth-goal-title">다음 레벨 목표</h3>
          <p>목표 날짜를 정하고 실제 성장 기록과 비교합니다.</p>
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
                ? `목표일까지 ${daysRemaining}일 · 필요 ${requiredRate.toFixed(4)}%p/일 · 최근 기록 ${observedRate.toFixed(4)}%p/일. ${observedRate >= requiredRate ? "현재 속도면 목표에 도달할 수 있습니다." : "목표를 맞추려면 성장 속도를 높여야 합니다."}`
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
      <p className="growth-goal-storage-note">목표는 이 브라우저에 저장돼요. 다른 기기와는 공유되지 않으며, 알림은 사이트를 열고 캐릭터를 다시 조회할 때 확인할 수 있어요.</p>
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
    ["총 경험치 증가량",fmt(summary.growth),summary.confirmedChangeDays + "일의 경험치 변화 기준"],
    ["하루 평균 경험치",fmt(summary.averageGrowth),summary.confirmedChangeDays + "일의 기록 기준"],
    ["랭킹 변화",summary.rankingChange === null ? "자료 부족" : (summary.rankingChange > 0 ? "▲ " + summary.rankingChange + "위 상승" : summary.rankingChange < 0 ? "▼ " + Math.abs(summary.rankingChange) + "위 하락" : "변화 없음"),"첫 기록과 마지막 기록 비교"],
    ["지난 기간과 비교",comparisonPercent === null ? "비교 자료 부족" : (comparisonPercent > 0 ? "+" : "") + comparisonPercent.toFixed(1) + "%",previous ? "바로 앞선 같은 기간과 비교" : "지난 기간 기록 없음"],
    ["기록이 남은 날짜",summary.availableDays + " / " + summary.days + "일",`아직 공개되지 않은 날짜 ${summary.notReadyDays}일 · 확인하지 못한 날짜 ${summary.notCollectedDays}일`],
    ["하루 최고 경험치",fmt(summary.bestDailyGrowth),summary.bestDailyGrowthDate ? localDate(summary.bestDailyGrowthDate) : "확인된 기록 없음"],
    ["경험치를 얻은 날",summary.growthDays + "일",`변화 없음 ${summary.zeroGrowthDays}일 · 감소 ${summary.negativeGrowthDays}일`],
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
        하루 평균은 경험치 변화가 확인된 날짜를 기준으로 계산했어요. 기록이 없는 날은 0으로 보지 않고, 레벨업으로 경험치가 초기화된 날은 증가량에서 제외했어요.
      </p>
    </section>
  );
}

export default function GrowthDashboard({ character, history, metrics: serverMetrics, analysisPeriod, onHistoryChange, onAnalysisPeriodChange, onPersist }) {
  const initialState = readTrackerState() || {};
  const initialRange = [7,30,90].includes(Number(initialState.historyRange)) ? Number(initialState.historyRange) : 7;
  const [range, setRange] = useState(initialRange);
  const [displayHistory, setDisplayHistory] = useState(
    initialRange === 7 || !Array.isArray(initialState.displayHistory) ? history || [] : initialState.displayHistory
  );
  const [rangeStatus, setRangeStatus] = useState(initialState.historyRangeStatus || null);
  const [periodSummary, setPeriodSummary] = useState(initialState.periodSummary || null);
  const [periodMetrics, setPeriodMetrics] = useState(initialRange === 7 ? serverMetrics : (initialState.periodMetrics || analysisPeriod?.metrics || null));
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
    setPeriodMetrics(savedRange === 7 ? serverMetrics : (saved.periodMetrics || analysisPeriod?.metrics || null));
    setError("");
    setProgressText("");
  }, [character.ocid]);

  const metrics = range === 7 ? serverMetrics : periodMetrics;
  const levelProgress = serverMetrics?.levelProgress || metrics?.levelProgress || null;
  const prediction = metrics?.prediction || null;
  const timeline = Array.isArray(metrics?.timeline) ? metrics.timeline : [];
  const chartNoticeRecords = sortHistoryAscending(displayHistory || []).filter(
    item => item?.date && item.date <= formatLocalISODate(new Date())
  );
  const chartNoticeLevelUps = detectLevelUpEvents(chartNoticeRecords);
  const levelUpDaysWithoutDailyChange = chartNoticeRecords.filter((item, index) =>
    chartNoticeLevelUps[index] &&
    (item.experienceChange === null || item.experienceChange === undefined || item.experienceChange === "")
  ).length;

  useEffect(() => {
    let cancelled = false;
    if (!canvasRef.current) return undefined;
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }
    const today = formatLocalISODate(new Date());
    const sorted = sortHistoryAscending(displayHistory)
      .filter(item => item?.date && item.date <= today);
    if (!sorted.length) return undefined;
    const { daily, cumulative, cumulativeHasUnknownGaps } = buildExperienceChartSeries(sorted);
    const cumulativeLabel = cumulativeHasUnknownGaps ? "확인된 누적 경험치 증가량" : "총 경험치 증가량";
    // 서버가 반환한 명시적 레벨업 플래그를 우선 사용하고,
    // 레거시 응답에 플래그가 없을 때만 차트 모듈이 이전 레벨을 보완한다.
    const levelUpEvents = detectLevelUpEvents(sorted);
    // 레벨업 날짜는 누적 경험치 선의 기본 점을 별 모양으로 교체한다.
    import("chart.js/auto").then(({ default: Chart }) => {
      if (cancelled || !canvasRef.current) return;
      chartRef.current = new Chart(canvasRef.current.getContext("2d"), {
      type: "line",
      plugins: [createLevelUpStarPlugin(levelUpEvents)],
      data: {
        labels: sorted.map(item => String(item.date || "").slice(5)),
        datasets: [
          { label:cumulativeLabel,data:cumulative,yAxisID:"experience",borderColor:"#36a2eb",backgroundColor:"#36a2eb",borderWidth:3,tension:0,spanGaps:true,segment:{borderDash:context=>cumulativeGrowthSegmentDash(context,cumulative)},pointRadius:levelUpEvents.map(isLevelUp=>isLevelUp?1:3),pointHoverRadius:levelUpEvents.map(isLevelUp=>isLevelUp?2:6),pointHitRadius:levelUpEvents.map(isLevelUp=>isLevelUp?12:8),pointStyle:"circle",pointBackgroundColor:"#36a2eb",pointBorderColor:"#36a2eb",pointBorderWidth:0,fill:false },
          { label:"일일 경험치 증가량",data:daily,yAxisID:"dailyGrowth",borderColor:"#ff6384",backgroundColor:"#ff6384",borderWidth:2,segment:{borderDash:dailyGrowthSegmentDash},spanGaps:false,tension:0,pointRadius:2,pointHoverRadius:5,fill:false }
        ]
      },
      options: {
        responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:"index"},
        plugins:{legend:{display:true},tooltip:{callbacks:{
          label(context) {
            if (levelUpEvents[context.dataIndex] && context.dataset.label === cumulativeLabel) {
              const current = sorted[context.dataIndex];
              const previous = sorted.slice(0, context.dataIndex).reverse()
                .find(item => item?.level !== null && item?.level !== undefined && Number.isFinite(Number(item.level)));
              const previousLevel = current?.levelUpPreviousLevel ?? previous?.level ?? "—";
              const currentLevel = current?.levelUpCurrentLevel ?? current?.level ?? "—";
              return "⭐ 레벨업 · Lv. " + previousLevel + " → " + currentLevel + (Number.isFinite(context.parsed.y) ? " · 확인된 누적 " + context.parsed.y.toFixed(2) + "조" : " · 레벨업 당일 증가량은 확인되지 않음");
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
          experience:{type:"linear",position:"left",title:{display:true,text:cumulativeLabel},ticks:{callback:value=>Number(value).toFixed(0)+"조"}},
          dailyGrowth:{type:"linear",position:"right",beginAtZero:true,title:{display:true,text:"일일 경험치 증가량"},grid:{drawOnChartArea:false},ticks:{callback:value=>Number(value).toFixed(0)+"조"}}
        }
      }
      });
    }).catch(() => {
      if (!cancelled) setError("성장 그래프를 불러오지 못했습니다. 페이지를 새로고침해 주세요.");
    });
    return () => {
      cancelled = true;
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
        setPeriodMetrics(serverMetrics || null);
        onAnalysisPeriodChange?.({ days:7, history:history || [], summary:null, metrics:serverMetrics || null });
        onPersist?.({historyRange:7,displayHistory:history || [],historyRangeStatus:null,periodSummary:null,periodMetrics:null,growthMetrics:serverMetrics || null});
      } else {
        const loaded = await loadGrowthPeriod(character,days,setProgressText);
        const currentHistory = loaded.history || [];
        const summary = loaded.summary || null;
        setRange(days);
        setDisplayHistory(currentHistory);
        setPeriodSummary(summary);
        setPeriodMetrics(loaded.metrics || null);
        onAnalysisPeriodChange?.({ days, history:currentHistory, summary, metrics:loaded.metrics || null });
        setRangeStatus(loaded.rangeStatus || null);
        onPersist?.({
          historyRange:days,
          displayHistory:currentHistory,
          historyRangeStatus:loaded.rangeStatus || null,
          periodSummary:summary,
          periodMetrics:loaded.metrics || null
        });
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

  const daily = metrics?.latestDailyGrowth ?? null;
  const weekly = metrics?.sevenDayGrowth ?? null;
  const average = metrics?.averageDailyGrowth ?? null;
  const rankChange = metrics?.rankingChange ?? null;
  const percent = levelProgress?.currentRate ?? null;

  return (
    <div className="growth-dashboard">
      <section className="section" id="growth-summary">
        <div className="section-header">
          <h2 className="section-title">성장 요약</h2>
          <p className="section-description">기록이 남아 있는 날짜를 기준으로 경험치가 얼마나 늘었는지 보여줍니다.</p>
        </div>
        <div className="summary-grid">
          <div className="summary-card"><div className="summary-label">최근 확인된 성장량</div><div className="summary-value">{signedFmt(daily)}</div></div>
          <div className="summary-card"><div className="summary-label">랭킹 변화</div><div className="summary-value">{rankChange === null ? "자료 부족" : rankChange > 0 ? "▲ "+rankChange : rankChange < 0 ? "▼ "+Math.abs(rankChange) : "변동 없음"}</div></div>
          <div className="summary-card"><div className="summary-label">최근 7일 성장</div><div className="summary-value">{signedFmt(weekly)}</div></div>
          <div className="summary-card"><div className="summary-label">하루 평균 경험치</div><div className="summary-value">{fmt(average)}</div></div>
        </div>
      </section>

      <section className="section" id="growth-trend">
        <div className="section-header history-chart-header">
          <div><h2 className="section-title">성장 추이</h2><p className="section-description">첫날보다 경험치가 얼마나 늘었는지와 하루 단위 변화, 레벨업 기록을 보여줍니다.</p></div>
          <label className="history-range-control">기록 범위
            <select className="history-range-select" value={range} onChange={event => changeRange(Number(event.target.value))} disabled={busy}>
              <option value="7">최근 7일</option><option value="30">저장 기록 30일</option><option value="90">저장 기록 90일</option>
            </select>
          </label>
        </div>
        <p className="history-range-notice" role="status">
          {busy ? progressText || "기록을 불러오고 있습니다..." : range === 7
            ? `최근 7일 확인된 기록 ${(history || []).filter(item=>item.recordStatus==="available").length}일`
            : `최근 ${range}일 · 확인된 기록 ${rangeStatus?.availableDays ?? 0}일 · 아직 공개되지 않은 기록 ${rangeStatus?.notReadyDays ?? 0}일 · 확인하지 못한 날짜 ${rangeStatus?.notCollectedDays ?? 0}일`}
          {!busy && levelUpDaysWithoutDailyChange > 0
            ? ` · 레벨업 ${levelUpDaysWithoutDailyChange}일 · 당일 일일 EXP 증가량 미확인`
            : ""}
        </p>
        {error && !busy && <p className="history-range-notice is-warning" role="alert">{error}</p>}
        {periodSummary && range !== 7 && <PeriodSummary summary={periodSummary} previous={periodSummary.previousSummary} label={`최근 ${range}일`} />}
        <div className="chart-card"><div className="chart-wrapper"><canvas ref={canvasRef} aria-label="기간별 성장 추이 그래프" /></div></div>
        <section className="growth-timeline-section" id="growth-timeline">
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

      <section className="section growth-prediction-section" id="growth-prediction">
        <div className="section-header"><h2 className="section-title">성장 예측</h2><p className="section-description">최근 성장 기록을 기준으로 다음 레벨업을 예상합니다.</p></div>
        <div className="growth-prediction-layout">
          <div className="prediction-card">
          <div className="prediction-grid">
            <div className="prediction-item"><div className="prediction-label">다음 레벨까지</div><div className="prediction-value">{prediction?.requiredExp == null ? "자료 부족" : fmt(prediction.requiredExp) + " (" + prediction.currentRate.toFixed(3) + "%)"}</div></div>
            <div className="prediction-item"><div className="prediction-label">예상 소요</div><div className="prediction-value">{Number.isFinite(prediction?.days) ? "약 "+prediction.days.toFixed(1)+"일" : "자료 부족"}</div></div>
            <div className="prediction-item"><div className="prediction-label">예상 레벨업</div><div className="prediction-value">{prediction?.date ? localDate(formatLocalISODate(prediction.date)) : "자료 부족"}</div></div>
            <div className="prediction-item"><div className="prediction-label">최근 평균</div><div className="prediction-value">{(prediction?.averageGrowth ?? average) == null ? "자료 부족" : fmt(prediction?.averageGrowth ?? average)}</div></div>
          </div>
          <p className="prediction-note">정확한 레벨별 필요 EXP 기준이 확인되지 않아 남은 EXP·예상 소요·예상 날짜는 계산하지 않아요. 최근 평균은 일일 증가량이 확인된 날짜만 기준으로 표시해요.</p>
        </div>
          <div id="growth-goal"><GoalPanel character={character} metrics={metrics} history={history || []} /></div>
        </div>
      </section>

    </div>
  );
}

export function GrowthHistoryTable({ history }) {
  const records = Array.isArray(history) ? history : [];
  return (
    <section className="section growth-history-section" aria-labelledby="growth-history-title">
      <div className="section-header">
        <h2 className="section-title" id="growth-history-title">날짜별 성장 기록</h2>
        <p className="section-description">선택한 기간의 경험치 진행률과 랭킹 변화입니다. 진행률을 확인할 수 없는 날짜는 빈칸으로 남겨두었어요.</p>
      </div>
      <div className="history-card">
        <div className="history-table-wrapper">
          <table className="history-table" aria-label="날짜별 캐릭터 성장 기록">
            <thead>
              <tr><th scope="col">날짜</th><th scope="col">랭킹</th><th scope="col">레벨</th><th scope="col">경험치</th><th scope="col">레벨 진행률</th></tr>
            </thead>
            <tbody>
              {sortHistoryDescending(records).map(item => {
                const rate = item.experienceRate == null
                  ? null
                  : Number(String(item.experienceRate).replace("%",""));
                const rateChange = item.experienceRateChange;
                const validRate = Number.isFinite(rate) && rate >= 0 && rate <= 100;
                const experienceChange = item.experienceChange == null
                  ? null
                  : Number(item.experienceChange);
                const validExperienceChange = Number.isFinite(experienceChange);
                const experienceChangeClass = !validExperienceChange
                  ? "is-neutral"
                  : experienceChange > 0
                    ? "is-positive"
                    : experienceChange < 0
                      ? "is-negative"
                      : "is-neutral";
                const experienceChangeLabel = validExperienceChange
                  ? signedFmt(experienceChange)
                  : "자료 없음";

                return (
                  <tr key={item.date}>
                    <td data-label="날짜">{localDate(item.date)}</td>
                    <td data-label="랭킹">{item.ranking == null ? "—" : Number(item.ranking).toLocaleString("ko-KR")+"위"}</td>
                    <td data-label="레벨">{item.level == null ? "—" : "Lv. "+item.level}</td>
                    <td
                      data-label="경험치"
                      className="history-experience-value"
                      aria-label={"경험치 "+(item.experience == null ? "자료 없음" : Number(item.experience).toLocaleString("ko-KR"))+" · 경험치 증가량 "+experienceChangeLabel}
                    >
                      <span>{item.experience == null ? "—" : Number(item.experience).toLocaleString("ko-KR")}</span>
                      {validExperienceChange && (
                        <small className={"history-experience-change "+experienceChangeClass}>
                          {signedFmt(experienceChange)}
                        </small>
                      )}
                    </td>
                    <td data-label="레벨 진행률">
                      {validRate ? (
                        <span className="history-level-progress-cell">
                          <span>{rate.toFixed(3)}%</span>
                          {Number.isFinite(rateChange) && (
                            <small className={"history-level-progress-change "+(
                              rateChange > 0 ? "is-positive" : rateChange < 0 ? "is-negative" : "is-neutral"
                            )}>
                              {rateChange > 0 ? "+" : ""}{rateChange.toFixed(3)}%p
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
        {!records.length && <p className="history-range-notice">성장 기록이 없습니다.</p>}
      </div>
    </section>
  );
}
