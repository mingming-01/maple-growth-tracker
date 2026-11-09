import "./GrowthHome.css";
import CharacterOverview from "./CharacterOverview.jsx";
import GrowthInsight from "./GrowthInsight.jsx";
import CharacterDetails from "../../components/character/CharacterDetails.jsx";
import GrowthDashboard, { GrowthHistoryTable } from "../growth/GrowthDashboard.jsx";
import { AIReport, GrowthComparison } from "../analytics/AnalyticsAndComparison.jsx";

const PAGE_META = {
  growth: {
    eyebrow: "GROWTH ANALYSIS",
    title: "성장 분석",
    description: "레벨 진행률과 경험치 변화, 성장 추이와 목표를 확인합니다."
  },
  details: {
    eyebrow: "CHARACTER DETAILS",
    title: "캐릭터 스펙",
    description: "장비와 능력치, 프리셋 등 현재 캐릭터의 세부 스펙을 살펴봅니다."
  },
  analytics: {
    eyebrow: "AI GROWTH REPORT",
    title: "성장 리포트 분석",
    description: "저장된 성장 기록을 바탕으로 변화와 흐름을 분석합니다."
  },
  history: {
    eyebrow: "GROWTH HISTORY",
    title: "성장 기록 모아보기",
    description: "날짜별 레벨과 경험치, 실제로 확인된 성장 변화를 확인합니다."
  },
  comparison: {
    eyebrow: "CHARACTER COMPARISON",
    title: "캐릭터 성장 비교",
    description: "두 캐릭터의 최근 성장 지표와 동일 기간의 기록을 비교합니다."
  }
};

const PAGE_LINKS = [
  { route: "growth", title: "성장 분석", description: "레벨 진행률, 성장 그래프, 목표와 성장 전망" },
  { route: "details", title: "캐릭터 상세", description: "장비, 능력치, 어빌리티와 프리셋" },
  { route: "analytics", title: "AI 리포트", description: "기간별 성장 분석과 AI 인사이트" },
  { route: "history", title: "날짜별 기록", description: "수집된 날짜별 레벨·경험치 기록" },
  { route: "comparison", title: "캐릭터 비교", description: "다른 캐릭터와 성장 흐름 비교" }
];

function GrowthSectionNav({ current }) {
  return (
    <nav className="mgt-growth-route-nav" aria-label="캐릭터 화면">
      <a href="#/" aria-current={current === "overview" ? "page" : undefined}>개요</a>
      {PAGE_LINKS.map(item => (
        <a key={item.route} href={`#/${item.route}`} aria-current={current === item.route ? "page" : undefined}>
          {item.title}
        </a>
      ))}
    </nav>
  );
}

export default function GrowthHome({
  character,
  history,
  onStatsLoaded,
  onHistoryChange,
  onAnalysisPeriodChange,
  onAnalysisPeriodSelect,
  onPersist,
  analysisPeriod,
  comparisonState,
  view = "overview"
}) {
  const page = PAGE_META[view];

  return (
    <div className="mgt-growth-home mgt-layout-stack">
      <GrowthSectionNav current={view} />

      {view === "overview" && (
        <>
          <div className="mgt-growth-home-top">
            <div id="character" className="mgt-growth-home__profile">
              <CharacterOverview character={character} history={history} />
            </div>
            <div id="insight" className="mgt-growth-home__insight">
              <GrowthInsight character={character} history={history} />
            </div>
          </div>
          <section className="mgt-growth-page-index" aria-labelledby="mgt-growth-page-index-title">
            <div className="mgt-growth-page-index-heading">
              <span className="mgt-eyebrow">YOUR GROWTH SPACE</span>
              <h2 id="mgt-growth-page-index-title">무엇을 살펴볼까요?</h2>
              <p>필요한 정보만 골라 각 화면에서 자세히 확인할 수 있습니다.</p>
            </div>
            <div className="mgt-growth-page-index-grid">
              {PAGE_LINKS.map(item => (
                <a className="mgt-growth-page-card" key={item.route} href={`#/${item.route}`}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                  <span className="mgt-growth-page-card-arrow" aria-hidden="true">→</span>
                </a>
              ))}
            </div>
          </section>
        </>
      )}

      {page && (
        <header className="mgt-growth-page-heading">
          <span className="mgt-eyebrow">{page.eyebrow}</span>
          <h1>{page.title}</h1>
          <p>{page.description}</p>
        </header>
      )}

      {view === "growth" && (
        <div id="growth" className="mgt-growth-page-content" data-testid="growth-page">
          <GrowthDashboard
            character={character}
            history={history}
            onHistoryChange={onHistoryChange}
            onAnalysisPeriodChange={onAnalysisPeriodChange}
            onPersist={onPersist}
          />
        </div>
      )}

      {view === "details" && (
        <div id="details" className="mgt-growth-page-content" data-testid="details-page">
          <CharacterDetails ocid={character.ocid} onStatsLoaded={onStatsLoaded} />
        </div>
      )}

      {view === "analytics" && (
        <div id="analytics" className="mgt-growth-page-content" data-testid="analytics-page">
          <AIReport
            character={character}
            history={history}
            analysisHistory={analysisPeriod.history || history}
            periodDays={analysisPeriod.days}
            periodSummary={analysisPeriod.summary}
            onPeriodSelect={onAnalysisPeriodSelect}
          />
        </div>
      )}

      {view === "history" && (
        <div id="history" className="mgt-growth-page-content" data-testid="history-page">
          <GrowthHistoryTable history={analysisPeriod.history || history} />
        </div>
      )}

      {view === "comparison" && (
        <div id="comparison" className="mgt-growth-page-content" data-testid="comparison-page">
          <GrowthComparison
            character={character}
            history={history}
            initialState={comparisonState}
            onSave={onPersist}
          />
        </div>
      )}
    </div>
  );
}
