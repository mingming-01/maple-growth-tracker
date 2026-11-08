import { sourceOf, DataState } from "./CharacterDetailsShared.jsx";

export function EquipmentTab({ data }) {
  const equipment = sourceOf(data, "itemEquipment");
  return (
    <div className="game-equipment-window">
      <DataState source={equipment} />
      <p className="game-empty">장비 상세 UI는 브랜치 복구 후 전체 버전으로 복원됩니다. 스탯 탭과 랭킹/백엔드 변경은 정상 동작합니다.</p>
    </div>
  );
}
