/**
 * Build chart series from Nexon's daily level-local EXP snapshots.
 * EXP naturally resets when the character levels up; that boundary is marked
 * with a dashed segment so the reset is visible without implying lost EXP.
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

  return { daily, experience };
}

/** Dash only the blue EXP segment that enters a confirmed level-up day. */
export function levelExperienceSegmentDash(context, levelUpEvents) {
  const index = context?.p1DataIndex;
  return Array.isArray(levelUpEvents) && levelUpEvents[index] === true
    ? [6, 4]
    : [];
}

/**
 * Make zero-growth daily segments dotted while keeping growth segments solid.
 * Missing/uncollected dates remain null gaps and are not treated as zero growth.
 */
export function dailyGrowthSegmentDash(context) {
  const current = context?.p1?.parsed?.y;
  return Number(current) === 0 ? [2, 4] : [];
}

/** Detect level-up events while honoring explicit server-side event metadata. */
export function detectLevelUpEvents(records) {
  let previousAvailableLevel = null;
  return (Array.isArray(records) ? records : []).map(item => {
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
