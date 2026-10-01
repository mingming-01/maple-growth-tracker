const searchForm = document.getElementById("searchForm");
const characterNameInput = document.getElementById("characterName");
const loadingMessage = document.getElementById("loadingMessage");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");

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

let growthChart = null;
let currentCharacter = null;
let currentHistory = [];


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
        const experience = Number(item.experience);
        const gainValue = Number(item.experienceChange);
        const gain = Number.isFinite(gainValue) && gainValue > 0 ? gainValue : null;
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHTML(formatDate(item.date))}</td>
            <td>${escapeHTML(formatRanking(item.ranking))}</td>
            <td class="experience-cell">
                <span class="experience-value">${Number.isFinite(experience) ? escapeHTML(formatNumber(experience)) : "-"}</span>
                ${gain !== null ? `<span class="experience-gain">↑${escapeHTML(formatTrillion(gain))}</span>` : ""}
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
    return data.analysis;
}

function buildCumulativeExperienceData(history) {
    const sorted = sortHistoryAscending(history);
    let cumulativeExperience = null;
    return sorted.map((item, index) => {
        const currentExperience = Number(item.experience);
        if (!Number.isFinite(currentExperience)) return cumulativeExperience;
        if (cumulativeExperience === null) {
            cumulativeExperience = currentExperience / 1_000_000_000_000;
            return cumulativeExperience;
        }
        const previous = sorted[index - 1];
        const previousExperience = Number(previous?.experience);
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
    if (!sorted.length) return;
    if (growthChart) {
        growthChart.destroy();
        growthChart = null;
    }
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

async function searchCharacter(name) {
    const response = await fetch(`/api/character?name=${encodeURIComponent(name)}`);
    return readApiResponse(response, "캐릭터 정보를 불러오지 못했습니다.");
}

async function searchHistory(name) {
    const response = await fetch(`/api/history?name=${encodeURIComponent(name)}`);
    const data = await readApiResponse(response, "성장 기록을 불러오지 못했습니다.");
    return data.history || [];
}

async function runAIReport(name, character, history, sharedMetrics) {
    if (aiAnalysisLoading) aiAnalysisLoading.hidden = false;
    if (aiAnalysisError) aiAnalysisError.hidden = true;
    if (aiAnalysisResult) aiAnalysisResult.hidden = true;
    try {
        const metrics = sharedMetrics || calculateGrowthMetrics(character, history);
        const analysis = await searchAIAnalysis(name, metrics);
        renderAIAnalysis(analysis);
    } catch (error) {
        console.error("AI 분석 실패:", error);
        if (aiAnalysisLoading) aiAnalysisLoading.hidden = true;
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
    if (saveImageButton) saveImageButton.disabled = true;
    if (savePdfButton) savePdfButton.disabled = true;
    if (comparisonResult) comparisonResult.hidden = true;
    setLoading(true);
    try {
        const character = await searchCharacter(name);
        const history = await searchHistory(name);
        currentCharacter = character;
        currentHistory = history;
        const prediction = calculatePrediction(character, history);
        const metrics = calculateGrowthMetrics(character, history, prediction);
        renderCharacter(character, history);
        renderRanking(character);
        renderGrowthSummary(character, history);
        renderPrediction(character, history, prediction);
        renderHistory(history);
        renderChart(history);
        if (saveImageButton) saveImageButton.disabled = false;
        if (savePdfButton) savePdfButton.disabled = false;
        if (resultSection) resultSection.hidden = false;
        setLoading(false);
        await runAIReport(name, character, history, metrics);
    } catch (error) {
        console.error(error);
        showError(error.message || "조회 중 오류가 발생했습니다.");
    } finally {
        setLoading(false);
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
    if (comparisonLoading) comparisonLoading.hidden = false;
    if (comparisonButton) comparisonButton.disabled = true;
    try {
        const [otherCharacter, otherHistory] = await Promise.all([
            searchCharacter(name),
            searchHistory(name)
        ]);
        if (String(otherCharacter.characterName).toLocaleLowerCase() === String(currentCharacter.characterName).toLocaleLowerCase()) {
            throw new Error("같은 캐릭터는 비교할 수 없습니다.");
        }
        const primaryPrediction = calculatePrediction(currentCharacter, currentHistory);
        const otherPrediction = calculatePrediction(otherCharacter, otherHistory);
        const primaryMetrics = calculateGrowthMetrics(currentCharacter, currentHistory, primaryPrediction);
        const otherMetrics = calculateGrowthMetrics(otherCharacter, otherHistory, otherPrediction);
        renderComparisonCharacter("primary", currentCharacter, primaryMetrics);
        renderComparisonCharacter("secondary", otherCharacter, otherMetrics);
        const response = await fetch("/api/ai-comparison", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                primary: { character: currentCharacter, metrics: primaryMetrics, history: currentHistory },
                comparison: { character: otherCharacter, metrics: otherMetrics, history: otherHistory }
            })
        });
        const data = await readApiResponse(response, "AI 성장 비교 분석을 불러오지 못했습니다.");
        if (comparisonAIAnalysis) comparisonAIAnalysis.textContent = data.analysis || "분석 결과가 없습니다.";
        if (comparisonResult) comparisonResult.hidden = false;
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