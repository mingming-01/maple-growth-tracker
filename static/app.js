import { apiFetch, readApiResponse } from "./js/api.js";
import { initCharacterDetails } from "./js/character-details.js";
import {
    sortHistoryAscending,
    sortHistoryDescending,
    getDailyGrowth,
    calculateAverageGrowth,
    calculateWeeklyGrowth,
    getRankingChange,
    calculatePrediction,
    formatLocalISODate,
    calculateLevelProgress,
    calculateGrowthMetrics,
    calculateAdvancedGrowthInsights,
    buildGrowthTimeline
} from "./js/growth.js";

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
const bestCombatPower = document.getElementById("bestCombatPower");
const bestCombatPowerDate = document.getElementById("bestCombatPowerDate");
const rankingMovementValue = document.getElementById("rankingMovementValue");
const rankingMovementDetail = document.getElementById("rankingMovementDetail");

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
const aiAnalysisEvidence = document.getElementById("aiAnalysisEvidence");
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
const comparisonPeriodRangeSelect = document.getElementById("comparisonPeriodRangeSelect");
const comparisonPeriodNotice = document.getElementById("comparisonPeriodNotice");
const comparisonPeriodVerdict = document.getElementById("comparisonPeriodVerdict");
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

const characterDetails = initCharacterDetails({
    apiFetch,
    readApiResponse,
    onStatsLoaded: data => {
        if (!currentCharacter) return;
        currentCharacter.bestCombatPower = data.bestCombatPower ?? currentCharacter.bestCombatPower ?? null;
        currentCharacter.bestCombatPowerObservedAt = data.bestCombatPowerObservedAt ?? currentCharacter.bestCombatPowerObservedAt ?? null;
        currentCharacter.bestPresetCombination = data.bestPresetCombination ?? currentCharacter.bestPresetCombination ?? null;
        if (bestCombatPower) bestCombatPower.textContent = currentCharacter.bestCombatPower !== null
            ? formatNumber(currentCharacter.bestCombatPower) : "-";
        if (bestCombatPowerDate) {
            bestCombatPowerDate.textContent = currentCharacter.bestCombatPowerObservedAt
                ? "조회 기록 중 최고 · " + new Date(currentCharacter.bestCombatPowerObservedAt).toLocaleDateString("ko-KR")
                : "스탯 API 조회 기록이 쌓이면 표시합니다.";
        }
    }
});

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

function formatSignedTrillion(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "-";
    const number = Number(value);
    const sign = number > 0 ? "+" : number < 0 ? "−" : "";
    return `${sign}${formatTrillion(Math.abs(number))}`;
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
    const progressValue = character.experienceRate;
    const progressRate = progressValue === null || progressValue === undefined || progressValue === ""
        ? NaN
        : Number(String(progressValue).replace("%", ""));
    const progressTrack = document.getElementById("levelProgressTrack");
    const progressFill = document.getElementById("levelProgressFill");
    const progressRemaining = document.getElementById("levelProgressRemaining");
    const progressDaily = document.getElementById("levelProgressDaily");
    const hasProgress = Number.isFinite(progressRate) && progressRate >= 0 && progressRate <= 100;
    if (progressTrack) {
        progressTrack.setAttribute("aria-valuenow", hasProgress ? String(progressRate) : "0");
        progressTrack.setAttribute("aria-valuetext", hasProgress ? `${progressRate.toFixed(3)}%` : "경험치 진행률 자료 없음");
    }
    if (progressFill) progressFill.style.width = hasProgress ? `${progressRate}%` : "0%";
    if (progressRemaining) {
        progressRemaining.textContent = hasProgress ? `다음 레벨까지 ${Math.max(0, 100 - progressRate).toFixed(3)}%` : "진행률 자료 없음";
    }
    const levelProgress = calculateGrowthMetrics(character, history || []).levelProgress;
    if (progressDaily) {
        progressDaily.textContent = levelProgress?.dailyProgressRate !== null && levelProgress?.dailyProgressRate !== undefined
            ? `최근 관측 평균 +${levelProgress.dailyProgressRate.toFixed(4)}%p / 일`
            : "성장 기록이 쌓이면 일일 레벨 진척을 계산합니다.";
    }
    if (averageDailyExperience) {
        const average = history?.length ? calculateAverageGrowth(history) : null;
        averageDailyExperience.textContent = average !== null ? formatTrillion(average) : "-";
    }
    if (bestCombatPower) {
        bestCombatPower.textContent = character.bestCombatPower !== null && character.bestCombatPower !== undefined
            ? formatNumber(character.bestCombatPower) : "-";
    }
    if (bestCombatPowerDate) {
        if (character.bestCombatPowerObservedAt) {
            const date = new Date(character.bestCombatPowerObservedAt);
            bestCombatPowerDate.textContent = Number.isNaN(date.getTime())
                ? "사이트 조회 기록 중 최고"
                : "조회 기록 중 최고 · " + date.toLocaleDateString("ko-KR");
        } else {
            bestCombatPowerDate.textContent = "스탯 API 조회 기록이 쌓이면 표시합니다.";
        }
    }
    updateFavoriteCurrentButton();
}

