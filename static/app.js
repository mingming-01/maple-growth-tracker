const searchForm = document.getElementById("searchForm");
const characterNameInput = document.getElementById("characterName");
const loadingMessage = document.getElementById("loadingMessage");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");
const refreshDataButton = document.getElementById("refreshDataButton");
const refreshDataButtonLabel = document.getElementById("refreshDataButtonLabel");

// 캐릭터 기본 정보
const characterName = document.getElementById("characterNameResult");
const characterImage = document.getElementById("characterImage");
const worldName = document.getElementById("worldName");
const worldLogo = document.getElementById("worldLogo");
const worldLogoMap = {
    "스카니아": "/static/images/worlds/SCANIA.PNG",
    "베라": "/static/images/worlds/BERA.PNG",
    "루나": "/static/images/worlds/LUNA.png",
    "제니스": "/static/images/worlds/ZENITH.png",
    "크로아": "/static/images/worlds/CROA.png",
    "유니온": "/static/images/worlds/UNION.png",
    "엘리시움": "/static/images/worlds/ELYSIUM.png",
    "이노시스": "/static/images/worlds/ENOSIS.png",
    "레드": "/static/images/worlds/RED.png",
    "오로라": "/static/images/worlds/AURORA.PNG",
    "아케인": "/static/images/worlds/ARCANE.png",
    "노바": "/static/images/worlds/NOVA.png",
    "에오스": "/static/images/worlds/EOS.png",
    "헬리오스": "/static/images/worlds/HELIOS.png",
    "챌린저스": "/static/images/worlds/CHALLENGERS.png"
};
const jobName = document.getElementById("jobName");
const levelValue = document.getElementById("levelValue");
const experienceRate = document.getElementById("experienceRate");
const guildName = document.getElementById("guildName");
const averageDailyExperience = document.getElementById("averageDailyExperience");

// 랭킹과 성장 요약
const overallRanking = document.getElementById("overallRanking");
const worldRanking = document.getElementById("worldRanking");
const jobWorldRanking = document.getElementById("jobWorldRanking");
const jobRanking = document.getElementById("jobRanking");
const yesterdayGrowth = document.getElementById("yesterdayGrowth");
const rankingChange = document.getElementById("rankingChange");
const weeklyGrowth = document.getElementById("weeklyGrowth");
const averageGrowth = document.getElementById("averageGrowth");

// 성장 예측 및 기록
const predictionRequired = document.getElementById("predictionRequired");
const predictionDays = document.getElementById("predictionDays");
const predictionDate = document.getElementById("predictionDate");
const predictionAverage = document.getElementById("predictionAverage");
const historyBody = document.getElementById("historyBody");
const historyRangeSelect = document.getElementById("historyRangeSelect");
const historyRangeNotice = document.getElementById("historyRangeNotice");
const periodSummarySection = document.getElementById("periodSummarySection");
const periodSummaryRange = document.getElementById("periodSummaryRange");
const periodSummaryCoverageBadge = document.getElementById("periodSummaryCoverageBadge");
const periodGrowthValue = document.getElementById("periodGrowthValue");
const periodGrowthDetail = document.getElementById("periodGrowthDetail");
const periodAverageValue = document.getElementById("periodAverageValue");
const periodAverageDetail = document.getElementById("periodAverageDetail");
const periodRankingValue = document.getElementById("periodRankingValue");
const periodRankingDetail = document.getElementById("periodRankingDetail");
const periodComparisonValue = document.getElementById("periodComparisonValue");
const periodComparisonDetail = document.getElementById("periodComparisonDetail");
const periodCoverageValue = document.getElementById("periodCoverageValue");
const periodCoverageDetail = document.getElementById("periodCoverageDetail");
const periodSummaryFootnote = document.getElementById("periodSummaryFootnote");

// AI 리포트 및 비교
const aiAnalysisLoading = document.getElementById("aiAnalysisLoading");
const aiAnalysisError = document.getElementById("aiAnalysisError");
const aiAnalysisResult = document.getElementById("aiAnalysisResult");
const aiGrowthPattern = document.getElementById("aiGrowthPattern");
const aiGrowthChange = document.getElementById("aiGrowthChange");
const aiLevelUp = document.getElementById("aiLevelUp");
const aiGrowthOutlook = document.getElementById("aiGrowthOutlook");
const aiJudgement = document.getElementById("aiJudgement");
const comparisonForm = document.getElementById("comparisonForm");
const comparisonNameInput = document.getElementById("comparisonName");
const comparisonButton = document.getElementById("comparisonButton");
const comparisonLoading = document.getElementById("comparisonLoading");
const comparisonError = document.getElementById("comparisonError");
const comparisonResult = document.getElementById("comparisonResult");
const comparisonAIAnalysis = document.getElementById("comparisonAIAnalysis");
const saveImageButton = document.getElementById("saveImageButton");
const savePdfButton = document.getElementById("savePdfButton");
const favoriteList = document.getElementById("favoriteList");
const favoriteEmpty = document.getElementById("favoriteEmpty");
const favoriteCount = document.getElementById("favoriteCount");
const favoriteFeedback = document.getElementById("favoriteFeedback");
const favoriteCurrentButton = document.getElementById("favoriteCurrentButton");
const favoriteCurrentButtonIcon = document.getElementById("favoriteCurrentButtonIcon");
const favoriteCurrentButtonLabel = document.getElementById("favoriteCurrentButtonLabel");

let growthChart = null;
let currentCharacter = null;
let currentHistory = [];
let currentDisplayHistory = [];
let currentHistoryRange = 7;
let currentHistoryRangeStatus = null;
let currentPeriodSummary = null;
const STORAGE_KEY = "mapleGrowthTrackerState";
const FAVORITES_STORAGE_KEY = "mapleGrowthTrackerFavorites";
const MAX_FAVORITES = 30;
const AI_CACHE_STORAGE_KEY = "mapleGrowthTrackerAIResponsesV1";
const AI_CACHE_MAX_ENTRIES = 40;
const AI_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const aiAnalysisCacheNotice = document.getElementById("aiAnalysisCacheNotice");
const comparisonAICacheNotice = document.getElementById("comparisonAICacheNotice");
const featureSection = document.getElementById("featureSection");
const dataStatusNotice = document.getElementById("dataStatusNotice");
const AUTO_REFRESH_KEY = `${STORAGE_KEY}:lastAutoRefresh`;
const AUTO_REFRESH_COOLDOWN_MS = 60_000;

// 결과 화면이 보이는 동안에는 메인 소개 카드를 숨긴다.
function syncHomeView() {
    if (featureSection) featureSection.hidden = !!(resultSection && !resultSection.hidden);
}

function getTrackerState() {
    try {
        const saved = sessionStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved) : null;
    } catch (error) {
        console.error("저장된 상태를 불러오지 못했습니다:", error);
        return null;
    }
}

function saveTrackerState(state) {
    try {
        const previous = getTrackerState() || {};
        const nextState = {
            ...previous,
            ...state
        };

        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
    } catch (error) {
        console.error("화면 상태 저장에 실패했습니다:", error);
    }
}

function readFavoriteCharacters() {
    try {
        const saved = JSON.parse(localStorage.getItem(FAVORITES_STORAGE_KEY) || "[]");
        if (!Array.isArray(saved)) return [];
        return saved
            .filter(item => item && typeof item.name === "string" && item.name.trim())
            .map(item => ({
                ocid: typeof item.ocid === "string" ? item.ocid : "",
                name: item.name.trim(),
                worldName: typeof item.worldName === "string" ? item.worldName : ""
            }))
            .slice(0, MAX_FAVORITES);
    } catch (error) {
        return [];
    }
}

function saveFavoriteCharacters(favorites) {
    try {
        localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites));
        return true;
    } catch (error) {
        showFavoriteFeedback("브라우저 저장소를 사용할 수 없어 관심 캐릭터를 저장하지 못했습니다.", true);
        return false;
    }
}

function isSameFavorite(left, right) {
    if (left.ocid && right.ocid) return left.ocid === right.ocid;
    return left.name === right.name && left.worldName === right.worldName;
}

function showFavoriteFeedback(message, isError = false) {
    if (!favoriteFeedback) return;
    favoriteFeedback.textContent = message;
    favoriteFeedback.classList.toggle("is-error", isError);
    favoriteFeedback.hidden = !message;
}

