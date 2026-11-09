import {
  calculateAverageGrowth,
  calculateLevelProgress,
  sortHistoryAscending
} from "../../lib/growth.js";

const WORLD_LOGOS = {
  "스카니아":"/static/images/worlds/SCANIA.PNG",
  "베라":"/static/images/worlds/BERA.PNG",
  "루나":"/static/images/worlds/LUNA.png",
  "제니스":"/static/images/worlds/ZENITH.png",
  "크로아":"/static/images/worlds/CROA.png",
  "유니온":"/static/images/worlds/UNION.png",
  "엘리시움":"/static/images/worlds/ELYSIUM.png",
  "이노시스":"/static/images/worlds/ENOSIS.png",
  "레드":"/static/images/worlds/RED.png",
  "오로라":"/static/images/worlds/AURORA.PNG",
  "아케인":"/static/images/worlds/ARCANE.png",
  "노바":"/static/images/worlds/NOVA.png",
  "에오스":"/static/images/worlds/EOS.png",
  "헬리오스":"/static/images/worlds/HELIOS.png",
  "챌린저스":"/static/images/worlds/CHALLENGERS.png"
};

function formatNumber(value) {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("ko-KR");
}

function formatRate(value) {
  const number = Number(String(value ?? "").replace("%",""));
  return Number.isFinite(number) && number >= 0 && number <= 100 ? number : null;
}

function formatTrillion(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
  const n = Number(value) / 1_000_000_000_000;
  return (Math.abs(n) >= 100 ? n.toFixed(0) : Math.abs(n) >= 10 ? n.toFixed(1) : n.toFixed(2)) + "조";
}

function rankingFallback(status, label) {
  if (status === "not_ready") return "당일 집계 전";
  if (status === "unavailable") return "조회 실패";
  if (status === "partial") return "일부 조회 실패";
  if (status === "empty") return "최근 집계자료 없음";
  return label || "랭킹 자료 없음";
}

function RankingItem({ label, value, status }) {
  return (
    <div className="ranking-item">
      <span>{label}</span>
      <strong>{value === null || value === undefined || value === "" ? rankingFallback(status) : formatNumber(value) + "위"}</strong>
      {value === null || value === undefined || value === "" ? <small>현재 순위 미확인</small> : <small>Nexon 랭킹 API</small>}
    </div>
  );
}

