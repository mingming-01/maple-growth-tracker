import {
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  optionNumber,
  apiImage,
  PresetSelect,
  DataState,
  Empty,
  DetailTooltip,
  badgeGlyph
} from "./CharacterDetailsShared.jsx";

function symbolFirstValue(symbol, keys) {
  for (const key of keys) {
    if (hasValue(symbol?.[key])) return symbol[key];
  }
  return null;
}

function symbolGrowthComplete(symbol) {
  const required = optionNumber(symbol?.symbol_require_growth_count);
  const current = optionNumber(symbol?.symbol_growth_count);
  const name = String(symbol?.symbol_name || "");
  const level = Number(symbol?.symbol_level);
  const knownMaxLevel = (/아케인/.test(name) && level >= 20) ||
    (/어센틱/.test(name) && level >= 11);
  return knownMaxLevel || (
    required !== null && (required === 0 || (current !== null && current >= required))
  );
}

function extractSymbolSpecialStats(symbol) {
  const description = String(symbol?.symbol_description || "");
  const patterns = [
    ["경험치", /(?:경험치(?:\s*획득량)?|EXP)\s*[+:]?\s*(\d+(?:\.\d+)?%?)/i],
    ["드롭률", /(?:아이템\s*)?드롭률?\s*[+:]?\s*(\d+(?:\.\d+)?%?)/i],
    ["메획", /(?:메소\s*(?:획득량|증가|량)?|메획)\s*[+:]?\s*(\d+(?:\.\d+)?%?)/i]
  ];
  return patterns.map(([label, pattern]) => {
    const match = description.match(pattern);
    return match ? [label, match[1].includes("%") ? match[1] : match[1] + "%"] : null;
  }).filter(Boolean);
}

export function SymbolsTab({ data }) {
  const source = sourceOf(data, "symbolEquipment");
  const symbols = source?.currentData?.symbol || source?.data?.symbol || [];
  return (
    <div className="game-symbol-window">
      <DataState source={source} />
      {Array.isArray(symbols) && symbols.length ? (
        <div className="game-symbol-grid">
          {symbols.map((symbol, index) => {
            const stats = [
              ["STR", symbol.symbol_str], ["DEX", symbol.symbol_dex],
              ["INT", symbol.symbol_int], ["LUK", symbol.symbol_luk], ["HP", symbol.symbol_hp]
            ].filter(([, value]) => hasValue(value));
            const isGrandAuthentic = /그랜드\s*어센틱/.test(String(symbol.symbol_name || ""));
            const descriptionSpecialStats = isGrandAuthentic
              ? extractSymbolSpecialStats(symbol) : [];
            const specialStatFromDescription = label =>
              descriptionSpecialStats.find(([descriptionLabel]) => descriptionLabel === label)?.[1];
            const specialStats = isGrandAuthentic ? [
              ["경험치", symbolFirstValue(symbol, ["symbol_exp_rate", "symbol_experience_rate", "symbol_exp"])
                ?? specialStatFromDescription("경험치")],
              ["드롭률", symbolFirstValue(symbol, ["symbol_drop_rate", "symbol_item_drop_rate"])
                ?? specialStatFromDescription("드롭률")],
              ["메획", symbolFirstValue(symbol, ["symbol_meso_rate", "symbol_meso_acquisition_rate"])
                ?? specialStatFromDescription("메획")]
            ].filter(([, value]) => hasValue(value)) : [];
            const force = symbol.symbol_force;
            const maxed = symbolGrowthComplete(symbol);
            const growthLine = maxed
              ? "성장량 MAX"
              : hasValue(symbol.symbol_require_growth_count)
                ? "성장량 " + numberText(symbol.symbol_growth_count) + " / " + numberText(symbol.symbol_require_growth_count)
                : "성장량 정보 API 미제공";
            const tooltipLines = [
              symbol.symbol_description,
              hasValue(force) ? "포스 +" + numberText(force) : null,
              ...stats.map(([key, value]) => key + " +" + numberText(value)),
              ...specialStats.map(([label, value]) => label + " " +
                (String(value).includes("%") ? value : String(value) + "%")),
              growthLine,
              maxed ? "최대 레벨 달성" : hasValue(symbol.symbol_require_growth_count)
                ? "다음 레벨까지 " + numberText(Math.max(0, optionNumber(symbol.symbol_require_growth_count) - (optionNumber(symbol.symbol_growth_count) || 0))) + " 남음"
                : null
            ];
            return (
              <DetailTooltip
                as="article"
                className={"game-symbol-tile game-tooltip-trigger " + (maxed ? "is-maxed" : "")}
                key={index}
                title={symbol.symbol_name || "심볼"}
                lines={tooltipLines}
              >
                {apiImage(symbol.symbol_icon, symbol.symbol_name, "game-symbol-icon")}
                <strong className="game-symbol-name">{symbol.symbol_name || "심볼"}</strong>
                <span className="game-symbol-level">Lv. {symbol.symbol_level ?? "—"}</span>
                {hasValue(force) && <span className="game-symbol-force">포스 {numberText(force)}</span>}
                <span className={"game-symbol-growth " + (maxed ? "is-max" : "")}>{maxed ? "MAX" : growthLine}</span>
                {specialStats.length > 0 && (
                  <span className="game-symbol-special-summary">
                    {specialStats.map(([label, value]) => label + " " +
                      (String(value).includes("%") ? value : String(value) + "%")).join(" · ")}
                  </span>
                )}
              </DetailTooltip>
            );
          })}
        </div>
      ) : !source?.message && <Empty>장착된 심볼 정보가 없습니다.</Empty>}
    </div>
  );
}

