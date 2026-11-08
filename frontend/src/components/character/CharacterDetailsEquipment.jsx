import { Fragment, useState } from "react";
import {
  SLOT_DEFS,
  sourceOf,
  fallbackPreset,
  presetData,
  hasValue,
  numberText,
  equipmentTotalOptions,
  equipmentPotentialOptions,
  equipmentIsStarforce,
  isSeedRing,
  seedRingLevel,
  equipmentCategory,
  equipmentJobRequirement,
  apiImage,
  PresetSelect,
  DataState,
  DetailTooltip,
  Empty
} from "./CharacterDetailsShared.jsx";
import { CosmeticsSubtab, PetsSubtab } from "./CharacterDetailsStats.jsx";

export function EquipmentTab({ data, selected, onSelect }) {
  const [subTab, setSubTab] = useState("equipment");
  const equipment = sourceOf(data, "itemEquipment");
  const appearanceSource = sourceOf(data, "characterAppearance");
  const androidSource = sourceOf(data, "androidEquipment");
  const cashSource = sourceOf(data, "cashItemEquipment");
  const petSource = sourceOf(data, "petEquipment");
  const setSource = sourceOf(data, "setEffect");
  const presetNumber = selected.equipment ?? fallbackPreset(equipment);
  const current = presetData(equipment
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
          {SLOT_DEFS.map(([slot, key]) => {
            const item = findSlotItem(slot, key);
            const totals = item ? equipmentTotalOptions(item) : [];
            const potentials = item ? equipmentPotentialOptions(item) : { normal: [], additional: [] };
            const lines = item ? [
              item.item_name,
              equipmentCategory(key, item),
              equipmentJobRequirement(item),
              equipmentIsStarforce(item) ? "스타포스 " + numberText(item.starforce ?? item.item_starforce) : null,
              ...totals.slice(0, 8).map(row => row.label + " " + row.value),
              potentials.normal.length ? "잠재: " + potentials.normal.join(" / ") : null,
              potentials.additional.length ? "에디: " + potentials.additional.join(" / ") : null
            ].filter(hasValue) : [slot + " 슬롯 비어 있음"];
            return (
              <DetailTooltip key={key} title={item?.item_name || slot} lines={lines} className="game-equipment-slot">
                <span className="game-equipment-slot-label">{slot}</span>
                <span className="game-equipment-slot-icon">
                  {item ? apiImage(item.item_icon, item.item_name) : null}
                </span>
                <span className="game-equipment-slot-name">{item?.item_name || "비어 있음"}</span>
              </DetailTooltip>
            );
          })}
        </div>
        {seedRings.length > 0 && (
          <section className="game-seed-ring-panel">
            <h4 className="game-window-title">시드링</h4>
            <div className="game-seed-ring-list">
              {seedRings.map((item, index) => (
                <div className="game-seed-ring-item" key={index}>
                  <span>{apiImage(item.item_icon, item.item_name)}</span>
                  <strong>{item.item_name}</strong>
                  <span>Lv. {numberText(seedRingLevel(item))}</span>
                </div>
              ))}
            </div>
          </section>
        )}
        {(presetSets.length > 0 || sets.length > 0) && (
          <section className="game-set-effect-panel">
            <h4 className="game-window-title">세트 효과{isActive ? " (적용 중 프리셋)" : ""}</h4>
            <div className="game-set-effect-list">
              {(presetSets.length ? presetSets : sets).slice(0, 12).map((setItem, index) => (
                <div className="game-set-effect-item" key={index}>
                  <strong>{setItem.set_name || setItem.set_effect_name || "세트"}</strong>
                  <span>{setItem.set_count || setItem.set_effect_level || ""}</span>
                </div>
              ))}
            </div>
          </section>
        )}
        {android && (android.android_name || android.android_icon) && (
          <section className="game-android-panel">
            <h4 className="game-window-title">안드로이드</h4>
            <div className="game-android-card">
              <span>{apiImage(android.android_icon, android.android_name)}</span>
              <strong>{android.android_name || "안드로이드"}</strong>
            </div>
          </section>
        )}
      </>}
      {subTab === "cosmetics" && (
        <CosmeticsSubtab appearance={appearance} cashSource={cashSource} selected={selected} onSelect={onSelect} />
      )}
      {subTab === "pets" && <PetsSubtab source={petSource} />}
    </div>
  );
}
