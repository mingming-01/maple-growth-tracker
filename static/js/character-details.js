/** MapleStory in-client inspired character detail windows. */

const PRESET_CATEGORY = {
    itemEquipment: "equipment", ability: "ability",
    linkSkill: "link", unionStateStat: "union"
};
const REQUIRED_PRESET_KEYS = ["equipment", "ability", "link", "union"];

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
// [표시명, 내부 키, 행, 열] — 좌측 4x2 / 우측 4x2 / 하단 2x7
const SLOT_DEFS = [
    ["반지 1","ring1",1,1],["얼굴장식","face",1,2],
    ["반지 2","ring2",2,1],["눈장식","eye",2,2],
    ["반지 3","ring3",3,1],["귀고리","ear",3,2],
    ["반지 4","ring4",4,1],["펜던트 1","pendant1",4,2],
    ["모자","hat",1,6],["망토","cape",1,7],
    ["상의","top",2,6],["장갑","gloves",2,7],
    ["하의","bottom",3,6],["신발","shoes",3,7],
    ["어깨장식","shoulder",4,6],["훈장","medal",4,7],
    ["벨트","belt",5,1],["펜던트 2","pendant2",5,2],
    ["헤어","hair",5,3],["성형","faceStyle",5,4],["피부","skin",5,5],
    ["안드로이드","android",5,6],["하트","heart",5,7],
    ["포켓","pocket",6,1],["빈 슬롯","empty1",6,2],
    ["무기","weapon",6,3],["보조무기","subweapon",6,4],
    ["엠블렘","emblem",6,5],["빈 슬롯","empty5",6,6],["뱃지","badge",6,7]
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
        option.textContent=item.number===0?"현재 구성":"프리셋 "+item.number;
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
    const wanted=/^(STR|DEX|INT|LUK|공격력|마력|보스 몬스터 공격 시 데미지|보스 데미지|몬스터 방어율 무시|크리티컬 데미지|크리티컬 확률|데미지|최종 데미지|메소 획득량|아이템 드롭률|아이템 획득률|추가 경험치 획득량|경험치 획득량|일반 몬스터 공격 시 데미지|재사용 대기시간 감소|재사용 대기시간 미적용|버프 지속시간|쿨타임 감소|공격 속도|이동 속도)$/;
    const grid=el("div","game-stat-grid");
    (Array.isArray(finalStats)?finalStats:[]).forEach(item=>{
        const name=String(item?.stat_name||"").trim();
        if(!wanted.test(name)||!present(item?.stat_value)||name==="전투력") return;
        const tile=el("div","game-stat-tile");
        tile.append(el("span","game-stat-name",STAT_LABELS[name]||name),el("strong","game-stat-number",fmt(item.stat_value)));
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty","스탯 정보를 확인할 수 없습니다."));
    panel.appendChild(grid);

    const extraGrid=el("div","game-stat-extra-grid");
    const abilitySource=sourceById(data,"ability");
    const abilityNumber=selection?.ability??abilitySource?.activePresetNo;
    const abilityData=presetData(abilitySource,abilityNumber);
    const abilityPanel=el("section","game-stat-detail-card");
    abilityPanel.appendChild(el("h4","game-window-title","어빌리티"));
    abilityPanel.appendChild(el("span","game-stat-detail-grade",abilityData.ability_grade||abilitySource?.data?.ability_grade||"등급 정보 없음"));
    const abilityRows=Array.isArray(abilityData.ability_info)?abilityData.ability_info:[];
    const abilityList=el("div","game-stat-detail-list");
    abilityRows.forEach(item=>{
        const row=el("div","game-stat-detail-row");
        row.append(el("span","game-stat-detail-name",item?.ability_grade||"어빌리티"),
            el("strong","game-stat-detail-value",item?.ability_value||"효과 정보 없음"));
        abilityList.appendChild(row);
    });
    if(!abilityList.childElementCount) abilityList.appendChild(el("p","game-empty","어빌리티 정보가 없습니다."));
    abilityPanel.appendChild(abilityList);
    extraGrid.appendChild(abilityPanel);

    const hyperSource=sourceById(data,"hyperStat");
    const hyperNumber=hyperSource?.activePresetNo??fallbackPreset(hyperSource);
    const hyperData=presetData(hyperSource,hyperNumber);
    const hyperPanel=el("section","game-stat-detail-card");
    hyperPanel.appendChild(el("h4","game-window-title","하이퍼 스탯"));
    const hyperRows=Array.isArray(hyperData.hyper_stat)?hyperData.hyper_stat:[];
    const invested=hyperRows.filter(item=>Number(item?.stat_level)>0);
    const hyperGrid=el("div","game-hyper-stat-list");
    invested.forEach(item=>{
        const tile=el("div","game-hyper-stat-item");
        tile.append(el("span","game-hyper-stat-name",item.stat_type||"스탯"),
            el("strong","game-hyper-stat-level","Lv. "+fmt(item.stat_level)));
        if(present(item.stat_increase)) tile.appendChild(el("span","game-hyper-stat-increase",String(item.stat_increase)));
        hyperGrid.appendChild(tile);
    });
    if(!hyperGrid.childElementCount) hyperGrid.appendChild(el("p","game-empty","투자된 하이퍼 스탯이 없습니다."));
    hyperPanel.appendChild(hyperGrid);
    extraGrid.appendChild(hyperPanel);
    panel.appendChild(extraGrid);

    panel.appendChild(el("p","game-stat-source-note",
        "위 최종 능력치와 전투력은 현재 게임 적용 상태의 Nexon API 값입니다. 프리셋 선택 시 어빌리티·하이퍼 스탯 구성이 함께 바뀌며, 비활성 조합의 최종 합산 능력치는 API에서 제공되지 않아 임의 계산하지 않습니다."));
    return panel;
}

function summaryFor(source,number) {
    const data=presetData(source,number);
    if(source.id==="itemEquipment") {
        const items=Array.isArray(data.item_equipment)?data.item_equipment:[];
        const hints=items.filter(item=>item?.item_name).slice(0,8).map(item=>item.item_name);
        const optionText=items.flatMap(item=>[
            item?.potential_option_1,item?.potential_option_2,item?.potential_option_3,
            item?.additional_potential_option_1,item?.additional_potential_option_2,item?.additional_potential_option_3,
            item?.soul_option
        ]).filter(Boolean);
        const highlights=optionText.filter(text=>/메소 획득량|아이템 드롭률|재사용 대기시간|쿨타임|경험치 획득/.test(text));
        return {title:"장비",detail:items.length+"개 장착",hints:[...hints,...highlights]};
    }
    if(source.id==="ability") {
        const ability=Array.isArray(data.ability_info)?data.ability_info:[];
        return {title:"어빌리티",detail:data.ability_grade||source.data?.ability_grade||"",hints:ability.map(item=>[item?.ability_grade,item?.ability_value].filter(Boolean).join(" · ")).filter(Boolean)};
    }
    if(source.id==="linkSkill") {
        const links=[...(Array.isArray(data.character_link_skill)?data.character_link_skill:[]),
            ...(data.character_owned_link_skill?[data.character_owned_link_skill]:[])];
        return {title:"링크 스킬",detail:links.length+"개 장착",hints:links.map(item=>item?.skill_name).filter(Boolean).slice(0,4)};
    }
    if(source.id==="unionStateStat") {
        const effects=Array.isArray(data.union_state_stat)?data.union_state_stat:[];
        return {title:"유니온 스탯",detail:"프리셋 "+(number??"—"),hints:effects};
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
    const selectableCategories=["equipment","ability","union"];
    (data.sources||[]).forEach(source=>{
        const category=PRESET_CATEGORY[source.id];
        if(!selectableCategories.includes(category)||!Array.isArray(source.presets)||!source.presets.length) return;
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
    return layout;
}

function equippedItems(source,number) {
    const data=presetData(source,number);
    return Array.isArray(data.item_equipment)?data.item_equipment:[];
}
function matchesSlot(item,slot) {
    const actual=String(item?.item_equipment_slot||item?.item_equipment_part||"").replace(/\s/g,"");
    const expected=slot.replace(/\s/g,"");
    return actual===expected || actual.includes(expected);
}
function findEquipmentForSlot(items,slotName,slotKey) {
    if(slotKey.startsWith("empty")) return null;
    if(/^ring[1-4]$/.test(slotKey)) {
        const ringNo=Number(slotKey.slice(-1));
        const rings=items.filter(item=>/반지/.test(String(item?.item_equipment_slot||item?.item_equipment_part||"")));
        const explicit=rings.find(item=>new RegExp("반지\\s*"+ringNo+"(?:$|[^0-9])").test(String(item?.item_equipment_slot||"")));
        return explicit||rings[ringNo-1]||null;
    }
    if(slotKey==="pendant1"||slotKey==="pendant2") {
        const pendants=items.filter(item=>/펜던트/.test(String(item?.item_equipment_slot||item?.item_equipment_part||"")));
        const explicit=pendants.find(item=>slotKey==="pendant2"
            ? /펜던트\s*2|슬롯\s*2/.test(String(item?.item_equipment_slot||""))
            : /펜던트\s*1/.test(String(item?.item_equipment_slot||"")));
        return explicit||pendants[slotKey==="pendant1"?0:1]||null;
    }
    const aliases={"android":["안드로이드"],"heart":["기계 심장","하트"],"pocket":["포켓 아이템","포켓"]};
    const candidates=aliases[slotKey]||[slotName];
    return items.find(item=>candidates.some(name=>matchesSlot(item,name)))||null;
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
    if(present(grade)) {
        const gradeNode=el("strong","equipment-potential-grade",grade);
        if(String(grade).includes("레전드리")) gradeNode.classList.add("is-legendary");
        titleNode.appendChild(gradeNode);
    }
    group.appendChild(titleNode);
    lines.forEach(line=>group.appendChild(el("p","equipment-tooltip-potential-line",line)));
    parent.appendChild(group);
}
function addCombinedOptionGroup(parent,item) {
    const sources=[
        ["기본","item_base_option","base"],
        ["추가","item_add_option","additional"],
        ["주문서","item_etc_option","scroll"],
        ["스타포스","item_starforce_option","starforce"]
    ];
    const keys=[...new Set(sources.flatMap(([,key])=>Object.keys(item[key]||{})))];
    const rows=[];
    keys.forEach(key=>{
        const parts=sources.map(([label,source,className])=>{
            const raw=item[source]?.[key];
            const number=Number(String(raw??"").replace(/,/g,""));
            return {label,className,value:Number.isFinite(number)?number:null};
        }).filter(part=>part.value!==null&&part.value!==0);
        if(!parts.length) return;
        const total=parts.reduce((sum,part)=>sum+part.value,0);
        rows.push({key,parts,total});
    });
    if(!rows.length) return;
    const group=el("section","equipment-tooltip-section equipment-tooltip-combined");
    group.appendChild(el("h5","equipment-tooltip-section-title","능력치 합산"));
    const list=el("div","equipment-tooltip-option-list");
    rows.forEach(row=>{
        const line=el("div","equipment-tooltip-combined-row");
        line.appendChild(el("span","equipment-tooltip-combined-name",OPTION_LABELS[row.key]||row.key.replace(/_/g," ")));
        const values=el("span","equipment-tooltip-combined-values");
        row.parts.forEach(part=>values.appendChild(el("span","equipment-option-"+part.className,
            part.label+" "+(part.value>0?"+":"")+fmt(part.value))));
        values.appendChild(el("strong","equipment-option-total",(row.total>0?"+":"")+fmt(row.total)));
        line.appendChild(values); list.appendChild(line);
    });
    group.appendChild(list); parent.appendChild(group);
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
    addCombinedOptionGroup(tip,item);
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
function renderEquipmentSection(data,onPresetChange=()=>{}) {
    const content=el("div","game-equipment-layout"), source=sourceById(data,"itemEquipment"), setSource=sourceById(data,"setEffect");
    if(!source||source.status==="unavailable") {
        content.appendChild(el("p","game-empty",source?.message||"장비 정보를 조회할 수 없습니다.")); return content;
    }
    const number=data.selectedEquipmentPreset??fallbackPreset(source);
    const toolbar=el("div","game-equipment-toolbar");
    toolbar.append(el("span","game-window-eyebrow","EQUIPMENT"),el("h3","game-window-title","장착 장비"));
    if(source.presets?.length>1) toolbar.appendChild(presetSelect(source,"equipment",number,next=>{
        onPresetChange(next);
        const updated=renderEquipmentSection({...data,selectedEquipmentPreset:next},onPresetChange);
        content.replaceChildren(...updated.childNodes);
    }));
    content.appendChild(toolbar);
    const items=equippedItems(source,number), board=el("div","game-equipment-board");
    const appearanceSource=sourceById(data,"characterAppearance");
    const appearance=appearanceSource?.currentData||appearanceSource?.data||{};
    const equipmentData=source.currentData||source.data||{};
    const androidName=equipmentData.android_name||equipmentData.android_nickname||"";
    const androidIcon=equipmentData.android_icon||"";
    board.style.display="grid";
    board.style.gridTemplateColumns="repeat(7,minmax(0,1fr))";
    board.style.gridTemplateRows="repeat(4,minmax(104px,auto)) repeat(2,minmax(92px,auto))";
    SLOT_DEFS.forEach(([slotName,slotKey,row,column])=>{
        const appearanceFields={hair:"character_hair",faceStyle:"character_face",skin:"character_skin_name"};
        const rawAppearance=appearanceFields[slotKey]?appearance[appearanceFields[slotKey]]:null;
        const appearanceValue=slotKey==="hair"
            ? (rawAppearance?.hair_name||rawAppearance?.name||rawAppearance)
            : slotKey==="faceStyle"
                ? (rawAppearance?.face_name||rawAppearance?.name||rawAppearance)
                : (rawAppearance?.skin_name||rawAppearance?.name||rawAppearance);
        const item=findEquipmentForSlot(items,slotName,slotKey);
        const hasAppearance=present(appearanceValue);
        const hasAndroid=slotKey==="android"&&(present(androidName)||present(androidIcon));
        const slot=el("div","equipment-game-slot"+((item||hasAppearance||hasAndroid)?" is-equipped":" is-empty"));
        slot.dataset.slot=slotKey; slot.style.gridRow=String(row); slot.style.gridColumn=String(column);
        slot.tabIndex=(item||hasAndroid)?0:-1;
        slot.setAttribute("aria-label",slotName+" · "+(hasAndroid?androidName||"안드로이드":item?.item_name||appearanceValue||"비어 있음"));
        slot.appendChild(el("span","equipment-slot-caption",slotName));
        const iconWrap=el("span","equipment-game-icon-frame");
        if(slotKey==="hair"||slotKey==="faceStyle"||slotKey==="skin") {
            const value=appearanceValue;
            iconWrap.appendChild(el("span","equipment-appearance-symbol",slotKey==="hair"?"✂":slotKey==="faceStyle"?"☺":"◉"));
            slot.append(iconWrap,el("strong","equipment-game-item-name",value?String(value):"정보 없음"));
        } else if(slotKey==="android"&&hasAndroid) {
            const icon=image(androidIcon,androidName||"안드로이드","");
            if(icon) iconWrap.appendChild(icon);
            else if(item?.item_icon) {
                const fallback=image(item.item_icon,item.item_name||"안드로이드","");
                if(fallback) iconWrap.appendChild(fallback);
            }
            slot.append(iconWrap,el("strong","equipment-game-item-name",androidName||item?.item_name||"안드로이드"));
            addHoverTooltip(slot,androidName||"안드로이드",[
                equipmentData.android_grade? "등급 · "+equipmentData.android_grade:null,
                equipmentData.android_gender? "성별 · "+equipmentData.android_gender:null,
                equipmentData.android_ear_sensor? "이어센서 · "+equipmentData.android_ear_sensor:null,
                equipmentData.android_description
            ]);
        } else if(item) {
            const icon=image(item.item_icon,item.item_name||slotName,"");
            if(icon) iconWrap.appendChild(icon); else iconWrap.appendChild(el("span","equipment-empty-icon","—"));
            slot.append(iconWrap,el("strong","equipment-game-item-name",item.item_name||"장착 아이템"));
            const stars=Number(item.starforce??item.item_starforce??0);
            if(stars>0) slot.appendChild(el("span","equipment-game-star","★ "+stars));
            slot.appendChild(renderItemTooltip(item));
            if(String(item.item_name||"").includes("리스트레인트 링")) {
                const gear=el("button","equipment-seed-ring-toggle","⚙");
                gear.type="button"; gear.setAttribute("aria-label","컨티뉴어스 링 정보 보기");
                gear.addEventListener("click",event=>{
                    event.stopPropagation();
                    const old=slot.querySelector(".equipment-seed-ring-panel");
                    if(old) { old.remove(); return; }
                    const continuous=items.find(candidate=>String(candidate.item_name||"").includes("컨티뉴어스 링"));
                    const detail=el("div","equipment-seed-ring-panel");
                    detail.appendChild(el("strong","", "컨티뉴어스 링"));
                    if(continuous) {
                        const icon=image(continuous.item_icon,continuous.item_name,"equipment-seed-ring-icon");
                        if(icon) detail.appendChild(icon);
                        detail.appendChild(el("span","",continuous.item_name));
                        detail.appendChild(el("span","",continuous.item_description||"장비 API에서 제공된 정보"));
                    } else detail.appendChild(el("span","","선택한 프리셋의 장비 응답에 컨티뉴어스 링 데이터가 없습니다."));
                    slot.appendChild(detail);
                });
                slot.appendChild(gear);
            }
        } else {
            iconWrap.appendChild(el("span","equipment-empty-icon","+"));
            slot.append(iconWrap,el("span","equipment-game-item-name is-empty",slotName==="빈 슬롯"?"":"비어 있음"));
        }
        board.appendChild(slot);
    });

    const panel=el("section","game-set-effects");
    panel.appendChild(el("h3","game-window-title","세트 효과"));
    const grid=el("div","game-set-grid");
    const isActivePreset=present(source.activePresetNo)&&Number(source.activePresetNo)===Number(number);
    const sets=isActivePreset
        ? (setSource?.currentData?.set_effect||setSource?.data?.set_effect||[])
        : [];
    if(isActivePreset&&Array.isArray(sets)&&sets.length) {
        sets.forEach(set=>{
            const tile=el("div","game-set-item");
            tile.append(el("strong","",set.set_name||"세트"),
                el("span","",present(set.total_set_count)?set.total_set_count+"개 부위 적용":"적용 부위 수 미제공"));
            grid.appendChild(tile);
        });
    } else {
        panel.appendChild(el("p","game-set-unavailable",isActivePreset
            ? (setSource?.message||"현재 적용 장비의 세트 효과를 조회할 수 없습니다.")
            : "선택한 장비 프리셋의 세트효과는 현재 API에서 별도로 제공하지 않습니다."));
    }
    if(grid.childElementCount) panel.appendChild(grid);
    content.appendChild(board);
    content.appendChild(panel);
    return content;
}
function addHoverTooltip(parent,title,lines,className="game-hover-tooltip") {
    const values=(lines||[]).filter(value=>present(value));
    if(!values.length) return null;
    const tip=el("div",className);
    if(title) tip.appendChild(el("strong","game-hover-tooltip-title",title));
    values.forEach(value=>tip.appendChild(el("p","game-hover-tooltip-line",value)));
    parent.appendChild(tip);
    parent.classList.add("has-hover-tooltip");
    return tip;
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
        const growthValue=symbol.symbol_growth_count;
        const requiredValue=symbol.symbol_require_growth_count;
        const growth=Number(growthValue||0);
        const required=Number(requiredValue||0);
        const isMax=present(requiredValue)&&required<=0;
        const growthLines=[
            symbol.symbol_description,
            isMax?"성장량 MAX":present(requiredValue)?"성장량 "+fmt(growth)+" / "+fmt(required):"성장량 정보 없음",
            isMax?"최대 레벨 달성":present(requiredValue)?"다음 레벨까지 "+fmt(Math.max(0,required-growth))+" 남음":null,
            present(symbol.symbol_drop_rate)?"아이템 드롭률 "+symbol.symbol_drop_rate:null,
            present(symbol.symbol_meso_rate)?"메소 획득량 "+symbol.symbol_meso_rate:null,
            present(symbol.symbol_exp_rate)?"경험치 획득량 "+symbol.symbol_exp_rate:null
        ];
        addHoverTooltip(tile,symbol.symbol_name||"심볼 성장 정보",growthLines);
        grid.appendChild(tile);
    });
    content.appendChild(grid); return content;
}

function renderSkillsSection(data) {
    const content=el("div","game-skill-window");
    const skillSource=sourceById(data,"skill6");
    const hexaSource=sourceById(data,"hexaMatrix");
    const hexaStat=sourceById(data,"hexaStat");

    const panel=el("section","game-sixth-skill-panel");
    panel.append(el("span","game-window-eyebrow","6TH JOB"),el("h3","game-window-title","6차 스킬 · HEXA 시스템"));
    panel.appendChild(el("p","game-sixth-explainer",
        "6차 스킬은 실제 습득한 스킬과 레벨을, HEXA 매트릭스는 HEXA 코어의 종류·강화 단계와 연결 스킬 구성을 보여줍니다. 서로 다른 데이터이므로 한 화면에서 구분해 확인할 수 있습니다."));
    const overview=el("div","game-sixth-overview-grid");

    const skillsPanel=el("section","game-sixth-subpanel");
    skillsPanel.append(el("h4","game-sixth-subtitle","6차 스킬"),el("p","game-sixth-caption","습득한 6차 스킬 및 현재 레벨"));
    const skills=skillSource?.data?.character_skill||[];
    const grid=el("div","game-sixth-skill-grid");
    if(Array.isArray(skills)) skills.forEach(skill=>{
        const tile=el("article","game-sixth-skill-tile");
        const icon=image(skill.skill_icon,skill.skill_name||"6차 스킬","game-sixth-skill-icon");
        if(icon) tile.appendChild(icon);
        tile.append(el("strong","game-sixth-skill-name",skill.skill_name||"스킬"),
            el("span","game-sixth-skill-level","Lv. "+(skill.skill_level??"—")));
        addHoverTooltip(tile,skill.skill_name||"스킬 정보",[
            skill.skill_description,
            present(skill.skill_effect)?"현재 효과 · "+skill.skill_effect:null,
            present(skill.skill_effect_next)?"다음 레벨 · "+skill.skill_effect_next:null
        ]);
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty",skillSource?.message||"조회된 6차 스킬이 없습니다."));
    skillsPanel.appendChild(grid);
    overview.appendChild(skillsPanel);

    const hexaPanel=el("section","game-sixth-subpanel");
    hexaPanel.append(el("h4","game-sixth-subtitle","HEXA 매트릭스"),el("p","game-sixth-caption","장착된 HEXA 코어와 코어에 연결된 스킬"));
    const cores=hexaSource?.data?.character_hexa_core_equipment||[];
    const coreGrid=el("div","game-hexa-grid");
    if(Array.isArray(cores)) cores.forEach(core=>{
        const tile=el("div","game-hexa-tile");
        const linked=Array.isArray(core.linked_skill)?core.linked_skill.map(item=>item?.hexa_skill_id).filter(Boolean):[];
        tile.append(el("span","game-hexa-kind",core.hexa_core_type||"코어"),
            el("strong","game-hexa-name",core.hexa_core_name||"HEXA 코어"),
            el("span","game-hexa-level","Lv. "+(core.hexa_core_level??"—")));
        addHoverTooltip(tile,core.hexa_core_name||"HEXA 코어",[
            core.hexa_core_type,
            linked.length?"연결 스킬 · "+linked.join(", "):null
        ]);
        coreGrid.appendChild(tile);
    });
    if(!coreGrid.childElementCount) coreGrid.appendChild(el("p","game-empty",hexaSource?.message||"조회된 HEXA 코어가 없습니다."));
    hexaPanel.appendChild(coreGrid);
    overview.appendChild(hexaPanel);
    panel.appendChild(overview);
    content.appendChild(panel);

    const hexaData=hexaStat?.data||{};
    const statPanel=el("section","game-hexa-stat-panel");
    statPanel.append(el("h3","game-window-title","HEXA 스탯"),el("p","game-sixth-caption","HEXA 1 · HEXA 2 · HEXA 3을 가로 3칸으로 배치했습니다. 각 코어에 마우스를 올리면 세부 능력치를 확인할 수 있습니다."));

    const appendStatRow=(title,definitions)=>{
        const groups=definitions.map(([label,key])=>({label,rows:Array.isArray(hexaData[key])?hexaData[key]:[]}));
        if(!groups.some(group=>group.rows.length)) return false;
        const row=el("section","game-hexa-stat-row");
        row.appendChild(el("h4","game-hexa-stat-heading",title));
        const columns=el("div","game-hexa-stat-columns");
        groups.forEach(group=>{
            const column=el("div","game-hexa-stat-column");
            column.appendChild(el("strong","game-hexa-stat-column-title",group.label));
            if(group.rows.length) group.rows.forEach(stat=>{
                const tile=el("article","game-hexa-tile game-hexa-stat-entry");
                const slot=present(stat.slot_id)?"슬롯 "+(Number(stat.slot_id)+1):null;
                tile.append(el("span","game-hexa-kind",slot||"스탯 코어"),
                    el("strong","game-hexa-name",stat.main_stat_name||"메인 스탯"),
                    el("span","game-hexa-level","Lv. "+(stat.main_stat_level??"—")));
                addHoverTooltip(tile,"HEXA 스탯 상세",[
                    (stat.main_stat_name||"메인 스탯")+" · Lv."+(stat.main_stat_level??"—"),
                    (stat.sub_stat_name_1||"서브 스탯 1")+" · Lv."+(stat.sub_stat_level_1??"—"),
                    (stat.sub_stat_name_2||"서브 스탯 2")+" · Lv."+(stat.sub_stat_level_2??"—"),
                    present(stat.stat_grade)?"코어 등급 "+stat.stat_grade:null
                ]);
                column.appendChild(tile);
            });
            else column.appendChild(el("p","game-empty","정보 없음"));
            columns.appendChild(column);
        });
        row.appendChild(columns);
        statPanel.appendChild(row);
        return true;
    };

    const currentFound=appendStatRow("현재 적용 중인 HEXA 스탯",[
        ["HEXA 1","character_hexa_stat_core"],
        ["HEXA 2","character_hexa_stat_core_2"],
        ["HEXA 3","character_hexa_stat_core_3"]
    ]);
    const presetFound=appendStatRow("저장된 프리셋 HEXA 스탯",[
        ["HEXA 1","preset_hexa_stat_core"],
        ["HEXA 2","preset_hexa_stat_core_2"],
        ["HEXA 3","preset_hexa_stat_core_3"]
    ]);
    if(!currentFound&&!presetFound) statPanel.appendChild(el("p","game-empty",hexaStat?.message||"HEXA 스탯 응답에 표시할 스탯 코어가 없습니다."));
    content.appendChild(statPanel);
    return content;
}

function renderLinkSection(data,selectedPresetNumber=null,onPresetChange=()=>{}) {
    const source=sourceById(data,"linkSkill"), content=el("div","game-link-window");
    if(!source||source.status==="unavailable") {
        content.appendChild(el("p","game-empty",source?.message||"링크 스킬 정보를 조회할 수 없습니다.")); return content;
    }
    const number=data.selectedLinkPreset??selectedPresetNumber??fallbackPreset(source), raw=presetData(source,number);
    const links=[...(Array.isArray(raw.character_link_skill)?raw.character_link_skill:[]),
        ...(raw.character_owned_link_skill?[raw.character_owned_link_skill]:[])];
    const toolbar=el("div","game-equipment-toolbar");
    toolbar.append(el("span","game-window-eyebrow","LINK SKILL"),el("h3","game-window-title","링크 스킬"));
    if(source.presets?.length>1) toolbar.appendChild(presetSelect(source,"link",number,next=>{
        onPresetChange(next);
        const updated=renderLinkSection({...data,selectedLinkPreset:next},next,onPresetChange);
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
        addHoverTooltip(tile,skill.skill_name||"링크 스킬",[
            skill.skill_description,
            present(skill.skill_effect)?"현재 효과 · "+skill.skill_effect:null,
            present(skill.skill_effect_next)?"다음 레벨 · "+skill.skill_effect_next:null
        ]);
        grid.appendChild(tile);
    });
    if(!grid.childElementCount) grid.appendChild(el("p","game-empty","장착된 링크 스킬이 없습니다."));
    content.appendChild(grid); return content;
}
function unionEffectTile(effect,index) {
    const raw=String(effect??"").trim();
    const match=raw.match(new RegExp("^(.+?)\\s+([+-]?\\d+(?:\\.\\d+)?%?)\\s*증가$"));
    const tile=el("article","game-union-state-stat");
    tile.append(
        el("span","game-union-state-index",String(index+1).padStart(2,"0")),
        el("strong","game-union-state-name",match?match[1]:raw||"효과 정보 없음"),
        el("span","game-union-state-value",match?match[2]+" 증가":"")
    );
    tile.title=raw;
    return tile;
}

function renderUnionArtifact(artifact,content) {
    const panel=el("section","game-union-artifact-panel");
    const heading=el("div","game-union-section-heading");
    heading.append(el("span","game-window-eyebrow","UNION ARTIFACT"),
        el("h3","game-window-title","유니온 아티팩트"));
    panel.appendChild(heading);
    if(!artifact||artifact.status==="unavailable") {
        panel.appendChild(el("p","game-empty",artifact?.message||"아티팩트 정보를 조회할 수 없습니다."));
        content.appendChild(panel);
        return;
    }

    const raw=artifact.currentData||artifact.data||{};
    const effects=Array.isArray(raw.union_artifact_effect)?raw.union_artifact_effect:[];
    const crystals=Array.isArray(raw.union_artifact_crystal)?raw.union_artifact_crystal:[];
    const summary=el("div","game-union-artifact-summary");
    if(present(raw.union_artifact_remain_ap)) {
        const remain=el("div","game-union-point-card");
        remain.append(el("span","","잔여 아티팩트 AP"),
            el("strong","",fmt(raw.union_artifact_remain_ap)));
        summary.appendChild(remain);
    }
    panel.appendChild(summary);

    const crystalPanel=el("div","game-union-subpanel");
    crystalPanel.appendChild(el("h4","game-union-subtitle","아티팩트 크리스탈"));
    const crystalGrid=el("div","game-union-crystal-grid");
    crystals.forEach((crystal,index)=>{
        const tile=el("article","game-union-crystal");
        const top=el("div","game-union-crystal-top");
        const order=el("span","game-union-crystal-order",String(index+1).padStart(2,"0"));
        top.appendChild(order);
        const mobUrl=crystal?.mob_icon||crystal?.monster_icon||crystal?.monster_image||crystal?.image_url||null;
        if(mobUrl) {
            const mobIcon=image(mobUrl,crystal?.name||"몬스터","game-union-crystal-monster");
            if(mobIcon) {
                const imageFrame=el("span","game-union-crystal-gem");
                mobIcon.addEventListener("error",()=>imageFrame.remove(),{once:true});
                imageFrame.appendChild(mobIcon);
                top.appendChild(imageFrame);
            }
        }
        top.append(el("strong","game-union-crystal-name",crystal?.name||"크리스탈"),
            el("span","game-union-crystal-level",present(crystal?.level)?"Lv. "+fmt(crystal.level):""));
        tile.appendChild(top);

        const valid=String(crystal?.validity_flag??"0")==="0" && crystal?.is_expired!==true;
        tile.appendChild(el("span","game-union-crystal-status "+(valid?"is-valid":"is-expired"),
            valid?"효과 적용 상태":"만료 또는 비활성"));
        const optionsList=el("div","game-union-crystal-options");
        [1,2,3].forEach(slot=>{
            const value=crystal?.["crystal_option_name_"+slot];
            if(present(value)) optionsList.appendChild(el("span","game-union-crystal-option",value));
        });
        if(optionsList.childElementCount) tile.appendChild(optionsList);
        if(present(crystal?.date_expire)&&crystal?.is_expired!==true) tile.appendChild(el("span","game-union-crystal-expiry","만료 예정 · "+String(crystal.date_expire)));
        crystalGrid.appendChild(tile);
    });
    if(crystalGrid.childElementCount) crystalPanel.appendChild(crystalGrid);
    else crystalPanel.appendChild(el("p","game-empty","등록된 아티팩트 크리스탈이 없습니다."));
    panel.appendChild(crystalPanel);

    const effectsPanel=el("div","game-union-subpanel");
    effectsPanel.appendChild(el("h4","game-union-subtitle","아티팩트 효과"));
    const effectGrid=el("div","game-union-artifact-effect-grid");
    effects.forEach(effect=>{
        const tile=el("article","game-union-artifact-effect");
        tile.append(el("strong","",effect?.name||"효과"),
            el("span","",present(effect?.level)?"Lv. "+fmt(effect.level):"레벨 정보 없음"));
        effectGrid.appendChild(tile);
    });
    if(effectGrid.childElementCount) effectsPanel.appendChild(effectGrid);
    else effectsPanel.appendChild(el("p","game-empty","조회된 아티팩트 효과가 없습니다."));
    panel.appendChild(effectsPanel);

    content.appendChild(panel);
}

function renderUnionChampions(championSource,content) {
    const panel=el("section","game-union-champion-panel");
    const heading=el("div","game-union-section-heading");
    heading.append(el("span","game-window-eyebrow","UNION CHAMPION"),
        el("h3","game-window-title","유니온 챔피언"));
    panel.appendChild(heading);
    if(!championSource||championSource.status==="unavailable") {
        panel.appendChild(el("p","game-empty",championSource?.message||"유니온 챔피언 정보를 조회할 수 없습니다."));
        content.appendChild(panel);
        return;
    }

    const raw=championSource.currentData||championSource.data||{};
    const champions=Array.isArray(raw.union_champion)?raw.union_champion:[];
    const gradeOrder=["SSS","SS","S","A","B"];
    const gradeCounts=new Map(gradeOrder.map(grade=>[grade,0]));
    champions.forEach(champion=>{
        const grade=String(champion?.champion_grade||"").toUpperCase();
        gradeCounts.set(grade,(gradeCounts.get(grade)||0)+1);
    });

    const distribution=el("div","game-union-grade-distribution");
    gradeOrder.forEach(grade=>{
        const count=gradeCounts.get(grade)||0;
        if(!count) return;
        const tile=el("div","game-union-grade-count");
        tile.append(el("span","game-union-grade-badge grade-"+grade.toLowerCase(),grade),
            el("strong","",String(count)+"명"));
        distribution.appendChild(tile);
    });
    if(distribution.childElementCount) panel.appendChild(distribution);

    const list=el("div","game-union-champion-grid");
    champions.forEach(champion=>{
        const card=el("article","game-union-champion-card");
        const grade=String(champion?.champion_grade||"—").toUpperCase();
        const head=el("div","game-union-champion-card-head");
        head.append(el("span","game-union-grade-badge grade-"+grade.toLowerCase(),grade),
            el("span","game-union-champion-slot","SLOT "+fmt(champion?.champion_slot??"—")));
        card.appendChild(head);
        card.append(el("strong","game-union-champion-name",champion?.champion_name||"캐릭터 정보 없음"),
            el("span","game-union-champion-class",champion?.champion_class||"직업 정보 없음"));
        const badges=Array.isArray(champion?.champion_badge_info)?champion.champion_badge_info:[];
        const badgeList=el("div","game-union-champion-badges");
        badges.forEach(badge=>{
            if(present(badge?.stat)) badgeList.appendChild(el("span","game-union-champion-effect",badge.stat));
        });
        if(badgeList.childElementCount) card.appendChild(badgeList);
        else card.appendChild(el("p","game-union-muted","개별 휘장 효과 정보 없음"));

        const championTip=addHoverTooltip(card,champion?.champion_name||"유니온 챔피언",[
            champion?.champion_class,
            "등급 · "+grade,
            "슬롯 · "+fmt(champion?.champion_slot??"—"),
            ...badges.map(item=>item?.stat).filter(Boolean)
        ],"game-champion-hover-tooltip");
        if(championTip&&champion?.character_image) {
            const preview=image(champion.character_image,champion.champion_name||"챔피언 이미지","game-champion-tooltip-image");
            if(preview) championTip.prepend(preview);
        }
        list.appendChild(card);
    });
    if(list.childElementCount) panel.appendChild(list);
    else panel.appendChild(el("p","game-empty","등록된 유니온 챔피언이 없습니다."));

    const totals=Array.isArray(raw.champion_badge_total_info)?raw.champion_badge_total_info:[];
    const totalPanel=el("div","game-union-champion-total");
    totalPanel.appendChild(el("h4","game-union-subtitle","전체 챔피언 휘장 효과"));
    const totalList=el("div","game-union-champion-total-list");
    totals.forEach(item=>{
        if(present(item?.stat)) totalList.appendChild(el("span","game-union-champion-effect",item.stat));
    });
    if(totalList.childElementCount) totalPanel.appendChild(totalList);
    else totalPanel.appendChild(el("p","game-union-muted","전체 휘장 효과 정보가 없습니다."));
    panel.appendChild(totalPanel);
    content.appendChild(panel);
}

function renderUnionSection(data,selectedPresetNumber=null,onPresetChange=()=>{}) {
    const content=el("div","game-union-window");
    const base=sourceById(data,"union");
    const stateStats=sourceById(data,"unionStateStat");
    const artifact=sourceById(data,"unionArtifact");
    const champion=sourceById(data,"unionChampion");
    const baseData=base?.data||{};
    const summary=el("div","game-union-summary");
    [
        ["유니온 레벨",baseData.union_level],
        ["유니온 등급",baseData.union_grade],
        ["아티팩트 레벨",baseData.union_artifact_level],
        ["아티팩트 경험치",baseData.union_artifact_exp],
        ["아티팩트 포인트",baseData.union_artifact_point]
    ].forEach(([label,value])=>{
        if(!present(value)) return;
        const tile=el("div","game-union-stat");
        tile.append(el("span","",label),el("strong","",fmt(value)));
        summary.appendChild(tile);
    });
    if(summary.childElementCount) content.appendChild(summary);

    const statePanel=el("section","game-union-state-panel");
    const stateHeading=el("div","game-union-section-heading");
    stateHeading.append(el("span","game-window-eyebrow","UNION STATE"),
        el("h3","game-window-title","유니온 스탯 투자"));
    statePanel.appendChild(stateHeading);

    if(!stateStats||stateStats.status==="unavailable") {
        statePanel.appendChild(el("p","game-empty",stateStats?.message||"유니온 스탯 정보를 조회할 수 없습니다."));
    } else {
        const presets=Array.isArray(stateStats.presets)?stateStats.presets:[];
        const selectedNumber=selectedPresetNumber??fallbackPreset(stateStats);
        const selected=presetByNumber(stateStats,selectedNumber);
        const raw=selected?.data?.union_state_stat||
            stateStats.currentData?.union_state_stat||[];
        const info=el("div","game-union-state-toolbar");
        const maxPoint=stateStats.data?.union_max_point;
        if(present(maxPoint)) {
            const point=el("div","game-union-point-card");
            point.append(el("span","","총 유니온 포인트"),el("strong","",fmt(maxPoint)));
            info.appendChild(point);
        }
        if(presets.length>0) {
            info.appendChild(presetSelect(stateStats,"union",selectedNumber,next=>{
                onPresetChange(next);
                const updated=renderUnionSection(data,next,onPresetChange);
                content.replaceChildren(...updated.childNodes);
            }));
        }
        statePanel.appendChild(info);

        const applied=stateStats.activePresetNo;
        const stateLabel=el("p","game-union-active-state");
        if(applied!==null&&applied!==undefined&&Number(applied)===Number(selectedNumber)) {
            stateLabel.textContent="현재 적용 중인 스탯 프리셋";
            stateLabel.classList.add("is-applied");
        } else if(applied!==null&&applied!==undefined) {
            stateLabel.textContent="선택한 프리셋 미리보기 · 현재 적용 프리셋 "+applied;
        } else {
            stateLabel.textContent="현재 적용 번호는 공개 응답에서 확정할 수 없어. 선택한 프리셋의 효과만 표시합니다.";
        }
        statePanel.appendChild(stateLabel);

        const statGrid=el("div","game-union-state-grid");
        if(Array.isArray(raw)) raw.forEach((effect,index)=>statGrid.appendChild(unionEffectTile(effect,index)));
        if(statGrid.childElementCount) statePanel.appendChild(statGrid);
        else statePanel.appendChild(el("p","game-empty","선택한 프리셋에 표시할 스탯 효과가 없습니다."));
    }
    content.appendChild(statePanel);

    renderUnionArtifact(artifact,content);
    renderUnionChampions(champion,content);
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
        else if(name==="equipment") content.replaceChildren(renderEquipmentSection(
            {...data,selectedEquipmentPreset:selectedNumbers.equipment},
            next=>{selectedNumbers.equipment=next;profileMode="custom";}
        ));
        else if(name==="symbols") content.replaceChildren(renderSymbolsSection(data));
        else if(name==="skills") content.replaceChildren(renderSkillsSection(data));
        else if(name==="link") content.replaceChildren(renderLinkSection(
            {...data,selectedLinkPreset:selectedNumbers.link},selectedNumbers.link,
            next=>{selectedNumbers.link=next;profileMode="custom";}
        ));
        else if(name==="union") content.replaceChildren(renderUnionSection(
            data,selectedNumbers.union,next=>{selectedNumbers.union=next;profileMode="custom";}
        ));

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
            if(name==="stats" && statsData!==cached) {
                statsData=cached; profileMode=cached.defaultProfile||profileMode;
                selectedNumbers=initialSelection(cached,profileMode);
            }
            if(token===requestToken) render(cached,name);
            return;
        }
        content.replaceChildren(el("div","game-loading-window","캐릭터 "+({stats:"능력치",equipment:"장비",symbols:"심볼",skills:"6차 / HEXA",link:"링크 스킬",union:"유니온"}[name]||"정보")+" 조회 중..."));
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
