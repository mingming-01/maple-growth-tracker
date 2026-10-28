"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""

from app import *
from tracker.integrations.ai_provider import request_openrouter, should_use_openrouter


def generate_ai_analysis(character, history, computed_metrics=None):

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
            "predictionDisplayDate": prediction_date_label,
            "history": growth_data
        }
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 과정을 해석하는 도우미야.
아래 데이터는 앱에서 계산했거나 API에서 가져온 사실이야. 새 숫자를 계산하거나 추정하지 말고, 사실을 반복해서 나열하기보다 변화의 특징과 의미를 설명해.
성장 요약과 전망 카드에 이미 숫자가 있으므로 레벨, 경험치, 평균·최고·최저 성장량, 랭킹, 소요일 등의 숫자를 리포트에서 되풀이하지 마. 긴 숫자나 괄호 속 원본 수치도 쓰지 마.
성장 전망에서 날짜를 언급할 때는 predictionDisplayDate 값을 그대로 사용해. 그 날짜를 다시 계산하거나 다른 날짜로 바꾸지 마. 날짜 값이 없으면 날짜를 만들어내지 마.
기록이 부족하거나 값이 확인되지 않으면 판단하기 어렵다고 자연스럽게 말해. 데이터 부족을 감추거나 없는 사실을 채워 넣지 마.
성장 흐름은 기록이 충분히 뒷받침할 때만 해석하고, 레벨업은 기록에서 확인될 때만 언급해. 플레이 방식이나 시간은 추측하지 마.
개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
마크다운 없이 일반 문장만 작성해. 제목 기호, 굵게·기울임 표시, 글머리표, 번호 목록, 수평선, 백틱, 코드 블록은 쓰지 마.
아래 다섯 구분 표시는 정확히 그대로 사용하고, 각 항목은 최대 두 개의 짧은 문장으로 작성해. 구분 표시 이외의 제목이나 목록은 추가하지 마.

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
        return {"analysis": cached_analysis, "cacheHit": True}

    gemini_error = None

    if gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            analysis = sanitize_ai_text(
                response.text or "분석 결과가 비어 있습니다.",
                expected_date
            )
            set_ai_response_cache(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            gemini_error = error
            print(f"Gemini 성장 분석 요청에 실패했습니다: {error}")

            if not should_use_openrouter(error):
                return {"error": "AI 분석을 불러오지 못했습니다."}

    if OPENROUTER_API_KEY:
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
            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
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

    if OPENROUTER_API_KEY:
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
