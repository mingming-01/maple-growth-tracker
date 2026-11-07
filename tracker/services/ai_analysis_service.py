"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""
import json
import time
from datetime import date

from tracker.integrations.ai_provider import request_openrouter, should_use_openrouter
from tracker.services.ai_text_service import sanitize_ai_text
from tracker.runtime import (
    get_ai_response_cache,
    get_gemini_client,
    get_runtime_state,
    set_ai_response_cache,
)


def _generate_gemini_content(client, prompt):
    """일시적인 Gemini 오류만 제한적으로 재시도한다."""
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
            return client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
        except Exception as error:
            if not should_use_openrouter(error) or attempt + 1 >= max_attempts:
                raise
            delay = min(3.0, backoff * (2 ** attempt))
            if delay:
                time.sleep(delay)


def generate_ai_analysis(character, history, computed_metrics=None, growth_insights=None, analysis_context=None):
    gemini_client = get_gemini_client()
    openrouter_api_key = get_runtime_state().openrouter_api_key

    growth_data = [
        {
            "date": item.get("date"),
            "level": item.get("level"),
            "experienceChange": item.get("experienceChange"),
            "ranking": item.get("ranking"),
            "rankingChange": item.get("rankingChange"),
            "levelUp": item.get("levelUp", False)
        }
        for item in history
    ]

    if computed_metrics is not None:
        # 프런트엔드에서 이미 계산한 지표를 Gemini에 전달하고 숫자 계산은 맡기지 않는다.
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
                "experienceRate": character.get("experienceRate")
            },
            "metrics": computed_metrics,
            "growthInsights": growth_insights or {},
            "selectedPeriod": analysis_context or {"periodDays": 7, "periodSummary": None},
            "predictionDisplayDate": prediction_date_label,
            "history": growth_data
        }
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 기록을 읽고 플레이어에게 결과를 설명하는 서비스의 리포트 작성자야.
목표는 데이터를 다시 설명하는 것이 아니라, 기록에서 실제로 확인되는 변화와 플레이어가 알아두면 좋은 점을 짧고 자연스럽게 전달하는 거야.

작성 원칙:
- 아래 데이터는 서비스가 계산하거나 공식 API에서 수집한 값이야. 숫자를 새로 계산하거나 추측하지 말고, 필요한 경우 제공된 값만 정확히 사용해.
- 화면의 요약 카드에 이미 표시되는 레벨·경험치·성장량·랭킹 숫자를 문장마다 반복하지 마. 숫자를 언급할 필요가 있을 때만 해당 변화의 의미와 함께 한 번 사용해.
- 비율 값은 반드시 비율로 표현해. 예를 들어 11.17은 '11.17%'이지 '11월 17일'이 아니야. 퍼센트와 날짜를 서로 바꾸거나 숫자의 단위를 임의로 바꾸지 마.
- 날짜는 predictionDisplayDate가 존재할 때에만 성장 전망에서 그대로 사용해. 날짜가 없거나 예측이 성립하지 않으면 특정 날짜를 만들어내지 말고 '현재 기록만으로는 예상하기 어렵습니다'라고 설명해.
- 데이터가 부족하거나 비교 가능한 기록이 없으면 그 사실을 솔직하게 말해. 기록이 적은데도 '꾸준한 성장', '성장세 향상', '높은 신뢰도'라고 단정하지 마.
- 레벨업은 실제 기록에서 확인된 경우에만 언급해. 주말·평일, 플레이 시간, 플레이 방식, 접속 빈도는 데이터가 직접 뒷받침하지 않으면 추측하지 마.
- selectedPeriod.periodDays와 selectedPeriod.periodSummary가 있으면 해당 선택 기간의 기록 요약을 우선 분석해. 이전 기간 요약이 없거나 표본이 부족하면 비교를 단정하지 마.
- 선택 기간 요약의 평균·기록 충실도·성장일 수는 제공된 값만 사용하고 다시 계산하지 마. 선택 기간이 30일 또는 90일이면 growthInsights의 7일 비교를 선택 기간 전체의 결과처럼 설명하지 마.
- 근거 없는 칭찬, 응원 문구, 과장된 전망, 같은 뜻의 문장 반복을 피하고 담백하고 친근한 어조를 사용해.
- 내부 모델명, API, Python, Gemini, OpenRouter, 프롬프트, 계산 근거, 데이터 필드명 등 서비스 구현 정보는 절대 언급하지 마.
- '분석 근거를 재사용했다'거나 'AI 모델을 호출하지 않았다' 같은 시스템 상태도 리포트 본문에 쓰지 마.
- 개발용 키, 영어 상태값, null, undefined, 원본 JSON을 답변에 노출하지 마.