export function SkillsTab({ data }) {
  const skill = sourceOf(data, "skill6");
  const hexa = sourceOf(data, "hexaMatrix");
  const hexaStat = sourceOf(data, "hexaStat");
  const skillData = skill?.data || skill?.currentData || {};
  const skills = skillData.character_skill || [];
  const hexaData = hexa?.data || hexa?.currentData || {};
  const cores = hexaData.character_hexa_core_equipment || [];
  const stats = hexaStat?.data || hexaStat?.currentData || {};
  const statGroups = [
    ["현재 HEXA 스탯", ["character_hexa_stat_core", "character_hexa_stat_core_2", "character_hexa_stat_core_3"]],
    ["저장된 HEXA 스탯", ["preset_hexa_stat_core", "preset_hexa_stat_core_2", "preset_hexa_stat_core_3"]]
  ];
  return (
    <div className="game-skill-window">
      <section className="game-sixth-skill-panel">
        <span className="game-window-eyebrow">6TH JOB</span>
        <h3 className="game-window-title">6차 스킬 · HEXA 시스템</h3>
        <div className="game-sixth-overview-grid">
          <section className="game-sixth-subpanel">
            <h4 className="game-sixth-subtitle">6차 스킬</h4>
            <div className="game-sixth-skill-grid">
              {Array.isArray(skills) && skills.length ? skills.map((item, index) => (
                <DetailTooltip
                  as="article"
                  className="game-sixth-skill-tile game-tooltip-trigger"
                  key={index}
                  title={item.skill_name || "6차 스킬"}
                  lines={[item.skill_description,item.skill_effect,item.skill_effect_next]}
                >
                  {apiImage(item.skill_icon, item.skill_name, "game-sixth-skill-icon")}
                  <strong className="game-sixth-skill-name">{item.skill_name || "스킬"}</strong>
                  <span className="game-sixth-skill-level">Lv. {item.skill_level ?? "—"}</span>
                </DetailTooltip>
              )) : <Empty>{skill?.message || "조회된 6차 스킬이 없습니다."}</Empty>}
            </div>
            <DataState source={skill} />
          </section>
          <section className="game-sixth-subpanel">
            <h4 className="game-sixth-subtitle">HEXA 매트릭스</h4>
            <div className="game-hexa-grid">
              {Array.isArray(cores) && cores.length ? cores.map((core, index) => (
                <DetailTooltip
                  as="article"
                  className="game-hexa-tile game-tooltip-trigger"
                  key={index}
                  title={core.hexa_core_name || "HEXA 코어"}
                  lines={[
                    ...(Array.isArray(core.linked_skill) ? core.linked_skill.map(item => item.hexa_skill_id) : [])
                  ]}
                >
                  <span className="game-hexa-kind">{core.hexa_core_type || "코어"}</span>
                  <strong className="game-hexa-name">{core.hexa_core_name || "HEXA 코어"}</strong>
                  <span className="game-hexa-level">Lv. {core.hexa_core_level ?? "—"}</span>
                </DetailTooltip>
              )) : <Empty>{hexa?.message || "조회된 HEXA 코어가 없습니다."}</Empty>}
            </div>
            <DataState source={hexa} />
          </section>
        </div>
      </section>
      <section className="game-hexa-stat-panel">
        <h3 className="game-window-title">HEXA 스탯</h3>
        {statGroups.map(([title, keys]) => {
          const columns = keys.map((key, index) => ({
            label: "HEXA " + (index + 1),
            rows: Array.isArray(stats[key]) ? stats[key] : []
          }));
          if (!columns.some(column => column.rows.length)) return null;
          return (
            <section className="game-hexa-stat-row" key={title}>
              <h4 className="game-hexa-stat-heading">{title}</h4>
              <div className="game-hexa-stat-columns">
                {columns.map(column => (
                  <div className="game-hexa-stat-column" key={column.label}>
                    <strong className="game-hexa-stat-column-title">{column.label}</strong>
                    {column.rows.map((row,index) => (
                      <article className="game-hexa-tile game-hexa-stat-entry" key={index}>
                        {[["주 옵션",row.main_stat_name,row.main_stat_level],
                          ["보조 1",row.sub_stat_name_1,row.sub_stat_level_1],
                          ["보조 2",row.sub_stat_name_2,row.sub_stat_level_2]].filter(([,name]) => hasValue(name)).map(([label,name,level]) => (
                          <div className="game-hexa-stat-option" key={label}>
                            <span className="game-hexa-stat-option-name">{name}</span>
                            <strong className="game-hexa-stat-option-level">Lv. {level ?? "—"}</strong>
                          </div>
                        ))}
                        {hasValue(row.stat_grade) && <span className="game-hexa-stat-grade">{row.stat_grade}</span>}
                      </article>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          );
        })}
        {!statGroups.some(([,keys]) => keys.some(key => Array.isArray(stats[key]) && stats[key].length)) &&
          <Empty>{hexaStat?.message || "HEXA 스탯 응답에 표시할 정보가 없습니다."}</Empty>}
        <DataState source={hexaStat} />
      </section>
    </div>
  );
}

export function LinkTab({ data, selected, onSelect }) {
  const source = sourceOf(data, "linkSkill");
  const number = selected.linkSkill ?? fallbackPreset(source);
  const raw = presetData(source, number);
  const equippedLinks = Array.isArray(raw.character_link_skill)
    ? raw.character_link_skill
    : Array.isArray(raw.link_skill) ? raw.link_skill : [];
  const ownedLink = raw.character_owned_link_skill;
  const ownedLinks = Array.isArray(ownedLink)
    ? ownedLink
    : ownedLink && typeof ownedLink === "object" ? [ownedLink] : [];
  const links = [...equippedLinks, ...ownedLinks];
  return (
    <div className="game-link-window">
      <div className="game-equipment-toolbar">
        <span className="game-window-eyebrow">LINK SKILL</span>
        <h3 className="game-window-title">링크 스킬</h3>
        <PresetSelect source={source} value={number} onChange={value => onSelect({ linkSkill: value })} label="링크 프리셋" />
      </div>
      <DataState source={source} />
      <div className="game-link-grid">
        {links.length ? links.map((skill,index) => (
          <DetailTooltip
            as="article"
            className="game-link-tile game-tooltip-trigger"
            key={index}
            title={skill.skill_name || "링크 스킬"}
            lines={[skill.skill_description,skill.skill_effect,skill.skill_effect_next]}
          >
            {apiImage(skill.skill_icon,skill.skill_name,"game-link-icon")}
            <strong className="game-link-name">{skill.skill_name || "링크 스킬"}</strong>
            <span className="game-link-level">Lv. {skill.skill_level ?? "—"}</span>
          </DetailTooltip>
        )) : <Empty>장착된 링크 스킬이 없습니다.</Empty>}
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
      <section className="game-union-champion-panel game-union-display">
        <div className="game-union-champion-banner">
          <span className="game-union-champion-banner-emblem" aria-hidden="true">✦</span>
          <div className="game-union-champion-banner-copy">
            <span className="game-window-eyebrow">UNION · CHAMPIONS</span>
            <h3 className="game-window-title">유니온 챔피언</h3>
            <p>등록된 챔피언과 보유한 휘장을 한눈에 확인합니다.</p>
          </div>
          <div className="game-union-champion-banner-count" aria-label={`등록된 챔피언 ${champions.length}명`}>
            <strong>{String(champions.length).padStart(2,"0")}</strong>
            <span>CHAMPIONS</span>
          </div>
        </div>
        <div className="game-union-champion-stage">
          <div className="game-union-champion-stage-lights" aria-hidden="true" />
          <div className="game-union-champion-grid">
            {champions.length ? champions.map((item,index) => {
              const level = item.character_level ?? item.champion_level ?? null;
              const championName = item.champion_name || "유니온 챔피언";
              const className = item.character_class || item.champion_class || "직업 정보 없음";
              const badgeInfo = Array.isArray(item.champion_badge_info) ? item.champion_badge_info : [];
              const grade = String(item.champion_grade || "").toLowerCase();
              return (
                <article
                  className={"game-union-champion-card"+(grade === "sss" ? " is-sss" : "")}
                  key={index}
                >
                  <div className="game-union-champion-card-head">
                    <span className={"game-union-grade-badge grade-"+grade}>{item.champion_grade || "—"}</span>
                    <span className="game-union-champion-slot">SLOT {item.champion_slot ?? index + 1}</span>
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
                    <span className="game-union-champion-podium" aria-hidden="true">
                      <span className="game-union-champion-podium-tier podium-tier-back" />
                      <span className="game-union-champion-podium-tier podium-tier-middle" />
                      <span className="game-union-champion-podium-tier podium-tier-top" />
                    </span>
                    {apiImage(item.character_image,championName,"game-union-champion-avatar-preview")}
                  </DetailTooltip>
                  <div className="game-union-champion-identity">
                    <div className="game-union-champion-identity-heading">
                      <strong className="game-union-champion-name">{championName}</strong>
                      <span className="game-union-champion-level">{hasValue(level) ? "Lv." + level : "Lv.—"}</span>
                    </div>
                    <span className="game-union-champion-class">{className}</span>
                  </div>
                  <div className="game-union-champion-badges" aria-label="챔피언 휘장">
                    {badgeInfo.map((badge,badgeIndex) => renderCrest(badge,badgeIndex,"champion-"+index))}
                  </div>
                </article>
              );
            }) : <Empty>등록된 유니온 챔피언이 없습니다.</Empty>}
          </div>
        </div>
        <div className="game-union-champion-total">
          <div className="game-union-champion-total-heading">
            <div>
              <span className="game-window-eyebrow">SHARED CRESTS</span>
              <h4 className="game-union-subtitle">전체 챔피언 휘장 효과</h4>
            </div>
            {totals.length > 0 && <span className="game-union-champion-total-count">{totals.length}개 효과</span>}
          </div>
          <div className="game-union-champion-total-list">
            {totals.length ? totals.map((item,index) => renderCrest(item,index,"total")) : <Empty>전체 휘장 효과 정보가 없습니다.</Empty>}
          </div>
        </div>
        <DataState source={champion} />
      </section>
    </div>
  );
}