function updateFavoriteCurrentButton() {
    if (!favoriteCurrentButton || !currentCharacter?.characterName) {
        if (favoriteCurrentButton) favoriteCurrentButton.hidden = true;
        return;
    }

    const current = {
        ocid: String(currentCharacter.ocid || ""),
        name: currentCharacter.characterName,
        worldName: currentCharacter.worldName || ""
    };
    const isSaved = readFavoriteCharacters().some(item => isSameFavorite(item, current));
    favoriteCurrentButton.hidden = false;
    favoriteCurrentButton.classList.toggle("is-saved", isSaved);
    favoriteCurrentButton.setAttribute("aria-pressed", String(isSaved));
    if (favoriteCurrentButtonIcon) favoriteCurrentButtonIcon.textContent = isSaved ? "★" : "☆";
    if (favoriteCurrentButtonLabel) {
        favoriteCurrentButtonLabel.textContent = isSaved ? "관심 캐릭터 해제" : "관심 캐릭터 등록";
    }
}

function renderFavoriteList() {
    if (!favoriteList) return;

    const favorites = readFavoriteCharacters();
    favoriteList.replaceChildren();
    if (favoriteCount) favoriteCount.textContent = `${favorites.length} / ${MAX_FAVORITES}명`;
    if (favoriteEmpty) favoriteEmpty.hidden = favorites.length > 0;

    favorites.forEach(favorite => {
        const item = document.createElement("div");
        item.className = "favorite-item";

        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "favorite-character-button";
        openButton.setAttribute("aria-label", `${favorite.name} 캐릭터 조회`);

        const icon = document.createElement("span");
        icon.className = "favorite-character-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "★";

        const details = document.createElement("span");
        details.className = "favorite-character-details";

        const name = document.createElement("span");
        name.className = "favorite-character-name";
        name.textContent = favorite.name;

        const world = document.createElement("span");
        world.className = "favorite-character-world";
        world.textContent = favorite.worldName || "월드 정보 없음";
        details.append(name, world);
        openButton.append(icon, details);
        openButton.addEventListener("click", () => {
            if (!characterNameInput || !searchForm) return;
            characterNameInput.value = favorite.name;
            searchForm.requestSubmit();
        });

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "favorite-remove-button";
        removeButton.textContent = "×";
        removeButton.setAttribute("aria-label", `${favorite.name} 관심 목록에서 제거`);
        removeButton.addEventListener("click", () => {
            const nextFavorites = readFavoriteCharacters().filter(item => !isSameFavorite(item, favorite));
            if (!saveFavoriteCharacters(nextFavorites)) return;
            renderFavoriteList();
            showFavoriteFeedback(`${favorite.name} 캐릭터를 관심 목록에서 제거했습니다.`);
        });

        item.append(openButton, removeButton);
        favoriteList.append(item);
    });

    updateFavoriteCurrentButton();
}

function toggleCurrentFavorite() {
    if (!currentCharacter?.characterName) return;

    const current = {
        ocid: String(currentCharacter.ocid || ""),
        name: currentCharacter.characterName,
        worldName: currentCharacter.worldName || ""
    };
    const favorites = readFavoriteCharacters();
    const index = favorites.findIndex(item => isSameFavorite(item, current));
    let message = "";

    if (index >= 0) {
        favorites.splice(index, 1);
        message = `${current.name} 캐릭터를 관심 목록에서 제거했습니다.`;
    } else {
        if (favorites.length >= MAX_FAVORITES) {
            showFavoriteFeedback(`관심 캐릭터는 최대 ${MAX_FAVORITES}명까지 저장할 수 있습니다.`, true);
            return;
        }
        favorites.unshift(current);
        message = `${current.name} 캐릭터를 관심 목록에 저장했습니다.`;
    }

    if (!saveFavoriteCharacters(favorites)) return;
    renderFavoriteList();
    showFavoriteFeedback(message);
}

// 공통 표시 함수
function formatNumber(value) {
    if (value === null || value === undefined || value === "") return "-";
    return Number(value).toLocaleString("ko-KR");
}

function formatRanking(value) {
    if (value === null || value === undefined || value === "") return "-";
    return `${formatNumber(value)}위`;
}

function formatTrillion(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "-";
    const trillion = Number(value) / 1_000_000_000_000;
    if (Math.abs(trillion) >= 100) return `${trillion.toFixed(0)}조`;
    if (Math.abs(trillion) >= 10) return `${trillion.toFixed(1)}조`;
    return `${trillion.toFixed(2)}조`;
}

function formatPercent(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "-";
    return `${Number(value).toFixed(3)}%`;
}

function formatDate(dateString) {
    if (!dateString) return "-";
    const parts = String(dateString).split("-");
    return parts.length === 3 ? `${parts[0]}.${parts[1]}.${parts[2]}` : dateString;
}

function formatShortDate(dateString) {
    if (!dateString) return "-";
    const parts = String(dateString).split("-");
    return parts.length === 3 ? `${parts[1]}/${parts[2]}` : dateString;
}

