"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""
import json
import re
import time
from datetime import date

from tracker.integrations.ai_provider import request_openrouter, should_use_openrouter
from tracker.services.ai_text_service import sanitize_ai_text, validate_growth_report
from tracker.runtime import (
    get_ai_response_cache,
    get_gemini_client,
    get_runtime_state,
    set_ai_response_cache,
)


def _is_quota_error(error):
    text = str(error).upper()
    status_code = getattr(error, "code", None) or getattr(
        getattr(error, "response", None), "status_code", None
    )
    return status_code == 429 or "RESOURCE_EXHAUSTED" in text or "QUOTA" in text


def _error_result(error, fallback_message):
    """공급자 오류를 HTTP 계층에서 구분할 수 있는 안전한 형태로 변환한다."""
    if _is_quota_error(error):
        retry_after = None
        delay_match = re.search(
            r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s",
            str(error),
            re.I,
        )
        if delay_match:
            retry_after = max(1, int(float(delay_match.group(1))))
        return {
            "error": "AI 분석 사용량 한도를 초과했습니다. 사용량이 초기화된 후 다시 시도해주세요.",
            "statusCode": 429,
            "retryAfterSeconds": retry_after,
            "errorType": "provider_quota",
        }
    return {"error": fallback_message, "statusCode": 502, "errorType": "provider_error"}


def _generate_gemini_content(client, prompt):
    """일시적인 오류만 제한적으로 재시도한다. 일일 할당량 초과는 재시도하지 않는다."""
    state = get_runtime_state()
    try:
        retry_count = int(state.ai_api_retries)
    except (TypeError, ValueError):
        retry_count = 1
    try:
        backoff = max(0.0, float(state.ai_api_retry_backoff))
    except (TypeError, ValueError):
        backoff = 0.5

    max_attempts = min(max(0, retry_count), 3) + 1
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        except Exception as error:
            if _is_quota_error(error):
                raise
            if not should_use_openrouter(error) or attempt + 1 >= max_attempts:
                raise
            delay = min(3.0, backoff * (2 ** attempt))
            if delay:
                time.sleep(delay)



def _deterministic_growth_forecast(character, metrics):
    """계산된 목표 레벨과 날짜를 사용해 성장 전망을 일관되게 작성한다."""
    prediction = (metrics or {}).get("prediction")
    if not isinstance(prediction, dict):
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
    try:
        parsed_date = date.fromisoformat(str(prediction.get("estimatedDate")))
        target_level = int(prediction.get("nextLevel"))
        current_level = int(character.get("level"))
    except (TypeError, ValueError):
        return "최근 성장 기록만으로는 다음 레벨 달성 시점을 신뢰도 있게 예측하기 어려워요."
    if target_level != current_level + 1 or target_level <= 0:
        return "최근 성장 기록만으로는 다음 레벨 달성 시점을 신뢰도 있게 예측하기 어려워요."
    date_label = f"{parsed_date.month}월 {parsed_date.day}일"
    return (
        f"최근처럼 경험치를 얻는다면 {date_label}쯤 "
        f"{target_level}레벨에 도달할 것으로 예상돼요. "
        "실제 레벨업 날짜는 앞으로의 성장 속도에 따라 달라질 수 있어요."
    )


def _apply_deterministic_growth_forecast(analysis, character, metrics):
    forecast = _deterministic_growth_forecast(character, metrics)
    pattern = r"(\[성장 전망\])([\s\S]*?)(?=\n\[AI 코멘트\])"
    return re.sub(pattern, lambda match: f"{match.group(1)}\n{forecast}", analysis, count=1)


