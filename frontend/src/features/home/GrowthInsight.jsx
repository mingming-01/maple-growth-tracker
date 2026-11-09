import { useMemo } from "react";
import { calculateGrowthMetrics, formatLocalISODate } from "../../lib/growth.js";

function formatTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const trillion = Number(value) / 1_000_000_000_000;
  const digits = Math.abs(trillion) >= 100 ? 0 : Math.abs(trillion) >= 10 ? 1 : 2;
  return trillion.toFixed(digits) + "조";
}

function formatDate(value) {
  if (!value) return "자료 부족";
  const [year, month, day] = String(value).split("-");
  return year && month && day ? `${year}년 ${Number(month)}월 ${Number(day)}일` : "자료 부족";
}

function buildInsight(metrics) {
  const comparison = metrics.growthComparison;
  if (metrics.observedChangeDays < 2 || comparison.direction === "insufficient_data") {
    return {
      title: "성장 흐름을 기록하고 있어요",
      description: "서로 다른 날짜의 성장 기록이 더 쌓이면 이전 구간과 최근 구간의 변화를 비교할 수 있습니다."
    };
  }
  if (comparison.direction === "increased") {
    return {
      title: "최근 관측 구간의 성장량이 더 높아요",
      description: `앞선 구간의 일 평균 ${formatTrillion(comparison.earlierAverage)}에서 최근 구간 ${formatTrillion(comparison.recentAverage)}으로 증가했습니다.`
    };
  }
  if (comparison.direction === "decreased") {
    return {
      title: "최근 관측 구간의 성장량이 낮아졌어요",
      description: `앞선 구간의 일 평균 ${formatTrillion(comparison.earlierAverage)}에서 최근 구간 ${formatTrillion(comparison.recentAverage)}으로 바뀌었습니다. 기록된 구간만 비교한 결과입니다.`
    };
  }
  return {
    title: "두 관측 구간의 성장량이 비슷해요",
    description: `앞선 구간과 최근 구간의 일 평균이 각각 ${formatTrillion(comparison.earlierAverage)}, ${formatTrillion(comparison.recentAverage)}입니다.`
  };
}

export default function GrowthInsight({ character, history }) {
  const metrics = useMemo(
    () => calculateGrowthMetrics(character, Array.isArray(history) ? history : []),
    [character, history]
  );
  const insight = buildInsight(metrics);
  const prediction = metrics.prediction;
  const rankingChange = metrics.rankingChange;

  return (
    <aside className="mgt-growth-insight" aria-labelledby="mgt-growth-insight-title" data-testid="growth-insight">
      <div className="mgt-growth-insight-heading">
        <span className="mgt-eyebrow">GROWTH INSIGHT</span>
        <span className="mgt-insight-record-count">정상 기록 {metrics.recordedDays}일</span>
      </div>
      <div className="mgt-growth-insight-copy">
        <span className="mgt-insight-spark" aria-hidden="true">✦</span>
        <h2 id="mgt-growth-insight-title">{insight.title}</h2>
        <p>{insight.description}</p>
      </div>
      <div className="mgt-growth-insight-facts">
        <div>
          <span>다음 레벨 예상</span>
          <strong>{prediction?.estimatedDate ? formatDate(prediction.estimatedDate) : "기록 부족"}</strong>
          <small>{prediction?.estimatedDays != null ? `최근 평균 기준 약 ${prediction.estimatedDays.toFixed(1)}일` : "관측 성장량이 더 필요합니다"}</small>
        </div>
        <div>
          <span>종합 랭킹 변화</span>
          <strong>{rankingChange === null ? "자료 부족" : rankingChange > 0 ? `▲ ${rankingChange.toLocaleString("ko-KR")}위` : rankingChange < 0 ? `▼ ${Math.abs(rankingChange).toLocaleString("ko-KR")}위` : "변동 없음"}</strong>
          <small>저장된 랭킹 기록 기준</small>
        </div>
      </div>
      <a className="mgt-insight-link" href="#growth">성장 기록 자세히 보기 <span aria-hidden="true">→</span></a>
      <span className="sr-only">기준일 {formatLocalISODate(new Date())}</span>
    </aside>
  );
}
