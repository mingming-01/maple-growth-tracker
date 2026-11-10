import { getHistoryArchive } from "../services/api.js";

const COLLECTION_BATCH_SIZE = 10;

function emptyCollectionSummary() {
  return { checkedDays: 0, savedRecords: 0, availableRecords: 0, noDataRecords: 0, remainingDays: 0 };
}

/** Collect missing records in bounded batches, then fetch the full archive once. */
export async function fetchHistoryArchive(
  days,
  character,
  { end = null, collect = false, onProgress = null, progressPrefix = "과거 기록 확인 중" } = {}
) {
  const normalizedDays = Number(days);
  if (![30, 90].includes(normalizedDays)) throw new Error("조회 기간은 30일 또는 90일이어야 합니다.");
  if (!character?.ocid) throw new Error("캐릭터 식별 정보를 확인할 수 없습니다.");

  if (!collect) {
    onProgress?.("저장된 기간 기록 조회 중...");
    return getHistoryArchive(character.ocid, normalizedDays, { end });
  }
  if (end) throw new Error("과거 기간은 기록 수집 대상이 될 수 없습니다.");

  const summary = emptyCollectionSummary();
  for (let offset = 0; offset < normalizedDays; offset += COLLECTION_BATCH_SIZE) {
    const limit = Math.min(COLLECTION_BATCH_SIZE, normalizedDays - offset);
    onProgress?.(`${progressPrefix} · ${Math.min(offset + limit, normalizedDays)}/${normalizedDays}일`);
    const result = await getHistoryArchive(character.ocid, normalizedDays, {
      collect: true,
      characterName: character.characterName,
      worldName: character.worldName,
      offset,
      limit,
      summaryOnly: true
    });
    const batch = result.collection || {};
    summary.checkedDays += Number(batch.checkedDays || 0);
    summary.savedRecords += Number(batch.savedRecords || 0);
    summary.availableRecords += Number(batch.availableRecords || 0);
    summary.noDataRecords += Number(batch.noDataRecords || 0);
    summary.remainingDays = Number(batch.remainingDays || 0);
    if (summary.remainingDays === 0) break;
  }

  onProgress?.("수집된 기간 기록 정리 중...");
  const archive = await getHistoryArchive(character.ocid, normalizedDays);
  archive.collectionSummary = summary;
  return archive;
}
