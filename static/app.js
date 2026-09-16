const searchForm = document.getElementById("searchForm");
const characterNameInput = document.getElementById("characterName");

const loadingMessage = document.getElementById("loadingMessage");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");

const characterName = document.getElementById("characterNameResult");
const characterImage = document.getElementById("characterImage");
const worldName = document.getElementById("worldName");
const worldLogo = document.getElementById("worldLogo");

const worldLogoMap = {
    "스카니아": "https://i.namu.wiki/i/KKOTR7Xte076Bgv4D6ChPKJI9D0QYpkkGgQRjUH4FLbixDtgtajTVI9oj0iOCYBwlnIitGrOnxL3CEpgHF7w7g.webp",
    "베라": "https://i.namu.wiki/i/yhIxuR6TStGsDOHeqNG4hNifTqjhDuwVyxVSPlhHg6INLYDHdLhW200ZHtPFHkY4-Up48FcURhPsJ6EY1VNM3A.webp",
    "루나": "https://i.namu.wiki/i/Uv7_9oLPDZDn4fBo9AdO-RqRretxvddokQIWO8oA583EoGt3D6FHYJ21Cr1uX2UcWLH3iOlGFW93Z3g1_jU9sw.png",
    "제니스": "https://i.namu.wiki/i/Nq_asxVWbBmP8Qno-vB7LdYCntBN-KyjJhcRepzL-j0BBKqHjevwkhTg90WE62TTPsLKUgV0YdxU-JXAM1Hz-w.png",
    "크로아": "https://i.namu.wiki/i/u62he1IN4_j6V29XuFLB9-YWmjh1p0hmJdPtbQ2FcchxJ-9Ctbx35MKSwxz0gYnaJAL_a8VcyVMKmqq5XkE0wQ.png",
    "유니온": "https://i.namu.wiki/i/cisP4awkxibHV6_0psLUxymYzTpTQj4WxS3y1XEIAaeNQMLLtZ1DVRphtui3MAwTk_VpvJg4WFhL7OEfoKdXhQ.png",
    "엘리시움": "https://i.namu.wiki/i/4Yf3L1PhNAqV579g7f2PH6RmWqVpWLhbXEenCO9E46AGROBX5DaHoikx8nC19_PFvv0Op_Px2069aabBgt2uSA.png",
    "이노시스": "https://i.namu.wiki/i/c0qakY1T6luY7OXY4dKaxTLyPK82FolLcnEeeVlHuK09H8wMAQeK8TKoLz4Aa6n1H2pyrB4um1eQ7JIOQy1xSQ.png",
    "레드": "https://i.namu.wiki/i/w6QZITsJVpNJJ-7PTbaDFJBtO2290DH1Wbmu-acB1XQNsqQHKqJpwNti8NHPpzxHVcEA7xShFVnb74wa_cwFFw.png",
    "오로라": "https://i.namu.wiki/i/WpS4HdlV7Zf-WkS3QHUB7dHaHCn3WK75xFoDYw_u2V5vRoC-wLpSTAENYJU4uBpus40t7wcfCHiE1MgfUeq79Q.webp",
    "아케인": "https://i.namu.wiki/i/Iy2id1ikp3Tt2RDJD5Rdnur6TXdQNNx1CTfUSTxMW1roFcXxHBr1kqJsxUfzZ_TVqH7r57ainNf0SC8VHUQFqQ.png",
    "노바": "https://i.namu.wiki/i/byw8B6SN8meTLgQ5B0sb6dVTBvAT0NhEl3dPNdFawXf9lC9ZD1gTckcBHt-wyeV3mSxuePYDcKcxP9I5mOnv0Q.png"
};

const jobName = document.getElementById("jobName");
const levelValue = document.getElementById("levelValue");
const experienceRate = document.getElementById("experienceRate");
const guildName = document.getElementById("guildName");
const averageDailyExperience = document.getElementById(
    "averageDailyExperience"
);

const overallRanking = document.getElementById("overallRanking");
const worldRanking = document.getElementById("worldRanking");
const jobWorldRanking = document.getElementById("jobWorldRanking");
const jobRanking = document.getElementById("jobRanking");

const yesterdayGrowth = document.getElementById("yesterdayGrowth");
const rankingChange = document.getElementById("rankingChange");
const weeklyGrowth = document.getElementById("weeklyGrowth");
const averageGrowth = document.getElementById("averageGrowth");

