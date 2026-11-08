import {
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  appearanceColors,
  apiImage,
  PresetSelect,
  Empty,
  DataState,
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
          <span className="game-power-hint">
            Nexon API 기준 현재 적용 중인 전투력입니다.
          </span>
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
                <strong className="game-stat-detail-value">{item.ability_value || "효과 정보 없음"}</strong>
              </div>
            )) : <Empty>어빌리티 정보가 없습니다.</Empty>}
          </div>
          <DataState source={ability} />
        </section>
        <section className="game-stat-detail-card">
          <div className="game-stat-detail-card-header">
            <h4 className="game-window-title">하이퍼 스탯</h4>
            <PresetSelect source={hyper} value={selectedHyper} onChange={value => onSelect({ hyperStat: value })} label="하이퍼 스탯 프리셋" />
          </div>
          <div className="game-hyper-stat-list">
            {hyperRows.length ? hyperRows.map((item, index) => (
              <div className="game-hyper-stat-item" key={index}>
                <span className="game-hyper-stat-name">{item.stat_type || "스탯"}</span>
                <strong className="game-hyper-stat-level">Lv. {numberText(item.stat_level)}</strong>
                {hasValue(item.stat_increase) && <span className="game-hyper-stat-increase">{item.stat_increase}</span>}
              </div>
            )) : <Empty>투자된 하이퍼 스탯이 없습니다.</Empty>}
          </div>
          <DataState source={hyper} />
        </section>
      </section>
    </div>
  );
}