function renderRanking(character, history = []) {
    if (overallRanking) overallRanking.textContent = formatRanking(character.ranking);
    if (worldRanking) worldRanking.textContent = formatRanking(character.worldRanking);
    if (jobWorldRanking) jobWorldRanking.textContent = formatRanking(character.jobWorldRanking);
    if (jobRanking) jobRanking.textContent = formatRanking(character.jobRanking);
    if (rankingMovementValue && rankingMovementDetail) {
        const movement = getRankingChange(history || []);
        const validRecords = (history || []).filter(item =>
            item.ranking !== null && item.ranking !== undefined && Number.isFinite(Number(item.ranking))
        );
        rankingMovementValue.classList.remove("is-up", "is-down");
        if (movement === null || validRecords.length < 2) {
            rankingMovementValue.textContent = "기록 부족";
            rankingMovementDetail.textContent = "랭킹 기록이 2개 이상 쌓이면 최근 변화를 표시합니다.";
        } else if (movement > 0) {
            rankingMovementValue.textContent = "▲ " + formatNumber(movement) + "계단 상승";
            rankingMovementValue.classList.add("is-up");
            rankingMovementDetail.textContent = "최근 두 개의 유효한 저장 기록을 비교했습니다.";
        } else if (movement < 0) {
            rankingMovementValue.textContent = "▼ " + formatNumber(Math.abs(movement)) + "계단 하락";
            rankingMovementValue.classList.add("is-down");
            rankingMovementDetail.textContent = "최근 두 개의 유효한 저장 기록을 비교했습니다.";
        } else {
            rankingMovementValue.textContent = "변동 없음";
            rankingMovementDetail.textContent = "최근 두 개의 저장 기록에서 순위 변동이 없었습니다.";
        }
    }
}