const predictionRequired = document.getElementById("predictionRequired");
const predictionDays = document.getElementById("predictionDays");
const predictionDate = document.getElementById("predictionDate");
const predictionAverage = document.getElementById("predictionAverage");

const historyBody = document.getElementById("historyBody");

const aiAnalysisCard =
    document.getElementById("aiAnalysisCard");

const aiAnalysisLoading =
    document.getElementById("aiAnalysisLoading");

const aiAnalysisError =
    document.getElementById("aiAnalysisError");

const aiAnalysisResult =
    document.getElementById("aiAnalysisResult");

const aiGrowthPattern =
    document.getElementById("aiGrowthPattern");

const aiGrowthAnalysis =
    document.getElementById("aiGrowthAnalysis");

const aiLevelUp =
    document.getElementById("aiLevelUp");

const aiJudgement =
    document.getElementById("aiJudgement");

const saveImageButton =
    document.getElementById("saveImageButton");

const savePdfButton =
    document.getElementById("savePdfButton");

let growthChart = null;


/* =========================
   공통 함수
========================= */

function formatNumber(value) {
    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "-";
    }

    return Number(value).toLocaleString("ko-KR");
}


function formatRanking(value) {
    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "-";
    }

    return `${formatNumber(value)}위`;
}


function formatTrillion(value) {
    if (
        value === null ||
        value === undefined ||
        Number.isNaN(Number(value))
    ) {
        return "-";
    }

    const trillion =
        Number(value) / 1_000_000_000_000;

    if (Math.abs(trillion) >= 100) {
        return `${trillion.toFixed(0)}조`;
    }

    if (Math.abs(trillion) >= 10) {
        return `${trillion.toFixed(1)}조`;
    }

    return `${trillion.toFixed(2)}조`;
}


function formatPercent(value) {
    if (
        value === null ||
        value === undefined ||
        Number.isNaN(Number(value))
    ) {
        return "-";
    }

    return `${Number(value).toFixed(3)}%`;
}


function formatDate(dateString) {
    if (!dateString) {
        return "-";
    }

    const parts =
        String(dateString).split("-");

    if (parts.length !== 3) {
        return dateString;
    }

    return `${parts[0]}.${parts[1]}.${parts[2]}`;
}


function formatShortDate(dateString) {
    if (!dateString) {
        return "-";
    }

    const parts =
        String(dateString).split("-");

    if (parts.length !== 3) {
        return dateString;
    }

    return `${parts[1]}/${parts[2]}`;
}


function escapeHTML(value) {
    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function setLoading(isLoading) {
    if (loadingMessage) {
        loadingMessage.hidden = !isLoading;
    }

    if (searchForm) {
        const button =
            searchForm.querySelector(
                ".search-button"
            );

        if (button) {
            button.disabled = isLoading;

            button.textContent =
                isLoading
                    ? "조회 중..."
                    : "조회하기 →";
        }
    }
}


function showError(message) {
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.hidden = false;
    }
}


function hideError() {
    if (errorMessage) {
        errorMessage.hidden = true;
        errorMessage.textContent = "";
    }
}


function showResult() {
    if (resultSection) {
        resultSection.hidden = false;
    }
}


/* =========================
   날짜 / 정렬
========================= */

function sortHistoryAscending(history) {
    return [...(history || [])].sort(
        (a, b) =>
            String(a.date).localeCompare(
                String(b.date)
            )
    );
}


function sortHistoryDescending(history) {
    return [...(history || [])].sort(
        (a, b) =>
            String(b.date).localeCompare(
                String(a.date)
            )
    );
}


/* =========================
   성장값 계산
========================= */

function getDailyGrowth(history) {
    if (!history || history.length < 2) {
        return null;
    }

    const sorted =
        sortHistoryAscending(history);

    const latest =
        sorted[sorted.length - 1];

    if (!latest) {
        return null;
    }

    /*
       레벨업 당일은 기존 레벨과
       경험치 기준이 달라지므로
       일일 상승량으로 사용하지 않는다.
    */
    if (latest.levelUp === true) {
        return null;
    }

    const growth =
        Number(latest.experienceChange);

    return Number.isFinite(growth) && growth > 0
        ? growth
        : null;
}


