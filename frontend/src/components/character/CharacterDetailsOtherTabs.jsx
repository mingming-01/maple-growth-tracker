import {
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  apiImage,
  PresetSelect,
  DataState,
  Empty,
  DetailTooltip,
  badgeGlyph
} from "./CharacterDetailsShared.jsx";

export function SymbolsTab({ data }) {
  const source = sourceOf(data, "symbolEquipment");
  const payload = source?.currentData || source?.data || {};
  const symbols = Array.isArray(payload.symbol) ? payload.symbol : [];
  return (
    <div className="game-symbol-window">
      <div className="game-window-heading">
        <span className="game-window-eyebrow">SYMBOL</span>
        <h3 className="game-window-title">심볼</h3>
      </div>
      <DataState source={source} />
      <div className="game-symbol-grid">
        {symbols.length ? symbols.map((item, index) => (
          <article className="game-symbol-card" key={index}>
            <span className="game-symbol-icon">{apiImage(item.symbol_icon, item.symbol_name)}</span>
            <strong>{item.symbol_name || "심볼"}</strong>
            <span>Lv. {numberText(item.symbol_level)}</span>
            {hasValue(item.symbol_force) && <span>포스 {numberText(item.symbol_force)}</span>}
          </article>
        )) : source?.status === "available" ? <Empty>표시할 심볼이 없습니다.</Empty> : null}
      </div>
    </div>
  );
}

export function SkillsTab({ data }) {
  const skill = sourceOf(data, "skill6");
  const hexa = sourceOf(data, "hexaMatrix");
  const hexaStat = sourceOf(data, "hexaStat");
  const skillData = skill?.currentData || skill?.data || {};
  const skills = Array.isArray(skillData.character_skill) ? skillData.character_skill : [];
  const hexaData = hexa?.currentData || hexa?.data || {};
  const hexaCores = Array.isArray(hexaData.character_hexa_core_equipment)
    ? hexaData.character_hexa_core_equipment : [];
  const hexaStatData = hexaStat?.currentData || hexaStat?.data || {};
  const hexaStatCores = Array.isArray(hexaStatData.character_hexa_stat_core)
    ? hexaStatData.character_hexa_stat_core : [];

  return (
    <div className="game-skill-window">
      <div className="game-window-heading">
        <span className="game-window-eyebrow">SKILL / HEXA</span>
        <h3 className="game-window-title">6차 / HEXA</h3>
      </div>
      <DataState source={skill || hexa || hexaStat} />
      <section className="game-skill-section">
        <h4 className="game-window-title">HEXA 코어</h4>
        <div className="game-skill-grid">
          {hexaCores.length ? hexaCores.map((core, index) => (
            <article className="game-skill-card" key={"hexa-"+index}>
              <strong>{core.hexa_core_name || "HEXA 코어"}</strong>
              <span>Lv. {numberText(core.hexa_core_level)}</span>
              <span>{core.hexa_core_type || ""}</span>
            </article>
          )) : <Empty>HEXA 코어 정보가 없습니다.</Empty>}
        </div>
      </section>
      <section className="game-skill-section">
        <h4 className="game-window-title">HEXA 스탯</h4>
        <div className="game-skill-grid">
          {hexaStatCores.length ? hexaStatCores.map((core, index) => (
            <article className="game-skill-card" key={"hexastat-"+index}>
              <strong>{core.preset_no != null ? "프리셋 " + core.preset_no : "HEXA 스탯"}</strong>
              <span>{core.main_stat_name || core.stat_name || ""}</span>
              <span>Lv. {numberText(core.main_stat_level || core.stat_level)}</span>
            </article>
          )) : <Empty>HEXA 스탯 정보가 없습니다.</Empty>}
        </div>
      </section>
      <section className="game-skill-section">
        <h4 className="game-window-title">스킬</h4>
        <div className="game-skill-grid">
          {skills.length ? skills.slice(0, 40).map((item, index) => (
            <article className="game-skill-card" key={"skill-"+index}>
              <span>{apiImage(item.skill_icon, item.skill_name)}</span>
              <strong>{item.skill_name || "스킬"}</strong>
              <span>Lv. {numberText(item.skill_level)}</span>
            </article>
          )) : <Empty>스킬 정보가 없습니다.</Empty>}
        </div>
      </section>
    </div>
  );
}

