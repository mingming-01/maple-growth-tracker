import { useState } from "react";
import { getCharacter } from "./services/api.js";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "정보 없음";
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed.toLocaleString("ko-KR") : String(value);
}

function formatRanking(value) {
  if (value === null || value === undefined || value === "" || Number(value) <= 0) {
    return "집계 정보 없음";
  }
  return formatNumber(value) + "위";
}

function CharacterResult({ character }) {
  return (
    <section className="character-result" aria-label="캐릭터 조회 결과">
      <div className="character-identity">
        <div className="character-avatar">
          {character.character_image ? (
            <img
              src={character.character_image}
              alt={character.characterName + " 캐릭터 이미지"}
              referrerPolicy="no-referrer"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          ) : (
            <span aria-hidden="true">M</span>
          )}
        </div>
        <div className="character-copy">
          <span className="eyebrow">CHARACTER PROFILE</span>
          <h2>{character.characterName || "이름 정보 없음"}</h2>
          <p>
            {[character.worldName, character.job, character.guildName]
              .filter(Boolean)
              .join(" · ") || "캐릭터 기본 정보"}
          </p>
        </div>
        <div className="level-pill">
          <span>LEVEL</span>
          <strong>{formatNumber(character.level)}</strong>
        </div>
      </div>

      <div className="profile-divider" />

      <div className="profile-stats">
        <div className="profile-stat">
          <span>경험치 진행률</span>
          <strong>{character.experienceRate ?? "정보 없음"}%</strong>
          <small>현재 레벨 기준</small>
        </div>
        <div className="profile-stat">
          <span>현재 경험치</span>
          <strong>{formatNumber(character.experience)}</strong>
          <small>넥슨 Open API 응답</small>
        </div>
        <div className="profile-stat">
          <span>최고 전투력 기록</span>
          <strong>{formatNumber(character.bestCombatPower)}</strong>
          <small>관측된 실제 전투력</small>
        </div>
      </div>

      <div className="ranking-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">RANKING</span>
            <h3>캐릭터 랭킹</h3>
          </div>
          <span className="section-caption">현재 공개 데이터 기준</span>
        </div>
        <div className="ranking-grid">
          <RankingItem label="종합 랭킹" value={character.ranking} />
          <RankingItem label="월드 랭킹" value={character.worldRanking} />
          <RankingItem label="직업 · 월드" value={character.jobWorldRanking} />
          <RankingItem label="직업 전체" value={character.jobRanking} />
        </div>
      </div>
    </section>
  );
}

function RankingItem({ label, value }) {
  return (
    <div className="ranking-item">
      <span>{label}</span>
      <strong>{formatRanking(value)}</strong>
    </div>
  );
}

function App() {
  const [name, setName] = useState("");
  const [character, setCharacter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastSearched, setLastSearched] = useState("");

  async function handleSearch(event) {
    event.preventDefault();
    const query = name.trim();
    if (!query || loading) return;

    setLoading(true);
    setError("");
    setCharacter(null);

    try {
      const result = await getCharacter(query);
      setCharacter(result);
      setLastSearched(new Date().toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit"
      }));
    } catch (requestError) {
      setError(requestError instanceof Error
        ? requestError.message
        : "캐릭터 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell" data-testid="react-preview-ready">
      <header className="topbar">
        <a className="brand" href="/" aria-label="기존 Maple Growth Tracker 메인으로 이동">
          <span className="brand-mark">M</span>
          <span className="brand-name">MAPLE <b>GROWTH</b></span>
        </a>
        <nav className="topbar-links" aria-label="상단 메뉴">
          <a href="/">기존 서비스</a>
          <a href="/admin/login">관리자</a>
        </nav>
      </header>

      <main className="page-content">
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-label"><span /> PHASE 7 · REACT PREVIEW</div>
            <h1>캐릭터의 성장을<br /><em>한눈에</em> 기록하다.</h1>
            <p>
              캐릭터 정보를 불러와 성장 흐름을 살펴보는 개인 대시보드입니다.
              현재는 프런트엔드 전환의 첫 단계로 기본 프로필과 랭킹 조회를 연결했습니다.
            </p>
          </div>
          <div className="hero-ornament" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit-core">M</div>
            <span className="spark spark-one">✦</span>
            <span className="spark spark-two">✧</span>
          </div>
        </section>

        <section className="search-panel" aria-labelledby="search-title">
          <div className="search-heading">
            <div>
              <span className="eyebrow">CHARACTER SEARCH</span>
              <h2 id="search-title">모험가 찾기</h2>
            </div>
            <span className="api-indicator"><i /> NEXON OPEN API</span>
          </div>
          <form className="search-form" onSubmit={handleSearch} data-testid="react-character-search">
            <label className="sr-only" htmlFor="react-character-name">캐릭터명</label>
            <input
              id="react-character-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="조회할 캐릭터명을 입력하세요"
              autoComplete="off"
              maxLength={30}
            />
            <button type="submit" disabled={loading || !name.trim()}>
              {loading ? "조회 중..." : "캐릭터 조회"}
              <span aria-hidden="true">→</span>
            </button>
          </form>
          <div className="search-footnote">
            <span>⌕</span> 넥슨 Open API에서 제공하는 최신 공개 데이터를 조회합니다.
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
        </section>

        {loading && (
          <div className="feedback-panel" role="status">
            <span className="loading-orb" />
            캐릭터 정보를 불러오고 있습니다.
          </div>
        )}

        {character && !loading && (
          <>
            <div className="result-toolbar">
              <div><span className="live-dot" /> 조회 완료 <span className="muted">· {lastSearched}</span></div>
              <span>캐릭터 기본 정보</span>
            </div>
            <CharacterResult character={character} />
            <section className="next-stage-panel">
              <span className="eyebrow">NEXT MIGRATION</span>
              <h3>성장 기록과 캐릭터 상세 정보는 다음 단계에서 연결합니다.</h3>
              <p>
                기존 서비스의 성장 기록, AI 분석, 프리셋, 장비 툴팁은 그대로 보존되어 있습니다.
                기능별 검증이 끝나는 순서대로 이 화면에 옮길 예정입니다.
              </p>
              <a href="/">기존 전체 기능 사용하기 <span aria-hidden="true">↗</span></a>
            </section>
          </>
        )}

        {!character && !loading && !error && (
          <section className="empty-state">
            <div className="empty-emblem">✧</div>
            <span className="eyebrow">YOUR ADVENTURE LOG</span>
            <h3>성장 기록을 시작해 보세요.</h3>
            <p>캐릭터명을 검색하면 현재 레벨과 랭킹 정보를 이곳에서 확인할 수 있습니다.</p>
          </section>
        )}

        <footer className="page-footer">
          <span>MAPLE GROWTH TRACKER</span>
          <span>Powered by NEXON Open API · React Preview</span>
        </footer>
      </main>
    </div>
  );
}

export default App;