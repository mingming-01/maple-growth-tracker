import { readGrowthGoals, favoriteKey, MAX_FAVORITE_CHARACTERS } from "../../lib/storage.js";

export default function FavoriteCharacters({ favorites, current, onOpen, onRemove }) {
  return (
    <section className="mgt-favorites-panel">
      <div className="mgt-section-heading">
        <div><span className="mgt-eyebrow">FAVORITES</span><h2>관심 캐릭터</h2></div>
        <span>{favorites.length} / {MAX_FAVORITE_CHARACTERS}명</span>
      </div>
      {favorites.length ? (
        <div className="mgt-favorites-list">
          {favorites.map(item => {
            const goal = item.ocid ? readGrowthGoals()[item.ocid] : null;
            return (
              <article className="mgt-favorite-card" key={favoriteKey(item)}>
                <button type="button" className="mgt-favorite-open" onClick={() => onOpen(item)}>
                  <span className="mgt-favorite-star">★</span>
                  <span className="mgt-favorite-details">
                    <strong>{item.name}</strong>
                    <small>{item.worldName || "월드 정보 없음"}</small>
                    {goal && <small className="mgt-favorite-goal">{goal.completedAt ? `목표 Lv.${goal.targetLevel} 달성` : `목표 Lv.${goal.targetLevel}`}</small>}
                  </span>
                </button>
                <button type="button" className="mgt-favorite-remove" aria-label={item.name+" 관심 목록에서 제거"} onClick={() => onRemove(item)}>×</button>
              </article>
            );
          })}
        </div>
      ) : <p className="mgt-favorites-empty">관심 캐릭터를 등록하면 이곳에서 빠르게 다시 조회할 수 있습니다.</p>}
      {current && <p className="mgt-favorites-note">관심 캐릭터 목록은 기존 브라우저 저장 데이터와 공유됩니다.</p>}
    </section>
  );
}