function calculateAverageGrowth(history) {
    if (!history || history.length < 2) {
        return null;
    }

    /*
       정상적으로 계산 가능한 양수 경험치 증가량만 사용한다.

       중요한 점:
       값이 매일 똑같아도 정상적인 성장 데이터이므로
       그대로 평균에 포함한다.
    */
    const gains =
        history
            .map(item =>
                Number(item.experienceChange)
            )
            .filter(
                value =>
                    Number.isFinite(value) &&
                    value > 0
            );

    if (!gains.length) {
        return null;
    }

    const total =
        gains.reduce(
            (sum, value) =>
                sum + value,
            0
        );

    return total / gains.length;
}


function calculateWeeklyGrowth(history) {
    if (!history || !history.length) {
        return null;
    }

    const gains =
        history
            .map(item =>
                Number(item.experienceChange)
            )
            .filter(
                value =>
                    Number.isFinite(value) &&
                    value > 0
            );

    if (!gains.length) {
        return null;
    }

    return gains.reduce(
        (sum, value) =>
            sum + value,
        0
    );
}


/* =========================
   성장 예측
========================= */

function calculatePrediction(character, history) {
    if (!character || !history?.length) {
        return null;
    }

    const currentExp =
        Number(character.experience);

    const currentLevel =
        Number(character.level);

    const currentRate =
        Number(
            String(character.experienceRate || "")
                .replace("%", "")
        );

    const averageGrowth =
        calculateAverageGrowth(history);

    if (
        !Number.isFinite(currentExp) ||
        !Number.isFinite(currentLevel) ||
        averageGrowth === null ||
        averageGrowth <= 0
    ) {
        return null;
    }

    /*
       현재 경험치 진행률이 정상적인 경우
       다음 레벨까지 필요한 경험치를 계산한다.
    */
    if (
        Number.isFinite(currentRate) &&
        currentRate > 0 &&
        currentRate < 100
    ) {
        const estimatedTotalExp =
            currentExp /
            (currentRate / 100);

        const requiredExp =
            estimatedTotalExp -
            currentExp;

        const days =
            requiredExp /
            averageGrowth;

        const targetDate =
            new Date();

        targetDate.setDate(
            targetDate.getDate() +
            Math.ceil(days)
        );

        return {
            currentLevel,
            nextLevel:
                currentLevel + 1,
            currentRate,
            averageGrowth,
            requiredExp,
            days,
            date: targetDate
        };
    }

    /*
       레벨업 직후 0.000%인 경우
       정확한 필요 경험치는 현재 API 데이터만으로
       계산할 수 없으므로 평균 성장량만 유지한다.
    */
    return {
        currentLevel,
        nextLevel:
            currentLevel + 1,
        currentRate,
        averageGrowth,
        requiredExp: null,
        days: null,
        date: null
    };
}

function renderPrediction(character, history) {
    const prediction =
        calculatePrediction(
            character,
            history
        );

    if (!prediction) {
        if (predictionRequired) {
            predictionRequired.textContent =
                "-";
        }

        if (predictionDays) {
            predictionDays.textContent =
                "-";
        }

        if (predictionDate) {
            predictionDate.textContent =
                "-";
        }

        if (predictionAverage) {
            predictionAverage.textContent =
                "-";
        }

        return;
    }

    /*
       다음 레벨까지 필요한 경험치
    */
    if (predictionRequired) {
        predictionRequired.innerHTML =
            prediction.requiredExp !== null
                ? `
                    ${formatTrillion(
                        prediction.requiredExp
                    )}
                    <span class="prediction-percent">
                        (${formatPercent(
                            prediction.currentRate
                        )})
                    </span>
                  `
                : "-";
    }

    /*
       예상 소요
    */
    if (predictionDays) {
        if (
            prediction.days !== null &&
            Number.isFinite(
                prediction.days
            )
        ) {
            predictionDays.textContent =
                `약 ${prediction.days.toFixed(1)}일 후`;
        } else {
            predictionDays.textContent =
                "-";
        }
    }

    /*
       예상 레벨업 날짜
    */
    if (predictionDate) {
        if (prediction.date) {
            const month =
                String(
                    prediction.date.getMonth() + 1
                ).padStart(2, "0");

            const day =
                String(
                    prediction.date.getDate()
                ).padStart(2, "0");

            predictionDate.textContent =
                `${month}/${day}`;
        } else {
            predictionDate.textContent =
                "-";
        }
    }

    /*
       일 평균 성장량
    */
    if (predictionAverage) {
        if (
            prediction.averageGrowth !== null &&
            prediction.averageGrowth > 0
        ) {
            predictionAverage.textContent =
                formatTrillion(
                    prediction.averageGrowth
                );
        } else {
            predictionAverage.textContent =
                "-";
        }
    }
}