export function CosmeticsSubtab({ appearance, cashSource, selected, onSelect }) {
  const cashNumber = selected.cashItemEquipment ?? fallbackPreset(cashSource);
  const cashPreset = presetData(cashSource, cashNumber);
  const baseItems = Array.isArray(cashSource?.currentData?.cash_item_equipment_base)
    ? cashSource.currentData.cash_item_equipment_base : [];
  const cashItems = Array.isArray(cashPreset.cash_item_equipment)
    ? cashPreset.cash_item_equipment : baseItems;
  const additionalItems = Array.isArray(cashPreset.additional_cash_item_equipment)
    ? cashPreset.additional_cash_item_equipment
    : (cashSource?.currentData?.additional_cash_item_equipment_base || []);
  const hair = appearance.character_hair;
  const face = appearance.character_face;
  const skin = appearance.character_skin_name;
  const lookMode = cashSource?.currentData?.character_look_mode || cashSource?.data?.character_look_mode;

  const renderCashItem = (item, index, kind = "cash") => {
    const icon = item.cash_item_icon || item.item_icon;
    const name = item.cash_item_name || item.item_name || item.cash_item_equipment_slot || "캐시 장비";
    return (
      <article className="game-cosmetic-item" key={kind + "-" + index}>
        <span className="game-cosmetic-item-icon">{apiImage(icon, name)}</span>
        <strong>{name}</strong>
        <span>{item.cash_item_equipment_part || item.cash_item_equipment_slot || item.item_equipment_part || "캐시 아이템"}</span>
      </article>
    );
  };

  const appearanceItems = [
    ["헤어", hair?.hair_name || hair?.name || (typeof hair === "string" ? hair : null), appearanceColors(hair)],
    ["성형", face?.face_name || face?.name || (typeof face === "string" ? face : null), appearanceColors(face)],
    ["피부", skin?.skin_name || skin?.name || (typeof skin === "string" ? skin : null), []]
  ];

  return (
    <div className="game-cosmetics-panel">
      <section className="game-cosmetics-appearance">
        <div className="game-subpanel-heading">
          <span className="game-window-eyebrow">CHARACTER LOOK</span>
          <h4 className="game-window-title">헤어 · 성형 · 피부</h4>
        </div>
        <div className="game-appearance-grid">
          {appearanceItems.map(([label, name, colors]) => (
            <article className="game-appearance-item" key={label}>
              <span className="game-appearance-symbol" aria-hidden="true">{label === "헤어" ? "✂" : label === "성형" ? "◉" : "✧"}</span>
              <div>
                <span className="game-cosmetic-overline">{label}</span>
                <strong>{name || "정보 없음"}</strong>
                {colors.map(([colorLabel, value]) => (
                  <small key={colorLabel}>{colorLabel} · {value}</small>
                ))}
              </div>
            </article>
          ))}
        </div>
        <p className="game-cosmetic-note">
          Nexon Open API의 외형 정보는 헤어·성형·피부 이름과 색상 위주이며, 개별 이미지 URL은 제공하지 않습니다. 별도 게임 리소스 매핑 전에는 임의 아이콘을 붙이지 않습니다.
        </p>
      </section>
      <section className="game-cash-equipment-panel">
        <div className="game-subpanel-heading game-cash-toolbar">
          <div>
            <span className="game-window-eyebrow">CASH COORDINATION</span>
            <h4 className="game-window-title">캐시 장비 · 외형 프리셋</h4>
            <span className="game-cosmetic-overline">착용 모드 · {lookMode || "API 응답에 모드 정보 없음"}</span>
          </div>
          <PresetSelect source={cashSource} value={cashNumber}
            onChange={value => onSelect({ cashItemEquipment: value })} label="외형 장비 프리셋" />
        </div>
        <DataState source={cashSource} />
        <h5 className="game-cosmetic-list-title">
          {cashNumber ? "외형 장비 프리셋 " + cashNumber : "착용 중인 캐시 장비"}
        </h5>
        <div className="game-cosmetic-grid">
          {cashItems.length ? cashItems.map((item, index) => renderCashItem(item, index)) : <Empty>조회된 캐시 장비가 없습니다.</Empty>}
        </div>
        {additionalItems.length > 0 && (
          <>
            <h5 className="game-cosmetic-list-title">추가 착용 캐시 장비</h5>
            <div className="game-cosmetic-grid">
              {additionalItems.map((item, index) => renderCashItem(item, index, "additional"))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export function PetsSubtab({ source }) {
  const petData = source?.currentData || source?.data || {};
  const asList = value => Array.isArray(value) ? value : (value && typeof value === "object" ? [value] : []);
  const pets = [1, 2, 3].map(number => ({
    number,
    name: petData["pet_" + number + "_name"],
    nickname: petData["pet_" + number + "_nickname"],
    icon: petData["pet_" + number + "_icon"],
    description: petData["pet_" + number + "_description"],
    type: petData["pet_" + number + "_pet_type"],
    equipment: asList(petData["pet_" + number + "_equipment"]),
    autoSkill: asList(petData["pet_" + number + "_auto_skill"])
  })).filter(pet => hasValue(pet.name) || hasValue(pet.nickname) || hasValue(pet.icon));

  return (
    <section className="game-pet-panel">
      <div className="game-subpanel-heading">
        <span className="game-window-eyebrow">PET EQUIPMENT</span>
        <h4 className="game-window-title">펫 정보</h4>
      </div>
      <DataState source={source} />
      <div className="game-pet-grid">
        {pets.length ? pets.map(pet => (
          <article className="game-pet-card" key={pet.number}>
            <div className="game-pet-card-heading">
              <span className="game-pet-icon">{apiImage(pet.icon, pet.name || pet.nickname)}</span>
              <div>
                <strong>{pet.nickname || pet.name || "펫"}</strong>
                <span>{pet.name || "이름 정보 없음"}{pet.type ? " · " + pet.type : ""}</span>
              </div>
            </div>
            {hasValue(pet.description) && <p className="game-pet-description">{pet.description}</p>}
            <h5>펫 장비</h5>
            <div className="game-pet-equipment-list">
              {pet.equipment.length ? pet.equipment.map((item, index) => (
                <span key={index}>{item.item_name || item.pet_equipment_name || item.item_equipment_part || "펫 장비"}</span>
              )) : <small>장착된 펫 장비 정보가 없습니다.</small>}
            </div>
            {pet.autoSkill.length > 0 && (
              <>
                <h5>자동 스킬</h5>
                <div className="game-pet-equipment-list">
                  {pet.autoSkill.map((skill, index) => <span key={index}>{skill.skill_name || skill.skill || "자동 스킬"}</span>)}
                </div>
              </>
            )}
          </article>
        )) : <Empty>등록된 펫 정보가 없습니다.</Empty>}
      </div>
    </section>
  );
}
