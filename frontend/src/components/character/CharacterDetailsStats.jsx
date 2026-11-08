import {
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  DataState,
  PresetSelect,
  StatRows
} from "./CharacterDetailsShared.jsx";

export function StatsTab({ data, selected, onSelect }) {
  const stat = sourceOf(data, "stat");
  const ability = sourceOf(data, "ability");
  const hyper = sourceOf(data, "hyperStat");
  const selectedAbility = selected.ability ?? fallbackPreset(ability);
  const selectedHyper = selected.hyperStat ?? fallbackPreset(hyper);
  const power = stat?.combatPower;
  const finalStats = stat?.data?.final_stat || [];
  const importantStats = finalStats.filter(item =>
    /^(STR|DEX|INT|LUK|공격력|마력|보스 몬스터 공격 시 데미지|몬스터 방어율 무시|크리티컬 데미지|크리티컬 확률|데미지|최종 데미지|메소 획득량|아이템 드롭률|아이템 획득률|추가 경험치 획득량|경험치 획득량|일반 몬스터 공격 시 데미지|재사용 대기시간 감소|재사용 대기시간 미적용|버프 지속시간|쿨타임 감소|공격 속도|이동 속도)$/.test(String(item?.stat_name || "")) &&
    item?.stat_name !== "전투력"
  );
  const abilityData = presetData(ability, selectedAbility);
  const hyperData = presetData(hyper, selectedHyper);
  const abilityRows = Array.isArray(abilityData.ability_info) ? abilityData.ability_info : [];
  const hyperRows = Array.isArray(hyperData.hyper_stat) ? hyperData.hyper_stat.filter(item => Number(item?.stat_level) > 0) : [];

  return (
    <div className="game-stats-layout">
      <section className="game-stat-window">
        <div className="game-window-heading">
          <span className="game-window-eyebrow">CHARACTER STATUS</span>
          <h3 className="game-window-title">능력치</h3>
        </div>
        <div className="game-power-panel">
          <span className="game-power-caption">현재 적용 중인 실제 전투력</span>
          <strong className="game-power-value">{hasValue(power) ? numberText(power) : "—"}</strong>
          <span className="game-power-hint">Nexon API 기준 현재 적용 중인 전투력입니다.</span>
        </div>
        <DataState source={stat} />
        {stat?.status === "available" && <StatRows entries={importantStats} />}
        <section className="game-stat-detail-card">
          <div className="game-stat-detail-card-header">
            <h4 className="game-window-title">어빌리티</h4>
            <PresetSelect source={ability} value={selectedAbility} onChange={value => onSelect({ ability: value })} label="어빌리티 프리셋" />
          </div>
          <span className="game-stat-detail-grade">{abilityData.ability_grade || ability?.data?.ability_grade || "등급 정보 없음"}</span>
          <div className="game-stat-detail-list">
            {abilityRows.length ? abilityRows.map((item, index) => (
              <div className="game-stat-detail-row" key={index}>
                <span className="game-stat-detail-name">{item.ability_grade || "어빌리티"}</span>
                <strong>{item.ability_value || "—"}</strong>
              </div>
            )) : <p className="game-empty">표시할 어빌리티가 없습니다.</p>}
          </div>
        </section>
        <section className="game-stat-detail-card">
          <div className="game-stat-detail-card-header">
            <h4 className="game-window-title">하이퍼 스탯</h4>
            <PresetSelect source={hyper} value={selectedHyper} onChange={value => onSelect({ hyperStat: value })} label="하이퍼 스탯 프리셋" />
          </div>
          <div className="game-stat-detail-list">
            {hyperRows.length ? hyperRows.map((item, index) => (
              <div className="game-stat-detail-row" key={index}>
                <span className="game-stat-detail-name">{item.stat_type || "하이퍼 스탯"}</span>
                <strong>Lv. {item.stat_level}</strong>
              </div>
            )) : <p className="game-empty">표시할 하이퍼 스탯이 없습니다.</p>}
          </div>
        </section>
      </section>
    </div>
  );
}
