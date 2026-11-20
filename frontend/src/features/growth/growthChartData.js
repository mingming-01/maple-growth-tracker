/**
 * Build calendar-anchored cumulative EXP and daily EXP chart series.
 *
 * The first observed EXP is the baseline. A level-up date carries the last
 * confirmed cumulative value because the cross-level delta is unknown; later
 * confirmed same-level daily deltas continue from that baseline.
 */
export function buildExperienceChartSeries(records) {
  const rows = Array.isArray(records) ? records : [];
  const daily = rows.map((item, index) => {
    if (item?.recordStatus && item.recordStatus !== "available") return null;
    if (index === 0) return null;
    const value = item?.experienceChange;
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number / 1_000_000_000_000 : null;
  });

  const cumulative = [];
  let running = null;
  let baselineEstablished = false;
  let cumulativeIsComplete = true;
  const levelUpEvents = detectLevelUpEvents(rows);

  rows.forEach((item, index) => {
    const available = !!item &&
      (!item.recordStatus || item.recordStatus === "available");
    if (!available) {
      cumulative.push(null);
      if (index === 0 || baselineEstablished) cumulativeIsComplete = false;
      return;
    }

    if (index === 0) {
      const startingExperience = item.experience;
      const parsed = startingExperience === null || startingExperience === undefined || startingExperience === ""
        ? null
        : Number(startingExperience);
      if (!Number.isFinite(parsed)) {
        cumulative.push(null);
        cumulativeIsComplete = false;
        return;
      }
      running = parsed;
      baselineEstablished = true;
      cumulative.push(running / 1_000_000_000_000);
      return;
    }

    if (!baselineEstablished || !cumulativeIsComplete || running === null) {
      cumulative.push(null);
      return;
    }

    if (levelUpEvents[index]) {
      // Nexon EXP resets at a level boundary; never invent the missing delta.
      cumulative.push(running / 1_000_000_000_000);
      return;
    }

    const change = item.experienceChange;
    if (change === null || change === undefined || change === "") {
      cumulative.push(null);
      cumulativeIsComplete = false;
      return;
    }
    const delta = Number(change);
    if (!Number.isFinite(delta)) {
      cumulative.push(null);
      cumulativeIsComplete = false;
      return;
    }

    running += delta;
    cumulative.push(running / 1_000_000_000_000);
  });

  return { daily, cumulative };
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

/** Place a distinct level-up star at the last confirmed cumulative EXP value. */
export function buildLevelUpMarkers(records, cumulative) {
  let lastKnownCumulative = null;
  const events = detectLevelUpEvents(records);
  return (Array.isArray(records) ? records : []).map((item, index) => {
    const value = cumulative?.[index];
    if (value !== null && value !== undefined && Number.isFinite(Number(value))) {
      lastKnownCumulative = Number(value);
    }
    return events[index] ? lastKnownCumulative : null;
  });
}