def _build_growth_report_prompt(source_data):
    prompt_data = dict(source_data)
    selected_period = prompt_data.get("selectedPeriod") or {}
    period_days = selected_period.get("periodDays", 7)
    if period_days in (30, 90):
        # 장기 리포트에는 7일 기준 평균/증감 지표를 섞지 않는다.
        # 장기 기간 통계는 periodSummary, 전망은 최근 7일 기준 prediction으로 분리한다.
        original_metrics = prompt_data.get("metrics") or {}
        level_progress = original_metrics.get("levelProgress") or {}
        prompt_data["metrics"] = {
            "recentSevenDayPrediction": original_metrics.get("prediction"),
            "currentLevelProgress": {
                key: level_progress.get(key)
                for key in ("currentRate", "remainingRate")
                if key in level_progress
            },
        }
        prompt_data["growthInsights"] = None

    return f"""
너는 메이플스토리 캐릭터의 성장 기록을 살펴보고, 플레이어가 편하게 읽을 수 있는 리포트를 쓰는 도우미야.
친근하고 담백한 해요체를 사용해. 딱딱한 보고서 말투나 AI가 쓴 듯한 상투적인 문장은 피하고, 실제 메이플을 하는 사람이 이해하기 쉬운 말로 설명해.
목표는 수치를 다시 계산하는 것이 아니라, 이미 확인된 성장 기록을 정확하고 자연스럽게 풀어 주는 거야.

[절대 규칙]
1. 데이터에 없는 수치·날짜·원인·행동을 만들지 마. 계산, 평균, 비율, 예측은 다시 수행하지 말고 입력값만 사용해.
2. 수치의 단위와 의미를 바꾸지 마. 경험치 증가량은 '경험치 증가량' 또는 '경험치 획득량'이라고 표현해. '경보'라는 단어는 어떤 경우에도 사용하지 마.
3. 퍼센트는 반드시 '%' 또는 '%p'의 원래 의미를 유지해. 퍼센트 숫자를 날짜나 월·일로 해석하지 마.
4. 과거 최고 성장일은 history의 실제 날짜와 경험치 변화가 확인될 때만 언급해. 예상 레벨업 날짜와 과거 기록 날짜를 혼동하지 마.
5. 현재 레벨 진행률과 다음 레벨까지 남은 비율을 혼동하지 마. experienceRate는 현재 레벨 진행률이므로, 남은 비율은 currentLevelProgress.remainingRate가 제공된 경우에만 언급해.
6. '꾸준한 성장', '성장세 상승', '안정적'이라는 표현은 여러 날짜의 경험치 변화가 확인될 때만 사용해. 기록이 적으면 '비교할 기록이 아직 많지 않아요'라고 말해.
7. 30일·90일 분석은 selectedPeriod.periodSummary를 가장 중요한 근거로 사용해. 이때 metrics에는 최근 7일 기준 예상 레벨업과 현재 레벨 진행률만 들어 있어. 이를 선택 기간 전체의 평균이나 성장 추세처럼 설명하지 마.
8. 7일 분석은 growthInsights의 최근 7일·직전 7일 비교를 사용해도 돼. 비교할 날짜가 충분하지 않으면 성장량이 늘거나 줄었다고 단정하지 마.
9. 예측은 metrics.recentSevenDayPrediction 또는 metrics.prediction에 예상 날짜가 있을 때만 언급해. 최근과 비슷한 속도로 경험치를 얻는다고 가정한 참고값이므로 확정된 일정처럼 말하지 마. 예상 날짜가 없으면 날짜나 소요 일수를 만들지 마.
10. 경험치처럼 큰 수는 과학적 표기(예: 1.78×10¹³)를 쓰지 말고 '17.8조'처럼 한국어 단위로 표현해. 숫자를 나열하지 말고 변화의 의미를 설명해. 화면 카드에 이미 표시되는 숫자를 불필요하게 반복하지 마.
11. 딱딱한 면책 문구나 번역투 표현을 쓰지 마. 자연스러운 한국어 문장으로 작성하고 조사와 단위를 확인해.
12. 근거 없는 칭찬, 과장, 플레이 시간·요일별 접속 습관 추측, 같은 뜻의 반복을 피하고 담백하고 친근하게 작성해.
13. 데이터 필드명, 내부 모델명, API, Python, Gemini, OpenRouter, 프롬프트, 시스템 동작, null, undefined, 영어 상태값을 본문에 노출하지 마.
14. '관측 구간', '표본', '결측', '기록 충실도', '유효 구간', '메트릭'처럼 개발·통계에 가까운 말은 쓰지 마. '확인된 날짜', '하루 평균 경험치', '지난 기간과 비교'처럼 일상적인 말로 바꿔.
15. 설명은 메이플스토리에서 익숙한 '경험치', '레벨업', '월드 랭킹', '장비', '심볼', 'HEXA', '링크 스킬', '유니온' 같은 표현을 우선 사용해. 실제 입력에 없는 사냥 방식이나 플레이 습관은 추측하지 마.
16. 시스템이 어떤 자료를 수집하거나 계산했는지 설명하기보다, 캐릭터가 어떻게 성장했는지와 플레이어가 알아두면 좋은 점을 먼저 말해.

[항목별 작성 지침]
- [성장 패턴]: 선택 기간의 전반적인 성장 흐름과 실제 관측 수준을 설명해. 기록 수나 기간을 근거로 삼아.
- [성장 변화]: 실제로 확인된 평균·비교 결과 또는 최고 성장일 등 구체적인 변화 한 가지를 설명해. 데이터가 없으면 없다고 밝혀.
- [레벨업 분석]: 관측된 레벨업 여부와 현재 레벨 진행 상황을 구분해 설명해. 레벨업이 없다는 사실만으로 추가 데이터가 반드시 필요하다고 단정하지 마.
- [성장 전망]: 제공된 예측값이 있을 때만 조건부 전망을 설명해. 예측값이 없으면 현재 기록으로 예상하기 어렵다고 밝혀.
- [AI 코멘트]: 앞 항목을 반복 요약하지 말고, 기록을 해석할 때 유의할 점 또는 가장 중요한 한 가지를 짧게 전달해.

[출력 형식]
- 아래 다섯 구분 표시를 정확히 한 번씩, 순서대로 사용해.
- 각 항목은 자연스러운 한국어 1~2문장으로 작성해.
- 각 항목에 근거가 없으면 해당 사실을 짧게 밝히고, 내용을 억지로 채우지 마.
- 마크다운, 글머리표, 별도 제목, 표, 코드 블록은 사용하지 마.
- 최종 답변을 출력하기 전에 숫자·단위·날짜·문맥·맞춤법·중복을 스스로 점검해.

[분석 데이터]
{json.dumps(prompt_data, ensure_ascii=False)}

[성장 패턴]
[성장 변화]
[레벨업 분석]
[성장 전망]
[AI 코멘트]
"""


