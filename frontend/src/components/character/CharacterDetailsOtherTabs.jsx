import { sourceOf, DataState } from "./CharacterDetailsShared.jsx";

export function SymbolsTab({ data }) {
  const source = sourceOf(data, "symbolEquipment");
  return (
    <div className="game-symbol-window">
      <DataState source={source} />
      <p className="game-empty">심볼 상세 UI는 브랜치 복구 후 전체 버전으로 복원됩니다.</p>
    </div>
  );
}

export function SkillsTab({ data }) {
  const skill = sourceOf(data, "skill");
  const hexa = sourceOf(data, "hexaMatrix");
  return (
    <div>
      <DataState source={skill || hexa} />
      <p className="game-empty">스킬 상세 UI는 브랜치 복구 후 전체 버전으로 복원됩니다.</p>
    </div>
  );
}

export function LinkTab({ data }) {
  const source = sourceOf(data, "linkSkill");
  return (
    <div>
      <DataState source={source} />
      <p className="game-empty">링크 스킬 상세 UI는 브랜치 복구 후 전체 버전으로 복원됩니다.</p>
    </div>
  );
}

export function UnionTab({ data }) {
  const source = sourceOf(data, "union");
  return (
    <div>
      <DataState source={source} />
      <p className="game-empty">유니온 상세 UI는 브랜치 복구 후 전체 버전으로 복원됩니다.</p>
    </div>
  );
}