function renderGrowthSummary(character, history) {
    const dailyGrowth = getDailyGrowth(history);
    const weeklyGrowthValue = calculateWeeklyGrowth(history);
    const averageGrowthValue = calculateAverageGrowth(history);
    if (yesterdayGrowth) yesterdayGrowth.textContent = formatSignedTrillion(dailyGrowth);
    if (rankingChange) {
        const change = getRankingChange(history);
        rankingChange.textContent = change === null || change === 0 ? "-" : change > 0 ? `▲ ${change}` : `▼ ${Math.abs(change)}`;
    }
    if (weeklyGrowth) weeklyGrowth.textContent = formatSignedTrillion(weeklyGrowthValue);
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

// AI 리포트가 실제로 사용한 기록과 코드에서 계산한 분석 근거를 표시한다.
function renderAIAnalysisEvidence(history, metrics = null) {
    if (!aiAnalysisEvidence) return;

    const records = sortHistoryAscending(Array.isArray(history) ? history : []);
    aiAnalysisEvidence.replaceChildren();
    if (!records.length) {
        aiAnalysisEvidence.hidden = true;
        return;
    }

    const hasFiniteValue = value =>
        value !== null &&
        value !== undefined &&
        value !== "" &&
        Number.isFinite(Number(value));
    const isConfirmedRecord = item =>
        (!item.recordStatus || item.recordStatus === "available") &&
        hasFiniteValue(item.level) &&
        hasFiniteValue(item.experience);

    const confirmedRecords = records.filter(isConfirmedRecord);
    const confirmedChanges = records.filter(item =>
        isConfirmedRecord(item) && hasFiniteValue(item.experienceChange)
    );
    const latestConfirmed = confirmedRecords[confirmedRecords.length - 1] || null;
    const missingDays = records.length - confirmedRecords.length;
    const firstDate = records[0]?.date || null;
    const lastDate = records[records.length - 1]?.date || null;
    const rangeLabel = firstDate && lastDate
        ? firstDate === lastDate
            ? formatDate(firstDate)
            : `${formatDate(firstDate)} ~ ${formatDate(lastDate)}`
        : "날짜 정보 없음";
    const insights = metrics?.analysisInsights || null;
    const items = [
        ["분석 대상 기간", rangeLabel],
        ["확인된 성장 기록", `${confirmedRecords.length} / ${records.length}일`],
        ["변화량 확인 구간", `${confirmedChanges.length}개`],
        ["최근 정상 기록", latestConfirmed ? formatDate(latestConfirmed.date) : "확인 기록 없음"]
    ];

    if (insights?.dataQuality) {
        items.push(["기록 충실도", `${Number(insights.dataQuality.coveragePercent || 0).toFixed(0)}% · ${insights.dataQuality.level === "high" ? "높음" : insights.dataQuality.level === "medium" ? "보통" : "낮음"}`]);
    }

    const comparison = insights?.periodComparison;
    if (comparison?.status === "available") {
        let comparisonText = comparison.changePercent === null
            ? (comparison.direction === "increased" ? "직전 기간보다 증가" : comparison.direction === "decreased" ? "직전 기간보다 감소" : "직전 기간과 동일")
            : `${comparison.changePercent > 0 ? "+" : ""}${comparison.changePercent.toFixed(1)}%`;
        items.push(["직전 동일 기간 대비", comparisonText]);
    } else if (comparison?.status === "unavailable") {
        items.push(["직전 동일 기간 대비", "비교 기록 조회 실패"]);
    } else if (comparison?.status === "insufficient_data") {
        items.push(["직전 동일 기간 대비", "비교 표본 부족"]);
    }

    const trend = insights?.growthTrend;
    if (trend && trend.direction !== "insufficient_data") {
        const directionLabel = trend.direction === "increased" ? "후반부 성장 속도 상승"
            : trend.direction === "decreased" ? "후반부 성장 속도 하락" : "성장 속도 유지";
        const trendText = trend.changePercent === null
            ? directionLabel
            : `${directionLabel} · ${trend.changePercent > 0 ? "+" : ""}${trend.changePercent.toFixed(1)}%`;
        items.push(["기간 내 성장 추세", trendText]);
    }

    const weekdayWeekend = insights?.weekdayWeekend;
    if (weekdayWeekend?.sufficientSamples) {
        const weekdayAverage = weekdayWeekend.weekday.averageGrowth;
        const weekendAverage = weekdayWeekend.weekend.averageGrowth;
        const share = weekdayWeekend.weekendPositiveGrowthSharePercent;
        const pattern = weekdayAverage === null || weekendAverage === null
            ? "요일별 비교 자료 부족"
            : weekendAverage > weekdayAverage ? "주말 평균이 더 높음"
                : weekendAverage < weekdayAverage ? "평일 평균이 더 높음" : "평일·주말 평균이 비슷함";
        items.push(["요일별 성장 패턴", share === null ? pattern : `${pattern} · 주말 순증가 비중 ${share.toFixed(1)}%`]);
    } else if (weekdayWeekend) {
        items.push(["요일별 성장 패턴", "비교할 평일·주말 표본 부족"]);
    }

    const heading = document.createElement("strong");
    heading.className = "ai-analysis-evidence-heading";
    heading.textContent = "분석에 사용한 기록과 계산 근거";

    const grid = document.createElement("div");
    grid.className = "ai-analysis-evidence-grid";

    items.forEach(([labelText, valueText]) => {
        const item = document.createElement("div");
        item.className = "ai-analysis-evidence-item";

        const label = document.createElement("span");
        label.className = "ai-analysis-evidence-label";
        label.textContent = labelText;

        const value = document.createElement("strong");
        value.className = "ai-analysis-evidence-value";
        value.textContent = valueText;

        item.append(label, value);
        grid.appendChild(item);
    });

    const note = document.createElement("p");
    note.className = "ai-analysis-evidence-note";
    note.textContent = missingDays > 0
        ? `기록 미확인 ${missingDays}일은 임의로 채우지 않았으며, 확인된 날짜 사이의 변화만 분석 근거로 사용했습니다.`
        : "API에서 확인된 날짜별 기록만 분석 근거로 사용했습니다.";

    aiAnalysisEvidence.append(heading, grid, note);
    aiAnalysisEvidence.hidden = false;
}

// AI 성장 리포트
function renderAIAnalysis(analysis, history = currentHistory, metrics = null) {
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
    renderAIAnalysisEvidence(history, metrics);
    if (aiAnalysisLoading) aiAnalysisLoading.hidden = true;
    if (aiAnalysisError) aiAnalysisError.hidden = true;
    aiAnalysisResult.hidden = false;
}

async function searchAIAnalysis(name, metrics) {
    const response = await apiFetch(`/api/ai-analysis?name=${encodeURIComponent(name)}`, {
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
        version: 2,
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
    let cumulativeExperience = 0;
    return sorted.map(item => {
        const hasExperience = item.experience !== null && item.experience !== undefined &&
            Number.isFinite(Number(item.experience));
        const isAvailable = !item.recordStatus || item.recordStatus === "available";
        if (!hasExperience || !isAvailable) return null;

        const change = item.experienceChange === null || item.experienceChange === undefined
            ? NaN
            : Number(item.experienceChange);
        // 레벨업 경계와 누락 구간은 추정하지 않고, 확인된 날짜 간 변화만 누적한다.
        if (Number.isFinite(change) && item.levelUp !== true) {
            cumulativeExperience += change / 1_000_000_000_000;
        }
        return cumulativeExperience;
    });
}

function renderGrowthTimeline(history) {
    const list = document.getElementById("growthTimelineList");
    if (!list) return;
    list.replaceChildren();
    const events = buildGrowthTimeline(history, 8);
    if (!events.length) {
        const empty = document.createElement("li");
        empty.className = "growth-timeline-empty";
        empty.textContent = "기록이 쌓이면 레벨업과 주요 성장 기록이 여기에 표시됩니다.";
        list.appendChild(empty);
        return;
    }
    events.forEach(event => {
        const item = document.createElement("li");
        item.className = `growth-timeline-item is-${event.type}`;
        const marker = document.createElement("span");
        marker.className = "growth-timeline-marker";
        marker.setAttribute("aria-hidden", "true");
        const body = document.createElement("div");
        body.className = "growth-timeline-body";
        const date = document.createElement("time");
        date.className = "growth-timeline-date";
        date.textContent = formatDate(event.date);
        const title = document.createElement("strong");
        title.className = "growth-timeline-title";
        title.textContent = event.title;
        const description = document.createElement("p");
        description.className = "growth-timeline-description";
        description.textContent = event.description;
        body.append(date, title, description);
        item.append(marker, body);
        list.appendChild(item);
    });
}

function renderChart(history) {
    renderGrowthTimeline(history);
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
        if (item.recordStatus && item.recordStatus !== "available") return null;
        if (item.experienceChange === null || item.experienceChange === undefined) return null;
        const value = Number(item.experienceChange);
        return Number.isFinite(value) ? value / 1_000_000_000_000 : null;
    });
    const levelUpData = experienceData.map((value, index) => sorted[index]?.levelUp === true ? value : null);
    growthChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels,
            datasets: [
                { label: "관측 누적 증가량", data: experienceData, yAxisID: "experience", borderWidth: 3, tension: 0, pointRadius: 4, pointHoverRadius: 6, fill: false },
                { label: "일일 순증가량", data: dailyGrowthData, yAxisID: "dailyGrowth", borderWidth: 2, borderDash: [7, 6], tension: 0, pointRadius: 3, pointHoverRadius: 5, fill: false },
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
                            if (context.dataset.label === "관측 누적 증가량") return `관측 누적 증가량: ${value.toFixed(1)}조`;
                            if (context.dataset.label === "일일 순증가량") return `일일 순증가량: ${value.toFixed(1)}조`;
                            return "";
                        }
                    }
                }
            },
            scales: {
                experience: {
                    type: "linear", position: "left", beginAtZero: false,
                    title: { display: true, text: "관측 누적 증가량" },
                    ticks: { callback: value => `${Number(value).toFixed(0)}조` }
                },
                dailyGrowth: {
                    type: "linear", position: "right", beginAtZero: true,
                    title: { display: true, text: "일일 순증가량" },
                    grid: { drawOnChartArea: false },
                    ticks: { callback: value => `${Number(value).toFixed(0)}조` }
                }
            }
        }
    });
}