/* =========================
   캐릭터 정보
========================= */

function renderCharacter(character, history) {
    if (characterName) {
        characterName.textContent =
            character.characterName || "-";
    }

    if (characterImage) {
        if (character.character_image) {
            characterImage.src =
                character.character_image;

            characterImage.hidden = false;
        } else {
            characterImage.removeAttribute("src");
            characterImage.hidden = true;
        }
    }

    if (worldName) {
        worldName.textContent =
            character.worldName || "-";
    }

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

    if (jobName) {
        jobName.textContent =
            character.job || "-";
    }

    if (guildName) {
        guildName.textContent =
            character.guildName || "길드 없음";
    }

    if (levelValue) {
        levelValue.textContent =
            character.level !== undefined &&
            character.level !== null
                ? formatNumber(character.level)
                : "-";
    }

    if (experienceRate) {
        experienceRate.textContent =
            formatPercent(
                character.experienceRate
            );
    }

    if (averageDailyExperience) {
        const average =
            history?.length
                ? calculateAverageGrowth(history)
                : null;

        averageDailyExperience.textContent =
            average !== null
                ? formatTrillion(average)
                : "-";
    }
}


/* =========================
   랭킹
========================= */

function renderRanking(character) {
    if (overallRanking) {
        overallRanking.textContent =
            formatRanking(
                character.ranking
            );
    }

    if (worldRanking) {
        worldRanking.textContent =
            formatRanking(
                character.worldRanking
            );
    }

    if (jobWorldRanking) {
        jobWorldRanking.textContent =
            formatRanking(
                character.jobWorldRanking
            );
    }

    if (jobRanking) {
        jobRanking.textContent =
            formatRanking(
                character.jobRanking
            );
    }
}


/* =========================
   성장 요약
========================= */

function renderGrowthSummary(
    character,
    history
) {
    const dailyGrowth =
        getDailyGrowth(history);

    const weeklyGrowthValue =
        calculateWeeklyGrowth(history);

    const averageGrowthValue =
        calculateAverageGrowth(history);


    /*
       어제 대비 획득량
    */
    if (yesterdayGrowth) {
        yesterdayGrowth.textContent =
            dailyGrowth !== null
                ? `+${formatTrillion(
                    dailyGrowth
                )}`
                : "-";
    }


    /*
       랭킹 변화
    */
    if (rankingChange) {
        const sorted =
            sortHistoryAscending(history);

        if (sorted.length >= 2) {
            const latest =
                sorted[sorted.length - 1];

            const previous =
                sorted[sorted.length - 2];

            const previousRanking =
                Number(previous.ranking);

            const latestRanking =
                Number(latest.ranking);

            if (
                Number.isFinite(
                    previousRanking
                ) &&
                Number.isFinite(
                    latestRanking
                )
            ) {
                const change =
                    previousRanking -
                    latestRanking;

                if (change > 0) {
                    rankingChange.textContent =
                        `▲ ${change}`;
                } else if (change < 0) {
                    rankingChange.textContent =
                        `▼ ${Math.abs(change)}`;
                } else {
                    rankingChange.textContent =
                        "-";
                }
            } else {
                rankingChange.textContent =
                    "-";
            }
        } else {
            rankingChange.textContent =
                "-";
        }
    }


    /*
       최근 7일 성장
    */
    if (weeklyGrowth) {
        weeklyGrowth.textContent =
            weeklyGrowthValue !== null
                ? `+${formatTrillion(
                    weeklyGrowthValue
                )}`
                : "-";
    }


    /*
       일 평균 획득량
    */
    if (averageGrowth) {
        averageGrowth.textContent =
            averageGrowthValue !== null
                ? formatTrillion(
                    averageGrowthValue
                )
                : "-";
    }
}


/* =========================
   성장 기록
========================= */

function renderHistory(history) {
    if (!historyBody) {
        return;
    }

    historyBody.innerHTML = "";

    const sorted =
        sortHistoryDescending(history);

    sorted.forEach(item => {
        const experience =
            Number(item.experience);

        const gainValue =
            Number(item.experienceChange);

        const gain =
            Number.isFinite(gainValue) &&
            gainValue > 0
                ? gainValue
                : null;

        const row =
            document.createElement("tr");

        row.innerHTML = `
            <td>
                ${escapeHTML(
                    formatDate(item.date)
                )}
            </td>

            <td>
                ${escapeHTML(
                    formatRanking(item.ranking)
                )}
            </td>

            <td class="experience-cell">
                <span class="experience-value">
                    ${
                        Number.isFinite(
                            experience
                        )
                            ? escapeHTML(
                                formatNumber(
                                    experience
                                )
                            )
                            : "-"
                    }
                </span>

                ${
                    gain !== null
                        ? `
                            <span class="experience-gain">
                                ↑${escapeHTML(
                                    formatTrillion(
                                        gain
                                    )
                                )}
                            </span>
                          `
                        : ""
                }
            </td>
        `;

        historyBody.appendChild(row);
    });
}

