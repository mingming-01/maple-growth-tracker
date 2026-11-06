/** Lazy-loaded Nexon character details with independent preset selectors. */

const FIELD_LABELS = {
    character_class: "직업", character_class_level: "직업 차수", character_gender: "성별",
    final_stat: "최종 스탯", stat_name: "스탯", stat_value: "수치", remain_ap: "남은 AP",
    stat_type: "스탯 종류", stat_point: "사용 포인트", stat_level: "레벨", stat_increase: "증가 효과",
    ability_grade: "어빌리티 등급", ability_info: "어빌리티", ability_value: "효과",
    item_equipment: "장착 장비", item_equipment_part: "장비 부위", item_equipment_slot: "장착 슬롯",
    item_name: "장비 이름", item_icon: "장비 아이콘", item_description: "설명",
    item_total_option: "기본·추가 옵션", item_base_option: "기본 옵션", item_add_option: "추가 옵션",
    item_etc_option: "기타 옵션", item_starforce: "스타포스", starforce: "스타포스",
    potential_option_grade: "잠재능력 등급", potential_option_1: "잠재능력 1",
    potential_option_2: "잠재능력 2", potential_option_3: "잠재능력 3",
    additional_potential_option_grade: "에디셔널 등급",
    additional_potential_option_1: "에디셔널 1", additional_potential_option_2: "에디셔널 2",
    additional_potential_option_3: "에디셔널 3",
    symbol: "심볼", symbol_name: "심볼 이름", symbol_icon: "심볼 아이콘",
    symbol_description: "심볼 설명", symbol_level: "심볼 레벨",
    symbol_force: "심볼 포스", symbol_growth_count: "성장 횟수",
    symbol_require_growth_count: "다음 성장 필요 횟수", set_effect: "세트 효과",
    skill_name: "스킬 이름", skill_description: "스킬 설명", skill_level: "스킬 레벨",
    skill_effect: "현재 레벨 효과", skill_effect_next: "다음 레벨 효과", skill_icon: "스킬 아이콘",
    hexa_core_name: "HEXA 코어 이름", hexa_core_level: "코어 레벨",
    hexa_core_type: "코어 종류", linked_skill: "연결 스킬", hexa_skill_id: "연결 스킬 이름",
    set_name: "세트 이름", set_effect_info: "세트 효과 정보", set_count: "세트 착용 수",
    character_link_skill: "링크 스킬", skill_name: "스킬 이름", skill_description: "스킬 설명",
    skill_level: "스킬 레벨", skill_effect: "스킬 효과", union_level: "유니온 레벨",
    union_grade: "유니온 등급", union_raider_stat: "공격대원 효과",
    union_occupied_stat: "점령 효과", union_block: "배치 블록",
    union_artifact_level: "아티팩트 레벨", union_artifact_exp: "아티팩트 경험치",
    union_artifact_point: "아티팩트 포인트", union_artifact_remain_ap: "남은 아티팩트 AP",
    union_artifact_effect: "아티팩트 효과", union_artifact_crystal: "아티팩트 크리스탈"
};

