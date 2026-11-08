import {
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  apiImage,
  PresetSelect,
  DataState,
  Empty
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
  const skill = sourceOf(data, "skill");
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
  const union = sourceOf(data, "union");
  const raider = sourceOf(data, "unionRaider");
  const artifact = sourceOf(data, "unionArtifact");
  const champion = sourceOf(data, "unionChampion");
  const unionData = union?.currentData || union?.data || {};
  const raiderData = raider?.currentData || raider?.data || {};
  const artifactData = artifact?.currentData || artifact?.data || {};
  const championData = champion?.currentData || champion?.data || {};
  const raiderPreset = selected.unionRaider ?? fallbackPreset(raider);
  const artifactPreset = selected.unionArtifact ?? fallbackPreset(artifact);
  const raiderPresetData = presetData(raider, raiderPreset);
  const artifactPresetData = presetData(artifact, artifactPreset);
  const innerStat = Array.isArray(raiderPresetData.union_inner_stat)
    ? raiderPresetData.union_inner_stat
    : (Array.isArray(raiderData.union_inner_stat) ? raiderData.union_inner_stat : []);
  const artifacts = Array.isArray(artifactPresetData.union_artifact)
    ? artifactPresetData.union_artifact
    : (Array.isArray(artifactData.union_artifact) ? artifactData.union_artifact : []);
  const champions = Array.isArray(championData.union_champion)
    ? championData.union_champion : [];

  return (
    <div className="game-union-window">
      <div className="game-window-heading">
        <span className="game-window-eyebrow">UNION</span>
        <h3 className="game-window-title">유니온</h3>
      </div>
      <DataState source={union || raider || artifact} />
      <section className="game-union-summary">
        <div><span>유니온 레벨</span><strong>{numberText(unionData.union_level)}</strong></div>
        <div><span>유니온 등급</span><strong>{unionData.union_grade || "—"}</strong></div>
        <div><span>공격대원 수</span><strong>{numberText(unionData.union_artifact_level || raiderData.use_preset_no)}</strong></div>
      </section>
      <div className="game-union-preset-row">
        <PresetSelect source={raider} value={raiderPreset}
          onChange={value => onSelect({ unionRaider: value })} label="유니온 공격대 프리셋" />
        <PresetSelect source={artifact} value={artifactPreset}
          onChange={value => onSelect({ unionArtifact: value })} label="아티팩트 프리셋" />
      </div>
      <section className="game-union-section">
        <h4 className="game-window-title">공격대 배치 스탯</h4>
        <div className="game-union-stat-list">
          {innerStat.length ? innerStat.map((item, index) => (
            <div className="game-union-stat-item" key={index}>
              <span>{item.stat_field_id || item.stat_name || "스탯"}</span>
              <strong>{item.stat_info || item.stat_value || "—"}</strong>
            </div>
          )) : <Empty>공격대 스탯 정보가 없습니다.</Empty>}
        </div>
      </section>
      <section className="game-union-section">
        <h4 className="game-window-title">아티팩트</h4>
        <div className="game-union-artifact-list">
          {artifacts.length ? artifacts.map((item, index) => (
            <div className="game-union-artifact-item" key={index}>
              <strong>{item.name || item.artifact_name || "아티팩트"}</strong>
              <span>Lv. {numberText(item.level || item.artifact_level)}</span>
            </div>
          )) : <Empty>아티팩트 정보가 없습니다.</Empty>}
        </div>
      </section>
      <section className="game-union-section">
        <h4 className="game-window-title">챔피언</h4>
        <div className="game-union-champion-list">
          {champions.length ? champions.map((item, index) => (
            <div className="game-union-champion-item" key={index}>
              <span>{apiImage(item.champion_icon || item.character_image, item.champion_name || item.character_name)}</span>
              <strong>{item.champion_name || item.character_name || "챔피언"}</strong>
            </div>
          )) : <Empty>챔피언 정보가 없습니다.</Empty>}
        </div>
      </section>
    </div>
  );
}