function escapeHTML(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function setLoading(isLoading) {
    if (loadingMessage) loadingMessage.hidden = !isLoading;
    const button = searchForm?.querySelector(".search-button");
    if (button) {
        button.disabled = isLoading;
        button.textContent = isLoading ? "조회 중..." : "조회하기 →";
    }
}

function showError(message) {
    if (!errorMessage) return;
    errorMessage.textContent = message;
    errorMessage.hidden = false;
}

function hideError() {
    if (!errorMessage) return;
    errorMessage.hidden = true;
    errorMessage.textContent = "";
}

function sortHistoryAscending(history) {
    return [...(history || [])].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function sortHistoryDescending(history) {
    return [...(history || [])].sort((a, b) => String(b.date).localeCompare(String(a.date)));
}


// 기존 성장 계산 함수를 AI 리포트와 비교 카드에서도 공유한다.
function getDailyGrowth(history) {
    if (!history || history.length < 2) return null;
    const sorted = sortHistoryAscending(history);
    const latest = sorted[sorted.length - 1];
    if (!latest || latest.levelUp === true) return null;
    const growth = Number(latest.experienceChange);
    return Number.isFinite(growth) && growth > 0 ? growth : null;
}

function calculateAverageGrowth(history) {
    if (!history || history.length < 2) return null;
    const gains = history
        .map(item => Number(item.experienceChange))
        .filter(value => Number.isFinite(value) && value > 0);
    if (!gains.length) return null;
    return gains.reduce((sum, value) => sum + value, 0) / gains.length;
}

function calculateWeeklyGrowth(history) {
    if (!history || !history.length) return null;
    const gains = history
        .map(item => Number(item.experienceChange))
        .filter(value => Number.isFinite(value) && value > 0);
    return gains.length ? gains.reduce((sum, value) => sum + value, 0) : null;
}

function getRankingChange(history) {
    const sorted = sortHistoryAscending(history);
    if (sorted.length < 2) return null;
    const latest = sorted[sorted.length - 1];
    const previous = sorted[sorted.length - 2];
    const change = Number(previous.ranking) - Number(latest.ranking);
    return Number.isFinite(change) ? change : null;
}

function calculatePrediction(character, history) {
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

function formatLocalISODate(value) {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return null;
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function calculateGrowthMetrics(character, history, sharedPrediction) {
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

function renderPrediction(character, history, sharedPrediction) {
    const prediction = sharedPrediction || calculatePrediction(character, history);
    if (!prediction) {
        if (predictionRequired) predictionRequired.textContent = "-";
        if (predictionDays) predictionDays.textContent = "-";
        if (predictionDate) predictionDate.textContent = "-";
        if (predictionAverage) predictionAverage.textContent = "-";
        return;
    }
    if (predictionRequired) {
        predictionRequired.innerHTML = prediction.requiredExp !== null
            ? `${formatTrillion(prediction.requiredExp)} <span class="prediction-percent">(${formatPercent(prediction.currentRate)})</span>`
            : "-";
    }
    if (predictionDays) {
        predictionDays.textContent = Number.isFinite(prediction.days)
            ? `약 ${prediction.days.toFixed(1)}일 후` : "-";
    }
    if (predictionDate) {
        predictionDate.textContent = prediction.date
            ? `${String(prediction.date.getMonth() + 1).padStart(2, "0")}/${String(prediction.date.getDate()).padStart(2, "0")}`
            : "-";
    }
    if (predictionAverage) {
        predictionAverage.textContent = prediction.averageGrowth > 0
            ? formatTrillion(prediction.averageGrowth) : "-";
    }
}

function renderCharacter(character, history) {
    if (characterName) characterName.textContent = character.characterName || "-";
    if (characterImage) {
        if (character.character_image) {
            characterImage.src = character.character_image;
            characterImage.hidden = false;
        } else {
            characterImage.removeAttribute("src");
            characterImage.hidden = true;
        }
    }
    if (worldName) worldName.textContent = character.worldName || "-";
    if (worldLogo) {
        const logoUrl = worldLogoMap[character.worldName];
        if (logoUrl) {
            worldLogo.src = logoUrl;
            worldLogo.hidden = false;
        } else {
            worldLogo.removeAttribute("src");
            worldLogo.hidden = true;
        }
    }
    if (jobName) jobName.textContent = character.job || "-";
    if (guildName) guildName.textContent = character.guildName || "길드 없음";
    if (levelValue) levelValue.textContent = character.level !== undefined && character.level !== null ? formatNumber(character.level) : "-";
    if (experienceRate) experienceRate.textContent = formatPercent(character.experienceRate);
    if (averageDailyExperience) {
        const average = history?.length ? calculateAverageGrowth(history) : null;
        averageDailyExperience.textContent = average !== null ? formatTrillion(average) : "-";
    }
    updateFavoriteCurrentButton();
}

function renderRanking(character) {
    if (overallRanking) overallRanking.textContent = formatRanking(character.ranking);
    if (worldRanking) worldRanking.textContent = formatRanking(character.worldRanking);
    if (jobWorldRanking) jobWorldRanking.textContent = formatRanking(character.jobWorldRanking);
    if (jobRanking) jobRanking.textContent = formatRanking(character.jobRanking);
}

function renderGrowthSummary(character, history) {
    const dailyGrowth = getDailyGrowth(history);
    const weeklyGrowthValue = calculateWeeklyGrowth(history);
    const averageGrowthValue = calculateAverageGrowth(history);
    if (yesterdayGrowth) yesterdayGrowth.textContent = dailyGrowth !== null ? `+${formatTrillion(dailyGrowth)}` : "-";
    if (rankingChange) {
        const change = getRankingChange(history);
        rankingChange.textContent = change === null || change === 0 ? "-" : change > 0 ? `▲ ${change}` : `▼ ${Math.abs(change)}`;
    }
    if (weeklyGrowth) weeklyGrowth.textContent = weeklyGrowthValue !== null ? `+${formatTrillion(weeklyGrowthValue)}` : "-";
    if (averageGrowth) averageGrowth.textContent = averageGrowthValue !== null ? formatTrillion(averageGrowthValue) : "-";
}

function renderHistory(history) {
    if (!historyBody) return;
    historyBody.innerHTML = "";
    sortHistoryDescending(history).forEach(item => {
        const experience = item.experience === null || item.experience === undefined
            ? NaN
            : Number(item.experience);
        const gainValue = Number(item.experienceChange);
        const gain = Number.isFinite(gainValue) && gainValue > 0 ? gainValue : null;
        const statusLabel = item.recordStatus === "not_collected"
            ? "미수집"
            : item.recordStatus === "not_ready" ? "API 미제공" : "";
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHTML(formatDate(item.date))}</td>
            <td>${escapeHTML(formatRanking(item.ranking))}</td>
            <td class="experience-cell">
                <span class="experience-value">${Number.isFinite(experience) ? escapeHTML(formatNumber(experience)) : "-"}</span>
                ${gain !== null ? `<span class="experience-gain">↑${escapeHTML(formatTrillion(gain))}</span>` : ""}
                ${statusLabel ? `<span class="history-record-status">${escapeHTML(statusLabel)}</span>` : ""}
            </td>`;
        historyBody.appendChild(row);
    });
}


// AI 성장 리포트
function renderAIAnalysis(analysis) {
    if (!aiAnalysisResult) return;
    const sections = {
        growthPattern: "",
        growthChange: "",
        levelUp: "",
        growthOutlook: "",
        judgement: ""
    };
    const headings = [
        ["growthPattern", "성장 패턴"],
        ["growthChange", "성장 변화"],
        ["levelUp", "레벨업 분석"],
        ["growthOutlook", "성장 전망"],
        ["judgement", "AI 코멘트"]
    ];
    headings.forEach(([key, title], index) => {
        const nextTitle = headings[index + 1]?.[1];
        const lookahead = nextTitle ? `(?=\\[${nextTitle}\\]|$)` : "$";
        const match = analysis.match(new RegExp(`\\[${title}\\]\\s*([\\s\\S]*?)${lookahead}`));
        if (match) sections[key] = match[1].trim();
    });

    // 이전 AI 응답 형식도 기존 내용을 최대한 이어서 표시한다.
    if (!sections.growthChange) {
        sections.growthChange = analysis.match(/\[성장 분석\]\s*([\s\S]*?)(?=\[레벨업\]|$)/)?.[1]?.trim() || "";
    }
    if (!sections.levelUp) {
        sections.levelUp = analysis.match(/\[레벨업\]\s*([\s\S]*?)(?=\[AI 판단\]|$)/)?.[1]?.trim() || "";
    }
    if (!sections.judgement) {
        sections.judgement = analysis.match(/\[AI 판단\]\s*([\s\S]*)/)?.[1]?.trim() || "";
    }
    if (aiGrowthPattern) aiGrowthPattern.textContent = sections.growthPattern || "-";
    if (aiGrowthChange) aiGrowthChange.textContent = sections.growthChange || "-";
    if (aiLevelUp) aiLevelUp.textContent = sections.levelUp || "-";
    if (aiGrowthOutlook) aiGrowthOutlook.textContent = sections.growthOutlook || "-";
    if (aiJudgement) aiJudgement.textContent = sections.judgement || "-";
    if (aiAnalysisLoading) aiAnalysisLoading.hidden = true;
    if (aiAnalysisError) aiAnalysisError.hidden = true;
    aiAnalysisResult.hidden = false;
}

async function searchAIAnalysis(name, metrics) {
    const response = await fetch(`/api/ai-analysis?name=${encodeURIComponent(name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metrics })
    });
    const data = await response.json();
    if (!response.ok) {
        if (response.status === 429) throw new Error("현재 AI 분석을 사용할 수 없습니다. 잠시 후 다시 시도해주세요.");
        throw new Error(data.error || "AI 분석을 불러오지 못했습니다.");
    }
    return {
        analysis: data.analysis,
        cacheHit: data.cacheHit === true
    };
}

function hashAIAnalysisSignature(signature) {
    let hash = 2166136261;
    for (let index = 0; index < signature.length; index += 1) {
        hash ^= signature.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
}

function readAIResponseCache() {
    try {
        const saved = JSON.parse(localStorage.getItem(AI_CACHE_STORAGE_KEY) || "[]");
        if (!Array.isArray(saved)) return [];
        const now = Date.now();
        return saved.filter(item =>
            item &&
            typeof item.signature === "string" &&
            typeof item.analysis === "string" &&
            Number.isFinite(item.savedAt) &&
            now - item.savedAt <= AI_CACHE_TTL_MS
        ).slice(0, AI_CACHE_MAX_ENTRIES);
    } catch (error) {
        return [];
    }
}

function getCachedAIAnalysis(type, signature) {
    const cache = readAIResponseCache();
    const key = `${type}:${hashAIAnalysisSignature(signature)}`;
    const entry = cache.find(item =>
        item.type === type &&
        item.key === key &&
        item.signature === signature
    );
    if (!entry) return null;

    entry.lastUsedAt = Date.now();
    try {
        localStorage.setItem(AI_CACHE_STORAGE_KEY, JSON.stringify(cache));
    } catch (error) {
        // 캐시를 저장할 수 없어도 이미 읽은 결과는 사용한다.
    }
    return entry.analysis;
}

function saveCachedAIAnalysis(type, signature, analysis) {
    if (typeof analysis !== "string" || !analysis.trim()) return;
    const cache = readAIResponseCache();
    const key = `${type}:${hashAIAnalysisSignature(signature)}`;
    const now = Date.now();
    const nextCache = cache.filter(item => !(item.type === type && item.key === key));
    nextCache.push({
        type,
        key,
        signature,
        analysis,
        savedAt: now,
        lastUsedAt: now
    });
    nextCache.sort((left, right) => (right.lastUsedAt || right.savedAt) - (left.lastUsedAt || left.savedAt));
    try {
        localStorage.setItem(AI_CACHE_STORAGE_KEY, JSON.stringify(nextCache.slice(0, AI_CACHE_MAX_ENTRIES)));
    } catch (error) {
        // 저장소가 꽉 찼거나 비활성화된 경우 서버 캐시가 계속 동작한다.
    }
}

function reportHistorySignature(history) {
    return (Array.isArray(history) ? history : []).map(item => ({
        date: item.date ?? null,
        level: item.level ?? null,
        experienceChange: item.experienceChange ?? null,
        ranking: item.ranking ?? null,
        rankingChange: item.rankingChange ?? null,
        levelUp: item.levelUp === true
    }));
}

function buildGrowthReportSignature(name, character, history, metrics) {
    return JSON.stringify({
        version: 1,
        type: "growth-report",
        character: {
            characterName: character.characterName || name,
            worldName: character.worldName ?? null,
            job: character.job ?? null,
            level: character.level ?? null,
            experienceRate: character.experienceRate ?? null
        },
        metrics,
        history: reportHistorySignature(history)
    });
}

function comparisonSubjectSignature(character, metrics, history) {
    return {
        character: {
            characterName: character.characterName ?? null,
            worldName: character.worldName ?? null,
            job: character.job ?? null,
            level: character.level ?? null,
            experienceRate: character.experienceRate ?? null
        },
        metrics,
        history: (Array.isArray(history) ? history : []).map(item => ({
            date: item.date ?? null,
            level: item.level ?? null,
            experienceChange: item.experienceChange ?? null,
            ranking: item.ranking ?? null,
            rankingChange: item.rankingChange ?? null,
            levelUp: item.levelUp ?? false,
            recordStatus: item.recordStatus ?? null
        }))
    };
}

function buildComparisonSignature(primaryCharacter, primaryMetrics, primaryHistory, otherCharacter, otherMetrics, otherHistory) {
    return JSON.stringify({
        version: 1,
        type: "growth-comparison",
        primary: comparisonSubjectSignature(primaryCharacter, primaryMetrics, primaryHistory),
        comparison: comparisonSubjectSignature(otherCharacter, otherMetrics, otherHistory)
    });
}

function showAICacheNotice(element, message, type = "info") {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("is-warning", type === "warning");
    element.hidden = !message;
}

function buildCumulativeExperienceData(history) {
    const sorted = sortHistoryAscending(history);
    let cumulativeExperience = null;
    return sorted.map((item, index) => {
        const currentExperience = item.experience === null || item.experience === undefined
            ? NaN
            : Number(item.experience);
        if (!Number.isFinite(currentExperience)) {
            cumulativeExperience = null;
            return null;
        }
        if (cumulativeExperience === null) {
            cumulativeExperience = currentExperience / 1_000_000_000_000;
            return cumulativeExperience;
        }
        const previous = sorted[index - 1];
        const previousExperience = previous?.experience === null || previous?.experience === undefined
            ? NaN
            : Number(previous.experience);
        if (!Number.isFinite(previousExperience)) return cumulativeExperience;
        if (item.levelUp === true || (Number.isFinite(Number(item.level)) && Number.isFinite(Number(previous?.level)) && Number(item.level) > Number(previous.level))) return cumulativeExperience;
        const difference = currentExperience - previousExperience;
        if (difference > 0) cumulativeExperience += difference / 1_000_000_000_000;
        return cumulativeExperience;
    });
}

function renderChart(history) {
    const canvas = document.getElementById("growthChart");
    if (!canvas) return;
    const sorted = sortHistoryAscending(history);
    if (growthChart) {
        growthChart.destroy();
        growthChart = null;
    }
    if (!sorted.length) return;
    const labels = sorted.map(item => formatShortDate(item.date));
    const experienceData = buildCumulativeExperienceData(sorted);
    const dailyGrowthData = sorted.map(item => {
        const value = Number(item.experienceChange);
        return Number.isFinite(value) && value > 0 ? value / 1_000_000_000_000 : null;
    });
    const levelUpData = experienceData.map((value, index) => sorted[index]?.levelUp === true ? value : null);
    growthChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels,
            datasets: [
                { label: "누적 경험치", data: experienceData, yAxisID: "experience", borderWidth: 3, tension: 0, pointRadius: 4, pointHoverRadius: 6, fill: false },
                { label: "일일 상승량", data: dailyGrowthData, yAxisID: "dailyGrowth", borderWidth: 2, borderDash: [7, 6], tension: 0, pointRadius: 3, pointHoverRadius: 5, fill: false },
                { label: "레벨업", data: levelUpData, yAxisID: "experience", showLine: false, pointStyle: "star", pointRadius: 9, pointHoverRadius: 12, pointBackgroundColor: "#f5c542", pointBorderColor: "#d89f00", pointBorderWidth: 2, borderWidth: 0, fill: false }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        title(context) {
                            if (!context.length) return "";
                            return formatShortDate(sorted[context[0].dataIndex].date);
                        },
                        label(context) {
                            const index = context.dataIndex;
                            const item = sorted[index];
                            if (context.dataset.label === "레벨업") {
                                return ["⭐ 레벨업!", `${index > 0 ? sorted[index - 1].level : "-"} → ${item?.level ?? "-"}`];
                            }
                            const value = context.parsed.y;
                            if (value === null || value === undefined) return "";
                            if (context.dataset.label === "누적 경험치") return `누적 경험치: ${value.toFixed(1)}조`;
                            if (context.dataset.label === "일일 상승량") return `일일 상승량: ${value.toFixed(1)}조`;
                            return "";
                        }
                    }
                }
            },
            scales: {
                experience: {
                    type: "linear", position: "left", beginAtZero: false,
                    title: { display: true, text: "누적 경험치" },
                    ticks: { callback: value => `${Number(value).toFixed(0)}조` }
                },
                dailyGrowth: {
                    type: "linear", position: "right", beginAtZero: true,
                    title: { display: true, text: "일일 상승량" },
                    grid: { drawOnChartArea: false },
                    ticks: { callback: value => `${Number(value).toFixed(0)}조` }
                }
            }
        }
    });
}

