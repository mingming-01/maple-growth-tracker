function toFiniteNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(String(value).replace(/,/g, "").replace(/%/g, "").trim());
    return Number.isFinite(number) ? number : null;
}

function getObservedChange(item) {
    if (!item || (item.recordStatus && item.recordStatus !== "available")) return null;
    return toFiniteNumber(item.experienceChange);
}

function isAvailableRecord(item) {
    return !!item && (!item.recordStatus || item.recordStatus === "available") &&
        toFiniteNumber(item.experience) !== null;
}

export function sortHistoryAscending(history) {
    return [...(history || [])].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

export function sortHistoryDescending(history) {
    return [...(history || [])].sort((a, b) => String(b.date).localeCompare(String(a.date)));
}

// 가장 최근에 정상적으로 계산된 날짜 간 변화량을 반환한다.
// 최신 날짜가 미수집·레벨업 경계여도 이전에 확인된 값을 사용할 수 있다.
export function getDailyGrowth(history) {
    const sorted = sortHistoryDescending(history);
    for (const item of sorted) {
        const change = getObservedChange(item);
        if (change !== null) return change;
    }
    return null;
}

// 평균은 실제로 변화량을 계산할 수 있었던 관측 구간만 대상으로 한다.
// 0 성장과 음수 보정도 표본에서 제외하지 않는다.
export function calculateAverageGrowth(history) {
    const changes = (history || [])
        .map(getObservedChange)
        .filter(value => value !== null);
    if (!changes.length) return null;
    return changes.reduce((sum, value) => sum + value, 0) / changes.length;
}

export function calculateWeeklyGrowth(history) {
    const changes = (history || [])
        .map(getObservedChange)
        .filter(value => value !== null);
    if (!changes.length) return null;
    return changes.reduce((sum, value) => sum + value, 0);
}

export function getRankingChange(history) {
    const ranked = sortHistoryAscending(history)
        .map(item => toFiniteNumber(item?.ranking))
        .filter(value => value !== null);
    if (ranked.length < 2) return null;
    return ranked[ranked.length - 2] - ranked[ranked.length - 1];
}

// Calculate same-level percentage-point changes only across consecutive calendar days.
export function calculateDailyExperienceRateChanges(history) {
    const sorted = sortHistoryAscending(history);
    const changes = {};

    const hasValidRate = item => {
        if (!item || (item.recordStatus && item.recordStatus !== "available")) return false;
        const rate = toFiniteNumber(item.experienceRate);
        return rate !== null && rate >= 0 && rate <= 100;
    };
    const isNextCalendarDay = (previousDate, currentDate) => {
        const parse = value => {
            const match = /^(\\d{4})-(\\d{2})-(\\d{2})$/.exec(String(value || ""));
            if (!match) return null;
            const [, year, month, day] = match;
            const timestamp = Date.UTC(Number(year), Number(month) - 1, Number(day));
            const date = new Date(timestamp);
            return date.getUTCFullYear() === Number(year) &&
                date.getUTCMonth() === Number(month) - 1 &&
                date.getUTCDate() === Number(day) ? timestamp : null;
        };
        const previous = parse(previousDate);
        const current = parse(currentDate);
        return previous !== null && current !== null && current - previous === 86400000;
    };

    for (let index = 1; index < sorted.length; index += 1) {
        const previous = sorted[index - 1];
        const current = sorted[index];
        if (!hasValidRate(previous) || !hasValidRate(current)) continue;
        if (!isNextCalendarDay(previous.date, current.date)) continue;

        const previousLevel = toFiniteNumber(previous.level);
        const currentLevel = toFiniteNumber(current.level);
        if (previousLevel === null || currentLevel === null || previousLevel !== currentLevel) continue;
        if (current.levelUp === true) continue;

        changes[current.date] = toFiniteNumber(current.experienceRate) -
            toFiniteNumber(previous.experienceRate);
    }

    return changes;
}

export function calculateLevelProgress(character, averageDailyGrowth = null) {
    if (!character) return null;
    const currentRate = toFiniteNumber(character.experienceRate);
    const currentExperience = toFiniteNumber(character.experience);
    if (currentRate === null || currentRate < 0 || currentRate > 100) return null;

    // 현재 경험치와 API 진행률로 현재 레벨의 필요 경험치를 추정한다.
    // 진행률이 0%이거나 경험치가 0이면 분모를 안정적으로 추정할 수 없다.
    const estimatedLevelExperience = currentRate > 0 && currentExperience > 0
        ? currentExperience / (currentRate / 100)
        : null;
    const average = toFiniteNumber(averageDailyGrowth);
    const dailyProgressRate = estimatedLevelExperience && average !== null && average > 0
        ? (average / estimatedLevelExperience) * 100
        : null;

    return {
        currentRate,
        remainingRate: Math.max(0, 100 - currentRate),
        estimatedLevelExperience,
        dailyProgressRate
    };
}

export function calculatePrediction(character, history) {
    if (!character || !history?.length) return null;
    const currentExp = toFiniteNumber(character.experience);
    const currentLevel = toFiniteNumber(character.level);
    const currentRate = toFiniteNumber(character.experienceRate);
    const averageGrowth = calculateAverageGrowth(history);
    if (currentExp === null || currentLevel === null || averageGrowth === null || averageGrowth <= 0) return null;

    if (currentRate !== null && currentRate > 0 && currentRate < 100) {
        const estimatedTotalExp = currentExp / (currentRate / 100);
        const requiredExp = Math.max(0, estimatedTotalExp - currentExp);
        const days = requiredExp / averageGrowth;
        const targetDate = new Date();
        targetDate.setDate(targetDate.getDate() + Math.ceil(days));
        return { currentLevel, nextLevel: currentLevel + 1, currentRate, averageGrowth, requiredExp, days, date: targetDate };
    }

    return { currentLevel, nextLevel: currentLevel + 1, currentRate, averageGrowth, requiredExp: null, days: null, date: null };
}

export function formatLocalISODate(value) {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return null;
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

export function buildGrowthTimeline(history, limit = 8) {
    const sorted = sortHistoryAscending(history);
    if (!sorted.length) return [];

    const events = [];
    const levelUpEvents = sorted.flatMap((item, index) => {
        const previous = sorted[index - 1];
        const previousLevel = toFiniteNumber(previous?.level);
        const currentLevel = toFiniteNumber(item?.level);
        const levelUp = item?.levelUp === true ||
            (previousLevel !== null && currentLevel !== null && currentLevel > previousLevel);
        if (!levelUp || !isAvailableRecord(item)) return [];
        return [{
            type: "level-up",
            date: item.date,
            title: `Lv. ${currentLevel ?? "?"} 달성`,
            description: previousLevel !== null ? `Lv. ${previousLevel}에서 레벨업` : "레벨업 기록 확인",
            priority: 0
        }];
    });
    events.push(...levelUpEvents);

    const growthRecords = sorted
        .map(item => ({ item, change: getObservedChange(item) }))
        .filter(entry => entry.change !== null && entry.change > 0)
        .sort((a, b) => b.change - a.change);
    if (growthRecords.length) {
        const best = growthRecords[0];
        events.push({
            type: "best-growth",
            date: best.item.date,
            title: "기간 최고 성장일",
            description: `+${(best.change / 1_000_000_000_000).toFixed(2)}조 경험치`,
            priority: 1
        });
    }

    const rankingRecords = sorted
        .filter(item => toFiniteNumber(item?.rankingChange) !== null && Number(item.rankingChange) > 0)
        .sort((a, b) => Number(b.rankingChange) - Number(a.rankingChange));
    if (rankingRecords.length) {
        const best = rankingRecords[0];
        events.push({
            type: "ranking",
            date: best.date,
            title: "랭킹 최고 상승일",
            description: `전일 대비 ${Number(best.rankingChange).toLocaleString("ko-KR")}위 상승`,
            priority: 2
        });
    }

    const latest = [...sorted].reverse().find(isAvailableRecord);
    if (latest && !events.some(event => event.date === latest.date && event.type === "level-up")) {
        events.push({
            type: "latest",
            date: latest.date,
            title: "최근 정상 기록",
            description: `Lv. ${toFiniteNumber(latest.level) ?? "-"} · 경험치 ${toFiniteNumber(latest.experience)?.toLocaleString("ko-KR") ?? "확인 불가"}`,
            priority: 3
        });
    }

    return events
        .sort((a, b) => String(b.date).localeCompare(String(a.date)) || a.priority - b.priority)
        .slice(0, Math.max(1, Number(limit) || 8));
}

export function calculateGrowthMetrics(character, history, sharedPrediction) {
    const sorted = sortHistoryAscending(history);
    const changes = sorted
        .map(getObservedChange)
        .filter(value => value !== null);
    const positiveChanges = changes.filter(value => value > 0);
    const midpoint = Math.floor(changes.length / 2);
    const firstHalf = midpoint > 0 ? changes.slice(0, midpoint) : [];
    const secondHalf = changes.length - midpoint > 0 ? changes.slice(midpoint) : [];
    const firstAverage = firstHalf.length ? firstHalf.reduce((sum, value) => sum + value, 0) / firstHalf.length : null;
    const recentAverage = secondHalf.length ? secondHalf.reduce((sum, value) => sum + value, 0) / secondHalf.length : null;
    const rankingDelta = getRankingChange(sorted);
    const averageDailyGrowth = calculateAverageGrowth(sorted);
    const prediction = sharedPrediction || calculatePrediction(character, sorted);
    const levelProgress = calculateLevelProgress(character, averageDailyGrowth);
    const levelUps = sorted
        .filter((item, index) => {
            const previousLevel = toFiniteNumber(sorted[index - 1]?.level);
            const currentLevel = toFiniteNumber(item?.level);
            return item.levelUp === true ||
                (previousLevel !== null && currentLevel !== null && currentLevel > previousLevel);
        })
        .map(item => {
            const index = sorted.indexOf(item);
            return {
                date: item.date,
                previousLevel: index > 0 ? sorted[index - 1].level : null,
                currentLevel: item.level
            };
        });

    return {
        validGrowthDays: positiveChanges.length,
        observedChangeDays: changes.length,
        zeroGrowthDays: changes.filter(value => value === 0).length,
        negativeGrowthDays: changes.filter(value => value < 0).length,
        recordedDays: sorted.filter(isAvailableRecord).length,
        latestDailyGrowth: getDailyGrowth(sorted),
        averageDailyGrowth,
        highestDailyGrowth: changes.length ? Math.max(...changes) : null,
        lowestDailyGrowth: changes.length ? Math.min(...changes) : null,
        sevenDayGrowth: calculateWeeklyGrowth(sorted),
        rankingChange: rankingDelta,
        levelProgress,
        growthComparison: {
            earlierAverage: firstAverage,
            recentAverage,
            direction: firstAverage === null || recentAverage === null
                ? "insufficient_data"
                : recentAverage > firstAverage ? "increased" : recentAverage < firstAverage ? "decreased" : "stable"
        },
        levelUps,
        timeline: buildGrowthTimeline(sorted),
        prediction: prediction ? {
            nextLevel: prediction.nextLevel,
            requiredExperience: prediction.requiredExp,
            averageDailyGrowth: prediction.averageGrowth,
            estimatedDays: prediction.days,
            estimatedDate: formatLocalISODate(prediction.date)
        } : null
    };
}
