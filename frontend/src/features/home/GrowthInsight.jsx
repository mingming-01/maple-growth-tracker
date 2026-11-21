function formatTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const trillion = Number(value) / 1_000_000_000_000;
  const digits = Math.abs(trillion) >= 100 ? 0 : Math.abs(trillion) >= 10 ? 1 : 2;
  return trillion.toFixed(digits) + "조";
}

function formatDate(value) {
  if (!value) return "자료 부족";
  const parts = String(value).split("-");
  return parts.length === 3 ? parts.join(".") : String(value);
}

function buildInsight(metrics) {
  const comparison = metrics.growthComparison;
  if (metrics.observedChangeDays < 2 || comparison.direction === "insufficient_data") {
    return {
      title: "성장 기록을 모으고 있어요",
      description: "경험치 기록이 조금 더 쌓이면 최근 사냥과 성장 흐름이 어떻게 달라졌는지 알려드릴게요."
    };
  }
  if (comparison.direction === "increased") {
    return {
      title: "최근에는 경험치를 더 많이 얻었어요",
      description: `이전에는 하루 평균 ${formatTrillion(comparison.earlierAverage)}, 최근에는 ${formatTrillion(comparison.recentAverage)}의 경험치를 얻었어요.`
    };
  }
  if (comparison.direction === "decreased") {
    return {
      title: "최근에는 경험치를 조금 덜 얻었어요",
      description: `이전에는 하루 평균 ${formatTrillion(comparison.earlierAverage)}, 최근에는 ${formatTrillion(comparison.recentAverage)}의 경험치를 얻었어요. 확인된 기록끼리 비교한 결과예요.`
    };
  }
  return {
    title: "최근 성장 속도는 이전과 비슷해요",
    description: `이전과 최근의 하루 평균 경험치가 각각 ${formatTrillion(comparison.earlierAverage)}, ${formatTrillion(comparison.recentAverage)}로 비슷해요.`
  };
}

export default function GrowthInsight({ character, metrics }) {
  const authoritativeMetrics = metrics || {
    observedChangeDays: 0,
    recordedDays: 0,
    growthComparison: { direction: "insufficient_data", earlierAverage: null, recentAverage: null },
    prediction: null,
    rankingChange: null
  };
  const insight = buildInsight(authoritativeMetrics);
  const rankingChange = authoritativeMetrics.rankingChange;
  const prediction = authoritativeMetrics.prediction || null;
  const predictionDate = prediction?.estimatedDate || prediction?.date || null;
  const predictionDetail = prediction?.requiredExp != null
    ? `다음 레벨까지 남은 EXP ${formatTrillion(prediction.requiredExp)}`
    : "현재 레벨의 경험치와 진행률이 확인되면 남은 EXP를 표시할 수 있어요.";

  return (
    <aside className="mgt-growth-insight" aria-labelledby="mgt-growth-insight-title" data-testid="growth-insight">
      <div className="mgt-growth-insight-heading">
        <span className="mgt-eyebrow">GROWTH INSIGHT</span>
        <h3 className="mgt-growth-insight-overline">이번 성장 기록에서 확인한 점</h3>
        <span className="mgt-insight-record-count">확인된 성장 기록 {authoritativeMetrics.recordedDays}일</span>
      </div>
      <div className="mgt-growth-insight-copy">
        <span className="mgt-insight-spark" aria-hidden="true">✦</span>
        <h2 id="mgt-growth-insight-title">{insight.title}</h2>
        <p>{insight.description}</p>
      </div>
      <div className="mgt-growth-insight-facts">
        <div>
          <span>다음 레벨 예상</span>
          <strong>{predictionDate ? formatDate(predictionDate) : "자료 부족"}</strong>
          <small>{predictionDate ? predictionDetail : "동일 레벨의 일일 EXP 관측값이 쌓이면 예상 날짜를 계산해요."}</small>
        </div>
        <div>
          <span>종합 랭킹 변화</span>
          <strong>{rankingChange === null ? "자료 부족" : rankingChange > 0 ? `▲ ${rankingChange.toLocaleString("ko-KR")}위` : rankingChange < 0 ? `▼ ${Math.abs(rankingChange).toLocaleString("ko-KR")}위` : "변동 없음"}</strong>
          <small>저장된 랭킹 기록 기준</small>
        </div>
      </div>
      <a className="mgt-insight-link" href="#growth">성장 기록 자세히 보기 <span aria-hidden="true">→</span></a>
    </aside>
  );
}