function renderAIAnalysis(analysis) {

    if (!aiAnalysisResult) {
        return;
    }

    const sections = {
        growthPattern: "",
        growthAnalysis: "",
        levelUp: "",
        judgement: ""
    };

    const patternMatch =
        analysis.match(
            /\[성장 패턴\]\s*([\s\S]*?)(?=\[성장 분석\]|$)/
        );

    const analysisMatch =
        analysis.match(
            /\[성장 분석\]\s*([\s\S]*?)(?=\[레벨업\]|$)/
        );

    const levelUpMatch =
        analysis.match(
            /\[레벨업\]\s*([\s\S]*?)(?=\[AI 판단\]|$)/
        );

    const judgementMatch =
        analysis.match(
            /\[AI 판단\]\s*([\s\S]*)/
        );


    if (patternMatch) {
        sections.growthPattern =
            patternMatch[1].trim();
    }

    if (analysisMatch) {
        sections.growthAnalysis =
            analysisMatch[1].trim();
    }

    if (levelUpMatch) {
        sections.levelUp =
            levelUpMatch[1].trim();
    }

    if (judgementMatch) {
        sections.judgement =
            judgementMatch[1].trim();
    }


    if (aiGrowthPattern) {
        aiGrowthPattern.textContent =
            sections.growthPattern || "-";
    }

    if (aiGrowthAnalysis) {
        aiGrowthAnalysis.textContent =
            sections.growthAnalysis || "-";
    }

    if (aiLevelUp) {
        aiLevelUp.textContent =
            sections.levelUp || "-";
    }

    if (aiJudgement) {
        aiJudgement.textContent =
            sections.judgement || "-";
    }


    if (aiAnalysisLoading) {
        aiAnalysisLoading.hidden = true;
    }

    if (aiAnalysisError) {
        aiAnalysisError.hidden = true;
    }

    aiAnalysisResult.hidden = false;
}

async function searchAIAnalysis(name) {

    const response =
        await fetch(
            `/api/ai-analysis?name=${encodeURIComponent(
                name
            )}`
        );

    const data =
        await response.json();

    if (!response.ok) {

        // Gemini API 요청 한도 초과
        if (response.status === 429) {
            throw new Error(
                "현재 AI 분석을 사용할 수 없습니다. 잠시 후 다시 시도해주세요."
            );
        }

        throw new Error(
            "AI 분석을 불러오지 못했습니다."
        );
    }

    return data.analysis;
}


/* =========================
   그래프 데이터
========================= */

function buildCumulativeExperienceData(
    history
) {
    const sorted =
        sortHistoryAscending(history);

    let cumulativeExperience = null;

    return sorted.map(
        (item, index) => {
            const currentExperience =
                Number(item.experience);

            /*
               잘못된 데이터
            */
            if (
                !Number.isFinite(
                    currentExperience
                )
            ) {
                return cumulativeExperience;
            }


            /*
               첫 번째 유효 데이터
            */
            if (
                cumulativeExperience === null
            ) {
                cumulativeExperience =
                    currentExperience /
                    1_000_000_000_000;

                return cumulativeExperience;
            }


            const previous =
                sorted[index - 1];

            const previousExperience =
                Number(
                    previous?.experience
                );


            /*
               이전 데이터가 없으면
               현재 누적값 유지
            */
            if (
                !Number.isFinite(
                    previousExperience
                )
            ) {
                return cumulativeExperience;
            }


            /*
               레벨업
               -------------------------
               레벨업 시 NEXON API의
               experience 기준이 새 레벨로
               초기화되므로 단순 뺄셈 금지.

               정확한 누적 경험치가 아닌
               "감소하지 않는 성장 추세"로 표시한다.
            */
            if (
                item.levelUp === true ||
                (
                    Number.isFinite(
                        Number(item.level)
                    ) &&
                    Number.isFinite(
                        Number(
                            previous?.level
                        )
                    ) &&
                    Number(item.level) >
                    Number(previous.level)
                )
            ) {
                return cumulativeExperience;
            }


            /*
               같은 레벨에서
               정상적으로 증가한 경험치
            */
            const difference =
                currentExperience -
                previousExperience;

            if (difference > 0) {
                cumulativeExperience +=
                    difference /
                    1_000_000_000_000;
            }

            return cumulativeExperience;
        }
    );
}


