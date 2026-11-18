"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""
import json
import re
from datetime import date
from types import SimpleNamespace

from tracker.integrations.ai_provider import request_gemini, request_openrouter, should_use_openrouter
from tracker.services.ai_text_service import (
    REQUIRED_GROWTH_SECTIONS,
    sanitize_ai_text,
    validate_growth_report,
)
from tracker.runtime import (
    get_ai_response_cache,
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


def _generate_gemini_content(client_or_prompt, prompt=None, api_key=None):
    """Gemini 호출을 제한 시간 REST 어댑터로 전달한다.

    두 인자 호출은 구버전 단위 테스트·외부 호출부와의 호환성을 위해 남긴다.
    실제 애플리케이션 경로는 프롬프트 한 인자로 호출해 전체 시간 제한을 적용한다.
    """
    if prompt is not None:
        return client_or_prompt.models.generate_content(
            model="gemini-3.6-flash", contents=prompt
        )
    return SimpleNamespace(text=request_gemini(client_or_prompt, api_key=api_key))



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
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
    if target_level != current_level + 1 or target_level <= 0:
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
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
너는 메이플스토리 캐릭터의 성장 기록을 읽고 플레이어가 편하게 이해할 수 있는 리포트를 쓰는 도우미야.
친근하고 담백한 해요체를 사용해. 메이플스토리에서 익숙한 경험치, 레벨업, 월드 랭킹 표현을 우선해.

[작성 규칙]
- 아래 분석 자료에 있는 사실만 사용해. 수치·날짜·평균·비율·원인·행동을 새로 계산하거나 추측하지 마.
- 경험치 증가량과 현재 레벨 진행률을 구분해. experienceRate는 현재 레벨 진행률이야. 남은 비율은 currentLevelProgress.remainingRate가 있을 때만 말해.
- 7일 리포트는 growthInsights의 최근/직전 7일 비교를 참고해. 비교할 기록이 부족하면 증가·감소를 단정하지 마.
- 30일·90일 리포트는 selectedPeriod.periodSummary가 선택 기간의 핵심 근거야. metrics의 전망과 진행률은 최근 7일 기준이므로 장기 기간 통계처럼 설명하지 마.
- 예상 레벨업은 metrics.prediction 또는 metrics.recentSevenDayPrediction에 날짜가 있을 때만, 참고값임을 밝혀 말해. 실제 전망 문장은 서버가 계산한 값으로 교체돼.
- 기록이 적으면 흐름이 꾸준하다거나 안정적이라고 말하지 마. 근거 없는 칭찬, 사냥 방식, 플레이 시간, 접속 습관을 만들지 마.
- 큰 경험치는 '17.8조'처럼 한국어 단위로 써. 과학적 표기, 개발 용어, 데이터 필드명, 모델명, API, null, undefined, 영어 상태값은 본문에 쓰지 마.
- '관측 구간', '표본', '결측', '기록 충실도', '유효 구간', '메트릭' 같은 말 대신 '확인된 날짜', '하루 평균 경험치', '지난 기간과 비교'처럼 자연스럽게 표현해.
- [성장 패턴]은 선택 기간의 전체 흐름, [성장 변화]는 확인된 구체적 차이, [레벨업 분석]은 실제 레벨 변화와 현재 진행 상황, [성장 전망]은 주어진 전망, [AI 코멘트]는 유의할 점 한 가지를 설명해.
- 각 항목은 근거가 있는 자연스러운 한국어 1~2문장으로 작성해. 근거가 없으면 짧게 밝혀.
- 아래 다섯 제목을 정확히 한 번씩 순서대로 사용해. 마크다운·목록·표·별도 제목은 쓰지 마.

[분석 자료]
{json.dumps(prompt_data, ensure_ascii=False)}

[성장 패턴]
[성장 변화]
[레벨업 분석]
[성장 전망]
[AI 코멘트]
"""


def generate_ai_analysis(character, history, computed_metrics=None, growth_insights=None, analysis_context=None, force_refresh=False):
    runtime_state = get_runtime_state()
    gemini_api_key = runtime_state.gemini_api_key
    openrouter_api_key = runtime_state.openrouter_api_key

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
        required_sections = "\n".join(REQUIRED_GROWTH_SECTIONS)
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 데이터를 해석하는 도우미야.
제공된 사실만 이용하고 경험치, 평균, 추세, 예측 날짜 등 숫자를 새로 계산하거나 미래를 추정하지 마.
경험치 증가는 '경험치 증가량' 또는 '경험치 획득량'이라고 표현하고 '경보'라는 단어는 사용하지 마.
기록이 부족한 경우 데이터 부족을 밝히고, 근거 없는 행동이나 플레이 스타일을 추측하지 마.
마크다운 없이 자연스러운 한국어 문장만 작성해. 개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
아래 필수 구분 표시는 표시된 이름과 순서를 그대로 지켜 각각 한 번씩 사용해.
{required_sections}
성장 패턴과 변화는 제공된 날짜별 기록으로 확인되는 사실만 설명해.
레벨업 분석은 실제 레벨 변화가 기록에 있을 때만 설명해.
계산된 전망 지표가 제공되지 않았으므로 구체적인 레벨업 날짜나 남은 기간을 만들지 말고, 기록만으로 예측하기 어렵다면 그 점을 밝혀.
마지막 코멘트는 확인된 기록에 근거해 짧고 자연스럽게 작성해.

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
    if gemini_api_key:
        try:
            response = _generate_gemini_content(prompt, api_key=gemini_api_key)
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
            response_text = request_openrouter(prompt, api_key=openrouter_api_key)
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
    runtime_state = get_runtime_state()
    gemini_api_key = runtime_state.gemini_api_key
    openrouter_api_key = runtime_state.openrouter_api_key

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
    if gemini_api_key:
        try:
            response = _generate_gemini_content(prompt)
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