async function readApiResponse(response, fallbackMessage) {
    let data = {};
    try { data = await response.json(); } catch (error) { /* JSON이 없으면 기본 오류 메시지를 사용한다. */ }
    if (!response.ok) throw new Error(data.error || fallbackMessage);
    return data;
}

async function searchCharacter(name, forceRefresh = false) {
    const refreshParam = forceRefresh ? "&refresh=1" : "";
    const response = await fetch(
        `/api/character?name=${encodeURIComponent(name)}${refreshParam}`,
        forceRefresh ? { cache: "no-store" } : {}
    );
    return readApiResponse(response, "캐릭터 정보를 불러오지 못했습니다.");
}

async function searchHistory(name, forceRefresh = false) {
    const refreshParam = forceRefresh ? "&refresh=1" : "";
    const response = await fetch(
        `/api/history?name=${encodeURIComponent(name)}${refreshParam}`,
        forceRefresh ? { cache: "no-store" } : {}
    );
    return readApiResponse(response, "성장 기록을 불러오지 못했습니다.");
}

function renderHistoryRangeNotice(days, status = null) {
    if (!historyRangeNotice) return;
    if (days === 7) {
        const available = currentHistory.filter(item => item.recordStatus === "available").length;
        historyRangeNotice.textContent =
            `최근 7일 기록을 표시합니다. API에서 확인한 날짜별 정상 기록은 ${available}일입니다.`;
        return;
    }
    if (!status) {
        historyRangeNotice.textContent =
            `저장된 최근 ${days}일 기록입니다. 저장된 값이 없는 날짜는 빈 기록으로 표시됩니다.`;
        return;
    }
    historyRangeNotice.textContent =
        `저장된 최근 ${days}일 기록: 정상 ${status.availableDays}일 · API 미제공 ${status.notReadyDays}일 · 미수집 ${status.notCollectedDays}일. 미수집 날짜는 이 사이트에 저장된 기록이 없는 날이며, 과거 데이터가 자동으로 복구된다는 뜻은 아닙니다.`;
}

function shiftSnapshotDate(dateString, offsetDays) {
    const [year, month, day] = String(dateString || "").split("-").map(Number);
    if (!year || !month || !day) return null;
    const shifted = new Date(Date.UTC(year, month - 1, day + offsetDays));
    return shifted.toISOString().slice(0, 10);
}

async function fetchArchiveRange(days, endDate = null) {
    const params = new URLSearchParams({
        ocid: currentCharacter?.ocid || "",
        days: String(days)
    });
    if (endDate) params.set("end", endDate);

    const response = await fetch(`/api/history/archive?${params.toString()}`, {
        cache: "no-store"
    });
    return readApiResponse(response, "저장된 성장 기록을 불러오지 못했습니다.");
}