export function LinkTab({ data, selected, onSelect }) {
  const source = sourceOf(data, "linkSkill");
  const presetNumber = selected.linkSkill ?? fallbackPreset(source);
  const current = presetData(source, presetNumber);
  const owned = Array.isArray(current.character_link_skill) ? current.character_link_skill
    : Array.isArray(current.link_skill) ? current.link_skill : [];
  const presetLinks = Array.isArray(current.character_owned_link_skill)
    ? current.character_owned_link_skill : [];
  const links = owned.length ? owned : presetLinks;

  return (
    <div className="game-link-window">
      <div className="game-window-heading">
        <span className="game-window-eyebrow">LINK SKILL</span>
        <h3 className="game-window-title">링크 스킬</h3>
        <PresetSelect source={source} value={presetNumber}
          onChange={value => onSelect({ linkSkill: value })} label="링크 스킬 프리셋" />
      </div>
      <DataState source={source} />
      <div className="game-link-grid">
        {links.length ? links.map((item, index) => (
          <article className="game-link-card" key={index}>
            <span>{apiImage(item.skill_icon, item.skill_name)}</span>
            <strong>{item.skill_name || "링크 스킬"}</strong>
            <span>Lv. {numberText(item.skill_level)}</span>
            {hasValue(item.skill_effect) && <small>{item.skill_effect}</small>}
          </article>
        )) : <Empty>링크 스킬 정보가 없습니다.</Empty>}
      </div>
    </div>
  );
}

