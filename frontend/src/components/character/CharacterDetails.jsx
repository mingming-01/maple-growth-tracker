import "./CharacterDetails.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCharacterDetails } from "../../services/api.js";

const DETAIL_TABS = [
  ["stats", "스탯"],
  ["equipment", "장비"],
  ["symbols", "심볼"],
  ["skills", "6차 / HEXA"],
  ["link", "링크 스킬"],
  ["union", "유니온"]
];

const STAT_LABELS = {
  STR:"STR",DEX:"DEX",INT:"INT",LUK:"LUK",
  "보스 몬스터 공격 시 데미지":"보스 데미지",
  "몬스터 방어율 무시":"방어율 무시",
  "일반 몬스터 공격 시 데미지":"일반 몬스터 데미지"
};

const SLOT_DEFS = [
  ["반지 1","ring1"],["얼굴장식","face"],["반지 2","ring2"],["눈장식","eye"],
  ["반지 3","ring3"],["귀고리","ear"],["반지 4","ring4"],["펜던트 1","pendant1"],
  ["모자","hat"],["망토","cape"],["상의","top"],["장갑","gloves"],
  ["하의","bottom"],["신발","shoes"],["어깨장식","shoulder"],["훈장","medal"],["벨트","belt"],
  ["펜던트 2","pendant2"],["무기","weapon"],["보조무기","subweapon"],
  ["엠블렘","emblem"],["안드로이드","android"],["하트","heart"],["포켓","pocket"],["뱃지","badge"]
];

function sourceOf(data, id) {
  return data?.sources?.find(source => source.id === id) || null;
}

function presetOf(source, number) {
  return source?.presets?.find(item => Number(item.number) === Number(number)) || null;
}

function fallbackPreset(source) {
  if (!source?.presets?.length) return null;
  const active = presetOf(source, source.activePresetNo);
  return active ? active.number : source.presets[0].number;
}