function summarizePeriod(history, days) {
    const records = sortHistoryAscending(Array.isArray(history) ? history : []);
    const available = records.filter(item =>
        item.recordStatus === "available" &&
        item.experience !== null &&
        item.experience !== undefined &&
        Number.isFinite(Number(item.experience))
    );
    const confirmedChanges = records.filter(item =>
        item.recordStatus === "available" &&
        item.experienceChange !== null &&
        item.experienceChange !== undefined &&
        Number.isFinite(Number(item.experienceChange))
    );
    const growth = confirmedChanges.length
        ? confirmedChanges.reduce((sum, item) => sum + Number(item.experienceChange), 0)
        : null;
    const averageGrowth = growth !== null ? growth / confirmedChanges.length : null;

    const ranked = records.filter(item =>
        item.recordStatus === "available" &&
        item.ranking !== null &&
        item.ranking !== undefined &&
        Number.isFinite(Number(item.ranking))
    );
    const rankingChange = ranked.length >= 2
        ? Number(ranked[0].ranking) - Number(ranked[ranked.length - 1].ranking)
        : null;

    const availableDays = records.filter(item => item.recordStatus === "available").length;
    const notReadyDays = records.filter(item => item.recordStatus === "not_ready").length;
    const notCollectedDays = records.filter(item => item.recordStatus === "not_collected").length;

    return {
        days,
        startDate: records[0]?.date || null,
        endDate: records[records.length - 1]?.date || null,
        firstObservedDate: available[0]?.date || null,
        lastObservedDate: available[available.length - 1]?.date || null,
        growth,
        confirmedChangeDays: confirmedChanges.length,
        averageGrowth,
        rankingChange,
        availableDays,
        notReadyDays,
        notCollectedDays,
        coveragePercent: records.length ? (availableDays / records.length) * 100 : 0
    };
}

function buildPeriodSummary(currentData, previousData, previousUnavailable = false) {
    const summary = summarizePeriod(currentData.history, currentData.days);
    summary.startDate = currentData.startDate || summary.startDate;
    summary.endDate = currentData.endDate || summary.endDate;
    summary.previousUnavailable = previousUnavailable;
    summary.previousGrowth = null;
    summary.previousGrowthSamples = 0;
    summary.comparisonPercent = null;

    if (previousData) {
        const previous = summarizePeriod(previousData.history, previousData.days);
        summary.previousGrowth = previous.growth;
        summary.previousGrowthSamples = previous.confirmedChangeDays;
        if (
            summary.growth !== null &&
            previous.growth !== null &&
            previous.confirmedChangeDays > 0 &&
            Math.abs(previous.growth) > 0
        ) {
            summary.comparisonPercent = (
                (summary.growth - previous.growth) / Math.abs(previous.growth)
            ) * 100;
        }
    }
    return summary;
}

function renderPeriodSummary(summary) {
    if (!periodSummarySection) return;
    const visible = !!summary && [30, 90].includes(Number(summary.days));
    periodSummarySection.hidden = !visible;
    if (!visible) return;

    const percent = summary.coveragePercent;
    if (periodSummaryRange) {
        periodSummaryRange.textContent =
            `${formatDate(summary.startDate)} ~ ${formatDate(summary.endDate)} · 직전 ${summary.days}일 기록과 비교`;
    }
    if (periodSummaryCoverageBadge) {
        periodSummaryCoverageBadge.textContent = `기록 ${percent.toFixed(0)}%`;
        periodSummaryCoverageBadge.classList.toggle("is-warning", percent < 70);
    }

    if (periodGrowthValue) {
        periodGrowthValue.textContent = summary.growth === null ? "자료 부족" : formatTrillion(summary.growth);
        periodGrowthValue.classList.toggle("is-muted", summary.growth === null);
    }
    if (periodGrowthDetail) {
        periodGrowthDetail.textContent = summary.confirmedChangeDays
            ? `연속 기록 ${summary.confirmedChangeDays}일의 증가량 합계`
            : "연속된 날짜의 증가량을 확인할 수 없습니다.";
    }

    if (periodAverageValue) {
        periodAverageValue.textContent = summary.averageGrowth === null
            ? "자료 부족"
            : formatTrillion(summary.averageGrowth);
        periodAverageValue.classList.toggle("is-muted", summary.averageGrowth === null);
    }
    if (periodAverageDetail) {
        periodAverageDetail.textContent = summary.confirmedChangeDays
            ? `증가량 확인 ${summary.confirmedChangeDays}일 기준`
            : "비교 가능한 일일 변화 기록이 없습니다.";
    }

    if (periodRankingValue) {
        let rankingText = "자료 부족";
        if (summary.rankingChange !== null) {
            if (summary.rankingChange > 0) rankingText = `▲ ${formatNumber(summary.rankingChange)}위 상승`;
            else if (summary.rankingChange < 0) rankingText = `▼ ${formatNumber(Math.abs(summary.rankingChange))}위 하락`;
            else rankingText = "변화 없음";
        }
        periodRankingValue.textContent = rankingText;
        periodRankingValue.classList.toggle("is-positive", summary.rankingChange > 0);
        periodRankingValue.classList.toggle("is-negative", summary.rankingChange < 0);
        periodRankingValue.classList.toggle("is-muted", summary.rankingChange === null);
    }
    if (periodRankingDetail) {
        periodRankingDetail.textContent = summary.firstObservedDate && summary.lastObservedDate
            ? `${formatDate(summary.firstObservedDate)} → ${formatDate(summary.lastObservedDate)}`
            : "랭킹 기록이 두 개 이상 필요합니다.";
    }

    if (periodComparisonValue) {
        let comparisonText = "비교 자료 부족";
        if (summary.comparisonPercent !== null) {
            const sign = summary.comparisonPercent > 0 ? "+" : "";
            comparisonText = `${sign}${summary.comparisonPercent.toFixed(1)}%`;
        }
        periodComparisonValue.textContent = comparisonText;
        periodComparisonValue.classList.toggle("is-positive", summary.comparisonPercent > 0);
        periodComparisonValue.classList.toggle("is-negative", summary.comparisonPercent < 0);
        periodComparisonValue.classList.toggle("is-muted", summary.comparisonPercent === null);
    }
    if (periodComparisonDetail) {
        if (summary.previousUnavailable) {
            periodComparisonDetail.textContent = "직전 기간 기록을 불러오지 못했습니다.";
        } else if (summary.previousGrowth !== null && summary.previousGrowthSamples > 0) {
            periodComparisonDetail.textContent = `직전 확인 증가량 ${formatTrillion(summary.previousGrowth)}`;
        } else {
            periodComparisonDetail.textContent = "직전 기간의 연속 기록이 부족합니다.";
        }
    }

    if (periodCoverageValue) {
        periodCoverageValue.textContent = `${summary.availableDays} / ${summary.days}일`;
    }
    if (periodCoverageDetail) {
        periodCoverageDetail.textContent =
            `API 미제공 ${summary.notReadyDays}일 · 미수집 ${summary.notCollectedDays}일`;
    }
    if (periodSummaryFootnote) {
        periodSummaryFootnote.textContent =
            "증가량은 연속된 날짜에서 확인된 경험치 변화만 합산합니다. 미수집 날짜와 레벨업으로 경험치 기준이 바뀐 구간은 계산에서 제외되므로 실제 전체 성장량보다 작게 표시될 수 있습니다.";
    }
}

