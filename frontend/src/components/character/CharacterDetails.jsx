import { useEffect, useState } from "react";
import "./CharacterDetails.css";
import { getCharacterDetails } from "../../services/api.js";
import {
  DETAIL_TABS,
  Empty
} from "./CharacterDetailsShared.jsx";
import { StatsTab } from "./CharacterDetailsStats.jsx";
import { EquipmentTab } from "./CharacterDetailsEquipment.jsx";
import { SymbolsTab, SkillsTab, LinkTab, UnionTab } from "./CharacterDetailsOtherTabs.jsx";

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