/* =========================
   성장 그래프
========================= */

function renderChart(history) {
    const canvas =
        document.getElementById(
            "growthChart"
        );

    if (!canvas) {
        return;
    }

    const sorted =
        sortHistoryAscending(history);

    if (!sorted.length) {
        return;
    }

    if (growthChart) {
        growthChart.destroy();
        growthChart = null;
    }


    /*
       날짜
    */
    const labels =
        sorted.map(item =>
            formatShortDate(
                item.date
            )
        );


    /*
       누적 경험치
    */
    const experienceData =
        buildCumulativeExperienceData(
            sorted
        );


    /*
       일일 상승량
    */
    const dailyGrowthData =
        sorted.map(item => {
            const value =
                Number(
                    item.experienceChange
                );

            return Number.isFinite(value) &&
                value > 0
                ? value /
                    1_000_000_000_000
                : null;
        });


    /*
       레벨업 표시용 데이터

       레벨업 날짜에만
       경험치 위치에 별을 표시한다.
    */
    const levelUpData =
        experienceData.map(
            (value, index) => {
                return sorted[index]?.levelUp === true
                    ? value
                    : null;
            }
        );


    const ctx =
        canvas.getContext("2d");


    growthChart =
        new Chart(
            ctx,
            {
                type: "line",

                data: {
                    labels,

                    datasets: [

                        /*
                           누적 경험치
                        */
                        {
                            label: "누적 경험치",

                            data:
                                experienceData,

                            yAxisID:
                                "experience",

                            borderWidth: 3,

                            tension: 0,

                            pointRadius: 4,

                            pointHoverRadius: 6,

                            fill: false
                        },


                        /*
                           일일 상승량
                        */
                        {
                            label: "일일 상승량",

                            data:
                                dailyGrowthData,

                            yAxisID:
                                "dailyGrowth",

                            borderWidth: 2,

                            borderDash: [
                                7,
                                6
                            ],

                            tension: 0,

                            pointRadius: 3,

                            pointHoverRadius: 5,

                            fill: false
                        },


                        /*
                           레벨업 별
                        */
                        {
                            label: "레벨업",

                            data:
                                levelUpData,

                            yAxisID:
                                "experience",

                            showLine: false,

                            pointStyle:
                                "star",

                            pointRadius: 9,

                            pointHoverRadius: 12,

                            pointBackgroundColor:
                                "#f5c542",

                            pointBorderColor:
                                "#d89f00",

                            pointBorderWidth: 2,

                            borderWidth: 0,

                            fill: false
                        }
                    ]
                },


                options: {
                    responsive: true,

                    maintainAspectRatio: false,

                    interaction: {
                        intersect: false,

                        mode: "index"
                    },


                    plugins: {
                        legend: {
                            display: true
                        },


                        tooltip: {
                            callbacks: {

                                title:
                                    function(
                                        context
                                    ) {
                                        if (
                                            !context.length
                                        ) {
                                            return "";
                                        }

                                        const index =
                                            context[0]
                                                .dataIndex;

                                        const item =
                                            sorted[index];

                                        return formatShortDate(
                                            item.date
                                        );
                                    },


                                label:
                                    function(
                                        context
                                    ) {
                                        const index =
                                            context.dataIndex;

                                        const item =
                                            sorted[index];

                                        /*
                                           레벨업 별
                                        */
                                        if (
                                            context.dataset
                                                .label ===
                                            "레벨업"
                                        ) {
                                            const previous =
                                                index > 0
                                                    ? sorted[
                                                        index - 1
                                                    ]
                                                    : null;

                                            const previousLevel =
                                                previous?.level;

                                            const currentLevel =
                                                item?.level;

                                            return [
                                                "⭐ 레벨업!",
                                                `${previousLevel ?? "-"} → ${currentLevel ?? "-"}`
                                            ];
                                        }


                                        const value =
                                            context.parsed.y;


                                        /*
                                           누적 경험치
                                        */
                                        if (
                                            context.dataset
                                                .label ===
                                            "누적 경험치"
                                        ) {
                                            if (
                                                value === null ||
                                                value === undefined
                                            ) {
                                                return "";
                                            }

                                            return `누적 경험치: ${value.toFixed(1)}조`;
                                        }


                                        /*
                                           일일 상승량
                                        */
                                        if (
                                            context.dataset
                                                .label ===
                                            "일일 상승량"
                                        ) {
                                            if (
                                                value === null ||
                                                value === undefined
                                            ) {
                                                return "";
                                            }

                                            return `일일 상승량: ${value.toFixed(1)}조`;
                                        }

                                        return "";
                                    }
                            }
                        }
                    },


                    scales: {

                        /*
                           누적 경험치 축
                        */
                        experience: {
                            type: "linear",

                            position: "left",

                            beginAtZero: false,

                            title: {
                                display: true,

                                text:
                                    "누적 경험치"
                            },

                            ticks: {
                                callback:
                                    function(
                                        value
                                    ) {
                                        return `${Number(
                                            value
                                        ).toFixed(0)}조`;
                                    }
                            }
                        },


                        /*
                           일일 상승량 축
                        */
                        dailyGrowth: {
                            type: "linear",

                            position: "right",

                            beginAtZero: true,

                            title: {
                                display: true,

                                text:
                                    "일일 상승량"
                            },

                            grid: {
                                drawOnChartArea:
                                    false
                            },

                            ticks: {
                                callback:
                                    function(
                                        value
                                    ) {
                                        return `${Number(
                                            value
                                        ).toFixed(0)}조`;
                                    }
                            }
                        }
                    }
                }
            }
        );
}