async function loadHistoryRange(days) {
    const selectedDays = [7, 30, 90].includes(Number(days)) ? Number(days) : 7;
    if (!currentCharacter) return;
    if (selectedDays === 7) {
        currentDisplayHistory = currentHistory;
        currentHistoryRange = 7;
        currentHistoryRangeStatus = null;
        currentPeriodSummary = null;
        if (historyRangeSelect) historyRangeSelect.value = "7";
        renderHistory(currentDisplayHistory);
        renderChart(currentDisplayHistory);
        renderHistoryRangeNotice(7);
        renderPeriodSummary(null);
        saveTrackerState({
            historyRange: 7,
            displayHistory: currentDisplayHistory,
            historyRangeStatus: null,
            periodSummary: null
        });
        return;
    }

    const data = await fetchArchiveRange(selectedDays);
    let previousData = null;
    let previousUnavailable = false;
    const previousEndDate = shiftSnapshotDate(data.startDate, -1);
    if (previousEndDate) {
        try {
            previousData = await fetchArchiveRange(selectedDays, previousEndDate);
        } catch (error) {
            previousUnavailable = true;
        }
    } else {
        previousUnavailable = true;
    }

    currentDisplayHistory = data.history || [];
    currentHistoryRange = selectedDays;
    currentHistoryRangeStatus = {
        availableDays: data.availableDays || 0,
        notReadyDays: data.notReadyDays || 0,
        notCollectedDays: data.notCollectedDays || 0,
        storageBackend: data.storageBackend || "unknown",
        persistentStorage: data.persistentStorage === true
    };
    currentPeriodSummary = buildPeriodSummary(data, previousData, previousUnavailable);

    if (historyRangeSelect) historyRangeSelect.value = String(selectedDays);
    renderHistory(currentDisplayHistory);
    renderChart(currentDisplayHistory);
    renderHistoryRangeNotice(selectedDays, currentHistoryRangeStatus);
    renderPeriodSummary(currentPeriodSummary);
    saveTrackerState({
        historyRange: selectedDays,
        displayHistory: currentDisplayHistory,
        historyRangeStatus: currentHistoryRangeStatus,
        periodSummary: currentPeriodSummary
    });
}

async function handleHistoryRangeChange() {
    const selectedDays = Number(historyRangeSelect?.value || 7);
    if (!currentCharacter) return;
    if (historyRangeSelect) historyRangeSelect.disabled = true;
    if (historyRangeNotice && selectedDays !== 7) {
        historyRangeNotice.textContent = `저장된 최근 ${selectedDays}일 기록을 불러오고 있습니다...`;
    }
    try {
        await loadHistoryRange(selectedDays);
    } catch (error) {
        if (historyRangeSelect) historyRangeSelect.value = String(currentHistoryRange);
        if (historyRangeNotice) {
            historyRangeNotice.textContent =
                `저장 기록을 불러오지 못했습니다. ${error.message || "저장소 연결을 확인해주세요."}`;
        }
    } finally {
        if (historyRangeSelect) historyRangeSelect.disabled = false;
    }
}

function formatStatusTime(value) {
    if (!value) return "기준 시각을 확인할 수 없음";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "기준 시각을 확인할 수 없음";
    return parsed.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" });
}

function renderDataStatus(character, historyResult) {
    if (!dataStatusNotice) return;

    // Keep data provenance with the saved session so a refresh can restore the notice.
    character.historyStatus = historyResult.historyStatus || null;
    character.historyDataStatus = historyResult.dataStatus || null;
    character.historyDataAsOf = historyResult.dataAsOf || null;

    const messages = [];
    let isWarning = false;
    const characterTime = formatStatusTime(character.dataAsOf);
    const historyTime = formatStatusTime(historyResult.dataAsOf);

    if (character.dataStatus === "stale") {
        messages.push(`캐릭터 정보는 마지막 정상 조회 결과입니다(${characterTime}). 최신 정보가 아닐 수 있습니다.`);
        isWarning = true;
    }
    if (historyResult.dataStatus === "stale") {
        messages.push(`성장 기록은 마지막 정상 조회 결과입니다(${historyTime}).`);
        isWarning = true;
    }
    if (historyResult.dataStatus === "unavailable") {
        messages.push("성장 기록을 조회하지 못했습니다. 캐릭터 기본 정보는 계속 표시합니다.");
        isWarning = true;
    }
    if (character.rankingDataStatus === "not_ready") {
        messages.push("당일 랭킹 정보가 아직 제공되지 않았거나 해당 랭킹 기록이 없습니다.");
        isWarning = true;
    } else if (["partial", "unavailable"].includes(character.rankingDataStatus)) {
        messages.push("랭킹 정보 일부를 가져오지 못했습니다. 표시된 순위가 불완전할 수 있습니다.");
        isWarning = true;
    }
    if (historyResult.historyStatus === "today_not_ready") {
        messages.push("오늘 날짜의 성장 기록이 아직 제공되지 않았습니다. 확인 가능한 기록만 표시합니다.");
        isWarning = true;
    }
    character.historyStorage = historyResult.historyStorage || character.historyStorage || null;
    if (historyResult.historyStorage?.status === "unavailable") {
        messages.push("장기 성장 기록 저장소에 연결하지 못했습니다. 현재 조회 결과는 표시하지만 기록은 저장되지 않았을 수 있습니다.");
        isWarning = true;
    } else if (historyResult.historyStorage?.backend === "sqlite") {
        messages.push("현재는 SQLite 저장소를 사용합니다. Render에서 기록을 장기 보존하려면 PostgreSQL 연결 설정이 필요합니다.");
        isWarning = true;
    }

    if (!messages.length) {
        messages.push(`조회 기준 시각 — 캐릭터: ${characterTime} · 성장 기록: ${historyTime}`);
    }

    dataStatusNotice.textContent = messages.join(" ");
    dataStatusNotice.classList.toggle("is-warning", isWarning);
    dataStatusNotice.classList.toggle("is-info", !isWarning);
    dataStatusNotice.hidden = false;
}

async function runAIReport(name, character, history, sharedMetrics) {
    if (aiAnalysisLoading) aiAnalysisLoading.hidden = false;
    if (aiAnalysisError) aiAnalysisError.hidden = true;
    if (aiAnalysisResult) aiAnalysisResult.hidden = true;
    showAICacheNotice(aiAnalysisCacheNotice, "동일 데이터의 저장된 분석을 확인하고 있습니다.");

    try {
        const metrics = sharedMetrics || calculateGrowthMetrics(character, history);
        const signature = buildGrowthReportSignature(name, character, history, metrics);
        const cachedAnalysis = getCachedAIAnalysis("growth-report-v1", signature);
        if (cachedAnalysis) {
            renderAIAnalysis(cachedAnalysis);
            showAICacheNotice(aiAnalysisCacheNotice, "저장된 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다.");
            saveTrackerState({ character, history, metrics, aiAnalysis: cachedAnalysis });
            return;
        }

        const result = await searchAIAnalysis(name, metrics);
        const analysis = result.analysis;
        saveCachedAIAnalysis("growth-report-v1", signature, analysis);
        renderAIAnalysis(analysis);

        const notice = result.cacheHit
            ? "서버에 저장된 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다."
            : "새 분석을 생성했습니다. 같은 데이터의 다음 조회에서는 저장된 결과를 재사용합니다.";
        showAICacheNotice(aiAnalysisCacheNotice, notice);
        saveTrackerState({
            character,
            history,
            metrics,
            aiAnalysis: analysis
        });
    } catch (error) {
        console.error("AI 분석 실패:", error);
        if (aiAnalysisLoading) aiAnalysisLoading.hidden = true;
        showAICacheNotice(aiAnalysisCacheNotice, "이번 분석은 완료되지 않아 캐시에 저장하지 않았습니다.", "warning");

        if (aiAnalysisError) {
            aiAnalysisError.textContent = error.message || "AI 분석을 불러오지 못했습니다.";
            aiAnalysisError.hidden = false;
        }
    }
}

async function handleSearch(event) {
    event.preventDefault();
    const name = characterNameInput?.value.trim();
    if (!name) {
        showError("캐릭터명을 입력해주세요.");
        return;
    }
    hideError();
    if (resultSection) resultSection.hidden = true;
    syncHomeView();
    if (saveImageButton) saveImageButton.disabled = true;
    if (savePdfButton) savePdfButton.disabled = true;
    if (comparisonResult) comparisonResult.hidden = true;
    setLoading(true);
    try {
        const character = await searchCharacter(name, true);
        let historyResult;
        try {
            historyResult = await searchHistory(name, true);
        } catch (historyError) {
            // Preserve the usable character panel when only history lookup fails.
            historyResult = {
                history: [],
                dataStatus: "unavailable",
                historyStatus: "unavailable",
                dataAsOf: null
            };
        }
        const history = historyResult.history || [];
        renderDataStatus(character, historyResult);
        currentCharacter = character;
        currentHistory = history;
        currentDisplayHistory = history;
        currentHistoryRange = 7;
        currentHistoryRangeStatus = null;
        currentPeriodSummary = null;
        if (historyRangeSelect) historyRangeSelect.value = "7";
        renderHistoryRangeNotice(7);
        renderPeriodSummary(null);
        const prediction = calculatePrediction(character, history);
        const metrics = calculateGrowthMetrics(character, history, prediction);
        sessionStorage.removeItem(STORAGE_KEY);
        renderCharacter(character, history);
        renderRanking(character);
        renderGrowthSummary(character, history);
        renderPrediction(character, history, prediction);
        renderHistory(currentDisplayHistory);
        renderChart(currentDisplayHistory);
        if (saveImageButton) saveImageButton.disabled = false;
        if (savePdfButton) savePdfButton.disabled = false;
        if (resultSection) resultSection.hidden = false;
        syncHomeView();
        saveTrackerState({
            character,
            history,
            metrics,
            aiAnalysis: null,
            comparison: null,
            historyRange: 7,
            displayHistory: currentDisplayHistory,
            historyRangeStatus: null
        });
        setLoading(false);
        await runAIReport(name, character, history, metrics);
    } catch (error) {
        console.error(error);
        showError(error.message || "조회 중 오류가 발생했습니다.");
    } finally {
        setLoading(false);
    }
}