async function searchCharacter(name, forceRefresh = false) {
    const refreshParam = forceRefresh ? "&refresh=1" : "";
    const response = await apiFetch(
        `/api/character?name=${encodeURIComponent(name)}${refreshParam}`,
        forceRefresh ? { cache: "no-store" } : {}
    );
    return readApiResponse(response, "캐릭터 정보를 불러오지 못했습니다.");
}

async function searchHistory(name, forceRefresh = false) {
    const refreshParam = forceRefresh ? "&refresh=1" : "";
    const response = await apiFetch(
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
            `저장된 최근 ${days}일 기록입니다. 선택한 기간에서 API가 제공하는 날짜별 데이터만 추가로 수집합니다.`;
        return;
    }
    const collection = status.collection || {};
    const collectionText = collection.checkedDays
        ? ` · 이번 조회에서 ${collection.savedRecords}건 저장${collection.remainingDays ? ` · 기록 미완성 ${collection.remainingDays}일` : ""}`
        : "";
    historyRangeNotice.textContent =
        `최근 ${days}일 기록: 정상 ${status.availableDays}일 · API 미제공 ${status.notReadyDays}일 · 미수집 ${status.notCollectedDays}일${collectionText}. API가 제공하지 않는 날짜는 빈 기록으로 남습니다.`;
}

function shiftSnapshotDate(dateString, offsetDays) {
    const [year, month, day] = String(dateString || "").split("-").map(Number);
    if (!year || !month || !day) return null;
    const shifted = new Date(Date.UTC(year, month - 1, day + offsetDays));
    return shifted.toISOString().slice(0, 10);
}

async function fetchArchiveRange(days, endDate = null, ocid = currentCharacter?.ocid, options = {}) {
    const params = new URLSearchParams({
        ocid: ocid || "",
        days: String(days)
    });
    if (endDate) params.set("end", endDate);
    if (options.collect) {
        params.set("collect", "1");
        params.set("character_name", options.characterName || "");
        params.set("world_name", options.worldName || "");
        params.set("offset", String(options.offset || 0));
        params.set("limit", String(options.limit || 10));
    }

    const response = await apiFetch(`/api/history/archive?${params.toString()}`, {
        cache: "no-store"
    });
    return readApiResponse(response, "저장된 성장 기록을 불러오지 못했습니다.");
}

