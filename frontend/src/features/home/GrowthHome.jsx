import CharacterOverview from "./CharacterOverview.jsx";
import GrowthInsight from "./GrowthInsight.jsx";
import CharacterDetails from "../../components/character/CharacterDetails.jsx";
import GrowthDashboard, { GrowthHistoryTable } from "../growth/GrowthDashboard.jsx";
import { AIReport, GrowthComparison } from "../analytics/AnalyticsAndComparison.jsx";

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