function humanizeKey(key) {
    if (FIELD_LABELS[key]) return FIELD_LABELS[key];
    return String(key).replace(/_/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
}

function renderScalar(container, key, value) {
    const row = createElement("div", "detail-data-row");
    row.append(
        createElement("span", "detail-data-label", humanizeKey(key)),
        createElement("strong", "detail-data-value", value)
    );
    container.appendChild(row);
}

function renderObject(container, value, depth = 0) {
    if (depth > 4 || !value || typeof value !== "object") return;
    if (Array.isArray(value)) {
        if (!value.length) {
            container.appendChild(createElement("p", "detail-empty", "표시할 항목이 없습니다."));
            return;
        }
        value.slice(0, 40).forEach((entry, index) => {
            if (entry === null || entry === undefined || entry === "") return;
            if (typeof entry !== "object") {
                renderScalar(container, "항목 " + (index + 1), entry);
                return;
            }
            const card = createElement("article", "detail-entry-card");
            const heading = entry.item_name || entry.symbol_name || entry.skill_name ||
                entry.stat_type || entry.set_name || entry.ability_value;
            if (heading) card.appendChild(createElement("h5", "detail-entry-title", heading));
            renderObject(card, entry, depth + 1);
            container.appendChild(card);
        });
        if (value.length > 40) {
            container.appendChild(createElement("p", "detail-muted", "그 외 " + (value.length - 40) + "개 항목"));
        }
        return;
    }

    Object.entries(value).forEach(([key, item]) => {
        if (item === null || item === undefined || item === "") return;
        if (key.endsWith("_icon") && typeof item === "string" && /^https:\/\//i.test(item)) {
            const row = createElement("div", "detail-data-row detail-image-row");
            row.appendChild(createElement("span", "detail-data-label", humanizeKey(key)));
            const img = document.createElement("img");
            img.src = item;
            img.alt = "";
            img.loading = "lazy";
            img.referrerPolicy = "no-referrer";
            row.appendChild(img);
            container.appendChild(row);
            return;
        }
        if (typeof item === "object") {
            const group = createElement("section", "detail-nested-group");
            group.appendChild(createElement("h5", "detail-nested-title", humanizeKey(key)));
            const body = createElement("div", Array.isArray(item) ? "detail-entry-list" : "detail-data-grid");
            renderObject(body, item, depth + 1);
            if (body.childElementCount) {
                group.appendChild(body);
                container.appendChild(group);
            }
            return;
        }
        renderScalar(container, key, item);
    });
}

function findArrayByKey(value, keys, depth = 0) {
    if (!value || typeof value !== "object" || depth > 7) return null;
    if (!Array.isArray(value)) for (const key of keys) if (Array.isArray(value[key])) return value[key];
    for (const child of Object.values(value)) {
        const found = findArrayByKey(child, keys, depth + 1);
        if (found) return found;
    }
    return null;
}

function appendTooltipRows(container, title, value) {
    if (value === null || value === undefined || value === "") return;
    const group = createElement("div", "equipment-tooltip-group");
    group.appendChild(createElement("strong", "equipment-tooltip-group-title", title));
    const entries = Array.isArray(value) ? value :
        (typeof value === "object" ? Object.entries(value).map(([key, entry]) => ({ [key]: entry })) : [value]);
    entries.forEach(entry => {
        if (entry === null || entry === undefined || entry === "") return;
        const line = typeof entry === "object"
            ? Object.entries(entry).filter(([, v]) => v !== null && v !== undefined && v !== "")
                .map(([key, v]) => humanizeKey(key) + ": " + String(v)).join(" · ")
            : String(entry);
        if (line) group.appendChild(createElement("p", "equipment-tooltip-line", line));
    });
    if (group.childElementCount > 1) container.appendChild(group);
}

function renderEquipmentSlots(container, data) {
    const items = findArrayByKey(data, ["item_equipment"]);
    if (!items || !items.length) { renderObject(container, data); return; }
    const grid = createElement("div", "equipment-slot-grid");
    items.forEach(item => {
        if (!item || typeof item !== "object") return;
        const slotName = item.item_equipment_slot || item.item_equipment_part || "기타 장비";
        const slot = createElement("article", "equipment-slot");
        slot.tabIndex = 0;
        slot.setAttribute("aria-label", slotName + " · " + (item.item_name || "장착 장비"));
        slot.appendChild(createElement("span", "equipment-slot-label", slotName));
        const iconFrame = createElement("span", "equipment-slot-icon-frame");
        if (typeof item.item_icon === "string" && /^https:\/\//i.test(item.item_icon)) {
            const icon = document.createElement("img");
            icon.src = item.item_icon; icon.alt = item.item_name || slotName;
            icon.loading = "lazy"; icon.referrerPolicy = "no-referrer";
            iconFrame.appendChild(icon);
        } else iconFrame.appendChild(createElement("span", "equipment-slot-no-icon", "장비"));
        slot.append(iconFrame, createElement("strong", "equipment-slot-name", item.item_name || "이름 정보 없음"));
        if (item.item_starforce !== null && item.item_starforce !== undefined) {
            slot.appendChild(createElement("span", "equipment-slot-starforce", "★ " + item.item_starforce));
        }
        const tooltip = createElement("div", "equipment-tooltip");
        tooltip.appendChild(createElement("strong", "equipment-tooltip-name", item.item_name || slotName));
        if (item.item_description) tooltip.appendChild(createElement("p", "equipment-tooltip-description", item.item_description));
        if (item.item_starforce !== null && item.item_starforce !== undefined) {
            tooltip.appendChild(createElement("p", "equipment-tooltip-meta", "스타포스 " + item.item_starforce));
        }
        appendTooltipRows(tooltip, "기본 옵션", item.item_base_option);
        appendTooltipRows(tooltip, "추가 옵션", item.item_add_option);
        appendTooltipRows(tooltip, "기타 옵션", item.item_etc_option);
        appendTooltipRows(tooltip, "스타포스 옵션", item.item_starforce_option);
        appendTooltipRows(tooltip, "잠재능력", [
            item.potential_option_grade, item.potential_option_1, item.potential_option_2, item.potential_option_3
        ].filter(Boolean));
        appendTooltipRows(tooltip, "에디셔널 잠재능력", [
            item.additional_potential_option_grade, item.additional_potential_option_1,
            item.additional_potential_option_2, item.additional_potential_option_3
        ].filter(Boolean));
        if (tooltip.childElementCount > 1) slot.appendChild(tooltip);
        grid.appendChild(slot);
    });
    container.appendChild(grid);
}

function renderSixthJobSkills(container, data) {
    const skills = findArrayByKey(data, ["character_skill"]);
    if (!skills || !skills.length) { renderObject(container, data); return; }
    const grid = createElement("div", "sixth-skill-grid");
    skills.forEach(skill => {
        if (!skill || typeof skill !== "object") return;
        const card = createElement("article", "sixth-skill-card");
        const iconFrame = createElement("div", "sixth-skill-icon-frame");
        if (typeof skill.skill_icon === "string" && /^https:\/\//i.test(skill.skill_icon)) {
            const icon = document.createElement("img");
            icon.src = skill.skill_icon; icon.alt = skill.skill_name || "스킬 아이콘";
            icon.loading = "lazy"; icon.referrerPolicy = "no-referrer";
            iconFrame.appendChild(icon);
        }
        const body = createElement("div", "sixth-skill-body");
        const heading = createElement("div", "sixth-skill-heading");
        heading.append(
            createElement("strong", "sixth-skill-name", skill.skill_name || "이름 정보 없음"),
            createElement("span", "sixth-skill-level", "Lv. " + (skill.skill_level ?? "-"))
        );
        body.append(heading);
        if (skill.skill_description) body.appendChild(createElement("p", "sixth-skill-description", skill.skill_description));
        if (skill.skill_effect) body.appendChild(createElement("p", "sixth-skill-effect", skill.skill_effect));
        card.append(iconFrame, body); grid.appendChild(card);
    });
    container.appendChild(grid);
}

function renderHexaCores(container, data) {
    const cores = findArrayByKey(data, ["character_hexa_core_equipment"]);
    if (!cores || !cores.length) { renderObject(container, data); return; }
    const grid = createElement("div", "hexa-core-grid");
    cores.forEach(core => {
        if (!core || typeof core !== "object") return;
        const card = createElement("article", "hexa-core-card");
        card.append(
            createElement("span", "hexa-core-type", core.hexa_core_type || "HEXA 코어"),
            createElement("strong", "hexa-core-name", core.hexa_core_name || "이름 정보 없음"),
            createElement("span", "hexa-core-level", "코어 레벨 " + (core.hexa_core_level ?? "-"))
        );
        const links = Array.isArray(core.linked_skill) ? core.linked_skill : [];
        const linked = links.map(item => item?.hexa_skill_id).filter(Boolean).join(", ");
        if (linked) card.appendChild(createElement("p", "hexa-core-linked", "연결 스킬 · " + linked));
        grid.appendChild(card);
    });
    container.appendChild(grid);
}

function getProfilePreset(source, mode, bestPresetCombination) {
    const presets = Array.isArray(source.presets) ? source.presets : [];
    if (!presets.length) return null;
    const active = presets.find(item => item.number === source.activePresetNo) || presets[0];
    if (mode === "boss" || mode === "hunting") {
        const purpose = mode === "boss" ? "boss" : "hunting";
        const recommendation = [...presets].filter(item => item.purpose === purpose)
            .sort((a, b) => (b.purposeScore || 0) - (a.purposeScore || 0))[0];
        return recommendation || active;
    }
    if (mode === "highest") {
        const key = {
            itemEquipment: "equipment", hyperStat: "hyperStat",
            ability: "ability", linkSkill: "link", unionRaider: "union"
        }[source.id];
        const preferred = key ? bestPresetCombination?.[key] : null;
        const match = preferred !== null && preferred !== undefined
            ? presets.find(item => item.number === Number(preferred)) : null;
        if (match) return match;
    }
    return active;
}

function renderSource(source, profileMode = "highest", bestPresetCombination = null) {
    const card = createElement("article", "detail-source-card");
    const heading = createElement("div", "detail-source-heading");
    const title = createElement("h4", "detail-source-title", source.label || source.id);
    const statusText = source.status === "available"
        ? "조회 완료"
        : source.status === "empty" ? "데이터 없음" : "조회 불가";
    const status = createElement("span", "detail-source-status is-" + source.status, statusText);
    heading.append(title, status);
    card.appendChild(heading);

    if (source.status === "unavailable") {
        card.appendChild(createElement("p", "detail-message is-warning",
            source.message || "이 상세 데이터를 불러오지 못했습니다. 다른 정보는 계속 확인할 수 있습니다."));
        return card;
    }
    if (source.status === "empty") {
        card.appendChild(createElement("p", "detail-message", source.message || "API에서 제공하는 데이터가 없습니다."));
        return card;
    }

    if (source.id === "stat" && source.combatPower !== null && source.combatPower !== undefined) {
        const combat = createElement("div", "detail-combat-power");
        combat.append(
            createElement("span", "detail-combat-label", "현재 적용 상태 전투력"),
            createElement("strong", "detail-combat-value", Number(source.combatPower).toLocaleString("ko-KR"))
        );
        card.appendChild(combat);
    }

    let chosenPreset = null;
    if (Array.isArray(source.presets) && source.presets.length) {
        const presets = source.presets;
        const active = presets.find(item => item.number === source.activePresetNo) || presets[0];
        chosenPreset = getProfilePreset(source, profileMode, bestPresetCombination) || active;
        if (presets.length > 1) {
            const control = createElement("label", "detail-preset-control");
            control.appendChild(createElement("span", "", "확인할 프리셋"));
            const select = document.createElement("select");
            select.className = "detail-preset-select";
            presets.forEach(preset => {
                const option = document.createElement("option");
                option.value = String(preset.number);
                option.textContent = preset.number === 0 ? "현재 구성" : "프리셋 " + preset.number + " · " + (preset.purposeLabel || "용도 미확인");
                option.selected = preset.number === chosenPreset.number;
                select.appendChild(option);
            });
            select.addEventListener("change", () => {
                chosenPreset = presets.find(item => String(item.number) === select.value) || presets[0];
                renderPresetBody();
            });
            control.appendChild(select);
            heading.appendChild(control);
        }
        const activeLabel = source.activePresetNo
            ? "게임 내 현재 적용 프리셋: " + source.activePresetNo + "번"
            : "현재 적용 프리셋 번호는 API 응답에서 확인되지 않음";
        card.appendChild(createElement("p", "detail-active-preset", activeLabel));
    }

    const body = createElement("div", "detail-source-body");
    card.appendChild(body);

    function renderPresetBody() {
        body.replaceChildren();
        const bodyData = chosenPreset && chosenPreset.data ? chosenPreset.data : (source.data || {});
        if (source.id === "itemEquipment") renderEquipmentSlots(body, bodyData);
        else if (source.id === "skill6") renderSixthJobSkills(body, bodyData);
        else if (source.id === "hexaMatrix") renderHexaCores(body, bodyData);
        else renderObject(body, bodyData);
        if (!body.childElementCount) {
            body.appendChild(createElement("p", "detail-empty", "표시할 항목이 없습니다."));
        }
    }
    renderPresetBody();

    if (source.id === "stat") {
        card.appendChild(createElement(
            "p",
            "detail-message",
            "전투력은 넥슨 API가 반환한 현재 적용 상태의 값입니다. 비활성 프리셋의 전투력이나 환산 점수는 API에서 별도 제공되지 않는 한 임의로 산출하지 않습니다."
        ));
    }
    return card;
}

export function initCharacterDetails({ apiFetch, readApiResponse }) {
    const section = document.getElementById("characterDetailsSection");
    const content = document.getElementById("characterDetailsContent");
    const notice = document.getElementById("characterDetailsNotice");
    const tabs = Array.from(document.querySelectorAll("[data-detail-tab]"));
    let currentOcid = "";
    let requestToken = 0;
    const cache = new Map();

    function setNotice(message, warning = false) {
        if (!notice) return;
        notice.textContent = message || "";
        notice.classList.toggle("is-warning", warning);
        notice.hidden = !message;
    }

    function setCharacter(ocid) {
        currentOcid = typeof ocid === "string" ? ocid.trim() : "";
        requestToken += 1;
        cache.clear();
        if (content) {
            content.replaceChildren(createElement(
                "p",
                "detail-placeholder",
                currentOcid
                    ? "스탯·장비·링크·유니온 탭을 선택하면 해당 상세 정보만 조회합니다."
                    : "캐릭터를 먼저 조회해주세요."
            ));
        }
        setNotice("");
        activeProfileMode = "highest";
        if (content) content.classList.remove("is-single");
        tabs.forEach(tab => {
            tab.disabled = !currentOcid;
            tab.setAttribute("aria-selected", "false");
            tab.classList.remove("is-active");
        });
    }

    async function loadSection(name, force = false) {
        if (!currentOcid || !content) return;
        const token = ++requestToken;
        const key = currentOcid + ":" + name;
        tabs.forEach(tab => {
            const active = tab.dataset.detailTab === name;
            tab.setAttribute("aria-selected", active ? "true" : "false");
            tab.classList.toggle("is-active", active);
        });
        const cached = !force ? cache.get(key) : null;
        if (cached) {
            renderSection(cached);
            return;
        }

        content.replaceChildren(createElement("p", "detail-loading", "상세 정보를 불러오고 있습니다..."));
        setNotice("");
        try {
            const url = "/api/character-details?ocid=" + encodeURIComponent(currentOcid) +
                "&section=" + encodeURIComponent(name) + (force ? "&refresh=1" : "");
            const response = await apiFetch(url);
            const data = await readApiResponse(response, "캐릭터 상세 정보를 불러오지 못했습니다.");
            if (token !== requestToken) return;
            cache.set(key, data);
            renderSection(data);
        } catch (error) {
            if (token !== requestToken) return;
            content.replaceChildren(createElement("p", "detail-message is-warning",
                error.message || "상세 정보를 불러오지 못했습니다."));
        }
    }

    let activeProfileMode = "highest";

    function renderSection(data, profileMode = activeProfileMode) {
        if (!content) return;
        activeProfileMode = profileMode;
        content.replaceChildren();
        content.classList.toggle("is-single", Array.isArray(data.sources) && data.sources.length === 1);
        if (data.section === "stats") {
            const panel = createElement("section", "detail-profile-panel");
            const heading = createElement("div", "detail-profile-heading");
            const copy = createElement("div", "detail-profile-copy");
            copy.append(
                createElement("strong", "detail-profile-title", "프리셋 조합 빠른 선택"),
                createElement("p", "detail-profile-description",
                    "영역별 프리셋 번호는 서로 독립적입니다. 보스·사냥 구분은 옵션 특징을 이용한 추천이며 인게임 별칭이 아닙니다.")
            );
            heading.append(copy, createElement("span", "detail-profile-record",
                data.bestCombatPower
                    ? "최고 관측 전투력 " + Number(data.bestCombatPower).toLocaleString("ko-KR")
                    : "최고 전투력 조합 기록 없음"));
            panel.appendChild(heading);
            const actions = createElement("div", "detail-profile-actions");
            [["highest", "최고 전투력 조합"], ["current", "게임 적용 상태"],
             ["boss", "보스 추천"], ["hunting", "사냥 추천"]].forEach(([mode, label]) => {
                const button = createElement("button",
                    "detail-profile-button" + (mode === profileMode ? " is-active" : ""), label);
                button.type = "button";
                button.setAttribute("aria-pressed", mode === profileMode ? "true" : "false");
                button.addEventListener("click", () => renderSection(data, mode));
                actions.appendChild(button);
            });
            panel.appendChild(actions);
            content.appendChild(panel);
        }
        if (!Array.isArray(data.sources) || !data.sources.length) {
            content.appendChild(createElement("p", "detail-placeholder", "표시할 상세 정보가 없습니다."));
            return;
        }
        data.sources.forEach(source =>
            content.appendChild(renderSource(source, profileMode, data.bestPresetCombination))
        );
        if (data.status === "partial") {
            setNotice("일부 항목만 조회됐습니다. 조회할 수 없는 정보가 있어도 다른 데이터는 정상적으로 표시됩니다.", true);
        } else if (data.status === "unavailable") {
            setNotice("이 탭의 상세 정보를 조회하지 못했습니다. 잠시 후 다시 시도해주세요.", true);
        } else {
            setNotice("넥슨 Open API에서 제공하는 현재 상세 데이터입니다. 정보 갱신 시점은 게임 내 상태와 다를 수 있습니다.");
        }
    }

    tabs.forEach(tab => {
        tab.disabled = true;
        tab.addEventListener("click", () => loadSection(tab.dataset.detailTab));
    });

    const refreshButton = document.getElementById("refreshCharacterDetailsButton");
    if (refreshButton) {
        refreshButton.addEventListener("click", () => {
            const active = tabs.find(tab => tab.getAttribute("aria-selected") === "true");
            if (active) loadSection(active.dataset.detailTab, true);
        });
    }

    if (section) section.hidden = false;
    setCharacter("");
    return { setCharacter, loadSection };
}