def generate_ai_analysis(character, history, computed_metrics=None, growth_insights=None, analysis_context=None, force_refresh=False):
    gemini_client = get_gemini_client()
    openrouter_api_key = get_runtime_state().openrouter_api_key

    growth_data = [
        {
            "date": item.get("date"),
            "level": item.get("level"),
            "experienceChange": item.get("experienceChange"),
            "ranking": item.get("ranking"),
            "rankingChange": item.get("rankingChange"),
            "levelUp": item.get("levelUp", False),
            "recordStatus": item.get("recordStatus"),
        }
        for item in history
    ]

    if computed_metrics is not None:
        prediction = computed_metrics.get("prediction")
        prediction_date = prediction.get("estimatedDate") if isinstance(prediction, dict) else None
        prediction_date_label = None
        if prediction_date:
            try:
                parsed_prediction_date = date.fromisoformat(str(prediction_date))
                prediction_date_label = f"{parsed_prediction_date.month}월 {parsed_prediction_date.day}일"
            except (TypeError, ValueError):
                prediction_date_label = None

        source_data = {
            "character": {
                "name": character.get("characterName"),
                "world": character.get("worldName"),
                "job": character.get("job"),
                "level": character.get("level"),
                "experienceRate": character.get("experienceRate"),
            },
            "metrics": computed_metrics,
            "growthInsights": growth_insights or {},
            "selectedPeriod": analysis_context or {"periodDays": 7, "periodSummary": None},
            "predictionDisplayDate": prediction_date_label,
            "history": growth_data,
        }
        prompt = _build_growth_report_prompt(source_data)
    else:
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 데이터를 해석하는 도우미야.
제공된 사실만 이용하고 경험치, 평균, 추세, 예측 날짜 등 숫자를 새로 계산하거나 미래를 추정하지 마.
경험치 증가는 '경험치 증가량' 또는 '경험치 획득량'이라고 표현하고 '경보'라는 단어는 사용하지 마.
기록이 부족한 경우 데이터 부족을 밝히고, 근거 없는 행동이나 플레이 스타일을 추측하지 마.
마크다운 없이 자연스러운 한국어 문장만 작성해. 개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
아래 네 구분 표시는 그대로 사용해.
[성장 패턴]
[성장 분석]
[레벨업]
[AI 판단]

