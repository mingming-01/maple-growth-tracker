export function sortHistoryAscending(history) {
    return [...(history || [])].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

export function sortHistoryDescending(history) {
    return [...(history || [])].sort((a, b) => String(b.date).localeCompare(String(a.date)));
}

// 기존 성장 계산 함수를 AI 리포트와 비교 카드에서도 공유한다.
export function getDailyGrowth(history) {
    if (!history || history.length < 2) return null;
    const sorted = sortHistoryAscending(history);
    const latest = sorted[sorted.length - 1];
    if (!latest || latest.levelUp === true) return null;
    const growth = Number(latest.experienceChange);
    return Number.isFinite(growth) && growth > 0 ? growth : null;
}

export function calculateAverageGrowth(history) {
    if (!history || history.length < 2) return null;
    const gains = history
        .map(item => Number(item.experienceChange))
        .filter(value => Number.isFinite(value) && value > 0);
    if (!gains.length) return null;
    return gains.reduce((sum, value) => sum + value, 0) / gains.length;
}

export function calculateWeeklyGrowth(history) {
    if (!history || !history.length) return null;
    const gains = history
        .map(item => Number(item.experienceChange))
        .filter(value => Number.isFinite(value) && value > 0);
    return gains.length ? gains.reduce((sum, value) => sum + value, 0) : null;
}

export function getRankingChange(history) {
    const sorted = sortHistoryAscending(history);
    if (sorted.length < 2) return null;
    const latest = sorted[sorted.length - 1];
    const previous = sorted[sorted.length - 2];
    const change = Number(previous.ranking) - Number(latest.ranking);
    return Number.isFinite(change) ? change : null;
}

export function calculatePrediction(character, history) {
    if (!character || !history?.length) return null;
    const currentExp = Number(character.experience);
    const currentLevel = Number(character.level);
    const currentRate = Number(String(character.experienceRate || "").replace("%", ""));
    const averageGrowth = calculateAverageGrowth(history);
    if (!Number.isFinite(currentExp) || !Number.isFinite(currentLevel) || averageGrowth === null || averageGrowth <= 0) return null;

    if (Number.isFinite(currentRate) && currentRate > 0 && currentRate < 100) {
        const estimatedTotalExp = currentExp / (currentRate / 100);
        const requiredExp = estimatedTotalExp - currentExp;
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

export function calculateGrowthMetrics(character, history, sharedPrediction) {
    const sorted = sortHistoryAscending(history);
    const gains = sorted
        .map(item => Number(item.experienceChange))
        .filter(value => Number.isFinite(value) && value > 0);
    const rankingDelta = getRankingChange(sorted);
    const prediction = sharedPrediction || calculatePrediction(character, sorted);
    const midpoint = Math.floor(gains.length / 2);
    const firstHalf = midpoint > 0 ? gains.slice(0, midpoint) : [];
    const secondHalf = gains.length - midpoint > 0 ? gains.slice(midpoint) : [];
    const firstAverage = firstHalf.length ? firstHalf.reduce((sum, value) => sum + value, 0) / firstHalf.length : null;
    const recentAverage = secondHalf.length ? secondHalf.reduce((sum, value) => sum + value, 0) / secondHalf.length : null;
    const levelUps = sorted
        .filter(item => item.levelUp === true)
        .map(item => {
            const index = sorted.indexOf(item);
            return {
                date: item.date,
                previousLevel: index > 0 ? sorted[index - 1].level : null,
                currentLevel: item.level
            };
        });

    return {
        validGrowthDays: gains.length,
        recordedDays: sorted.filter(item => item.experience !== null && item.experience !== undefined).length,
        latestDailyGrowth: getDailyGrowth(sorted),
        averageDailyGrowth: calculateAverageGrowth(sorted),
        highestDailyGrowth: gains.length ? Math.max(...gains) : null,
        lowestDailyGrowth: gains.length ? Math.min(...gains) : null,
        sevenDayGrowth: calculateWeeklyGrowth(sorted),
        rankingChange: rankingDelta,
        growthComparison: {
            earlierAverage: firstAverage,
            recentAverage,
            direction: firstAverage === null || recentAverage === null
                ? "insufficient_data"
                : recentAverage > firstAverage ? "increased" : recentAverage < firstAverage ? "decreased" : "stable"
        },
        levelUps,
        prediction: prediction ? {
            nextLevel: prediction.nextLevel,
            requiredExperience: prediction.requiredExp,
            averageDailyGrowth: prediction.averageGrowth,
            estimatedDays: prediction.days,
            estimatedDate: formatLocalISODate(prediction.date)
        } : null
    };
}
