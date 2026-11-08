import { Fragment, useState } from "react";
import {
  SLOT_DEFS, sourceOf, fallbackPreset, presetData, hasValue, numberText, optionNumber,
  equipmentTotalOptions, equipmentPotentialOptions, equipmentIsStarforce, isSeedRing,
  seedRingLevel, equipmentCategory, equipmentJobRequirement, apiImage, PresetSelect,
  DataState, Empty, DetailTooltip
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
                    <strong>스탯</strong><span>기본 · 스타포스 · 주문서 · 추옵</span>
                  </div>
                  <div className="game-equipment-tooltip-total">
                    {totalOptions.length ? totalOptions.map(option => (
                      <div className="game-equipment-tooltip-stat" key={option.label}>
                        <span>{option.label}</span>
                        <div className="game-equipment-tooltip-stat-values">
                          <b>{option.value}</b>
                          {option.breakdown.filter(part => part.value !== 0).length > 0 && (
                            <span className="game-equipment-tooltip-stat-breakdown">
                              ({option.breakdown.filter(part => part.value !== 0).map((part,index) => {
                                const value = Number(part.value);
                                const formatted = index === 0
                                  ? numberText(value)
                                  : value < 0
                                    ? "− " + numberText(Math.abs(value))
                                    : "+ " + numberText(value);
                                return (
                                  <Fragment key={part.source}>
                                    <small className={"is-" + part.source}>{formatted}</small>
                                    {index < option.breakdown.filter(entry => entry.value !== 0).length - 1 ? " " : ""}
                                  </Fragment>
                                );
                              })})
                            </span>
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
