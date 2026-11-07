/**
 * Build a dedicated Chart.js dataset for level-up markers.
 * A level-up can be a valid event even when that day's EXP delta is unavailable.
 */
export function buildLevelUpMarkers(records, cumulative) {
  let lastKnownCumulative = null;
  return records.map((item, index) => {
    const value = cumulative[index];
    if (value !== null && value !== undefined && Number.isFinite(Number(value))) {
      lastKnownCumulative = Number(value);
    }
    return item?.levelUp === true ? (lastKnownCumulative ?? 0) : null;
  });
}
