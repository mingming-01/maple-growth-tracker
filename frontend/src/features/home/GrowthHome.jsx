import { useMemo } from "react";
import CharacterOverview from "./CharacterOverview.jsx";
import CharacterDetails from "../../components/character/CharacterDetails.jsx";
import GrowthDashboard, { GrowthHistoryTable } from "../growth/GrowthDashboard.jsx";
import { AIReport, GrowthComparison } from "../analytics/AnalyticsAndComparison.jsx";
import { calculateGrowthMetrics } from "../../lib/growth.js";

function formatGrowth(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const amount = Number(value) / 1_000_000_000_000;
  const digits = Math.abs(amount) >= 100 ? 0 : Math.abs(amount) >= 10 ? 1 : 2;
  return (amount > 0 ? "+" : amount < 0 ? "−" : "") + Math.abs(amount).toFixed(digits) + "조";
}

function GrowthInsight({ character, history }) {
  const metrics = useMemo(() => calculateGrowthMetrics(character, history || []), [character, history]);
  const comparison = metrics.growthComparison;
  const insight = metrics.observedChangeDays === 0
    ? "성장 기록이 더 쌓이면 실제 관측 구간을 기준으로 성장 흐름을 분석합니다."
    : metrics.validGrowthDays === 0
      ? "현재 선택된 기록에서 확인된 경험치 증가 구간이 없습니다. 누락된 날짜나 레벨업 경계는 임의로 보정하지 않습니다."
      : `확인된 ${metrics.observedChangeDays}개 성장 구간에서 평균 ${formatGrowth(metrics.averageDailyGrowth)} 경험치가 증가했습니다.`;
  const trend = comparison.direction === "increased"
    ? "최근 관측 구간의 평균 성장량이 앞선 구간보다 높습니다."
    : comparison.direction === "decreased"
      ? "최근 관측 구간의 평균 성장량이 앞선 구간보다 낮습니다."
      : comparison.direction === "stable"
        ? "앞선 구간과 최근 구간의 평균 성장량이 비슷합니다."
        : "성장 속도의 변화를 비교하려면 관측 기록이 더 필요합니다.";

  return (
    <section className="mgt-growth-insight" aria-labelledby="mgt-growth-insight-title" data-testid="growth-insight">
      <div className="mgt-growth-insight__heading">
        <span className="mgt-eyebrow">GROWTH INSIGHT</span>
        <h2 id="mgt-growth-insight-title">이번 성장 기록에서 확인한 점</h2>
      </div>
      <p className="mgt-growth-insight__lead">{insight}</p>
      <div className="mgt-growth-insight__facts">
        <div><span>성장 활동일</span><strong>{metrics.validGrowthDays}일</strong></div>
        <div><span>레벨업 기록</span><strong>{metrics.levelUps.length}회</strong></div>
        <div><span>관측 구간</span><strong>{metrics.observedChangeDays}개</strong></div>
      </div>
      <p className="mgt-growth-insight__trend">{trend}</p>
      <a className="mgt-growth-insight__link" href="#history">날짜별 기록 확인 <span aria-hidden="true">→</span></a>
    </section>
  );
}

function GrowthSectionNav() {
  return (
    <nav className="mgt-growth-section-nav" aria-label="성장 화면 바로가기">
      <a href="#growth">성장 추이</a>
      <a href="#insight">성장 인사이트</a>
      <a href="#details">캐릭터 상세</a>
      <a href="#analytics">AI 리포트</a>
      <a href="#history">날짜별 기록</a>
      <a href="#comparison">캐릭터 비교</a>
    </nav>
  );
}

export default function GrowthHome({
  character,
  history,
  onStatsLoaded,
  onHistoryChange,
  onAnalysisPeriodChange,
  onPersist,
  analysisPeriod,
  comparisonState
}) {
  return (
    <div className="mgt-growth-home mgt-layout-stack">
      <div id="character" className="mgt-growth-home__profile">
        <CharacterOverview character={character} history={history} />
      </div>
      <GrowthSectionNav />
      <div id="growth" className="mgt-growth-home__dashboard">
        <GrowthDashboard
          character={character}
          history={history}
          onHistoryChange={onHistoryChange}
          onAnalysisPeriodChange={onAnalysisPeriodChange}
          onPersist={onPersist}
        />
      </div>
      <div id="insight" className="mgt-growth-home__insight">
        <GrowthInsight character={character} history={history} />
      </div>
      <div id="details" className="mgt-growth-home__details">
        <CharacterDetails ocid={character.ocid} onStatsLoaded={onStatsLoaded} />
      </div>
      <div id="analytics" className="mgt-growth-home__analytics">
        <AIReport
          character={character}
          history={history}
          analysisHistory={analysisPeriod.history || history}
          periodDays={analysisPeriod.days}
          periodSummary={analysisPeriod.summary}
        />
      </div>
      <div id="history" className="mgt-growth-home__history">
        <GrowthHistoryTable history={analysisPeriod.history || history} />
      </div>
      <div id="comparison" className="mgt-growth-home__comparison">
        <GrowthComparison
          character={character}
          history={history}
          initialState={comparisonState}
          onSave={onPersist}
        />
      </div>
    </div>
  );
}