// 30일·90일을 선택한 경우에만 누락된 날짜를 10일씩 확인해 과거 기록을 보충한다.
async function collectArchiveRange(days, character, progressElement = null, label = "성장 기록") {
    const batchSize = 10;
    let result = null;
    const totals = {
        checkedDays: 0,
        savedRecords: 0,
        availableRecords: 0,
        noDataRecords: 0,
        remainingDays: 0
    };

    for (let offset = 0; offset < days; offset += batchSize) {
        const limit = Math.min(batchSize, days - offset);
        if (progressElement) {
            progressElement.textContent = `${label} 보충 중 · ${Math.min(offset + limit, days)}/${days}일 확인`;
        }

        result = await fetchArchiveRange(days, null, character.ocid, {
            collect: true,
            characterName: character.characterName,
            worldName: character.worldName,
            offset,
            limit
        });
        const batch = result.collection || {};
        totals.checkedDays += Number(batch.checkedDays || 0);
        totals.savedRecords += Number(batch.savedRecords || 0);
        totals.availableRecords += Number(batch.availableRecords || 0);
        totals.noDataRecords += Number(batch.noDataRecords || 0);
        totals.remainingDays = Number(batch.remainingDays || 0);
        if (totals.remainingDays === 0) break;
    }

    if (result) result.collectionSummary = totals;
    return result;
}