/* =========================
   API 조회
========================= */

async function searchCharacter(name) {
    const response =
        await fetch(
            `/api/character?name=${encodeURIComponent(
                name
            )}`
        );

    if (!response.ok) {
        let message =
            "캐릭터 정보를 불러오지 못했습니다.";

        try {
            const data =
                await response.json();

            if (data.error) {
                message =
                    data.error;
            }
        } catch (error) {
            // 기본 메시지 사용
        }

        throw new Error(message);
    }

    return response.json();
}


async function searchHistory(name) {
    const response =
        await fetch(
            `/api/history?name=${encodeURIComponent(
                name
            )}`
        );

    if (!response.ok) {
        let message =
            "성장 기록을 불러오지 못했습니다.";

        try {
            const data =
                await response.json();

            if (data.error) {
                message =
                    data.error;
            }
        } catch (error) {
            // 기본 메시지 사용
        }

        throw new Error(message);
    }

    const data =
        await response.json();

    return data.history || [];
}


/* =========================
   전체 조회
========================= */

async function handleSearch(event) {
    event.preventDefault();

    const name =
        characterNameInput?.value.trim();

    if (!name) {
        showError(
            "캐릭터명을 입력해주세요."
        );

        return;
    }

    hideError();

    if (resultSection) {
        resultSection.hidden = true;
    }

    /*
       조회 전 저장 버튼 비활성화
    */
    if (saveImageButton) {
        saveImageButton.disabled = true;
    }

    if (savePdfButton) {
        savePdfButton.disabled = true;
    }

    setLoading(true);

    try {
        /*
           캐릭터 정보
        */
        const character =
            await searchCharacter(
                name
            );


        /*
           성장 기록
        */
        const history =
            await searchHistory(
                name
            );


        /*
           화면 출력
        */
        renderCharacter(
            character,
            history
        );

        renderRanking(
            character
        );

        renderGrowthSummary(
            character,
            history
        );

        renderPrediction(
            character,
            history
        );

        renderHistory(
            history
        );

        renderChart(
            history
        );


        /*
           기존 조회 결과를 먼저 표시
        */
        if (saveImageButton) {
            saveImageButton.disabled = false;
        }

        if (savePdfButton) {
            savePdfButton.disabled = false;
        }

        showResult();


        /*
           조회 로딩 종료
        */
        setLoading(false);


        /*
           Gemini AI 성장 분석
        */

        if (aiAnalysisLoading) {
            aiAnalysisLoading.hidden = false;
        }

        if (aiAnalysisError) {
            aiAnalysisError.hidden = true;
        }

        if (aiAnalysisResult) {
            aiAnalysisResult.hidden = true;
        }


        try {

            const analysis =
                await searchAIAnalysis(
                    name
                );

            renderAIAnalysis(
                analysis
            );

        } catch (error) {

            console.error(
                "AI 분석 실패:",
                error
            );

            if (aiAnalysisLoading) {
                aiAnalysisLoading.hidden = true;
            }

            if (aiAnalysisError) {
                aiAnalysisError.textContent =
                    error.message ||
                    "AI 분석을 불러오지 못했습니다.";

                aiAnalysisError.hidden = false;
            }
        }

    } catch (error) {

        console.error(error);

        showError(
            error.message ||
            "조회 중 오류가 발생했습니다."
        );

    } finally {

        setLoading(false);
    }
}