캐릭터:
{character.get("characterName")} / {character.get("worldName")} / Lv.{character.get("level")}
최근 성장 기록:
{json.dumps(growth_data, ensure_ascii=False)}
"""

    expected_date = None
    if computed_metrics is not None:
        prediction = computed_metrics.get("prediction")
        if isinstance(prediction, dict):
            expected_date = prediction.get("estimatedDate")

    cached_analysis = None if force_refresh else get_ai_response_cache(prompt)
    if cached_analysis is not None:
        print("저장된 AI 성장 리포트를 재사용했습니다.")
        if computed_metrics is not None:
            cached_analysis = _apply_deterministic_growth_forecast(cached_analysis, character, computed_metrics)
        return {"analysis": cached_analysis, "cacheHit": True, "growthInsights": growth_insights}

    gemini_error = None
    if gemini_client:
        try:
            response = _generate_gemini_content(gemini_client, prompt)
            analysis = sanitize_ai_text(response.text or "분석 결과가 비어 있습니다.", expected_date)
            if computed_metrics is not None:
                analysis = _apply_deterministic_growth_forecast(analysis, character, computed_metrics)
            if not validate_growth_report(analysis):
                return {
                    "error": "AI 분석 결과의 문장 품질이나 필수 항목을 확인하지 못했습니다. 다시 분석해주세요.",
                    "statusCode": 502,
                    "errorType": "invalid_model_output",
                }
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False, "growthInsights": growth_insights}
        except Exception as error:
            gemini_error = error
            print(f"Gemini 성장 분석 요청에 실패했습니다: {error}")
            if not should_use_openrouter(error):
                return _error_result(error, "AI 분석을 불러오지 못했습니다.")

    if openrouter_api_key:
        try:
            response_text = request_openrouter(prompt)
            print("OpenRouter로 성장 분석을 처리했습니다.")
            analysis = sanitize_ai_text(response_text or "분석 결과가 비어 있습니다.", expected_date)
            if computed_metrics is not None:
                analysis = _apply_deterministic_growth_forecast(analysis, character, computed_metrics)
            if not validate_growth_report(analysis):
                return {
                    "error": "AI 분석 결과의 문장 품질이나 필수 항목을 확인하지 못했습니다. 다시 분석해주세요.",
                    "statusCode": 502,
                    "errorType": "invalid_model_output",
                }
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False, "growthInsights": growth_insights}
        except Exception as error:
            print(f"OpenRouter 성장 분석 요청에 실패했습니다: {error}")
            if gemini_error and _is_quota_error(gemini_error):
                return _error_result(gemini_error, "AI 분석 사용량 한도를 초과했습니다.")
            return _error_result(error, "AI 분석을 불러오지 못했습니다.")

    if gemini_error:
        return _error_result(gemini_error, "AI 분석을 불러오지 못했습니다.")
    return {"error": "AI 분석을 사용할 수 없습니다.", "statusCode": 503, "errorType": "provider_unavailable"}


def generate_ai_comparison(primary, comparison):
    gemini_client = get_gemini_client()
    openrouter_api_key = get_runtime_state().openrouter_api_key

    def prepare_subject(subject):
        character = subject["character"]
        metrics = subject["metrics"]
        history = subject.get("history") or []
        return {
            "character": {
                "characterName": character.get("characterName"),
                "worldName": character.get("worldName"),
                "job": character.get("job"),
                "level": character.get("level"),
                "experienceRate": character.get("experienceRate"),
            },
            "metrics": metrics,
            "history": [
                {
                    "date": item.get("date"),
                    "level": item.get("level"),
                    "experienceChange": item.get("experienceChange"),
                    "ranking": item.get("ranking"),
                    "rankingChange": item.get("rankingChange"),
                    "levelUp": item.get("levelUp", False),
                    "recordStatus": item.get("recordStatus"),
                }
                for item in history
            ],
        }

    prompt_data = {"primary": prepare_subject(primary), "comparison": prepare_subject(comparison)}
    prompt = f"""