function summarizePeriod(history, days) {
    const records = sortHistoryAscending(Array.isArray(history) ? history : []);
    const available = records.filter(item =>
        (!item.recordStatus || item.recordStatus === "available") &&
        item.experience !== null &&
        item.experience !== undefined &&
        Number.isFinite(Number(item.experience))
    );
    const confirmedChanges = records
        .map(item => ({
            item,
            value: item.experienceChange === null || item.experienceChange === undefined
                ? null
                : Number(item.experienceChange)
        }))
        .filter(entry => (!entry.item.recordStatus || entry.item.recordStatus === "available") &&
            entry.value !== null && Number.isFinite(entry.value));
    const growth = confirmedChanges.length
        ? confirmedChanges.reduce((sum, item) => sum + item.value, 0)
        : null;
    const averageGrowth = growth !== null ? growth / confirmedChanges.length : null;
    const positiveChanges = confirmedChanges.filter(entry => entry.value > 0);
    const bestGrowth = positiveChanges.reduce((best, entry) =>
        !best || entry.value > best.value ? entry : best, null);

    const ranked = records.filter(item =>
        (!item.recordStatus || item.recordStatus === "available") &&
        item.ranking !== null &&
        item.ranking !== undefined &&
        Number.isFinite(Number(item.ranking))
    );
    const rankingChange = ranked.length >= 2
        ? Number(ranked[0].ranking) - Number(ranked[ranked.length - 1].ranking)
        : null;
    const levelUps = records.filter((item, index) => {
        const previousLevel = Number(records[index - 1]?.level);
        const currentLevel = Number(item.level);
        return item.levelUp === true ||
            (Number.isFinite(previousLevel) && Number.isFinite(currentLevel) && currentLevel > previousLevel);
    });

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
        bestDailyGrowth: bestGrowth?.value ?? null,
        bestDailyGrowthDate: bestGrowth?.item.date ?? null,
        growthDays: positiveChanges.length,
        zeroGrowthDays: confirmedChanges.filter(entry => entry.value === 0).length,
        negativeGrowthDays: confirmedChanges.filter(entry => entry.value < 0).length,
        levelUpCount: levelUps.length,
        levelUpDates: levelUps.map(item => item.date),
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
    summary.previousAverageGrowth = null;
    summary.previousGrowthSamples = 0;
    summary.comparisonPercent = null;

    if (previousData) {
        const previous = summarizePeriod(previousData.history, previousData.days);
        summary.previousGrowth = previous.growth;
        summary.previousAverageGrowth = previous.averageGrowth;
        summary.previousGrowthSamples = previous.confirmedChangeDays;
        // 기록 누락으로 관측일 수가 다를 수 있으므로 총합이 아닌 관측 구간 평균으로 비교한다.
        if (
            summary.averageGrowth !== null &&
            previous.averageGrowth !== null &&
            previous.averageGrowth !== 0 &&
            previous.confirmedChangeDays > 0
        ) {
            summary.comparisonPercent = (
                (summary.averageGrowth - previous.averageGrowth) / Math.abs(previous.averageGrowth)
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
            ? `연속 관측 ${summary.confirmedChangeDays}개 구간의 순증가량 합계`
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
            ? `변화 확인 ${summary.confirmedChangeDays}개 구간 기준`
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
        } else if (summary.previousAverageGrowth !== null && summary.previousGrowthSamples > 0) {
            periodComparisonDetail.textContent = `직전 관측 구간 평균 ${formatTrillion(summary.previousAverageGrowth)}`;
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

    const bestValue = document.getElementById("periodBestGrowthValue");
    const bestDetail = document.getElementById("periodBestGrowthDetail");
    const activeValue = document.getElementById("periodActiveDaysValue");
    const activeDetail = document.getElementById("periodActiveDaysDetail");
    const levelUpValue = document.getElementById("periodLevelUpsValue");
    const levelUpDetail = document.getElementById("periodLevelUpsDetail");
    if (bestValue) bestValue.textContent = summary.bestDailyGrowth === null ? "자료 부족" : formatTrillion(summary.bestDailyGrowth);
    if (bestDetail) bestDetail.textContent = summary.bestDailyGrowthDate
        ? `최고 성장일 · ${formatDate(summary.bestDailyGrowthDate)}`
        : "확인된 양수 성장 기록이 없습니다.";
    if (activeValue) activeValue.textContent = `${summary.growthDays}일`;
    if (activeDetail) activeDetail.textContent =
        `정체 ${summary.zeroGrowthDays}일 · 감소 ${summary.negativeGrowthDays}일`;
    if (levelUpValue) levelUpValue.textContent = `${summary.levelUpCount}회`;
    if (levelUpDetail) levelUpDetail.textContent = summary.levelUpDates.length
        ? summary.levelUpDates.map(formatDate).join(" · ")
        : "기간 내 레벨업 기록 없음";

    if (periodSummaryFootnote) {
        periodSummaryFootnote.textContent =
            "평균은 실제 변화량을 확인한 날짜 간 구간 기준입니다. 미수집 날짜는 0으로 간주하지 않으며, 레벨업 경계는 경험치 기준이 초기화되므로 증가량 합계에서 제외합니다.";
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

    const data = await collectArchiveRange(
        selectedDays,
        currentCharacter,
        historyRangeNotice,
        "과거 기록"
    );
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
        persistentStorage: data.persistentStorage === true,
        collection: data.collectionSummary || null
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
        const reportMetrics = calculateGrowthMetrics(currentCharacter, currentDisplayHistory);
        await runAIReport(
            currentCharacter.characterName,
            currentCharacter,
            currentDisplayHistory,
            reportMetrics,
            currentPeriodSummary
        );
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

    // 데이터 조회 시각과 상태를 세션에 저장해 새로고침 후에도 안내를 복원한다.
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

async function runAIReport(name, character, history, sharedMetrics, periodSummary = null) {
    if (aiAnalysisLoading) aiAnalysisLoading.hidden = false;
    if (aiAnalysisError) aiAnalysisError.hidden = true;
    if (aiAnalysisResult) aiAnalysisResult.hidden = true;
    showAICacheNotice(aiAnalysisCacheNotice, "동일 데이터의 저장된 분석을 확인하고 있습니다.");

    try {
        const baseMetrics = sharedMetrics || calculateGrowthMetrics(character, history);
        const metrics = {
            ...baseMetrics,
            analysisInsights: calculateAdvancedGrowthInsights(history, periodSummary)
        };
        const signature = buildGrowthReportSignature(name, character, history, metrics);
        const cachedAnalysis = getCachedAIAnalysis("growth-report-v2", signature);
        if (cachedAnalysis) {
            renderAIAnalysis(cachedAnalysis, history, metrics);
            showAICacheNotice(aiAnalysisCacheNotice, "저장된 분석을 재사용했습니다. AI 모델을 다시 호출하지 않았습니다.");
            saveTrackerState({ character, history, metrics, aiAnalysis: cachedAnalysis });
            return;
        }

        const result = await searchAIAnalysis(name, metrics);
        const analysis = result.analysis;
        saveCachedAIAnalysis("growth-report-v2", signature, analysis);
        renderAIAnalysis(analysis, history, metrics);

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
            // 성장 기록 조회만 실패하면 캐릭터 기본 정보는 계속 표시한다.
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
        characterDetails.setCharacter(character.ocid || "");
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
        renderRanking(character, history);
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
        characterDetails.setCharacter(character.ocid || "");
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

        // 기준 캐릭터 정보가 갱신되면 기존 비교 결과는 오래된 데이터일 수 있어 다시 비교하기 전까지 숨긴다.
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

        // AI 리포트 생성 중에도 갱신된 캐릭터 화면을 먼저 표시한다.
        runAIReport(
            name,
            character,
            currentDisplayHistory,
            calculateGrowthMetrics(character, currentDisplayHistory),
            currentPeriodSummary
        );
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

function formatLevelPace(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "자료 부족";
    return `+${Number(value).toFixed(4)}%p / 일`;
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

function renderComparisonPeriod(summary, primaryCharacter, otherCharacter, errorMessage = "") {
    if (!comparisonPeriodVerdict || !comparisonPeriodNotice) return;
    const primaryName = primaryCharacter?.characterName || "현재 캐릭터";
    const otherName = otherCharacter?.characterName || "비교 캐릭터";
    const days = Number(summary?.days || comparisonPeriodRangeSelect?.value || 30);
    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    };

    setText("comparisonPeriodPrimaryName", primaryName);
    setText("comparisonPeriodSecondaryName", otherName);

    const renderSubject = (prefix, subject) => {
        const growth = subject?.growth;
        const average = subject?.averageGrowth;
        setText(`comparisonPeriod${prefix}Growth`, growth === null || growth === undefined ? "자료 부족" : formatTrillion(growth));
        setText(`comparisonPeriod${prefix}Average`, average === null || average === undefined ? "자료 부족" : formatTrillion(average));
        setText(`comparisonPeriod${prefix}Ranking`, subject ? formatRankingChange(subject.rankingChange) : "자료 부족");
        setText(
            `comparisonPeriod${prefix}Coverage`,
            subject ? `${subject.availableDays} / ${subject.days}일 (${subject.coveragePercent.toFixed(0)}%)` : "-"
        );
        setText(
            `comparisonPeriod${prefix}Detail`,
            subject ? `변화 확인 ${subject.confirmedChangeDays}개 구간 · API 미제공 ${subject.notReadyDays}일 · 미수집 ${subject.notCollectedDays}일` : ""
        );
        setText(
            `comparisonPeriod${prefix}LevelPace`,
            subject?.levelProgress ? formatLevelPace(subject.levelProgress.dailyProgressRate) : "자료 부족"
        );
    };

    renderSubject("Primary", summary?.primary || null);
    renderSubject("Secondary", summary?.secondary || null);

    if (summary?.primary && summary?.secondary) {
        const firstPace = summary.primary.levelProgress?.dailyProgressRate;
        const secondPace = summary.secondary.levelProgress?.dailyProgressRate;
        const firstAverage = summary.primary.averageGrowth;
        const secondAverage = summary.secondary.averageGrowth;

        if (Number.isFinite(firstPace) && Number.isFinite(secondPace)) {
            const difference = firstPace - secondPace;
            if (Math.abs(difference) < 0.00005) {
                comparisonPeriodVerdict.textContent = "현재 레벨 기준 일일 진척률은 두 캐릭터가 비슷합니다.";
            } else if (difference > 0) {
                comparisonPeriodVerdict.textContent =
                    `${primaryName}의 현재 레벨 기준 일일 진척률이 ${otherName}보다 ${difference.toFixed(4)}%p 높습니다.`;
            } else {
                comparisonPeriodVerdict.textContent =
                    `${otherName}의 현재 레벨 기준 일일 진척률이 ${primaryName}보다 ${Math.abs(difference).toFixed(4)}%p 높습니다.`;
            }
        } else if (Number.isFinite(firstAverage) && Number.isFinite(secondAverage)) {
            const difference = firstAverage - secondAverage;
            if (difference > 0) {
                comparisonPeriodVerdict.textContent =
                    `${primaryName}의 관측 일 평균 경험치가 ${otherName}보다 ${formatTrillion(difference)} 많습니다. (레벨 보정 진척률 자료 부족)`;
            } else if (difference < 0) {
                comparisonPeriodVerdict.textContent =
                    `${otherName}의 관측 일 평균 경험치가 ${primaryName}보다 ${formatTrillion(Math.abs(difference))} 많습니다. (레벨 보정 진척률 자료 부족)`;
            } else {
                comparisonPeriodVerdict.textContent = "두 캐릭터의 관측 일 평균 경험치가 같습니다. (레벨 보정 진척률 자료 부족)";
            }
        } else {
            comparisonPeriodVerdict.textContent = "확인된 성장 기록이 부족해 성장 속도를 비교하기 어렵습니다.";
        }
        comparisonPeriodNotice.textContent = `최근 ${days}일의 동일한 날짜 범위입니다. 진척률은 각 캐릭터의 현재 레벨 진행률을 이용한 근사치이며, 누락 날짜와 레벨업 전환 구간은 추정하지 않습니다.`;
    } else {
        comparisonPeriodVerdict.textContent = errorMessage || "기간별 비교 자료를 아직 불러오지 못했습니다.";
        comparisonPeriodNotice.textContent = "캐릭터별 저장 기록이 있어야 장기 성장량과 랭킹 변화를 비교할 수 있습니다.";
    }
    comparisonPeriodNotice.classList.toggle("is-warning", !!errorMessage);
}

async function fetchComparisonPeriodSummary(otherCharacter, days) {
    if (!currentCharacter?.ocid || !otherCharacter?.ocid) {
        throw new Error("캐릭터 식별 정보를 확인할 수 없어 장기 기록을 비교할 수 없습니다.");
    }
    const primaryData = await collectArchiveRange(
        days, currentCharacter, comparisonPeriodNotice, "기준 캐릭터 기록"
    );
    const secondaryData = await collectArchiveRange(
        days, otherCharacter, comparisonPeriodNotice, "비교 캐릭터 기록"
    );
    const primary = summarizePeriod(primaryData.history, days);
    const secondary = summarizePeriod(secondaryData.history, days);
    primary.levelProgress = calculateLevelProgress(currentCharacter, primary.averageGrowth);
    secondary.levelProgress = calculateLevelProgress(otherCharacter, secondary.averageGrowth);
    return { days, primary, secondary };
}

async function handleComparisonPeriodChange() {
    const savedComparison = getTrackerState()?.comparison;
    if (!currentCharacter || !savedComparison?.character) return;
    const days = [30, 90].includes(Number(comparisonPeriodRangeSelect?.value))
        ? Number(comparisonPeriodRangeSelect.value)
        : 30;
    if (comparisonPeriodRangeSelect) comparisonPeriodRangeSelect.disabled = true;
    if (comparisonPeriodNotice) {
        comparisonPeriodNotice.textContent = `최근 ${days}일 저장 기록을 불러오는 중입니다...`;
        comparisonPeriodNotice.classList.remove("is-warning");
    }

    let periodSummary = null;
    let periodError = "";
    try {
        periodSummary = await fetchComparisonPeriodSummary(savedComparison.character, days);
        renderComparisonPeriod(periodSummary, currentCharacter, savedComparison.character);
    } catch (error) {
        periodError = error.message || "기간별 비교 기록을 불러오지 못했습니다.";
        renderComparisonPeriod(null, currentCharacter, savedComparison.character, periodError);
    } finally {
        if (comparisonPeriodRangeSelect) comparisonPeriodRangeSelect.disabled = false;
    }

    saveTrackerState({
        comparison: {
            ...savedComparison,
            periodDays: days,
            periodSummary,
            periodError
        }
    });
}

function renderComparisonCharacter(prefix, character, metrics) {
    const values = {
        Name: character.characterName || "-",
        Level: character.level !== null && character.level !== undefined ? `Lv. ${formatNumber(character.level)}` : "-",
        ExpRate: formatPercent(character.experienceRate),
        Daily: formatSignedTrillion(metrics.latestDailyGrowth),
        Average: formatTrillion(metrics.averageDailyGrowth),
        LevelPace: formatLevelPace(metrics.levelProgress?.dailyProgressRate),
        Weekly: formatSignedTrillion(metrics.sevenDayGrowth),
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

        const periodDays = [30, 90].includes(Number(comparisonPeriodRangeSelect?.value))
            ? Number(comparisonPeriodRangeSelect.value)
            : 30;
        let periodSummary = null;
        let periodError = "";
        try {
            periodSummary = await fetchComparisonPeriodSummary(otherCharacter, periodDays);
            renderComparisonPeriod(periodSummary, currentCharacter, otherCharacter);
        } catch (error) {
            periodError = error.message || "기간별 비교 기록을 불러오지 못했습니다.";
            renderComparisonPeriod(null, currentCharacter, otherCharacter, periodError);
        }

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
            const response = await apiFetch("/api/ai-comparison", {
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
                aiAnalysis: comparisonAnalysis,
                periodDays,
                periodSummary,
                periodError
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
    characterDetails.setCharacter(currentCharacter.ocid || "");
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
    renderRanking(currentCharacter, currentHistory);
    renderGrowthSummary(currentCharacter, currentHistory);
    renderPrediction(currentCharacter, currentHistory, prediction);
    renderHistory(currentDisplayHistory);
    renderChart(currentDisplayHistory);

    if (saveImageButton) saveImageButton.disabled = false;
    if (savePdfButton) savePdfButton.disabled = false;
    if (resultSection) resultSection.hidden = false;
    syncHomeView();

    if (state.aiAnalysis) {
        renderAIAnalysis(state.aiAnalysis, state.displayHistory || state.history || currentHistory, state.metrics || null);
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

        if (comparisonPeriodRangeSelect) {
            comparisonPeriodRangeSelect.value = String(
                [30, 90].includes(Number(comparison.periodDays)) ? Number(comparison.periodDays) : 30
            );
        }
        renderComparisonPeriod(
            comparison.periodSummary || null,
            currentCharacter,
            comparison.character,
            comparison.periodError || "저장된 기간 비교 결과가 없습니다. 비교 기간을 선택해 다시 조회해주세요."
        );

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
if (comparisonPeriodRangeSelect) comparisonPeriodRangeSelect.addEventListener("change", handleComparisonPeriodChange);
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

// 브라우저 새로고침 시 저장된 화면을 먼저 복원한 다음 넥슨의 최신 공개 데이터를 다시 조회한다.
// 짧은 시간 안에 반복 새로고침해도 외부 API 요청이 급증하지 않도록 대기 시간을 둔다.
let lastAutoRefresh = 0;
try {
    lastAutoRefresh = Number(sessionStorage.getItem(AUTO_REFRESH_KEY) || 0);
} catch (storageError) {
    // 브라우저 저장소를 사용할 수 없어도 사용자가 직접 누르는 갱신 버튼은 동작하게 한다.
}
if (currentCharacter && Date.now() - lastAutoRefresh >= AUTO_REFRESH_COOLDOWN_MS) {
    refreshVisibleCharacter({ automatic: true });
} else if (currentCharacter && dataStatusNotice) {
    dataStatusNotice.textContent += " 최근 1분 이내에 조회한 결과라 자동 재조회는 생략했습니다. 최신 정보가 필요하면 '최신 정보 다시 조회'를 누르세요.";
}