function RankingStatus({ character }) {
  const status = character.rankingDataStatus;
  const rankingDate = character.rankingDate
    ? new Date(character.rankingDate + "T00:00:00+09:00").toLocaleDateString("ko-KR")
    : "";
  const dateNote = rankingDate ? " 집계 기준일 · " + rankingDate + "." : "";
  const warnings = Array.isArray(character.rankingWarnings) ? character.rankingWarnings : [];

  if (status === "available" && [character.ranking,character.worldRanking,character.jobWorldRanking,character.jobRanking].some(value => value !== null && value !== undefined)) {
    return <p className="mgt-ranking-status is-success">Nexon 공개 랭킹 데이터입니다.{dateNote}</p>;
  }

  const message = status === "not_ready"
    ? "오늘 날짜의 랭킹 집계가 아직 준비되지 않았습니다. 잠시 후 최신 정보 다시 조회를 눌러 확인해주세요."
    : status === "unavailable"
      ? "Nexon 랭킹 API 요청에 실패했습니다. 캐릭터 기본 정보는 정상 조회됐으며, 최신 정보 다시 조회로 재시도할 수 있습니다."
      : status === "partial"
        ? "일부 랭킹만 확인됐습니다. 확인된 순위만 표시하고 누락된 값은 임의로 채우지 않았습니다."
        : status === "empty"
          ? "최근 3일의 공개 랭킹 응답에 이 캐릭터의 순위가 없습니다. 집계 대상 외 캐릭터이거나 랭킹 데이터가 아직 제공되지 않았을 수 있습니다."
          : "현재 응답에서 랭킹을 확인하지 못했습니다. 최신 정보 다시 조회를 눌러 다시 확인해주세요.";

  return (
    <div className="mgt-ranking-status is-warning" role="status">
      <p>{message}{dateNote}</p>
      {warnings.length > 0 && <small>{warnings.join(" ")}</small>}
      {character.rankingApiDiagnostics && Object.keys(character.rankingApiDiagnostics).length > 0 && (
        <details className="mgt-ranking-diagnostics">
          <summary>랭킹 API 응답 상세</summary>
          <div>
            {Object.entries(character.rankingApiDiagnostics).map(([key, item]) => (
              <span key={key}>
                {({ranking:"종합",worldRanking:"월드",jobWorldRanking:"직업·월드",jobRanking:"직업"})[key] || key}
                {" · HTTP "}{item.statusCode ?? "응답 없음"}
                {" · 항목 "}{item.returnedEntries ?? "확인 불가"}건
                {item.errorCode ? " · " + item.errorCode : ""}
                {item.errorMessage ? " · " + item.errorMessage : ""}
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export default function CharacterOverview({ character, history }) {
  const rate = formatRate(character.experienceRate);
  const weeklyHistory = sortHistoryAscending(history || []).slice(-7);
  const average = calculateAverageGrowth(weeklyHistory);
  const progress = calculateLevelProgress(character,average);
  const logo = WORLD_LOGOS[character.worldName];

  return (
    <section className="mgt-profile-shell" aria-label="캐릭터 프로필">
      <div className="mgt-profile-main">
        <div className="mgt-character-identity">
          <div className="mgt-character-avatar-frame">
            {character.character_image
              ? <img className="mgt-character-avatar" src={character.character_image}
                  alt={character.characterName + " 캐릭터 아바타"}
                  referrerPolicy="no-referrer" />
              : <span className="mgt-avatar-fallback">M</span>}
          </div>
          <div className="mgt-character-copy">
            <span className="mgt-eyebrow">CHARACTER PROFILE</span>
            <h2>{character.characterName || "이름 정보 없음"}</h2>
            <div className="mgt-character-meta">
              {logo && <img src={logo} alt="" className="mgt-world-logo" />}
              <span>{character.worldName || "월드 정보 없음"}</span>
              <span>Lv. {formatNumber(character.level)}</span>
              <span>{character.job || "직업 정보 없음"}</span>
              <span>{character.guildName || "길드 없음"}</span>
            </div>
          </div>
        </div>
        <div className="mgt-profile-progress">
          <div className="mgt-progress-top">
            <div><span className="mgt-stat-label">현재 레벨 진행률</span><strong>{rate === null ? "자료 부족" : rate.toFixed(3)+"%"}</strong></div>
            <span className="mgt-progress-remaining">{rate === null ? "진행률 정보 없음" : "다음 레벨까지 "+(100-rate).toFixed(3)+"%"}</span>
          </div>
          <div className="mgt-exp-track" role="progressbar" aria-label="현재 레벨 경험치 진행률"
            aria-valuemin="0" aria-valuemax="100" aria-valuenow={rate ?? 0}>
            <span className="mgt-exp-fill" style={{width:(rate ?? 0)+"%"}} />
          </div>
          <p className="mgt-progress-note">
            {progress?.dailyProgressRate != null
              ? "최근 하루 평균 +" + progress.dailyProgressRate.toFixed(4) + "%p / 일"
              : "성장 기록이 쌓이면 하루에 레벨이 얼마나 가까워지는지 보여드려요."}
          </p>
        </div>
      </div>
      <div className="mgt-profile-side">
        <div className="mgt-eyebrow">CHARACTER SNAPSHOT</div>
        <div className="mgt-snapshot-stat"><span>현재 경험치</span><strong>{formatNumber(character.experience)}</strong></div>
        <div className="mgt-snapshot-stat"><span>주간 일일 평균 경험치</span><strong>{average === null ? "자료 부족" : formatTrillion(average)}</strong></div>
        <div className="mgt-snapshot-stat" data-testid="profile-combat-power">
          <span>전투력</span><strong>{character.currentCombatPower == null ? "정보 확인 중" : formatNumber(character.currentCombatPower)}</strong>
        </div>
      </div>
      <div className="mgt-ranking-panel">
        <div className="mgt-ranking-heading">
          <div><span className="mgt-eyebrow">RANKING</span><h3>캐릭터 랭킹</h3></div>
          <span>현재 순위</span>
        </div>
        <div className="mgt-ranking-grid">
          <RankingItem label="종합 랭킹" value={character.ranking} status={character.rankingDataStatus} />
          <RankingItem label="월드 랭킹" value={character.worldRanking} status={character.rankingDataStatus} />
          <RankingItem label="직업 · 월드" value={character.jobWorldRanking} status={character.rankingDataStatus} />
          <RankingItem label="직업 전체" value={character.jobRanking} status={character.rankingDataStatus} />
        </div>
        <RankingStatus character={character} />
      </div>
    </section>
  );
}
