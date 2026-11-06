/** MapleStory in-client inspired character detail windows. */

const PRESET_CATEGORY = {
    itemEquipment: "equipment", hyperStat: "hyperStat",
    ability: "ability", linkSkill: "link", unionRaider: "union"
};
const REQUIRED_PRESET_KEYS = ["equipment", "hyperStat", "ability", "link", "union"];

const STAT_LABELS = {
    STR:"STR", DEX:"DEX", INT:"INT", LUK:"LUK", "공격력":"공격력", "마력":"마력",
    "보스 몬스터 공격 시 데미지":"보스 데미지", "몬스터 방어율 무시":"방어율 무시",
    "크리티컬 데미지":"크리티컬 데미지", "크리티컬 확률":"크리티컬 확률",
    "데미지":"데미지", "최종 데미지":"최종 데미지",
    "메소 획득량":"메소 획득량", "아이템 드롭률":"아이템 드롭률",
    "일반 몬스터 공격 시 데미지":"일반 몬스터 데미지", "경험치 획득량":"경험치 획득량",
    "최대 HP":"최대 HP", "최대 MP":"최대 MP"
};
const OPTION_LABELS = {
    str:"STR",dex:"DEX",int:"INT",luk:"LUK",max_hp:"최대 HP",max_mp:"최대 MP",
    attack_power:"공격력",magic_power:"마력",armor:"방어력",speed:"이동속도",jump:"점프력",
    boss_damage:"보스 데미지",ignore_monster_armor:"방어율 무시",all_stat:"올스탯",
    max_hp_rate:"최대 HP",max_mp_rate:"최대 MP",attack_power_rate:"공격력",magic_power_rate:"마력"
};
const SLOT_DEFS = [
    ["모자","hat"],["얼굴장식","face"],["눈장식","eye"],["귀고리","ear"],["반지4","ring4"],["반지3","ring3"],
    ["펜던트","pendant1"],["상의","top"],["어깨장식","shoulder"],["펜던트(슬롯2)","pendant2"],["반지2","ring2"],["반지1","ring1"],
    ["벨트","belt"],["하의","bottom"],["무기","weapon"],["망토","cape"],["보조무기","subweapon"],["엠블렘","emblem"],
    ["포켓 아이템","pocket"],["신발","shoes"],["장갑","gloves"],["뱃지","badge"],["훈장","medal"],["기계 심장","heart"]
];

