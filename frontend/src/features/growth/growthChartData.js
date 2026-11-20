/**
 * Build chart series from Nexon's raw daily snapshots.
 * experience is level-local EXP, so it resets on level-up and remains visible.
 */
export function buildExperienceChartSeries(records) {
  const rows = Array.isArray(records) ? records : [];
  const available = item => !!item && (!item.recordStatus || item.recordStatus === "available");

  const experience = rows.map(item => {
    if (!available(item) || item.experience === null || item.experience === undefined || item.experience === "") return null;
    const value = Number(item.experience);
    return Number.isFinite(value) ? value / 1_000_000_000_000 : null;
  });

  const daily = rows.map((item, index) => {
    if (!available(item) || index === 0) return null;
    const value = item.experienceChange;
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number / 1_000_000_000_000 : null;
  });

  return { experience, daily };
}

/** Hide the segment arriving at a level-up point but keep that raw EXP point visible. */
export function levelExperienceSegmentColor(context, levelUpEvents) {
  const index = context?.p1DataIndex;
  return Array.isArray(levelUpEvents) && levelUpEvents[index] === true
    ? "transparent"
    : "#36a2eb";
}

export function dailyGrowthSegmentDash(context) {
  const current = context?.p1?.parsed?.y;
  return Number(current) === 0 ? [2, 4] : [];
}

export function detectLevelUpEvents(records) {
  let previousAvailableLevel = null;
  return records.map(item => {
    const parsedLevel = item?.level === null || item?.level === undefined || item.level === ""
      ? null
      : Number(item.level);
    const currentLevel = Number.isFinite(parsedLevel) ? parsedLevel : null;
    const available = !!item && (!item.recordStatus || item.recordStatus === "available");
    const explicitlyMarked = available && item.levelUp === true;
    const delayedLevelCatchUp = available && item.levelUpCatchUp === true;

    if (!available || currentLevel === null) {
      previousAvailableLevel = null;
      return explicitlyMarked;
    }
    const detected = typeof item?.levelUp === "boolean"
      ? explicitlyMarked && !delayedLevelCatchUp
      : !delayedLevelCatchUp && previousAvailableLevel !== null && currentLevel > previousAvailableLevel;
    previousAvailableLevel = currentLevel;
    return detected;
  });
}