출력 형식:
- 아래 다섯 구분 표시를 정확히 그대로 사용해.
- 각 항목은 1~2개의 자연스러운 문장으로 작성하고, 데이터가 해당 항목을 뒷받침하지 못하면 짧게 '확인할 수 있는 기록이 부족합니다'라고 밝혀.
- AI 코멘트는 앞선 항목을 그대로 요약하지 말고, 전체 기록에서 플레이어가 기억할 핵심 한 가지를 말해.
- 마크다운, 번호 목록, 불필요한 제목, 기술 설명은 쓰지 마.

데이터:
{json.dumps(source_data, ensure_ascii=False)}

[성장 패턴]
[성장 변화]
[레벨업 분석]
[성장 전망]
[AI 코멘트]
"""
    else:
        # 기존 GET 방식 호출 호환성을 유지하며 애플리케이션이 준 기록만 해석한다.
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 데이터를 해석하는 도우미야.
제공된 사실만 이용하고 경험치, 평균, 추세, 예측 날짜 등 숫자를 새로 계산하거나 미래를 추정하지 마.
기록이 부족한 경우 데이터 부족을 밝히고, 근거 없는 행동이나 플레이 스타일을 추측하지 마.
화면에 수치가 별도로 표시되므로 원본 숫자를 나열하지 말고 흐름의 특징을 간결하게 설명해.
마크다운 없이 일반 한국어 문장만 작성하고 개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
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

    cached_analysis = get_ai_response_cache(prompt)
    if cached_analysis is not None:
        print("저장된 AI 성장 리포트를 재사용했습니다.")
        return {"analysis": cached_analysis, "cacheHit": True, "growthInsights": growth_insights}

    gemini_error = None

    if gemini_client:
        try:
            response = _generate_gemini_content(gemini_client, prompt)
            analysis = sanitize_ai_text(
                response.text or "분석 결과가 비어 있습니다.",
                expected_date
            )
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False, "growthInsights": growth_insights}
        except Exception as error:
            gemini_error = error
            print(f"Gemini 성장 분석 요청에 실패했습니다: {error}")

            if not should_use_openrouter(error):
                return {"error": "AI 분석을 불러오지 못했습니다."}

    if openrouter_api_key:
        try:
            response_text = request_openrouter(prompt)
            print("OpenRouter로 성장 분석을 처리했습니다.")
            analysis = sanitize_ai_text(
                response_text or "분석 결과가 비어 있습니다.",
                expected_date
            )
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            print(f"OpenRouter 성장 분석 요청에 실패했습니다: {error}")

    if gemini_error:
        return {"error": "AI 분석을 불러오지 못했습니다."}

    return {"error": "AI 분석을 사용할 수 없습니다."}


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

    prompt_data = {
        "primary": prepare_subject(primary),
        "comparison": prepare_subject(comparison),
    }
    prompt = f"""
너는 두 메이플스토리 캐릭터의 성장 흐름 차이를 설명하는 도우미야.
아래 지표는 앱이 같은 기준으로 계산했어. 어떤 수도 직접 계산하거나 다시 예측하지 마.
비교 카드에 숫자가 표시되므로 숫자와 순위를 반복하지 말고, 두 캐릭터의 최근 성장 변화, 흐름의 안정성, 순위 변화와 성장의 관계에서 실제로 확인되는 차이를 해석해.
기록이 충분하지 않으면 그 비교는 어렵다고 자연스럽게 알려. 현재 레벨만으로 우위를 단정하거나 행동 방식·플레이 시간을 추측하지 마.
마크다운, 제목, 번호, 글머리표, 굵게 표시, 코드 표현, 원본 수치 없이 자연스러운 한국어 2~4문장으로 작성해.
개발용 키 이름, 영어 상태값, null, undefined는 답변에 절대 쓰지 마. 예측 날짜나 새 수치를 만들어내지 마.

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
            analysis = sanitize_ai_text(
                response.text or "비교 분석 결과가 비어 있습니다."
            )
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            gemini_error = error
            print(f"Gemini 성장 비교 분석 요청에 실패했습니다: {error}")

            if not should_use_openrouter(error):
                return {"error": "AI 성장 분석을 불러오지 못했습니다."}

    if openrouter_api_key:
        try:
            response_text = request_openrouter(prompt)
            print("OpenRouter로 성장 비교 분석을 처리했습니다.")
            analysis = sanitize_ai_text(
                response_text or "비교 분석 결과가 비어 있습니다."
            )
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            print(f"OpenRouter 성장 비교 분석 요청에 실패했습니다: {error}")

    if gemini_error:
        return {"error": "AI 성장 분석을 불러오지 못했습니다."}

    return {"error": "AI 성장 분석을 사용할 수 없습니다."}