async function refreshVisibleCharacter({ automatic = false } = {}) {
    if (!currentCharacter) return;

    const name = currentCharacter.characterName || characterNameInput?.value.trim();
    if (!name) return;

    if (refreshDataButton) {
        refreshDataButton.disabled = true;
        refreshDataButton.classList.add("is-loading");
        refreshDataButton.setAttribute("aria-busy", "true");
    }
    if (refreshDataButtonLabel) {
        refreshDataButtonLabel.textContent = "최신 정보 확인 중";
    }
    if (dataStatusNotice) {
        dataStatusNotice.textContent = "넥슨 Open API에서 현재 제공하는 최신 정보를 확인하고 있습니다.";
        dataStatusNotice.classList.add("is-info");
        dataStatusNotice.classList.remove("is-warning");
        dataStatusNotice.hidden = false;
    }

    try {
        const character = await searchCharacter(name, true);
        const historyResult = await searchHistory(name, true);
        const history = historyResult.history || [];
        currentCharacter = character;
        currentHistory = history;
        try {
            await loadHistoryRange(Number(historyRangeSelect?.value || currentHistoryRange));
        } catch (rangeError) {
            currentDisplayHistory = history;
            currentHistoryRange = 7;
            currentHistoryRangeStatus = null;
            if (historyRangeSelect) historyRangeSelect.value = "7";
            renderHistoryRangeNotice(7);
        }

        const prediction = calculatePrediction(character, history);
        const metrics = calculateGrowthMetrics(character, history, prediction);

        renderDataStatus(character, historyResult);
        if (dataStatusNotice) {
            dataStatusNotice.textContent += " 표시 시각은 웹 조회 시각이며, 인게임 변경 사항의 API 반영 시점과 다를 수 있습니다.";
        }
        renderCharacter(character, history);
        renderRanking(character);
        renderGrowthSummary(character, history);
        renderPrediction(character, history, prediction);
        renderHistory(currentDisplayHistory);
        renderChart(currentDisplayHistory);

        // The previous comparison refers to the old data, so hide it until compared again.
        if (comparisonResult) comparisonResult.hidden = true;
        saveTrackerState({
            character,
            history,
            metrics,
            aiAnalysis: null,
            comparison: null,
            historyRange: currentHistoryRange,
            displayHistory: currentDisplayHistory,
            historyRangeStatus: currentHistoryRangeStatus
        });

        try {
            sessionStorage.setItem(AUTO_REFRESH_KEY, String(Date.now()));
        } catch (storageError) {
            console.warn("자동 갱신 시각을 저장하지 못했습니다.");
        }

        const usingPreviousData = character.dataStatus === "stale" || historyResult.dataStatus === "stale";
        if (dataStatusNotice) {
            const prefix = usingPreviousData
                ? "최신 조회에 실패해 마지막 정상 데이터를 표시합니다. "
                : automatic
                    ? "저장된 결과를 최신 공개 데이터로 다시 확인했습니다. "
                    : "최신 공개 데이터 조회를 마쳤습니다. ";
            dataStatusNotice.textContent = prefix + dataStatusNotice.textContent;
        }

        // Do not block the refreshed character screen while the AI report is generated.
        runAIReport(name, character, history, metrics);
    } catch (error) {
        console.error("최신 정보 갱신 실패:", error);
        if (dataStatusNotice) {
            dataStatusNotice.textContent = "최신 정보 조회에 실패했습니다. 기존 화면 결과를 유지합니다. " +
                "잠시 후 다시 시도하거나, 인게임 정보가 API에 반영된 뒤 다시 조회해주세요.";
            dataStatusNotice.classList.add("is-warning");
            dataStatusNotice.classList.remove("is-info");
            dataStatusNotice.hidden = false;
        }
    } finally {
        if (refreshDataButton) {
            refreshDataButton.disabled = false;
            refreshDataButton.classList.remove("is-loading");
            refreshDataButton.setAttribute("aria-busy", "false");
        }
        if (refreshDataButtonLabel) {
            refreshDataButtonLabel.textContent = "최신 정보 다시 조회";
        }
    }
}

function formatRankingChange(value) {
    if (value === null || value === undefined) return "기록 없음";
    if (value > 0) return `▲ ${formatNumber(value)}위 상승`;
    if (value < 0) return `▼ ${formatNumber(Math.abs(value))}위 하락`;
    return "변화 없음";
}

function getPredictionLabel(metrics) {
    const days = metrics?.prediction?.estimatedDays;
    return Number.isFinite(days) ? `약 ${days.toFixed(1)}일` : "예측 자료 부족";
}

function renderComparisonCharacter(prefix, character, metrics) {
    const values = {
        Name: character.characterName || "-",
        Level: character.level !== null && character.level !== undefined ? `Lv. ${formatNumber(character.level)}` : "-",
        ExpRate: formatPercent(character.experienceRate),
        Daily: formatTrillion(metrics.latestDailyGrowth),
        Average: formatTrillion(metrics.averageDailyGrowth),
        Weekly: formatTrillion(metrics.sevenDayGrowth),
        Ranking: formatRankingChange(metrics.rankingChange),
        Prediction: getPredictionLabel(metrics)
    };
    Object.entries(values).forEach(([suffix, value]) => {
        const element = document.getElementById(`${prefix}Compare${suffix}`);
        if (element) element.textContent = value;
    });
}

async function handleComparison(event) {
    event.preventDefault();
    const name = comparisonNameInput?.value.trim();
    if (!currentCharacter || !currentHistory.length) {
        if (comparisonError) {
            comparisonError.textContent = "먼저 기준 캐릭터를 조회해주세요.";
            comparisonError.hidden = false;
        }
        return;
    }
    if (!name) {
        if (comparisonError) {
            comparisonError.textContent = "비교할 캐릭터명을 입력해주세요.";
            comparisonError.hidden = false;
        }
        return;
    }
    if (name.toLocaleLowerCase() === String(currentCharacter.characterName).toLocaleLowerCase()) {
        if (comparisonError) {
            comparisonError.textContent = "같은 캐릭터는 비교할 수 없습니다.";
            comparisonError.hidden = false;
        }
        return;
    }
    if (comparisonError) comparisonError.hidden = true;
    if (comparisonResult) comparisonResult.hidden = true;
    showAICacheNotice(comparisonAICacheNotice, "동일한 비교 데이터의 저장된 분석을 확인하고 있습니다.");
    if (comparisonLoading) comparisonLoading.hidden = false;
    if (comparisonButton) comparisonButton.disabled = true;
    try {
        const otherCharacter = await searchCharacter(name, true);
        const otherHistoryResult = await searchHistory(name, true);
        const otherHistory = otherHistoryResult.history || [];
        if (String(otherCharacter.characterName).toLocaleLowerCase() === String(currentCharacter.characterName).toLocaleLowerCase()) {
            throw new Error("같은 캐릭터는 비교할 수 없습니다.");
        }
        const primaryPrediction = calculatePrediction(currentCharacter, currentHistory);
        const otherPrediction = calculatePrediction(otherCharacter, otherHistory);
        const primaryMetrics = calculateGrowthMetrics(currentCharacter, currentHistory, primaryPrediction);
        const otherMetrics = calculateGrowthMetrics(otherCharacter, otherHistory, otherPrediction);
        renderComparisonCharacter("primary", currentCharacter, primaryMetrics);
        renderComparisonCharacter("secondary", otherCharacter, otherMetrics);
        const signature = buildComparisonSignature(
            currentCharacter,
            primaryMetrics,
            currentHistory,
            otherCharacter,
            otherMetrics,
            otherHistory
        );
        let comparisonAnalysis = getCachedAIAnalysis("growth-comparison-v1", signature);
        let comparisonCacheMessage = "저장된 비교 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다.";

        if (!comparisonAnalysis) {
            const response = await fetch("/api/ai-comparison", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    primary: { character: currentCharacter, metrics: primaryMetrics, history: currentHistory },
                    comparison: { character: otherCharacter, metrics: otherMetrics, history: otherHistory }
                })
            });
            const data = await readApiResponse(response, "AI 성장 비교 분석을 불러오지 못했습니다.");
            comparisonAnalysis = data.analysis || "분석 결과가 없습니다.";
            saveCachedAIAnalysis("growth-comparison-v1", signature, comparisonAnalysis);
            comparisonCacheMessage = data.cacheHit
                ? "서버에 저장된 비교 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다."
                : "새 비교 분석을 생성했습니다. 같은 데이터는 저장된 결과를 재사용합니다.";
        }
        if (comparisonAIAnalysis) comparisonAIAnalysis.textContent = comparisonAnalysis;
        showAICacheNotice(comparisonAICacheNotice, comparisonCacheMessage);
        if (comparisonResult) comparisonResult.hidden = false;
        saveTrackerState({
            comparison: {
                character: otherCharacter,
                history: otherHistory,
                metrics: otherMetrics,
                aiAnalysis: comparisonAnalysis
            }
        });
    } catch (error) {
        console.error("성장 비교 실패:", error);
        if (comparisonError) {
            comparisonError.textContent = error.message || "성장 비교를 불러오지 못했습니다.";
            comparisonError.hidden = false;
        }
    } finally {
        if (comparisonLoading) comparisonLoading.hidden = true;
        if (comparisonButton) comparisonButton.disabled = false;
    }
}

