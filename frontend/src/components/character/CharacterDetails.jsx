import { useEffect, useRef, useState } from "react";
import "./CharacterDetails.css";
import { getCharacterDetails } from "../../services/api.js";
import {
  DETAIL_TABS,
  Empty
} from "./CharacterDetailsShared.jsx";
import { StatsTab } from "./CharacterDetailsStats.jsx";
import { EquipmentTab } from "./CharacterDetailsEquipment.jsx";
import { SymbolsTab, SkillsTab, LinkTab, UnionTab } from "./CharacterDetailsOtherTabs.jsx";

export default function CharacterDetails({ ocid, onStatsLoaded, initialTab = "stats" }) {
  const sectionRef = useRef(null);
  const [visibleOcid, setVisibleOcid] = useState(null);
  const [tab, setTab] = useState("stats");
  const [cache, setCache] = useState({});
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const section = sectionRef.current;
    if (!ocid || !section) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisibleOcid(ocid);
      return;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisibleOcid(ocid);
        observer.disconnect();
      }
    }, { rootMargin: "140px 0px" });
    observer.observe(section);
    return () => observer.disconnect();
  }, [ocid]);

  useEffect(() => {
    setTab("stats");
    setCache({});
    setData(null);
    setSelected({});
    setError("");
    setNotice("");
  }, [ocid]);

  useEffect(() => {
    if (["stats","equipment","symbols","skills","link","union"].includes(initialTab)) {
      setTab(initialTab);
    }
  }, [ocid, initialTab]);

  useEffect(() => {
    if (!ocid || visibleOcid !== ocid) return;
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
        if (result.status === "partial") setNotice("일부 항목만 확인할 수 있어요. 나머지 정보는 현재 공개된 자료에서 찾을 수 없습니다.");
        else setNotice("넥슨에서 공개한 정보를 바탕으로 표시합니다. 게임 안의 변경 사항이 바로 반영되지 않을 수 있어요.");
      })
      .catch(requestError => {
        if (!cancelled) setError(requestError.message || "캐릭터 상세 정보를 불러오지 못했습니다.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ocid, tab, cache, onStatsLoaded, visibleOcid]);

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
    <section ref={sectionRef} className="section character-details-section react-character-details" aria-labelledby="react-detail-title">
      <div className="section-header character-details-header">
        <div>
          <h2 className="section-title" id="react-detail-title">캐릭터 상세 정보</h2>
          <p className="section-description">스탯부터 장비, 심볼, 6차 스킬과 유니온까지 원하는 항목을 골라 살펴보세요.</p>
        </div>
        <button type="button" className="export-button" onClick={refresh} disabled={loading}>정보 새로고침</button>
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
      {loading && <div className="game-loading-window" role="status">캐릭터 {DETAIL_TABS.find(item=>item[0]===tab)?.[1] || "정보"}을(를) 불러오고 있어요...</div>}
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
      <p className="detail-disclaimer">여기서 프리셋을 바꿔도 게임 안의 설정은 바뀌지 않아요. 확인할 수 없는 능력치나 세트 효과는 표시하지 않습니다.</p>
    </section>
  );
}