너는 두 메이플스토리 캐릭터의 성장 차이를 플레이어가 쉽게 이해하도록 설명하는 도우미야.
친근하고 담백한 해요체로 2~4문장만 작성해. 딱딱한 보고서 말투나 AI가 쓴 듯한 상투적인 표현은 피하고, '경험치', '레벨업', '월드 랭킹'처럼 익숙한 메이플 용어를 사용해.
아래 수치는 이미 같은 기준으로 계산되어 있으니 다시 계산하거나 새로운 예측을 만들지 마. 비교 카드에 표시된 숫자와 순위를 반복하기보다, 실제로 확인되는 차이를 쉽게 설명해.
기록이 충분하지 않으면 아직 비교하기 어렵다고 자연스럽게 알려줘. 현재 레벨만으로 우위를 단정하거나 사냥 방식·플레이 시간을 추측하지 마.
개발 용어, 데이터 필드명, 영어 상태값, null, undefined는 본문에 쓰지 마.

비교 데이터:
{json.dumps(prompt_data, ensure_ascii=False)}
"""
    cached_analysis = get_ai_response_cache(prompt)
    if cached_analysis is not None:
        print("저장된 AI 성장 비교 분석을 재사용했습니다.")
        return {"analysis": cached_analysis, "cacheHit": True}

    gemini_error = None
    if gemini_client:
        try:
            response = _generate_gemini_content(gemini_client, prompt)
            analysis = sanitize_ai_text(response.text or "비교 분석 결과가 비어 있습니다.")
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            gemini_error = error
            print(f"Gemini 성장 비교 분석 요청에 실패했습니다: {error}")
            if not should_use_openrouter(error):
                return _error_result(error, "AI 성장 분석을 불러오지 못했습니다.")

    if openrouter_api_key:
        try:
            response_text = request_openrouter(prompt)
            print("OpenRouter로 성장 비교 분석을 처리했습니다.")
            analysis = sanitize_ai_text(response_text or "비교 분석 결과가 비어 있습니다.")
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            print(f"OpenRouter 성장 비교 분석 요청에 실패했습니다: {error}")
            if gemini_error and _is_quota_error(gemini_error):
                return _error_result(gemini_error, "AI 분석 사용량 한도를 초과했습니다.")
            return _error_result(error, "AI 성장 분석을 불러오지 못했습니다.")

    if gemini_error:
        return _error_result(gemini_error, "AI 성장 분석을 불러오지 못했습니다.")
    return {"error": "AI 성장 분석을 사용할 수 없습니다.", "statusCode": 503, "errorType": "provider_unavailable"}