/* =========================
   결과 화면 이미지 / PDF 저장
========================= */

if (saveImageButton) {
    saveImageButton.disabled = true;
}


if (savePdfButton) {
    savePdfButton.disabled = true;
}


async function captureResultSection() {
    const section =
        document.getElementById(
            "resultSection"
        );

    if (
        !section ||
        section.hidden
    ) {
        alert(
            "먼저 캐릭터를 조회해주세요."
        );

        return null;
    }

    return await html2canvas(
        section,
        {
            backgroundColor:
                "#f7f6fb",

            scale: 2,

            useCORS: true
        }
    );
}


/* =========================
   이미지 저장
========================= */

if (saveImageButton) {
    saveImageButton.addEventListener(
        "click",
        async function() {
            try {
                saveImageButton.disabled =
                    true;

                saveImageButton.textContent =
                    "저장 중...";


                const canvas =
                    await captureResultSection();

                if (!canvas) {
                    return;
                }


                const character =
                    document.getElementById(
                        "characterNameResult"
                    )?.textContent ||
                    "character";


                const link =
                    document.createElement(
                        "a"
                    );

                link.download =
                    `maple-growth-${character}.png`;

                link.href =
                    canvas.toDataURL(
                        "image/png"
                    );

                link.click();

            } catch (error) {
                console.error(
                    "이미지 저장 실패:",
                    error
                );

                alert(
                    "이미지 저장 중 오류가 발생했습니다."
                );

            } finally {
                saveImageButton.disabled =
                    false;

                saveImageButton.textContent =
                    "이미지 저장";
            }
        }
    );
}


/* =========================
   PDF 저장
========================= */

if (savePdfButton) {
    savePdfButton.addEventListener(
        "click",
        async function() {
            try {
                savePdfButton.disabled =
                    true;

                savePdfButton.textContent =
                    "생성 중...";


                const canvas =
                    await captureResultSection();

                if (!canvas) {
                    return;
                }


                const character =
                    document.getElementById(
                        "characterNameResult"
                    )?.textContent ||
                    "character";


                const imgData =
                    canvas.toDataURL(
                        "image/png"
                    );


                const {
                    jsPDF
                } = window.jspdf;


                const pdf =
                    new jsPDF({
                        orientation:
                            "portrait",

                        unit: "mm",

                        format: "a4"
                    });


                const pageWidth =
                    pdf.internal.pageSize
                        .getWidth();

                const pageHeight =
                    pdf.internal.pageSize
                        .getHeight();


                const margin = 10;


                const availableWidth =
                    pageWidth -
                    margin * 2;


                const imageHeight =
                    canvas.height *
                    availableWidth /
                    canvas.width;


                let heightLeft =
                    imageHeight;

                let position =
                    margin;


                pdf.addImage(
                    imgData,
                    "PNG",
                    margin,
                    position,
                    availableWidth,
                    imageHeight
                );


                heightLeft -=
                    pageHeight -
                    margin * 2;


                while (
                    heightLeft > 0
                ) {
                    position =
                        -(
                            imageHeight -
                            heightLeft
                        ) +
                        margin;


                    pdf.addPage();


                    pdf.addImage(
                        imgData,
                        "PNG",
                        margin,
                        position,
                        availableWidth,
                        imageHeight
                    );


                    heightLeft -=
                        pageHeight -
                        margin * 2;
                }


                pdf.save(
                    `maple-growth-${character}.pdf`
                );

            } catch (error) {
                console.error(
                    "PDF 저장 실패:",
                    error
                );

                alert(
                    "PDF 저장 중 오류가 발생했습니다."
                );

            } finally {
                savePdfButton.disabled =
                    false;

                savePdfButton.textContent =
                    "PDF 저장";
            }
        }
    );
}


/* =========================
   초기 실행
========================= */

if (searchForm) {
    searchForm.addEventListener(
        "submit",
        handleSearch
    );
}