function presetData(source, number) {
  return presetOf(source, number)?.data || source?.currentData || source?.data || {};
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function numberText(value) {
  if (!hasValue(value)) return "—";
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed.toLocaleString("ko-KR") : String(value);
}

const EQUIPMENT_OPTION_FIELDS = [
  ["STR", "str"], ["DEX", "dex"], ["INT", "int"], ["LUK", "luk"],
  ["최대 HP", "max_hp"], ["최대 MP", "max_mp"],
  ["공격력", "attack_power"], ["마력", "magic_power"], ["방어력", "armor"],
  ["이동 속도", "speed"], ["점프력", "jump"],
  ["보스 몬스터 공격 시 데미지", "boss_damage", "%"],
  ["몬스터 방어율 무시", "ignore_monster_armor", "%"],
  ["올스탯", "all_stat", "%"], ["데미지", "damage", "%"]
];

function optionNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(String(value).replace(/,/g, "").replace(/%/g, "").replace(/\+/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function equipmentTotalOptions(item) {
  const total = item?.item_total_option;
  let values = total && typeof total === "object" ? { ...total } : {};
  const sources = [
    ["base", "기본", item?.item_base_option],
    ["starforce", "스타포스", item?.item_starforce_option],
    ["scroll", "주문서", item?.item_etc_option],
    ["bonus", "추옵", item?.item_add_option]
  ];
  if (!Object.keys(values).length) {
    for (const [, , source] of sources) {
      if (!source || typeof source !== "object") continue;
      for (const [key, raw] of Object.entries(source)) {
        const value = optionNumber(raw);
        if (value === null) continue;
        values[key] = (optionNumber(values[key]) || 0) + value;
      }
    }
  }

  return EQUIPMENT_OPTION_FIELDS.flatMap(([label, key, suffix = ""]) => {
    const value = optionNumber(values[key]);
    if (value === null || value === 0) return [];
    const amount = (value > 0 ? "+" : "") + numberText(value) + suffix;
    const breakdown = sources.map(([sourceName, label, source]) => ({
      source: sourceName,
      label,
      value: optionNumber(source?.[key]) || 0
    }));
    return [{ label, value: amount, breakdown }];
  });
}

function equipmentPotentialOptions(item) {
  const normal = [item?.potential_option_1, item?.potential_option_2, item?.potential_option_3].filter(hasValue);
  const additional = [
    item?.additional_potential_option_1,
    item?.additional_potential_option_2,
    item?.additional_potential_option_3
  ].filter(hasValue);
  return { normal, additional };
}

function equipmentIsStarforce(item) {
  const value = optionNumber(item?.starforce ?? item?.item_starforce);
  return value !== null && value > 0;
}

function isSeedRing(item) {
  const name = String(item?.item_name || "");
  return /리스트레인트\s*링|컨티뉴어스\s*링|웨폰퍼프\s*링|리스크테이커\s*링|크라이시스\s*링|레벨퍼프\s*링|얼티메이덤\s*링/.test(name);
}

function seedRingLevel(item) {
  // 장비명에 명시된 레벨을 우선한다. 설명문 안의 다른 숫자를
  // 시드링 레벨로 오인해 표시하는 일을 막는다.
  const name = String(item?.item_name || "");
  const nameMatch = name.match(/(?:Lv\.?\s*(\d+)|(\d+)\s*레벨|레벨\s*(\d+))/i);
  const namedLevel = nameMatch?.[1] || nameMatch?.[2] || nameMatch?.[3];
  if (namedLevel) return Number(namedLevel);

  const candidates = [
    item?.ring_level,
    item?.item_base_option?.ring_level,
    item?.item_special_option?.ring_level
  ];
  const explicit = candidates.find(value => hasValue(value) && Number.isFinite(Number(value)));
  return explicit === undefined ? null : Number(explicit);
}

function equipmentCategory(key, item) {
  if (["hat", "top", "bottom", "cape", "gloves", "shoes", "shoulder"].includes(key)) return "방어구";
  if (key === "weapon") return "무기";
  if (["subweapon", "emblem"].includes(key)) return "보조 장비";
  if (/^ring|pendant|face|eye|ear|belt|pocket|badge|medal|heart/.test(key)) return "장신구";
  return item?.item_equipment_category || "장비";
}

function equipmentJobRequirement(item) {
  const base = item?.item_base_option || {};
  const value = base.base_equipment_job ?? item?.base_equipment_job ?? item?.item_equipment_job;
  if (Array.isArray(value)) return value.filter(hasValue).join(" · ");
  return hasValue(value) ? String(value) : null;
}

function appearanceColors(value) {
  if (!value || typeof value !== "object") return [];
  return [
    ["기본 색상", value.base_color],
    ["믹스 색상", value.mix_color],
    ["믹스 비율", hasValue(value.mix_rate) ? value.mix_rate + "%" : null]
  ].filter(([, item]) => hasValue(item));
}

function badgeGlyph(stat, index = 0) {
  const value = String(stat || "");
  if (/경험치/.test(value)) return "✦";
  if (/공격력|마력|보스|최종 데미지/.test(value)) return "⚔";
  if (/드롭|아이템/.test(value)) return "⬡";
  if (/메소|획득/.test(value)) return "◈";
  if (/크리티컬|데미지/.test(value)) return "✧";
  return ["✦", "⚔", "◈", "✧", "⬡"][index % 5];
}

function apiImage(url, alt, className = "") {
  if (typeof url !== "string" || !/^https:\/\//i.test(url)) return null;
  return <img className={className} src={url} alt={alt || ""} loading="lazy" referrerPolicy="no-referrer" />;
}

function PresetSelect({ source, value, onChange, label = "프리셋" }) {
  if (!source?.presets?.length) return null;
  return (
    <label className="game-preset-select-wrap">
      <span className="game-preset-select-label">{label}</span>
      <select className="game-preset-select" aria-label={label}
        value={value ?? fallbackPreset(source) ?? ""}
        onChange={event => onChange(Number(event.target.value))}>
        {source.presets.map(item => (
          <option key={item.number} value={item.number}>
            {item.number === 0 ? "현재 구성" : "프리셋 " + item.number}
          </option>
        ))}
      </select>
    </label>
  );
}

function Empty({ children = "표시할 데이터가 없습니다." }) {
  return <p className="game-empty">{children}</p>;
}

function DataState({ source }) {
  if (!source) return <Empty>이 탭에서 제공하는 데이터가 없습니다.</Empty>;
  if (source.status === "unavailable") return <Empty>{source.message || "Nexon API에서 이 정보를 조회하지 못했습니다."}</Empty>;
  if (source.status === "empty") return <Empty>{source.message || "API 응답에 표시할 데이터가 없습니다."}</Empty>;
  return null;
}

function DetailTooltip({
  title,
  lines = [],
  children,
  as = "div",
  className = "",
  tooltipContent = null,
  ...wrapperProps
}) {
  const visible = lines.filter(hasValue);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);
  const Wrapper = as;

  function updatePosition() {
    const element = triggerRef.current;
    if (!element || typeof window === "undefined") return;
    const rect = element.getBoundingClientRect();
    const width = Math.min(390, Math.max(180, window.innerWidth - 24));
    const measuredHeight = tooltipRef.current?.getBoundingClientRect().height;
    const estimatedHeight = measuredHeight || Math.min(520, Math.max(100, visible.length * 22 + 110));
    const below = window.innerHeight - rect.bottom - 20;
    const above = rect.top - 20;
    let top = below >= estimatedHeight || below >= above
      ? rect.bottom + 8
      : rect.top - estimatedHeight - 8;
    top = Math.max(12, Math.min(top, window.innerHeight - estimatedHeight - 12));
    const left = Math.max(
      12,
      Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 12)
    );
    setPosition(previous => previous &&
      Math.abs(previous.top - top) < 1 &&
      Math.abs(previous.left - left) < 1 &&
      Math.abs(previous.width - width) < 1
        ? previous
        : { top, left, width });
  }

  useEffect(() => {
    if (!open) return undefined;
    updatePosition();

    const closeOutside = event => {
      if (!triggerRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = event => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, position, visible.length, Boolean(tooltipContent)]);

  const hasTooltip = visible.length > 0 || Boolean(tooltipContent);

  return (
    <Wrapper
      {...wrapperProps}
      ref={triggerRef}
      className={className}
      data-tooltip-trigger={hasTooltip ? "true" : undefined}
      role={hasTooltip ? "button" : undefined}
      tabIndex={hasTooltip ? 0 : undefined}
      aria-label={hasTooltip ? (title ? title + " 상세 정보" : "상세 정보") : undefined}
      aria-expanded={hasTooltip ? open : undefined}
      onPointerEnter={event => {
        if (hasTooltip && event.pointerType === "mouse") setOpen(true);
      }}
      onPointerLeave={event => {
        if (hasTooltip && event.pointerType === "mouse") setOpen(false);
      }}
      onPointerDown={event => {
        if (hasTooltip && event.pointerType === "touch") {
          setOpen(value => !value);
        }
      }}
      onBlur={() => setOpen(false)}
      onKeyDown={event => {
        if (hasTooltip && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          setOpen(value => !value);
        }
      }}
    >
      {children}
      {open && position && createPortal(
        <div
          ref={tooltipRef}
          className="game-floating-tooltip"
          role="tooltip"
          style={{ top: position.top, left: position.left, width: position.width }}
        >
          {tooltipContent || (
            <>
              {title && <strong>{title}</strong>}
              {visible.map((line, index) => <p key={index}>{line}</p>)}
            </>
          )}
        </div>,
        document.body
      )}
    </Wrapper>
  );
}

function StatRows({ entries }) {
  const valid = (entries || []).filter(item => hasValue(item?.stat_name) && hasValue(item?.stat_value));
  if (!valid.length) return <Empty>표시할 능력치가 없습니다.</Empty>;
  return (
    <div className="game-stat-grid">
      {valid.map((item, index) => (
        <div className="game-stat-tile" key={item.stat_name + index}>
          <span className="game-stat-name">{STAT_LABELS[item.stat_name] || item.stat_name}</span>
          <strong className="game-stat-number">{item.stat_name === "전투력" ? numberText(item.stat_value) : item.stat_value}</strong>
        </div>
      ))}
    </div>
  );
}

function StatsTab({ data, selected, onSelect }) {
  const stat = sourceOf(data, "stat");
  const ability = sourceOf(data, "ability");
  const hyper = sourceOf(data, "hyperStat");
  const selectedAbility = selected.ability ?? fallbackPreset(ability);
  const selectedHyper = selected.hyperStat ?? fallbackPreset(hyper);
  const power = stat?.combatPower;
  const best = data.bestCombatPower;
  const recommendations = data.profileRecommendations || {};

  const applyProfile = mode => {
    const selectedNumbers = mode === "highest" ? data.bestPresetCombination
      : mode === "boss" || mode === "hunting" ? recommendations[mode]?.presetNumbers
      : data.actualPresetNumbers;
    if (selectedNumbers && typeof selectedNumbers === "object") onSelect(selectedNumbers);
  };

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
            {hasValue(best) ? "사이트가 관측한 최고 전투력 " + numberText(best) : "상세 스탯 조회 시 실제 전투력 기록을 갱신합니다."}
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

function CosmeticsSubtab({ appearance, cashSource, selected, onSelect }) {
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

function PetsSubtab({ source }) {
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

function EquipmentTab({ data, selected, onSelect }) {
  const [subTab, setSubTab] = useState("equipment");
  const equipment = sourceOf(data, "itemEquipment");
  const appearanceSource = sourceOf(data, "characterAppearance");
  const androidSource = sourceOf(data, "androidEquipment");
  const cashSource = sourceOf(data, "cashItemEquipment");
  const petSource = sourceOf(data, "petEquipment");
  const setSource = sourceOf(data, "setEffect");
  const presetNumber = selected.equipment ?? fallbackPreset(equipment);
  const current = presetData(equipment, presetNumber);
  const items = Array.isArray(current.item_equipment) ? current.item_equipment : [];
  const appearance = { ...(appearanceSource?.data || {}), ...(appearanceSource?.currentData || {}) };
  const android = { ...(androidSource?.data || {}), ...(androidSource?.currentData || {}) };
  const seedRings = items.filter(isSeedRing);

  const findSlotItem = (slot, key) => {
    if (/^ring[1-4]$/.test(key)) {
      const rings = items.filter(item => /반지/.test(String(item.item_equipment_slot || item.item_equipment_part || "")));
      const number = Number(key.slice(-1));
      return rings.find(item => new RegExp("반지\\s*" + number).test(String(item.item_equipment_slot || ""))) || rings[number - 1] || null;
    }
    if (key === "pendant1" || key === "pendant2") {
      const list = items.filter(item => /펜던트/.test(String(item.item_equipment_slot || item.item_equipment_part || "")));
      return list[key === "pendant1" ? 0 : 1] || null;
    }
    const aliases = { android: ["안드로이드"], heart: ["기계 심장", "하트"], pocket: ["포켓 아이템", "포켓"] };
    const candidates = aliases[key] || [slot];
    return items.find(item => candidates.includes(String(item.item_equipment_slot || item.item_equipment_part || ""))) || null;
  };

  const sets = setSource?.currentData?.set_effect || setSource?.data?.set_effect || [];
  const isActive = equipment?.activePresetNo != null && Number(equipment.activePresetNo) === Number(presetNumber);
  const presetSets = Array.isArray(current.set_effect) ? current.set_effect
    : Array.isArray(current.item_set_effect) ? current.item_set_effect : [];

  return (
    <div className="game-equipment-layout">
      <div className="game-equipment-toolbar">
        <span className="game-window-eyebrow">EQUIPMENT</span>
        <h3 className="game-window-title">장비 · 치장 · 펫</h3>
      </div>
      <div className="game-equipment-subtabs" role="tablist" aria-label="장비 상세 구분">
        {[
          ["equipment", "장비"],
          ["cosmetics", "치장"],
          ["pets", "펫"]
        ].map(([value, label]) => (
          <button type="button" role="tab" key={value} aria-selected={subTab === value}
            className={subTab === value ? "is-active" : ""} onClick={() => setSubTab(value)}>{label}</button>
        ))}
      </div>
      {subTab === "equipment" && <>
        <div className="game-equipment-preset-toolbar">
          <PresetSelect source={equipment} value={presetNumber}
            onChange={value => onSelect({ equipment: value })} label="장비 프리셋" />
        </div>
        <DataState source={equipment} />
        <div className="game-equipment-board react-equipment-board">
          {SLOT_DEFS.map(([slotName, key]) => {
            const item = findSlotItem(slotName, key);
            const androidName = android.android_name || android.android_nickname || "";
            const isAndroid = key === "android" && (androidName || android.android_icon);
            const iconUrl = isAndroid ? android.android_icon : item?.item_icon;
            const title = isAndroid ? androidName || "안드로이드" : item?.item_name || "";
            const totalOptions = item ? equipmentTotalOptions(item) : [];
            const potentialOptions = item ? equipmentPotentialOptions(item) : { normal: [], additional: [] };
            const requiredLevel = optionNumber(item?.item_base_option?.base_equipment_level);
            const levelIncrease = optionNumber(item?.equipment_level_increase);
            const requiredJob = equipmentJobRequirement(item);
            const part = item?.item_equipment_part || item?.item_equipment_slot || slotName;
            const category = equipmentCategory(key, item);
            const starforce = optionNumber(item?.starforce ?? item?.item_starforce);
            const hasStarforce = equipmentIsStarforce(item);
            const isSeedRingItem = isSeedRing(item);
            const ringLevel = isSeedRingItem ? seedRingLevel(item) : null;
            const companionRings = isSeedRingItem ? seedRings.filter(ring => ring !== item) : [];
            const tooltipLines = item ? [
              ...totalOptions.map(option => option.label + " " + option.value),
              ...potentialOptions.normal,
              ...potentialOptions.additional
            ] : isAndroid ? [
              android.android_grade, android.android_gender, android.android_description,
              android.android_hair?.hair_name, android.android_face?.face_name, android.android_skin_name
            ] : [];
            const tooltipContent = item ? (
              <div className="game-equipment-tooltip">
                <div className="game-equipment-tooltip-topline">
                  <div className="game-equipment-tooltip-requirements">
                    <span>착용 직업 {requiredJob || "제한 정보 API 미제공"}</span>
                    <span>{requiredLevel ? "요구 레벨 Lv. " + requiredLevel + (levelIncrease ? " (+" + levelIncrease + ")" : "") : "요구 레벨 정보 API 미제공"}</span>
                  </div>
                  <span>{category} · {part}</span>
                </div>
                {hasStarforce && <span className="game-equipment-tooltip-star">★ {starforce}</span>}
                <div className="game-equipment-tooltip-heading">
                  {apiImage(item.item_icon, title, "game-equipment-tooltip-icon")}
                  <div className="game-equipment-tooltip-title-wrap">
                    <strong>{title || slotName}</strong>
                    <span className="game-equipment-tooltip-meta">
                      {requiredLevel ? "요구 레벨 Lv. " + requiredLevel + (levelIncrease ? " (+" + levelIncrease + ")" : "") : "현재 장착 장비"}
                      {isSeedRingItem && ringLevel ? " · 시드링 Lv. " + ringLevel : ""}
                    </span>
                  </div>
                </div>
                {isSeedRingItem && seedRings.length > 1 && (
                  <div className="game-equipment-tooltip-rings">
                    <strong>시드링 구성</strong>
                    <div>
                      {seedRings.map((ring, index) => (
                        <span key={index}>
                          {apiImage(ring.item_icon, ring.item_name || "시드링", "game-equipment-tooltip-ring-icon")}
                          <em>{ring.item_name || "시드링"}{seedRingLevel(ring) ? " · Lv. " + seedRingLevel(ring) : ""}</em>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="game-equipment-tooltip-section">
                  <div className="game-equipment-tooltip-section-title">
                    <strong>스탯</strong><span>합계와 구성 수치</span>
                  </div>
                  <div className="game-equipment-tooltip-total">
                    {totalOptions.length ? totalOptions.map(option => (
                      <div className="game-equipment-tooltip-stat" key={option.label}>
                        <span>{option.label}</span>
                        <div className="game-equipment-tooltip-stat-values">
                          <b>{option.value}</b>
                          {option.breakdown.filter(part => part.value !== 0).length > 0 && (
                            <small className="game-equipment-tooltip-stat-breakdown">
                              ({option.breakdown.filter(part => part.value !== 0).map((part,index) => {
                                const value = Number(part.value);
                                if (index === 0) return numberText(value);
                                return value < 0
                                  ? "− " + numberText(Math.abs(value))
                                  : "+ " + numberText(value);
                              }).join(" ")})
                            </small>
                          )}
                        </div>
                      </div>
                    )) : <p className="game-equipment-tooltip-empty">합산 옵션 정보가 없습니다.</p>}
                  </div>
                </div>
                <div className="game-equipment-tooltip-potential">
                  <div className="game-equipment-tooltip-section-title">
                    <strong>잠재능력</strong>
                    <span>{item.potential_option_grade || "등급 정보 없음"}</span>
                  </div>
                  {potentialOptions.normal.length ? (
                    <div className="game-equipment-tooltip-potential-group">
                      <span className="game-equipment-tooltip-subtitle">잠재 옵션</span>
                      {potentialOptions.normal.map((value, optionIndex) => (
                        <p key={optionIndex}><i />{value}</p>
                      ))}
                    </div>
                  ) : null}
                  {potentialOptions.additional.length ? (
                    <div className="game-equipment-tooltip-potential-group is-additional">
                      <span className="game-equipment-tooltip-subtitle">에디셔널 잠재 옵션 · {item.additional_potential_option_grade || "등급 정보 없음"}</span>
                      {potentialOptions.additional.map((value, optionIndex) => (
                        <p key={optionIndex}><i />{value}</p>
                      ))}
                    </div>
                  ) : null}
                  {!potentialOptions.normal.length && !potentialOptions.additional.length
                    ? <p className="game-equipment-tooltip-empty">잠재능력 정보가 없습니다.</p> : null}
                </div>
              </div>
            ) : isAndroid ? (
              <div className="game-equipment-tooltip">
                <div className="game-equipment-tooltip-topline">
                  <span>안드로이드</span>
                  <span>{android.android_grade || "등급 정보 없음"}</span>
                </div>
                <div className="game-equipment-tooltip-heading">
                  {apiImage(android.android_icon, title, "game-equipment-tooltip-icon")}
                  <div className="game-equipment-tooltip-title-wrap"><strong>{title}</strong>
                    <span className="game-equipment-tooltip-meta">{android.android_gender || "성별 정보 없음"}</span>
                  </div>
                </div>
                {hasValue(android.android_description) && <p>{android.android_description}</p>}
                {hasValue(android.android_ear_sensor) && <p>이어 센서 · {String(android.android_ear_sensor)}</p>}
                {hasValue(android.android_non_humanoid) && <p>비인간형 · {String(android.android_non_humanoid)}</p>}
                {hasValue(android.android_hair?.hair_name) && <p>헤어 · {android.android_hair.hair_name}</p>}
                {hasValue(android.android_face?.face_name) && <p>성형 · {android.android_face.face_name}</p>}
                {hasValue(android.android_skin_name) && <p>피부 · {String(android.android_skin_name)}</p>}
              </div>
            ) : null;
            return (
              <DetailTooltip
                as="article"
                className={"equipment-game-slot game-tooltip-trigger " + (item || isAndroid ? "is-equipped" : "is-empty")}
                data-slot={key}
                key={key}
                style={{ gridArea: equipmentGridArea(key) }}
                title={title || slotName}
                lines={tooltipLines}
                tooltipContent={tooltipContent}
              >
                <span className="equipment-slot-caption">{slotName}</span>
                <span className="equipment-game-icon-frame">
                  {apiImage(iconUrl, title || slotName)}
                  {!iconUrl && <span className="equipment-empty-icon">+</span>}
                  {isSeedRingItem && ringLevel && <span className="equipment-game-ring-level">Lv.{ringLevel}</span>}
                  {isSeedRingItem && companionRings.length > 0 && (
                    <span className="equipment-ring-companion-count" title={"함께 착용한 시드링 " + companionRings.length + "개"}>
                      +{companionRings.length}
                    </span>
                  )}
                </span>
                <strong className="equipment-game-item-name">{title || "비어 있음"}</strong>
                {hasStarforce && <span className="equipment-game-star">★ {starforce}</span>}
              </DetailTooltip>
            );
          })}
        </div>
        <section className="game-set-effects">
          <div className="game-subpanel-heading">
            <h3 className="game-window-title">세트 효과</h3>
            <span className="game-cosmetic-overline">{isActive ? "활성 장비 프리셋 " + presetNumber : "비활성 장비 프리셋 " + presetNumber}</span>
          </div>
          {isActive && Array.isArray(sets) && sets.length ? (
            <div className="game-set-grid">
              {sets.map((set, index) => (
                <div className="game-set-item" key={index}>
                  <strong>{set.set_name || "세트"}</strong>
                  <span>{hasValue(set.total_set_count) ? set.total_set_count + "개 부위 적용" : "적용 부위 수 미제공"}</span>
                </div>
              ))}
            </div>
          ) : presetSets.length ? (
            <div className="game-set-grid">
              {presetSets.map((set, index) => (
                <div className="game-set-item" key={index}>
                  <strong>{set.set_name || "세트"}</strong>
                  <span>{hasValue(set.total_set_count) ? set.total_set_count + "개 부위 적용" : "적용 부위 수 미제공"}</span>
                </div>
              ))}
            </div>
          ) : !isActive && items.some(item => hasValue(item.item_set_name)) ? (
            <div className="game-set-grid">
              {[...new Set(items.map(item => item.item_set_name).filter(hasValue))].map(name => (
                <div className="game-set-item" key={name}>
                  <strong>{name}</strong>
                  <span>{items.filter(item => item.item_set_name === name).length}개 부위 확인 · 효과 수치 미제공</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="game-set-unavailable">
              {isActive
                ? setSource?.message || "현재 적용 장비의 세트 효과를 조회할 수 없습니다."
                : "세트 효과 API는 현재 적용 중인 장비 기준으로 응답합니다. 선택 프리셋의 원본 정보에 포함되지 않은 효과는 임의 계산하지 않습니다."}
            </p>
          )}
        </section>
      </>}
      {subTab === "cosmetics" && (
        <>
          <DataState source={appearanceSource} />
          <CosmeticsSubtab appearance={appearance} cashSource={cashSource} selected={selected} onSelect={onSelect} />
        </>
      )}
      {subTab === "pets" && <PetsSubtab source={petSource} />}
    </div>
  );
}

function equipmentGridArea(key) {
  const map = {
    ring1:"1 / 1 / 2 / 2",face:"1 / 2 / 2 / 3",ring2:"2 / 1 / 3 / 2",eye:"2 / 2 / 3 / 3",
    ring3:"3 / 1 / 4 / 2",ear:"3 / 2 / 4 / 3",ring4:"4 / 1 / 5 / 2",pendant1:"4 / 2 / 5 / 3",
    hat:"1 / 6 / 2 / 7",cape:"1 / 7 / 2 / 8",top:"2 / 6 / 3 / 7",gloves:"2 / 7 / 3 / 8",
    bottom:"3 / 6 / 4 / 7",shoes:"3 / 7 / 4 / 8",hair:"4 / 3 / 5 / 4",faceStyle:"4 / 4 / 5 / 5",
    skin:"4 / 5 / 5 / 6",shoulder:"4 / 6 / 5 / 7",medal:"4 / 7 / 5 / 8",
    belt:"5 / 1 / 6 / 2",pendant2:"5 / 2 / 6 / 3",weapon:"5 / 3 / 6 / 4",
    subweapon:"5 / 4 / 6 / 5",emblem:"5 / 5 / 6 / 6",android:"5 / 6 / 6 / 7",
    heart:"5 / 7 / 6 / 8",pocket:"6 / 1 / 7 / 2",badge:"6 / 7 / 7 / 8"
  };
  return map[key] || "auto";
}

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

function SymbolsTab({ data }) {
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

function SkillsTab({ data }) {
  const skill = sourceOf(data, "skill6");
  const hexa = sourceOf(data, "hexaMatrix");
  const hexaStat = sourceOf(data, "hexaStat");
  const skills = skill?.data?.character_skill || [];
  const cores = hexa?.data?.character_hexa_core_equipment || [];
  const stats = hexaStat?.data || {};
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

function LinkTab({ data, selected, onSelect }) {
  const source = sourceOf(data, "linkSkill");
  const number = selected.link ?? fallbackPreset(source);
  const raw = presetData(source, number);
  const links = [
    ...(Array.isArray(raw.character_link_skill) ? raw.character_link_skill : []),
    ...(raw.character_owned_link_skill ? [raw.character_owned_link_skill] : [])
  ];
  return (
    <div className="game-link-window">
      <div className="game-equipment-toolbar">
        <span className="game-window-eyebrow">LINK SKILL</span>
        <h3 className="game-window-title">링크 스킬</h3>
        <PresetSelect source={source} value={number} onChange={value => onSelect({ link: value })} label="링크 프리셋" />
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

function UnionTab({ data, selected, onSelect }) {
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

export default function CharacterDetails({ ocid, onStatsLoaded }) {
  const [tab, setTab] = useState("stats");
  const [cache, setCache] = useState({});
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setTab("stats");
    setCache({});
    setData(null);
    setSelected({});
    setError("");
    setNotice("");
  }, [ocid]);

  useEffect(() => {
    if (!ocid) return;
    const key = ocid + ":" + tab;
    const cached = cache[key];
    let cancelled = false;
    if (cached) {
      setData(cached);
      setError("");
      setLoading(false);
      if (tab === "stats") onStatsLoaded?.(cached);
      return () => { cancelled = true; };
    }

    setData(null);
    setLoading(true);
    setError("");
    setNotice("");
    getCharacterDetails(ocid, tab)
      .then(result => {
        if (cancelled) return;
        setData(result);
        setCache(previous => ({ ...previous, [key]: result }));
        if (tab === "stats") onStatsLoaded?.(result);
        if (result.status === "partial") setNotice("일부 공개 데이터만 확인됐습니다. 조회되지 않은 항목은 임의로 채우지 않았습니다.");
        else setNotice("Nexon Open API에서 제공하는 공개 데이터를 표시합니다. 게임 내 변경 사항은 API 반영 시점과 다를 수 있습니다.");
      })
      .catch(requestError => {
        if (!cancelled) setError(requestError.message || "캐릭터 상세 정보를 불러오지 못했습니다.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ocid, tab, cache, onStatsLoaded]);

  const changePreset = patch => setSelected(previous => ({ ...previous, ...patch }));

  async function refresh() {
    if (!ocid) return;
    setLoading(true);
    setError("");
    try {
      const result = await getCharacterDetails(ocid, tab, { refresh: true });
      setData(result);
      setCache(previous => ({ ...previous, [ocid + ":" + tab]: result }));
      if (tab === "stats") onStatsLoaded?.(result);
    } catch (requestError) {
      setError(requestError.message || "상세 정보를 새로고침하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  if (!ocid) return null;

  return (
    <section className="section character-details-section react-character-details" aria-labelledby="react-detail-title">
      <div className="section-header character-details-header">
        <div>
          <h2 className="section-title" id="react-detail-title">캐릭터 상세 정보</h2>
          <p className="section-description">능력치·장비·심볼·6차 스킬·링크·유니온 데이터를 게임 정보창 형태로 확인합니다.</p>
        </div>
        <button type="button" className="export-button" onClick={refresh} disabled={loading}>선택 탭 새로고침</button>
      </div>
      <div className="detail-tabs" role="tablist" aria-label="캐릭터 상세 정보 구분">
        {DETAIL_TABS.map(([value,label]) => (
          <button key={value} type="button" role="tab" data-detail-tab={value}
            aria-selected={tab === value} className={"detail-tab " + (tab === value ? "is-active" : "")}
            onClick={() => setTab(value)}>{label}</button>
        ))}
      </div>
      {notice && <p className="detail-notice" role="status">{notice}</p>}
      {error && <p className="detail-notice is-warning" role="alert">{error}</p>}
      {loading && <div className="game-loading-window" role="status">캐릭터 {DETAIL_TABS.find(item=>item[0]===tab)?.[1] || "정보"} 조회 중...</div>}
      {!loading && data && (
        <div className="character-details-content">
          {tab === "stats" && <StatsTab data={data} selected={selected} onSelect={changePreset} />}
          {tab === "equipment" && <EquipmentTab data={data} selected={selected} onSelect={changePreset} />}
          {tab === "symbols" && <SymbolsTab data={data} />}
          {tab === "skills" && <SkillsTab data={data} />}
          {tab === "link" && <LinkTab data={data} selected={selected} onSelect={changePreset} />}
          {tab === "union" && <UnionTab data={data} selected={selected} onSelect={changePreset} />}
        </div>
      )}
      {!loading && !data && !error && <Empty>캐릭터 상세 정보를 준비하고 있습니다.</Empty>}
      <p className="detail-disclaimer">프리셋 전환은 조회 데이터만 바꿉니다. 게임 내 프리셋을 적용하지 않으며, Nexon API에서 제공하지 않는 수치와 세트 효과는 임의 계산하지 않습니다.</p>
    </section>
  );
}