function restoreTrackerState() {
    const state = getTrackerState();

    if (!state?.character || !Array.isArray(state.history)) {
        return;
    }

    currentCharacter = state.character;
    currentHistory = state.history;
    renderDataStatus(currentCharacter, {
        historyStatus: currentCharacter.historyStatus,
        dataStatus: currentCharacter.historyDataStatus || "cached",
        dataAsOf: currentCharacter.historyDataAsOf,
        historyStorage: currentCharacter.historyStorage
    });

    const prediction = calculatePrediction(
        currentCharacter,
        currentHistory
    );

    const metrics = state.metrics ||
        calculateGrowthMetrics(
            currentCharacter,
            currentHistory,
            prediction
        );

    if (characterNameInput) {
        characterNameInput.value = currentCharacter.characterName || "";
    }

    currentHistoryRange = [7, 30, 90].includes(Number(state.historyRange))
        ? Number(state.historyRange)
        : 7;
    currentDisplayHistory = Array.isArray(state.displayHistory)
        ? state.displayHistory
        : currentHistory;
    currentHistoryRangeStatus = state.historyRangeStatus || null;
    currentPeriodSummary = state.periodSummary || null;
    if (historyRangeSelect) historyRangeSelect.value = String(currentHistoryRange);
    renderHistoryRangeNotice(currentHistoryRange, currentHistoryRangeStatus);
    renderPeriodSummary(currentPeriodSummary);

    renderCharacter(currentCharacter, currentHistory);
    renderRanking(currentCharacter);
    renderGrowthSummary(currentCharacter, currentHistory);
    renderPrediction(currentCharacter, currentHistory, prediction);
    renderHistory(currentDisplayHistory);
    renderChart(currentDisplayHistory);

    if (saveImageButton) saveImageButton.disabled = false;
    if (savePdfButton) savePdfButton.disabled = false;
    if (resultSection) resultSection.hidden = false;
    syncHomeView();

    if (state.aiAnalysis) {
        renderAIAnalysis(state.aiAnalysis);
    }

    const comparison = state.comparison;

    if (
        comparison?.character &&
        Array.isArray(comparison.history) &&
        comparison.metrics
    ) {
        renderComparisonCharacter(
            "primary",
            currentCharacter,
            metrics
        );

        renderComparisonCharacter(
            "secondary",
            comparison.character,
            comparison.metrics
        );

        if (comparisonNameInput) {
            comparisonNameInput.value =
                comparison.character.characterName || "";
        }

        if (comparisonAIAnalysis) {
            comparisonAIAnalysis.textContent =
                comparison.aiAnalysis || "분석 결과가 없습니다.";
        }

        if (comparisonResult) {
            comparisonResult.hidden = false;
        }
    }
}


// 결과 화면 이미지 / PDF 저장
async function captureResultSection() {
    const section = document.getElementById("resultSection");
    if (!section || section.hidden) {
        alert("먼저 캐릭터를 조회해주세요.");
        return null;
    }
    return await html2canvas(section, { backgroundColor: "#f7f6fb", scale: 2, useCORS: true });
}

if (saveImageButton) {
    saveImageButton.disabled = true;
    saveImageButton.addEventListener("click", async function() {
        try {
            saveImageButton.disabled = true;
            saveImageButton.textContent = "저장 중...";
            const canvas = await captureResultSection();
            if (!canvas) return;
            const name = document.getElementById("characterNameResult")?.textContent || "character";
            const link = document.createElement("a");
            link.download = `maple-growth-${name}.png`;
            link.href = canvas.toDataURL("image/png");
            link.click();
        } catch (error) {
            console.error("이미지 저장 실패:", error);
            alert("이미지 저장 중 오류가 발생했습니다.");
        } finally {
            saveImageButton.disabled = false;
            saveImageButton.textContent = "이미지 저장";
        }
    });
}

if (savePdfButton) {
    savePdfButton.disabled = true;
    savePdfButton.addEventListener("click", async function() {
        try {
            savePdfButton.disabled = true;
            savePdfButton.textContent = "생성 중...";
            const canvas = await captureResultSection();
            if (!canvas) return;
            const name = document.getElementById("characterNameResult")?.textContent || "character";
            const imgData = canvas.toDataURL("image/png");
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const margin = 10;
            const availableWidth = pageWidth - margin * 2;
            const imageHeight = canvas.height * availableWidth / canvas.width;
            let heightLeft = imageHeight;
            let position = margin;
            pdf.addImage(imgData, "PNG", margin, position, availableWidth, imageHeight);
            heightLeft -= pageHeight - margin * 2;
            while (heightLeft > 0) {
                position = -(imageHeight - heightLeft) + margin;
                pdf.addPage();
                pdf.addImage(imgData, "PNG", margin, position, availableWidth, imageHeight);
                heightLeft -= pageHeight - margin * 2;
            }
            pdf.save(`maple-growth-${name}.pdf`);
        } catch (error) {
            console.error("PDF 저장 실패:", error);
            alert("PDF 저장 중 오류가 발생했습니다.");
        } finally {
            savePdfButton.disabled = false;
            savePdfButton.textContent = "PDF 저장";
        }
    });
}

if (searchForm) searchForm.addEventListener("submit", handleSearch);
if (comparisonForm) comparisonForm.addEventListener("submit", handleComparison);
if (favoriteCurrentButton) favoriteCurrentButton.addEventListener("click", toggleCurrentFavorite);
if (refreshDataButton) refreshDataButton.addEventListener("click", () => refreshVisibleCharacter());
if (historyRangeSelect) historyRangeSelect.addEventListener("change", handleHistoryRangeChange);

// 사이트 이름 클릭: 저장된 상태를 지우고 초기 메인 화면으로 이동
const homeLink = document.getElementById("homeLink");
if (homeLink) {
    homeLink.addEventListener("click", function(event) {
        event.preventDefault();
        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch (error) {
            console.error("저장된 상태를 삭제하지 못했습니다:", error);
        }
        window.location.href = "/";
    });
}

restoreTrackerState();
renderFavoriteList();

// A full browser reload first restores the visible session, then rechecks NEXON's latest public data.
// A cooldown avoids making another multi-request refresh on every accidental rapid reload.
let lastAutoRefresh = 0;
try {
    lastAutoRefresh = Number(sessionStorage.getItem(AUTO_REFRESH_KEY) || 0);
} catch (storageError) {
    // If browser storage is unavailable, still allow the explicit refresh button to work.
}
if (currentCharacter && Date.now() - lastAutoRefresh >= AUTO_REFRESH_COOLDOWN_MS) {
    refreshVisibleCharacter({ automatic: true });
} else if (currentCharacter && dataStatusNotice) {
    dataStatusNotice.textContent += " 최근 1분 이내에 조회한 결과라 자동 재조회는 생략했습니다. 최신 정보가 필요하면 '최신 정보 다시 조회'를 누르세요.";
}