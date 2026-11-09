import CharacterOverview from "./CharacterOverview.jsx";
import CharacterDetails from "../../components/character/CharacterDetails.jsx";
import GrowthDashboard, { GrowthHistoryTable } from "../growth/GrowthDashboard.jsx";
import { AIReport, GrowthComparison } from "../analytics/AnalyticsAndComparison.jsx";

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
    <>
      <div id="character">
        <CharacterOverview character={character} history={history} />
      </div>
      <div id="details">
        <CharacterDetails ocid={character.ocid} onStatsLoaded={onStatsLoaded} />
      </div>
      <div id="growth">
        <GrowthDashboard
          character={character}
          history={history}
          onHistoryChange={onHistoryChange}
          onAnalysisPeriodChange={onAnalysisPeriodChange}
          onPersist={onPersist}
        />
      </div>
      <div id="analytics">
        <AIReport
          character={character}
          history={history}
          analysisHistory={analysisPeriod.history || history}
          periodDays={analysisPeriod.days}
          periodSummary={analysisPeriod.summary}
        />
      </div>
      <div id="history">
        <GrowthHistoryTable history={analysisPeriod.history || history} />
      </div>
      <div id="comparison">
        <GrowthComparison
          character={character}
          history={history}
          initialState={comparisonState}
          onSave={onPersist}
        />
      </div>
    </>
  );
}
