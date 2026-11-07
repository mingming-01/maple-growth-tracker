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


/**
 * Build the two experience series from the actual daily snapshots.
 *
 * The total line uses the recorded EXP value for every day, so the first
 * date in a 7-day range is a real starting value rather than an artificial 0.
 * The daily line uses the already calculated day-over-day delta. A missing
 * delta stays null; only a confirmed zero delta is marked as no growth.
 */
export function buildExperienceChartSeries(records) {
  const items = Array.isArray(records) ? records : [];
  const isAvailable = item =>
    !!item &&
    (!item.recordStatus || item.recordStatus === "available");

  const totalExperience = items.map(item => {
    if (!isAvailable(item) || item.experience === null || item.experience === undefined || item.experience === "") {
      return null;
    }
    const value = Number(String(item.experience).replace(/,/g, "").trim());
    return Number.isFinite(value) ? value / 1_000_000_000_000 : null;
  });

  const dailyGrowth = items.map(item => {
    if (!isAvailable(item) || item.experienceChange === null || item.experienceChange === undefined || item.experienceChange === "") {
      return null;
    }
    const value = Number(String(item.experienceChange).replace(/,/g, "").trim());
    return Number.isFinite(value) ? value / 1_000_000_000_000 : null;
  });

  const zeroGrowthDays = items.map((item, index) =>
    totalExperience[index] !== null && dailyGrowth[index] === 0
  );

  return { totalExperience, dailyGrowth, zeroGrowthDays };
}
