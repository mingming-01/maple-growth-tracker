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
    symbol: "심볼", symbol_name: "심볼 이름", symbol_level: "심볼 레벨",
    symbol_force: "심볼 포스", symbol_growth_count: "성장 횟수",
    symbol_require_growth_count: "다음 성장 필요 횟수", set_effect: "세트 효과",
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

function renderSource(source) {
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
        chosenPreset = active;
        if (presets.length > 1) {
            const control = createElement("label", "detail-preset-control");
            control.appendChild(createElement("span", "", "확인할 프리셋"));
            const select = document.createElement("select");
            select.className = "detail-preset-select";
            presets.forEach(preset => {
                const option = document.createElement("option");
                option.value = String(preset.number);
                option.textContent = preset.number === 0 ? "현재 구성" : "프리셋 " + preset.number;
                option.selected = preset.number === active.number;
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
        if (chosenPreset && chosenPreset.data) {
            renderObject(body, chosenPreset.data);
        } else {
            renderObject(body, source.data || {});
        }
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

    function renderSection(data) {
        if (!content) return;
        content.replaceChildren();
        if (!Array.isArray(data.sources) || !data.sources.length) {
            content.appendChild(createElement("p", "detail-placeholder", "표시할 상세 정보가 없습니다."));
            return;
        }
        data.sources.forEach(source => content.appendChild(renderSource(source)));
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
