/**
 * Build calendar-anchored total EXP and daily EXP chart series.
 *
 * The first calendar date is the fixed baseline. It is never shifted to the
 * first later observed record, and missing records are never converted to zero.
 * A level-up day has no comparable same-level delta, so the total line carries
 * the last confirmed value while the level-up marker explains the boundary.
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

    if (item.levelUp === true) {
      // Nexon EXP resets at a level boundary; do not invent cross-level EXP.
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
