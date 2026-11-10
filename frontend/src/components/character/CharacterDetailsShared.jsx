import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export const DETAIL_TABS = [
  ["stats", "스탯"],
  ["equipment", "장비"],
  ["symbols", "심볼"],
  ["skills", "6차 / HEXA"],
  ["link", "링크 스킬"],
  ["union", "유니온"]
];

export const STAT_LABELS = {
  STR:"STR",DEX:"DEX",INT:"INT",LUK:"LUK",
  "보스 몬스터 공격 시 데미지":"보스 데미지",
  "몬스터 방어율 무시":"방어율 무시",
  "일반 몬스터 공격 시 데미지":"일반 몬스터 데미지"
};

export const SLOT_DEFS = [
  ["반지 1","ring1"],["얼굴장식","face"],["반지 2","ring2"],["눈장식","eye"],
  ["반지 3","ring3"],["귀고리","ear"],["반지 4","ring4"],["펜던트 1","pendant1"],
  ["모자","hat"],["망토","cape"],["상의","top"],["장갑","gloves"],
  ["하의","bottom"],["신발","shoes"],["어깨장식","shoulder"],["훈장","medal"],["벨트","belt"],
  ["펜던트 2","pendant2"],["무기","weapon"],["보조무기","subweapon"],
  ["엠블렘","emblem"],["안드로이드","android"],["하트","heart"],["포켓","pocket"],["뱃지","badge"]
];

export function sourceOf(data, id) {
  return data?.sources?.find(source => source.id === id) || null;
}

export function presetOf(source, number) {
  return source?.presets?.find(item => Number(item.number) === Number(number)) || null;
}

export function fallbackPreset(source) {
  if (!source?.presets?.length) return null;
  const active = presetOf(source, source.activePresetNo);
  return active ? active.number : source.presets[0].number;
}

export function presetData(source, number) {
  return presetOf(source, number)?.data || source?.currentData || source?.data || {};
}

export function hasValue(value) {
  return value !== null && value !== undefined && value !== "";
}

export function numberText(value) {
  if (!hasValue(value)) return "—";
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed.toLocaleString("ko-KR") : String(value);
}

export const EQUIPMENT_OPTION_FIELDS = [
  ["STR", "str"], ["DEX", "dex"], ["INT", "int"], ["LUK", "luk"],
  ["최대 HP", "max_hp"], ["최대 MP", "max_mp"],
  ["공격력", "attack_power"], ["마력", "magic_power"], ["방어력", "armor"],
  ["이동 속도", "speed"], ["점프력", "jump"],
  ["보스 몬스터 공격 시 데미지", "boss_damage", "%"],
  ["몬스터 방어율 무시", "ignore_monster_armor", "%"],
  ["올스탯", "all_stat", "%"], ["데미지", "damage", "%"]
];

export function optionNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(String(value).replace(/,/g, "").replace(/%/g, "").replace(/\+/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

export function equipmentTotalOptions(item) {
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

export function equipmentPotentialOptions(item) {
  const normal = [item?.potential_option_1, item?.potential_option_2, item?.potential_option_3].filter(hasValue);
  const additional = [
    item?.additional_potential_option_1,
    item?.additional_potential_option_2,
    item?.additional_potential_option_3
  ].filter(hasValue);
  return { normal, additional };
}

export function equipmentIsStarforce(item) {
  const value = optionNumber(item?.starforce ?? item?.item_starforce);
  return value !== null && value > 0;
}

export function isSeedRing(item) {
  const name = String(item?.item_name || "");
  return /리스트레인트\s*링|컨티뉴어스\s*링|웨폰퍼프\s*링|리스크테이커\s*링|크라이시스\s*링|레벨퍼프\s*링|얼티메이덤\s*링/.test(name);
}

export function seedRingLevel(item) {
  const candidates = [
    item?.special_ring_level,
    item?.ring_level,
    item?.item_base_option?.special_ring_level,
    item?.item_base_option?.ring_level,
    item?.item_special_option?.special_ring_level,
    item?.item_special_option?.ring_level
  ];
  const explicit = candidates.map(optionNumber).find(value => value !== null && value > 0);
  if (explicit !== undefined) return explicit;
  const name = String(item?.item_name || "");
  const nameMatch = name.match(/(?:Lv\.?\s*(\d+)|(\d+)\s*레벨|레벨\s*(\d+))/i);
  const namedLevel = nameMatch?.[1] || nameMatch?.[2] || nameMatch?.[3];
  return namedLevel ? Number(namedLevel) : null;
}

export function equipmentCategory(key, item) {
  if (["hat", "top", "bottom", "cape", "gloves", "shoes", "shoulder"].includes(key)) return "방어구";
  if (key === "weapon") return "무기";
  if (["subweapon", "emblem"].includes(key)) return "보조 장비";
  if (/^ring|pendant|face|eye|ear|belt|pocket|badge|medal|heart/.test(key)) return "장신구";
  return item?.item_equipment_category || "장비";
}

export function equipmentJobRequirement(item) {
  const base = item?.item_base_option || {};
  const value = base.base_equipment_job ?? item?.base_equipment_job ?? item?.item_equipment_job;
  if (Array.isArray(value)) return value.filter(hasValue).join(" · ");
  return hasValue(value) ? String(value) : null;
}

export function appearanceColors(value) {
  if (!value || typeof value !== "object") return [];
  return [
    ["기본 색상", value.base_color],
    ["믹스 색상", value.mix_color],
    ["믹스 비율", hasValue(value.mix_rate) ? value.mix_rate + "%" : null]
  ].filter(([, item]) => hasValue(item));
}

export function badgeGlyph(stat, index = 0) {
  const value = String(stat || "");
  if (/경험치/.test(value)) return "✦";
  if (/공격력|마력|보스|최종 데미지/.test(value)) return "⚔";
  if (/드롭|아이템/.test(value)) return "⬡";
  if (/메소|획득/.test(value)) return "◈";
  if (/크리티컬|데미지/.test(value)) return "✧";
  return ["✦", "⚔", "◈", "✧", "⬡"][index % 5];
}

export function apiImage(url, alt, className = "") {
  if (typeof url !== "string" || !/^https:\/\//i.test(url)) return null;
  return <img className={className} src={url} alt={alt || ""} loading="lazy" referrerPolicy="no-referrer" />;
}

export function PresetSelect({ source, value, onChange, label = "프리셋" }) {
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

export function Empty({ children = "표시할 데이터가 없습니다." }) {
  return <p className="game-empty">{children}</p>;
}

export function DataState({ source }) {
  if (!source) return <Empty>이 탭에서 제공하는 데이터가 없습니다.</Empty>;
  if (source.status === "unavailable") return <Empty>{source.message || "Nexon API에서 이 정보를 조회하지 못했습니다."}</Empty>;
  if (source.status === "empty") return <Empty>{source.message || "API 응답에 표시할 데이터가 없습니다."}</Empty>;
  return null;
}

export function DetailTooltip({
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
  const touchStartRef = useRef(null);
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
          touchStartRef.current = {
            pointerId: event.pointerId,
            x: event.clientX,
            y: event.clientY
          };
        }
      }}
      onPointerUp={event => {
        if (event.pointerType !== "touch") return;
        const start = touchStartRef.current;
        touchStartRef.current = null;
        if (!hasTooltip || !start || start.pointerId !== event.pointerId) return;
        const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
        if (moved < 8) setOpen(value => !value);
      }}
      onPointerCancel={() => { touchStartRef.current = null; }}
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

export function StatRows({ entries }) {
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