function el(tag, cls, text) {
    const node=document.createElement(tag);
    if(cls) node.className=cls;
    if(text!==undefined && text!==null) node.textContent=String(text);
    return node;
}
function image(url, alt, cls) {
    if(typeof url!=="string" || !/^https:\/\//i.test(url)) return null;
    const img=document.createElement("img");
    img.src=url; img.alt=alt||""; img.loading="lazy"; img.referrerPolicy="no-referrer";
    if(cls) img.className=cls;
    return img;
}
function present(value) { return value!==null && value!==undefined && value!==""; }
function fmt(value) {
    if(!present(value)) return "";
    const raw=String(value).trim();
    if(/^-?\d+(\.\d+)?$/.test(raw)) {
        const number=Number(raw);
        return Number.isInteger(number) ? number.toLocaleString("ko-KR") : number.toLocaleString("ko-KR",{maximumFractionDigits:2});
    }
    return raw;
}
function sourceById(data,id) { return (data.sources||[]).find(source=>source.id===id)||null; }
function presetByNumber(source,number) {
    return (source?.presets||[]).find(item=>Number(item.number)===Number(number))||null;
}
function fallbackPreset(source) {
    if(!source?.presets?.length) return null;
    const active=presetByNumber(source,source.activePresetNo);
    return active ? active.number : source.presets[0].number;
}
function presetData(source,number) {
    const preset=presetByNumber(source,number);
    return preset?.data || source?.currentData || source?.data || {};
}
function initialSelection(data,mode) {
    const selected={}, recommendations=data.profileRecommendations||{};
    for(const source of data.sources||[]) {
        const category=PRESET_CATEGORY[source.id];
        if(!category) continue;
        let number=null;
        if(mode==="boss"||mode==="hunting") number=recommendations[mode]?.presetNumbers?.[category];
        else if(mode==="highest") number=data.bestPresetCombination?.[category];
        else if(mode==="current") number=data.actualPresetNumbers?.[category];
        if(number===null||number===undefined) number=fallbackPreset(source);
        if(number!==null&&number!==undefined) selected[category]=Number(number);
    }
    return selected;
}
function exactCombination(left,right) {
    if(!left||!right) return false;
    return REQUIRED_PRESET_KEYS.every(key=>left[key]!==undefined&&left[key]!==null&&right[key]!==undefined&&right[key]!==null&&Number(left[key])===Number(right[key]));
}
function resolvePower(data,selection,mode) {
    const stat=sourceById(data,"stat"), actual=stat?.combatPower;
    if(mode==="current" && present(actual)) return {value:actual,label:"현재 적용 중인 실제 전투력"};
    if(exactCombination(selection,data.actualPresetNumbers)&&present(actual)) return {value:actual,label:"현재 적용 조합과 일치 · 실제 전투력"};
    if(exactCombination(selection,data.bestPresetCombination)&&present(data.bestCombatPower)) return {value:data.bestCombatPower,label:"이 조합으로 관측한 최고 전투력"};
    return {value:null,label:"선택한 조합의 실제 전투력 기록 없음"};
}

function presetSelect(source,category,selected,onChange) {
    const labels={equipment:"장비",hyperStat:"하이퍼 스탯",ability:"어빌리티",link:"링크 스킬",union:"유니온"};
    const wrap=el("label","game-preset-select-wrap");
    wrap.appendChild(el("span","game-preset-select-label",labels[category]||source.label));
    const select=document.createElement("select");
    select.className="game-preset-select";
    select.setAttribute("aria-label",labels[category]||source.label);
    (source.presets||[]).forEach(item=>{
        const option=document.createElement("option");
        option.value=String(item.number);
        const tag=item.purpose==="boss"?" · 보스":item.purpose==="hunting"?" · 사냥":"";
        option.textContent=item.number===0?"현재 구성":"프리셋 "+item.number+tag;
        option.selected=Number(item.number)===Number(selected);
        select.appendChild(option);
    });
    select.addEventListener("change",()=>onChange(Number(select.value)));
    wrap.appendChild(select);
    return wrap;
}

function renderStatsWindow(data,selection,mode) {
    const panel=el("section","game-stat-window");
    const heading=el("div","game-window-heading");
    heading.append(el("span","game-window-eyebrow","CHARACTER STATUS"),el("h3","game-window-title","능력치"));
    panel.appendChild(heading);
    const power=resolvePower(data,selection,mode);
    const powerPanel=el("div","game-power-panel");
    powerPanel.append(el("span","game-power-caption",power.label),
        el("strong","game-power-value",power.value!==null?Number(String(power.value).replace(/,/g,"")).toLocaleString("ko-KR"):"—"));
    if(power.value===null) powerPanel.appendChild(el("span","game-power-hint","비활성 프리셋의 전투력은 API에서 제공되지 않아 임의 계산하지 않습니다."));
    panel.appendChild(powerPanel);

    const finalStats=sourceById(data,"stat")?.data?.final_stat||[];
    const wanted=["STR","DEX","INT","LUK","공격력","마력","보스 몬스터 공격 시 데미지","몬스터 방어율 무시","크리티컬 데미지","크리티컬 확률","데미지"];
    const byName=new Map((Array.isArray(finalStats)?finalStats:[]).map(item=>[item.stat_name,item.stat_value]));
    const grid=el("div","game-stat-grid");
    wanted.forEach(name=>{
        if(!present(byName.get(name))) return;
        const tile=el("div","game-stat-tile");
        tile.append(el("span","game-stat-name",STAT_LABELS[name]||name),el("strong","game-stat-number",fmt(byName.get(name))));
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty","스탯 정보를 확인할 수 없습니다."));
    panel.appendChild(grid);
    return panel;
}

function summaryFor(source,number) {
    const data=presetData(source,number);
    if(source.id==="itemEquipment") {
        const items=Array.isArray(data.item_equipment)?data.item_equipment:[];
        const rings=items.filter(item=>/링/.test(item?.item_name||"")).map(item=>item.item_name);
        const hints=[];
        if(rings.length) hints.push(...rings.slice(0,2));
        const drop=items.filter(item=>/메소 획득량|아이템 드롭률|드롭률/.test(JSON.stringify(item)));
        if(drop.length) hints.push("드롭·메획 장비 "+drop.length+"개");
        return {title:"장비",detail:items.length+"개 장착",hints};
    }
    if(source.id==="hyperStat") {
        const items=Array.isArray(data.hyper_stat)?data.hyper_stat:[];
        return {title:"하이퍼 스탯",detail:items.filter(item=>Number(item?.stat_level)>0).length+"개 투자",
            hints:items.filter(item=>Number(item?.stat_level)>0).slice(0,4).map(item=>(item.stat_type||"스탯")+" Lv."+item.stat_level)};
    }
    if(source.id==="ability") {
        const ability=Array.isArray(data.ability_info)?data.ability_info:[];
        return {title:"어빌리티",detail:source.data?.ability_grade||"",hints:ability.map(item=>item?.ability_value).filter(Boolean).slice(0,3)};
    }
    if(source.id==="linkSkill") {
        const links=[...(Array.isArray(data.character_link_skill)?data.character_link_skill:[]),
            ...(data.character_owned_link_skill?[data.character_owned_link_skill]:[])];
        return {title:"링크 스킬",detail:links.length+"개 장착",hints:links.map(item=>item?.skill_name).filter(Boolean).slice(0,4)};
    }
    if(source.id==="unionRaider") {
        const text=JSON.stringify(data);
        const terms=["보스 데미지","방어율 무시","크리티컬 데미지","일반 몬스터","경험치","메소 획득량","아이템 드롭률"];
        return {title:"유니온",detail:"프리셋 "+(number??"—"),hints:terms.filter(term=>text.includes(term)).slice(0,4)};
    }
    return {title:source.label||source.id,detail:"",hints:[]};
}
function renderPresetSummary(source,number) {
    const summary=summaryFor(source,number), card=el("article","game-preset-summary");
    const head=el("div","game-preset-summary-top");
    head.append(el("strong","game-preset-summary-title",summary.title),el("span","game-preset-summary-count",summary.detail));
    card.appendChild(head);
    if(summary.hints.length) {
        const chips=el("div","game-preset-chips");
        summary.hints.forEach(value=>chips.appendChild(el("span","game-preset-chip",value)));
        card.appendChild(chips);
    } else card.appendChild(el("p","game-preset-no-signal","표시할 구성 정보가 없습니다."));
    return card;
}
function renderStatsSection(data,mode,selection,onModeChange) {
    const layout=el("div","game-stats-layout");
    const profile=el("section","game-profile-window");
    const heading=el("div","game-profile-title-row");
    heading.append(el("span","game-window-eyebrow","BATTLE PRESET"),el("h3","game-window-title","전투 세팅 조합"));
    profile.appendChild(heading);
    const modes=el("div","game-profile-mode-row");
    [["boss","보스 추천"],["hunting","사냥 추천"],["current","게임 적용 상태"],["highest","최고 전투력 기록"]].forEach(([key,label])=>{
        const button=el("button","game-profile-mode"+(mode===key?" is-active":""),label);
        button.type="button"; button.setAttribute("aria-pressed",mode===key?"true":"false");
        button.addEventListener("click",()=>onModeChange(key));
        modes.appendChild(button);
    });
    profile.appendChild(modes);
    const selects=el("div","game-preset-select-grid");
    (data.sources||[]).forEach(source=>{
        const category=PRESET_CATEGORY[source.id];
        if(!category||!Array.isArray(source.presets)||!source.presets.length) return;
        selects.appendChild(presetSelect(source,category,selection[category],number=>onModeChange("custom",category,number)));
    });
    profile.appendChild(selects);
    const recommendation=data.profileRecommendations?.[mode];
    const confidence=recommendation?.confidence==="high"?"판별 신뢰도 높음":recommendation?.confidence==="medium"?"판별 신호 확인":"판별 신호 부족 · 현재 프리셋 유지";
    const matched=recommendation?.matchedCategories?.length||0;
    profile.appendChild(el("p","game-profile-note",mode==="boss"||mode==="hunting"
        ? confidence+" · "+matched+"개 영역에서 특징 확인"
        : mode==="custom"?"직접 선택한 프리셋 조합입니다. 게임 내 프리셋은 변경되지 않습니다."
        :"각 영역의 프리셋 번호는 독립적이며, 인게임에 설정한 별칭을 가져온 값은 아닙니다."));
    layout.appendChild(profile);
    layout.appendChild(renderStatsWindow(data,selection,mode));

    const builds=el("section","game-selected-build-window");
    builds.appendChild(el("h3","game-window-title","선택된 세팅 구성"));
    const grid=el("div","game-selected-build-grid");
    (data.sources||[]).forEach(source=>{
        const category=PRESET_CATEGORY[source.id];
        if(category) grid.appendChild(renderPresetSummary(source,selection[category]));
    });
    builds.appendChild(grid); layout.appendChild(builds);
    return layout;
}

function equippedItems(source,number) {
    const data=presetData(source,number);
    return Array.isArray(data.item_equipment)?data.item_equipment:[];
}
function matchesSlot(item,slot) {
    const actual=String(item?.item_equipment_slot||item?.item_equipment_part||"").replace(/\s/g,"");
    const expected=slot.replace(/\s/g,"");
    return actual===expected || (expected==="펜던트(슬롯2)"&&actual.includes("펜던트")&&actual.includes("2"));
}
function options(value) {
    if(!value||typeof value!=="object") return [];
    return Object.entries(value).filter(([,raw])=>{
        if(!present(raw)) return false;
        return !/^0+(\.0+)?$/.test(String(raw).replace(/,/g,""));
    });
}
function addOptionGroup(parent,title,value) {
    const entries=options(value); if(!entries.length) return;
    const group=el("section","equipment-tooltip-section");
    group.appendChild(el("h5","equipment-tooltip-section-title",title));
    const list=el("div","equipment-tooltip-option-list");
    entries.forEach(([key,raw])=>{
        const row=el("div","equipment-tooltip-option");
        row.append(el("span","",OPTION_LABELS[key]||key.replace(/_/g," ")),el("strong","",fmt(raw)));
        list.appendChild(row);
    });
    group.appendChild(list); parent.appendChild(group);
}
function addPotentialGroup(parent,item,prefix,title) {
    const grade=item[prefix+"_grade"];
    const lines=[1,2,3].map(i=>item[prefix+"_"+i]).filter(present);
    if(!present(grade)&&!lines.length) return;
    const group=el("section","equipment-tooltip-section");
    const titleNode=el("h5","equipment-tooltip-section-title",title);
    if(present(grade)) titleNode.appendChild(el("strong","equipment-potential-grade",grade));
    group.appendChild(titleNode);
    lines.forEach(line=>group.appendChild(el("p","equipment-tooltip-potential-line",line)));
    parent.appendChild(group);
}
function renderItemTooltip(item) {
    const tip=el("div","equipment-game-tooltip");
    const stars=Number(item.starforce??item.item_starforce??0);
    const top=el("div","equipment-tooltip-topline");
    top.append(el("span","equipment-tooltip-stars","★ "+(Number.isFinite(stars)?stars:0)),
        el("span","equipment-tooltip-enhance",present(item.scroll_upgrade)?"주문서 "+item.scroll_upgrade+"회":""));
    tip.appendChild(top);
    const head=el("div","equipment-tooltip-item-heading");
    const icon=image(item.item_icon,item.item_name||"장비 아이콘","equipment-tooltip-icon");
    if(icon) head.appendChild(icon);
    const names=el("div","equipment-tooltip-item-names");
    names.append(el("strong","equipment-tooltip-item-name",item.item_name||"이름 정보 없음"),
        el("span","equipment-tooltip-item-part",item.item_equipment_part||item.item_equipment_slot||""));
    head.appendChild(names); tip.appendChild(head);
    addOptionGroup(tip,"기본 옵션",item.item_base_option);
    addOptionGroup(tip,"추가 옵션",item.item_add_option);
    addOptionGroup(tip,"주문서 옵션",item.item_etc_option);
    addOptionGroup(tip,"스타포스 옵션",item.item_starforce_option);
    addPotentialGroup(tip,item,"potential_option","잠재능력");
    addPotentialGroup(tip,item,"additional_potential_option","에디셔널 잠재능력");
    if(present(item.soul_name)||present(item.soul_option)) {
        const group=el("section","equipment-tooltip-section");
        group.appendChild(el("h5","equipment-tooltip-section-title","소울"));
        if(present(item.soul_name)) group.appendChild(el("p","equipment-tooltip-potential-line",item.soul_name));
        if(present(item.soul_option)) group.appendChild(el("p","equipment-tooltip-potential-line",item.soul_option));
        tip.appendChild(group);
    }
    return tip;
}
function renderEquipmentSection(data) {
    const content=el("div","game-equipment-layout"), source=sourceById(data,"itemEquipment"), setSource=sourceById(data,"setEffect");
    if(!source||source.status==="unavailable") {
        content.appendChild(el("p","game-empty",source?.message||"장비 정보를 조회할 수 없습니다.")); return content;
    }
    const number=data.selectedEquipmentPreset??fallbackPreset(source);
    const toolbar=el("div","game-equipment-toolbar");
    toolbar.append(el("span","game-window-eyebrow","EQUIPMENT"),el("h3","game-window-title","장착 장비"));
    if(source.presets?.length>1) toolbar.appendChild(presetSelect(source,"equipment",number,next=>{
        const updated=renderEquipmentSection({...data,selectedEquipmentPreset:next});
        content.replaceChildren(...updated.childNodes);
    }));
    content.appendChild(toolbar);
    const items=equippedItems(source,number), board=el("div","game-equipment-board");
    SLOT_DEFS.forEach(([slotName,slotKey])=>{
        const item=items.find(candidate=>matchesSlot(candidate,slotName));
        const slot=el("div","equipment-game-slot"+(item?" is-equipped":" is-empty"));
        slot.dataset.slot=slotKey; slot.tabIndex=item?0:-1;
        slot.setAttribute("aria-label",item?slotName+" · "+item.item_name:slotName+" 비어 있음");
        slot.appendChild(el("span","equipment-slot-caption",slotName));
        const iconWrap=el("span","equipment-game-icon-frame");
        if(item) {
            const icon=image(item.item_icon,item.item_name||slotName,"");
            if(icon) iconWrap.appendChild(icon); else iconWrap.appendChild(el("span","equipment-empty-icon","—"));
            slot.append(iconWrap,el("strong","equipment-game-item-name",item.item_name||"장착 아이템"));
            const stars=Number(item.starforce??item.item_starforce??0);
            if(stars>0) slot.appendChild(el("span","equipment-game-star","★ "+stars));
            slot.appendChild(renderItemTooltip(item));
        } else {
            iconWrap.appendChild(el("span","equipment-empty-icon","+"));
            slot.append(iconWrap,el("span","equipment-game-item-name is-empty","비어 있음"));
        }
        board.appendChild(slot);
    });
    content.appendChild(board);

    const sets=setSource?.currentData?.set_effect||setSource?.data?.set_effect||[];
    if(Array.isArray(sets)&&sets.length) {
        const panel=el("section","game-set-effects"); panel.appendChild(el("h3","game-window-title","세트 효과"));
        const grid=el("div","game-set-grid");
        sets.forEach(set=>{
            const tile=el("div","game-set-item");
            tile.append(el("strong","",set.set_name||"세트"),el("span","",set.total_parts?set.total_parts+"세트":""));
            grid.appendChild(tile);
        });
        panel.appendChild(grid); content.appendChild(panel);
    }
    return content;
}
function renderSymbolsSection(data) {
    const source=sourceById(data,"symbolEquipment"), content=el("div","game-symbol-window");
    if(!source||source.status!=="available") {
        content.appendChild(el("p","game-empty",source?.message||"심볼 정보를 조회할 수 없습니다.")); return content;
    }
    const symbols=source.currentData?.symbol||source.data?.symbol||[];
    if(!Array.isArray(symbols)||!symbols.length) {
        content.appendChild(el("p","game-empty","장착된 심볼 정보가 없습니다.")); return content;
    }
    const grid=el("div","game-symbol-grid");
    symbols.forEach(symbol=>{
        const tile=el("article","game-symbol-tile");
        const icon=image(symbol.symbol_icon,symbol.symbol_name||"심볼","game-symbol-icon");
        if(icon) tile.appendChild(icon);
        tile.append(el("strong","game-symbol-name",symbol.symbol_name||"심볼"),
            el("span","game-symbol-level","Lv. "+(symbol.symbol_level??"—")));
        if(present(symbol.symbol_force)) tile.appendChild(el("span","game-symbol-force","포스 "+symbol.symbol_force));
        grid.appendChild(tile);
    });
    content.appendChild(grid); return content;
}
function renderSkillsSection(data) {
    const content=el("div","game-skill-window");
    const skillSource=sourceById(data,"skill6"), hexaSource=sourceById(data,"hexaMatrix"), hexaStat=sourceById(data,"hexaStat");
    const skills=skillSource?.data?.character_skill||[];
    const panel=el("section","game-sixth-skill-panel");
    panel.append(el("span","game-window-eyebrow","6TH JOB"),el("h3","game-window-title","6차 스킬"));
    const grid=el("div","game-sixth-skill-grid");
    if(Array.isArray(skills)) skills.forEach(skill=>{
        const tile=el("article","game-sixth-skill-tile");
        const icon=image(skill.skill_icon,skill.skill_name||"6차 스킬","game-sixth-skill-icon");
        if(icon) tile.appendChild(icon);
        tile.append(el("strong","game-sixth-skill-name",skill.skill_name||"스킬"),
            el("span","game-sixth-skill-level","Lv. "+(skill.skill_level??"—")));
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty",skillSource?.message||"조회된 6차 스킬이 없습니다."));
    panel.appendChild(grid); content.appendChild(panel);

    const cores=hexaSource?.data?.character_hexa_core_equipment||[];
    const hexa=el("section","game-hexa-panel"); hexa.appendChild(el("h3","game-window-title","HEXA 매트릭스"));
    const coreGrid=el("div","game-hexa-grid");
    if(Array.isArray(cores)) cores.forEach(core=>{
        const tile=el("div","game-hexa-tile");
        tile.append(el("span","game-hexa-kind",core.hexa_core_type||"코어"),
            el("strong","game-hexa-name",core.hexa_core_name||"HEXA 코어"),
            el("span","game-hexa-level","Lv. "+(core.hexa_core_level??"—")));
        coreGrid.appendChild(tile);
    });
    if(!coreGrid.childElementCount) coreGrid.appendChild(el("p","game-empty",hexaSource?.message||"조회된 HEXA 코어가 없습니다."));
    hexa.appendChild(coreGrid); content.appendChild(hexa);

    const stats=hexaStat?.data?.character_hexa_stat_core||[];
    if(Array.isArray(stats)&&stats.length) {
        const statPanel=el("section","game-hexa-stat-panel");
        statPanel.appendChild(el("h3","game-window-title","HEXA 스탯"));
        const statGrid=el("div","game-hexa-grid");
        stats.forEach(stat=>{
            const tile=el("div","game-hexa-tile");
            tile.append(el("strong","game-hexa-name",stat.stat_type||stat.stat_name||"스탯"),
                el("span","game-hexa-level","Lv. "+(stat.stat_level??"—")));
            statGrid.appendChild(tile);
        });
        statPanel.appendChild(statGrid); content.appendChild(statPanel);
    }
    return content;
}
function renderLinkSection(data) {
    const source=sourceById(data,"linkSkill"), content=el("div","game-link-window");
    if(!source||source.status==="unavailable") {
        content.appendChild(el("p","game-empty",source?.message||"링크 스킬 정보를 조회할 수 없습니다.")); return content;
    }
    const number=data.selectedLinkPreset??fallbackPreset(source), raw=presetData(source,number);
    const links=[...(Array.isArray(raw.character_link_skill)?raw.character_link_skill:[]),
        ...(raw.character_owned_link_skill?[raw.character_owned_link_skill]:[])];
    const toolbar=el("div","game-equipment-toolbar");
    toolbar.append(el("span","game-window-eyebrow","LINK SKILL"),el("h3","game-window-title","링크 스킬"));
    if(source.presets?.length>1) toolbar.appendChild(presetSelect(source,"link",number,next=>{
        const updated=renderLinkSection({...data,selectedLinkPreset:next});
        content.replaceChildren(...updated.childNodes);
    }));
    content.appendChild(toolbar);
    const grid=el("div","game-link-grid");
    links.forEach(skill=>{
        const tile=el("article","game-link-tile");
        const icon=image(skill.skill_icon,skill.skill_name||"링크 스킬","game-link-icon");
        if(icon) tile.appendChild(icon);
        tile.append(el("strong","game-link-name",skill.skill_name||"링크 스킬"),
            el("span","game-link-level","Lv. "+(skill.skill_level??"—")));
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty","장착된 링크 스킬이 없습니다."));
    content.appendChild(grid); return content;
}
function renderUnionSection(data) {
    const content=el("div","game-union-window"), base=sourceById(data,"union");
    const raider=sourceById(data,"unionRaider"), artifact=sourceById(data,"unionArtifact");
    const baseData=base?.data||{}, summary=el("div","game-union-summary");
    [["유니온 레벨",baseData.union_level],["유니온 등급",baseData.union_grade],
     ["아티팩트 레벨",baseData.union_artifact_level],["아티팩트 포인트",baseData.union_artifact_point]]
      .forEach(([label,value])=>{
        if(!present(value)) return;
        const tile=el("div","game-union-stat");
        tile.append(el("span","",label),el("strong","",fmt(value))); summary.appendChild(tile);
      });
    if(summary.childElementCount) content.appendChild(summary);
    const number=fallbackPreset(raider), raidData=presetData(raider,number);
    const panel=el("section","game-union-raider"); panel.appendChild(el("h3","game-window-title","공격대 효과"));
    const effectTerms=["보스 데미지","방어율 무시","크리티컬 데미지","일반 몬스터","경험치","메소 획득량","아이템 드롭률"];
    const text=JSON.stringify(raidData);
    const found=effectTerms.filter(term=>text.includes(term));
    if(found.length) {
        const grid=el("div","game-union-effect-grid");
        found.forEach(value=>grid.appendChild(el("span","game-union-effect",value)));
        panel.appendChild(grid);
    } else panel.appendChild(el("p","game-empty","공격대 효과 정보가 없습니다."));
    content.appendChild(panel);
    if(artifact?.status==="available") {
        const artifactPanel=el("section","game-union-artifact");
        artifactPanel.appendChild(el("h3","game-window-title","유니온 아티팩트"));
        Object.entries(artifact.data||{}).filter(([key,value])=>/level|point|exp/i.test(key)&&present(value)&&typeof value!=="object")
          .forEach(([key,value])=>{
            const row=el("div","game-union-stat");
            row.append(el("span","",key.replace(/_/g," ")),el("strong","",fmt(value)));
            artifactPanel.appendChild(row);
          });
        content.appendChild(artifactPanel);
    }
    return content;
}

export function initCharacterDetails({apiFetch,readApiResponse,onStatsLoaded=()=>{}}) {
    const section=document.getElementById("characterDetailsSection");
    const content=document.getElementById("characterDetailsContent");
    const notice=document.getElementById("characterDetailsNotice");
    const tabs=Array.from(document.querySelectorAll("[data-detail-tab]"));
    let currentOcid="", requestToken=0, activeSection="stats";
    const cache=new Map();
    let statsData=null, selectedNumbers={}, profileMode="current";

    function setNotice(message,warning=false) {
        if(!notice) return;
        notice.textContent=message||"";
        notice.classList.toggle("is-warning",warning);
        notice.hidden=!message;
    }
    function updateTabs(name) {
        tabs.forEach(tab=>{
            const active=tab.dataset.detailTab===name;
            tab.setAttribute("aria-selected",active?"true":"false");
            tab.classList.toggle("is-active",active);
        });
    }
    function renderStats(data) {
        const handleChange=(nextMode,category,number)=>{
            if(nextMode==="custom") {
                selectedNumbers[category]=number;
                profileMode="custom";
            } else {
                profileMode=nextMode;
                selectedNumbers=initialSelection(statsData,nextMode);
            }
            renderStats(data);
        };
        content.replaceChildren(renderStatsSection(data,profileMode,selectedNumbers,handleChange));
        onStatsLoaded(data);
    }
    function render(data,name) {
        if(!content) return;
        if(name==="stats") renderStats(data);
        else if(name==="equipment") content.replaceChildren(renderEquipmentSection(data));
        else if(name==="symbols") content.replaceChildren(renderSymbolsSection(data));
        else if(name==="skills") content.replaceChildren(renderSkillsSection(data));
        else if(name==="link") content.replaceChildren(renderLinkSection(data));
        else if(name==="union") content.replaceChildren(renderUnionSection(data));

        if(data.status==="partial") setNotice("일부 공개 데이터만 확인됐습니다. 조회되지 않은 항목은 임의로 채우지 않았습니다.",true);
        else if(data.status==="unavailable") setNotice("상세 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",true);
        else setNotice("넥슨 Open API의 공개 데이터를 게임 정보창 형태로 표시합니다. API 반영 시점은 게임 내 상태와 다를 수 있습니다.");
    }

    async function loadSection(name,force=false) {
        if(!currentOcid||!content) return;
        const token=++requestToken;
        activeSection=name; updateTabs(name);
        const key=currentOcid+":"+name, cached=!force?cache.get(key):null;
        if(cached) {
            if(name==="stats") {
                statsData=cached; profileMode=cached.defaultProfile||profileMode;
                selectedNumbers=initialSelection(cached,profileMode);
            }
            if(token===requestToken) render(cached,name);
            return;
        }
        content.replaceChildren(el("div","game-loading-window","캐릭터 "+({stats:"능력치",equipment:"장비",symbols:"심볼",skills:"6차 스킬",link:"링크 스킬",union:"유니온"}[name]||"정보")+" 조회 중..."));
        setNotice("");
        try {
            const url="/api/character-details?ocid="+encodeURIComponent(currentOcid)+
                "&section="+encodeURIComponent(name)+(force?"&refresh=1":"");
            const response=await apiFetch(url);
            const data=await readApiResponse(response,"캐릭터 상세 정보를 불러오지 못했습니다.");
            if(token!==requestToken) return;
            cache.set(key,data);
            if(name==="stats") {
                statsData=data; profileMode=data.defaultProfile||"current";
                selectedNumbers=initialSelection(data,profileMode);
            }
            render(data,name);
        } catch(error) {
            if(token!==requestToken) return;
            content.replaceChildren(el("p","game-empty",error.message||"상세 정보를 불러오지 못했습니다."));
            setNotice("상세 데이터 조회에 실패했습니다.",true);
        }
    }
    function setCharacter(ocid) {
        currentOcid=typeof ocid==="string"?ocid.trim():"";
        requestToken++; cache.clear(); statsData=null; selectedNumbers={}; profileMode="current";
        if(content) content.replaceChildren(el("div","game-empty",currentOcid?"캐릭터 스탯 정보를 준비하고 있습니다.":"캐릭터를 먼저 조회해주세요."));
        setNotice("");
        tabs.forEach(tab=>{
            tab.disabled=!currentOcid; tab.setAttribute("aria-selected","false"); tab.classList.remove("is-active");
        });
        if(currentOcid) loadSection("stats");
    }
    tabs.forEach(tab=>{
        tab.disabled=true;
        tab.addEventListener("click",()=>loadSection(tab.dataset.detailTab));
    });
    const refresh=document.getElementById("refreshCharacterDetailsButton");
    if(refresh) refresh.addEventListener("click",()=>loadSection(activeSection,true));
    if(section) section.hidden=false;
    setCharacter("");
    return {setCharacter,loadSection};
}
