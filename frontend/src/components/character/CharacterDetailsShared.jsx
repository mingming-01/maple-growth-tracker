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

export function Empty({ children = "표시할 데이터가 없습니다." }) {
  return <p className="game-empty">{children}</p>;
}

export function DataState({ source }) {
  if (!source) return <Empty>이 탭에서 제공하는 데이터가 없습니다.</Empty>;
  if (source.status === "unavailable") return <Empty>{source.message || "Nexon API에서 이 정보를 조회하지 못했습니다."}</Empty>;
  if (source.status === "empty") return <Empty>{source.message || "API 응답에 표시할 데이터가 없습니다."}</Empty>;
  return null;
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