export function UnionTab({ data, selected, onSelect }) {
  const base = sourceOf(data, "union")?.data || {};
  const states = sourceOf(data, "unionStateStat");
  const artifact = sourceOf(data, "unionArtifact");
  const champion = sourceOf(data, "unionChampion");
  const stateNumber = selected.union ?? fallbackPreset(states);
  const state = presetData(states,stateNumber);
  const stateRows = Array.isArray(state.union_state_stat) ? state.union_state_stat : [];
  const artifactData = artifact?.currentData || artifact?.data || {};
  const champions = champion?.currentData?.union_champion || champion?.data?.union_champion || [];
  const crystals = artifactData.union_artifact_crystal || [];
  const effects = artifactData.union_artifact_effect || [];
  const totals = champion?.currentData?.champion_badge_total_info || champion?.data?.champion_badge_total_info || [];

  const renderCrest = (badge, index, keyPrefix = "badge") => {
    const stat = badge?.stat || badge?.badge_stat || badge?.name || "휘장 효과 정보 없음";
    return (
      <DetailTooltip
        as="span"
        className="game-union-champion-crest game-tooltip-trigger"
        key={keyPrefix + "-" + index}
        title={stat}
        lines={[stat]}
      >
        <span className="game-union-champion-crest-glyph" aria-hidden="true">{badgeGlyph(stat,index)}</span>
      </DetailTooltip>
    );
  };

  return (
    <div className="game-union-window">
      <div className="game-union-summary">
        {[
          ["유니온 레벨",base.union_level],["유니온 등급",base.union_grade],
          ["아티팩트 레벨",base.union_artifact_level],["아티팩트 경험치",base.union_artifact_exp],
          ["아티팩트 포인트",base.union_artifact_point]
        ].filter(([,value]) => hasValue(value)).map(([label,value]) => (
          <div className="game-union-stat" key={label}><span>{label}</span><strong>{numberText(value)}</strong></div>
        ))}
      </div>
      <DataState source={sourceOf(data,"union")} />
      <section className="game-union-state-panel">
        <div className="game-union-section-heading">
          <span className="game-window-eyebrow">UNION STATE</span>
          <h3 className="game-window-title">유니온 스탯 투자</h3>
        </div>
        <div className="game-union-state-toolbar">
          <PresetSelect source={states} value={stateNumber} onChange={value => onSelect({union:value})} label="유니온 프리셋" />
        </div>
        <div className="game-union-state-grid">
          {stateRows.length ? stateRows.map((effect,index) => (
            <article className="game-union-state-stat" key={index}>
              <span className="game-union-state-index">{String(index+1).padStart(2,"0")}</span>
              <strong className="game-union-state-name">{effect}</strong>
            </article>
          )) : <Empty>선택한 프리셋에 표시할 스탯 효과가 없습니다.</Empty>}
        </div>
        <DataState source={states} />
      </section>
      <section className="game-union-artifact-panel">
        <div className="game-union-section-heading">
          <span className="game-window-eyebrow">UNION ARTIFACT</span>
          <h3 className="game-window-title">유니온 아티팩트</h3>
        </div>
        {hasValue(artifactData.union_artifact_remain_ap) && (
          <div className="game-union-point-card"><span>잔여 아티팩트 AP</span><strong>{numberText(artifactData.union_artifact_remain_ap)}</strong></div>
        )}
        <h4 className="game-union-subtitle">아티팩트 크리스탈</h4>
        <div className="game-union-crystal-grid">
          {crystals.length ? crystals.map((crystal,index) => (
            <article className="game-union-crystal" key={index}>
              <div className="game-union-crystal-top">
                <span className="game-union-crystal-order">{String(index+1).padStart(2,"0")}</span>
                <strong className="game-union-crystal-name">{crystal.name || "크리스탈"}</strong>
                {hasValue(crystal.level) && <span className="game-union-crystal-level">Lv. {crystal.level}</span>}
              </div>
              <span className={"game-union-crystal-status " + (String(crystal.validity_flag ?? "0") === "0" ? "is-valid" : "is-expired")}>
                {String(crystal.validity_flag ?? "0") === "0" ? "효과 적용 상태" : "만료 또는 비활성"}
              </span>
              <div className="game-union-crystal-options">
                {[1,2,3].filter(number => hasValue(crystal["crystal_option_name_"+number])).map(number => (
                  <span className="game-union-crystal-option" key={number}>{crystal["crystal_option_name_"+number]}</span>
                ))}
              </div>
              {hasValue(crystal.date_expire) && <span className="game-union-crystal-expiry">만료 예정 · {crystal.date_expire}</span>}
            </article>
          )) : <Empty>등록된 아티팩트 크리스탈이 없습니다.</Empty>}
        </div>
        <h4 className="game-union-subtitle">아티팩트 효과</h4>
        <div className="game-union-artifact-effect-grid">
          {effects.length ? effects.map((effect,index) => (
            <article className="game-union-artifact-effect" key={index}>
              <strong>{effect.name || "효과"}</strong>
              <span>{hasValue(effect.level) ? "Lv. "+effect.level : "레벨 정보 없음"}</span>
            </article>
          )) : <Empty>조회된 아티팩트 효과가 없습니다.</Empty>}
        </div>
        <DataState source={artifact} />
      </section>
      <section className="game-union-champion-panel">
        <div className="game-union-section-heading">
          <span className="game-window-eyebrow">UNION CHAMPION</span>
          <h3 className="game-window-title">유니온 챔피언</h3>
        </div>
        <div className="game-union-champion-grid">
          {champions.length ? champions.map((item,index) => {
            const level = item.character_level ?? item.champion_level ?? null;
            const championName = item.champion_name || "유니온 챔피언";
            const className = item.character_class || item.champion_class || "직업 정보 없음";
            const badgeInfo = Array.isArray(item.champion_badge_info) ? item.champion_badge_info : [];
            return (
              <article className="game-union-champion-card" key={index}>
                <div className="game-union-champion-card-head">
                  <span className={"game-union-grade-badge grade-"+String(item.champion_grade||"").toLowerCase()}>{item.champion_grade || "—"}</span>
                  <span className="game-union-champion-level">{hasValue(level) ? "Lv."+level : "Lv.—"}</span>
                </div>
                <DetailTooltip
                  as="div"
                  className="game-union-champion-avatar game-union-champion-avatar-trigger game-tooltip-trigger"
                  title={championName}
                  lines={[
                    "직업 · " + className,
                    hasValue(level) ? "레벨 · Lv. " + level : null,
                    hasValue(item.character_world_name) ? "월드 · " + item.character_world_name : null,
                    "등급 · " + (item.champion_grade || "정보 없음"),
                    hasValue(item.champion_slot) ? "챔피언 슬롯 · " + item.champion_slot : null
                  ]}
                >
                  {apiImage(item.character_image,championName,"game-union-champion-avatar-preview")}
                </DetailTooltip>
                <strong className="game-union-champion-name">{championName}</strong>
                <span className="game-union-champion-class">{className}</span>
                <div className="game-union-champion-badges" aria-label="챔피언 휘장">
                  {badgeInfo.map((badge,badgeIndex) => renderCrest(badge,badgeIndex,"champion-"+index))}
                </div>
              </article>
            );
          }) : <Empty>등록된 유니온 챔피언이 없습니다.</Empty>}
        </div>
        <h4 className="game-union-subtitle">전체 챔피언 휘장 효과</h4>
        <div className="game-union-champion-total-list">
          {totals.length ? totals.map((item,index) => renderCrest(item,index,"total")) : <Empty>전체 휘장 효과 정보가 없습니다.</Empty>}
        </div>
        <DataState source={champion} />
      </section>
    </div>
  );
}
