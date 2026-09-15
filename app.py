from flask import Flask, jsonify, request, render_template
import requests
import os
from dotenv import load_dotenv
from google import genai
from datetime import datetime, date, timedelta
import json
from concurrent.futures import ThreadPoolExecutor
import time


# =========================
# 기본 설정
# =========================

load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False


# =========================
# NEXON API 설정
# =========================

API_KEY = os.getenv("NEXON_API_KEY")

BASE_URL = (
    "https://open.api.nexon.com/"
    "maplestory/v1"
)

HEADERS = {
    "x-nxopen-api-key": API_KEY
}


# =========================
# Gemini API 설정
# =========================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

gemini_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )


# =========================
# 캐시 설정
# =========================

CACHE = {}

CHARACTER_CACHE_TTL = 300       # 현재 캐릭터 정보: 5분
HISTORY_CACHE_TTL = 1800        # 최근 7일 기록: 30분


def get_cache(key):

    item = CACHE.get(key)

    if not item:
        return None

    saved_time = item["time"]
    data = item["data"]
    ttl = item["ttl"]

    if time.time() - saved_time > ttl:

        del CACHE[key]

        return None

    return data


def set_cache(key, data, ttl):

    CACHE[key] = {

        "time":
            time.time(),

        "data":
            data,

        "ttl":
            ttl

    }

# =========================
# 공통 함수
# =========================

def get_ocid(character_name):
    """
    캐릭터 이름으로 OCID 조회
    """

    response = requests.get(
        f"{BASE_URL}/id",
        headers=HEADERS,
        params={
            "character_name": character_name
        }
    )

    if response.status_code != 200:
        return None, response

    return response.json()["ocid"], response


def get_basic_character(ocid):
    """
    OCID로 현재 캐릭터 기본 정보 조회
    """

    response = requests.get(
        f"{BASE_URL}/character/basic",
        headers=HEADERS,
        params={
            "ocid": ocid
        }
    )

    if response.status_code != 200:
        return None, response

    return response.json(), response


# =========================
# 랭킹 API
# =========================

def get_ranking(
    target_date,
    world_name=None,
    ocid=None,
    character_class=None
):
    """
    메이플스토리 종합 랭킹 API 조회

    world_name:
        입력하면 해당 월드 기준

    character_class:
        입력하면 해당 직업 기준

    ocid:
        입력하면 해당 캐릭터의 순위 조회
    """

    params = {
        "date": target_date,
        "world_type": 0,
        "page": 1
    }

    if world_name:
        params["world_name"] = world_name

    if character_class:
        params["class"] = character_class

    if ocid:
        params["ocid"] = ocid

    print(
        "랭킹 API 최종 파라미터:",
        params
    )

    response = requests.get(
        f"{BASE_URL}/ranking/overall",
        headers=HEADERS,
        params=params
    )

    print(
        "랭킹 API 상태코드:",
        response.status_code
    )

    if response.status_code != 200:

        print(
            "랭킹 API 응답:",
            response.text
        )

        return None, response

    ranking_list = response.json().get(
        "ranking",
        []
    )

    if not ranking_list:
        return None, response

    return ranking_list[0], response


# =========================
# NEXON API 직업값 조회
# =========================

def get_api_class(character_class):
    """
    캐릭터 직업명을
    NEXON Open API ranking class 값으로 변환한다.
    """

    jobs_path = os.path.join(
        app.root_path,
        "static",
        "jobs.json"
    )

    try:

        with open(
            jobs_path,
            "r",
            encoding="utf-8"
        ) as file:

            jobs_data = json.load(file)

    except Exception as error:

        print(
            "jobs.json 로드 실패:",
            error
        )

        return None

    api_class = jobs_data.get(
        character_class
    )

    return api_class


# =========================
# 캐릭터 랭킹 4종
# =========================

def get_character_rankings(
    target_date,
    world_name,
    character_class,
    ocid
):
    """
    캐릭터의 현재 랭킹 4종 조회

    1. 종합 랭킹
    2. 월드 랭킹
    3. 직업 랭킹(월드)
    4. 직업 랭킹(전체)

    서로 독립적인 API 요청은 동시에 실행한다.
    """

    result = {
        "ranking": None,
        "worldRanking": None,
        "jobWorldRanking": None,
        "jobRanking": None
    }

    # =========================
    # 직업 → NEXON API 직업값
    # =========================

    api_class = get_api_class(
        character_class
    )

    print(
        "캐릭터 직업:",
        character_class
    )

    print(
        "NEXON API 직업값:",
        api_class
    )

    # =========================
    # 동시에 실행할 요청 함수
    # =========================

    def fetch_overall():

        return get_ranking(
            target_date=target_date,
            ocid=ocid
        )


    def fetch_world():

        return get_ranking(
            target_date=target_date,
            world_name=world_name,
            ocid=ocid
        )


    def fetch_job_world():

        if not api_class:
            return None, None

        return get_ranking(
            target_date=target_date,
            world_name=world_name,
            character_class=api_class,
            ocid=ocid
        )


    def fetch_job():

        if not api_class:
            return None, None

        return get_ranking(
            target_date=target_date,
            character_class=api_class,
            ocid=ocid
        )


    # =========================
    # 4개 API 병렬 실행
    # =========================

    with ThreadPoolExecutor(
        max_workers=4
    ) as executor:

        futures = [

            executor.submit(
                fetch_overall
            ),

            executor.submit(
                fetch_world
            ),

            executor.submit(
                fetch_job_world
            ),

            executor.submit(
                fetch_job
            )

        ]

        overall_data, _ = futures[0].result()

        world_data, _ = futures[1].result()

        job_world_data, _ = futures[2].result()

        job_data, _ = futures[3].result()


    # =========================
    # 결과 정리
    # =========================

    if overall_data:

        result["ranking"] = (
            overall_data.get(
                "ranking"
            )
        )


    if world_data:

        result["worldRanking"] = (
            world_data.get(
                "ranking"
            )
        )


    if job_world_data:

        result["jobWorldRanking"] = (
            job_world_data.get(
                "ranking"
            )
        )


    if job_data:

        result["jobRanking"] = (
            job_data.get(
                "ranking"
            )
        )


    print(
        "랭킹 결과:",
        result
    )

    return result


# =========================
# 메인 페이지
# =========================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================
# 서버 / 직업 목록
# =========================

@app.route("/api/options")
def get_options():

    today = date.today().strftime(
        "%Y-%m-%d"
    )

    response = requests.get(

        f"{BASE_URL}/ranking/overall",

        headers=HEADERS,

        params={

            "date": today,

            "world_type": 0,

            "page": 1

        }

    )

    if response.status_code != 200:

        return jsonify({

            "error":
                "서버 및 직업 목록을 가져오지 못했습니다.",

            "detail":
                response.json()

        }), response.status_code


    ranking_list = response.json().get(
        "ranking",
        []
    )


    # =========================
    # 서버 목록
    # =========================

    worlds = set()


    # =========================
    # 직업군 → 직업 목록
    # =========================

    classes = {}


    for character in ranking_list:

        world_name = character.get(
            "world_name"
        )

        class_name = character.get(
            "class_name"
        )

        sub_class_name = character.get(
            "sub_class_name"
        )


        if world_name:

            worlds.add(
                world_name
            )


        if class_name:

            if class_name not in classes:

                classes[class_name] = set()


            if sub_class_name:

                classes[
                    class_name
                ].add(
                    sub_class_name
                )


    # =========================
    # set → list
    # =========================

    class_data = {}


    for class_name, jobs in classes.items():

        class_data[class_name] = sorted(
            jobs
        )


    # =========================
    # 결과
    # =========================

    return jsonify({

        "worlds":
            sorted(
                worlds
            ),

        "classes":
            dict(
                sorted(
                    class_data.items()
                )
            )

    })


# =========================
# 현재 캐릭터 조회
# =========================

@app.route("/api/character")
def get_character():

    character_name = request.args.get(
        "name"
    )


    print(
        "받은 캐릭터명:",
        character_name
    )


    if not character_name:

        return jsonify({

            "error":
                "캐릭터 이름을 입력해주세요."

        }), 400


    # =========================
    # 캐릭터 캐시 확인
    # =========================

    cache_key = (
        f"character:{character_name}"
    )

    cached_character = get_cache(
        cache_key
    )


    if cached_character is not None:

        print(
            "캐릭터 캐시 사용:",
            character_name
        )

        return jsonify(
            cached_character
        )


    # =========================
    # 1. 캐릭터명 → OCID
    # =========================

    ocid, response = get_ocid(
        character_name
    )


    if not ocid:

        return jsonify({

            "error":
                "캐릭터 정보를 찾을 수 없습니다.",

            "detail":
                response.json()

        }), response.status_code


    # =========================
    # 2. OCID → 기본 정보
    # =========================

    basic, response = get_basic_character(
        ocid
    )


    if not basic:

        return jsonify({

            "error":
                "캐릭터 기본 정보를 가져오지 못했습니다.",

            "detail":
                response.json()

        }), response.status_code


    # =========================
    # 3. 캐릭터 직업
    # =========================

    character_class = basic[
        "character_class"
    ]


    api_class = get_api_class(
        character_class
    )


    print(
        "캐릭터 직업:",
        character_class
    )


    print(
        "NEXON API 직업값:",
        api_class
    )


    # =========================
    # 4. 오늘 랭킹
    # =========================

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    character_rankings = (
        get_character_rankings(

            target_date=today,

            world_name=basic[
                "world_name"
            ],

            character_class=character_class,

            ocid=ocid

        )
    )


    # =========================
    # 5. 현재 경험치
    # =========================

    ranking_experience = basic[
        "character_exp"
    ]


    # =========================
    # 6. 서비스용 데이터
    # =========================

    result = {

        "characterName":
            basic[
                "character_name"
            ],

        "worldName":
            basic[
                "world_name"
            ],

        "job":
            basic[
                "character_class"
            ],

        "guildName":
            basic.get(
                "character_guild_name"
            ),

        "level":
            basic[
                "character_level"
            ],

        "experience":
            basic[
                "character_exp"
            ],

        "experienceRate":
            basic[
                "character_exp_rate"
            ],


        # =========================
        # 랭킹 4종
        # =========================

        "ranking":
            character_rankings[
                "ranking"
            ],

        "worldRanking":
            character_rankings[
                "worldRanking"
            ],

        "jobWorldRanking":
            character_rankings[
                "jobWorldRanking"
            ],

        "jobRanking":
            character_rankings[
                "jobRanking"
            ],


        "rankingExperience":
            ranking_experience,

        "ocid":
            ocid

    }


    print(
        "최종 캐릭터 데이터:",
        result
    )


    # =========================
    # 캐릭터 결과 캐시 저장
    # =========================

    set_cache(
        cache_key,
        result,
        CHARACTER_CACHE_TTL
    )


    return jsonify(
        result
    )


# =========================
# 최근 7일 성장 데이터
# =========================

@app.route("/api/history")
def get_history():

    character_name = request.args.get(
        "name"
    )


    print(
        "7일 기록 조회:",
        character_name
    )


    if not character_name:

        return jsonify({

            "error":
                "캐릭터 이름을 입력해주세요."

        }), 400


    # =========================
    # 7일 기록 캐시 확인
    # =========================

    cache_key = (
        f"history:{character_name}"
    )

    cached_history = get_cache(
        cache_key
    )


    if cached_history is not None:

        print(
            "7일 기록 캐시 사용:",
            character_name
        )

        return jsonify(
            cached_history
        )


    # =========================
    # 1. OCID 조회
    # =========================

    ocid, response = get_ocid(
        character_name
    )


    if not ocid:

        return jsonify({

            "error":
                "캐릭터 정보를 찾을 수 없습니다.",

            "detail":
                response.json()

        }), response.status_code


    # =========================
    # 2. 현재 기본 정보
    # =========================

    basic, response = get_basic_character(
        ocid
    )


    if not basic:

        return jsonify({

            "error":
                "캐릭터 정보를 가져오지 못했습니다.",

            "detail":
                response.json()

        }), response.status_code


    world_name = basic[
        "world_name"
    ]


    # =========================
    # 3. 최근 7일 조회
    # =========================

    today = date.today()


    def fetch_history(
        target_date
    ):

        date_string = (
            target_date.strftime(
                "%Y-%m-%d"
            )
        )


        ranking_data, ranking_response = (
            get_ranking(

                target_date=date_string,

                world_name=world_name,

                ocid=ocid

            )
        )


        if ranking_data:
            print("history 반환용 level:", ranking_data.get("character_level"))
            return {

                "date":
                    date_string,

                "ranking":
                    ranking_data.get(
                        "ranking"
                    ),

                "level": 
                    ranking_data.get(
                            "character_level"
                    ),

                "experience":
                    ranking_data.get(
                        "character_exp"
                    )

            }

        if ranking_data:

            return {

                "date":
                    date_string,

                "ranking":
                    ranking_data.get(
                        "ranking"
                    ),

                "level":
                    ranking_data.get(
                        "character_level"
                    ),

                "experience":
                    ranking_data.get(
                        "character_exp"
                    )

            }


        return {

            "date":
                date_string,

            "ranking":
                None,

            "level":
                None,

            "experience":
                None

        }


    # =========================
    # 조회할 날짜 7개
    # =========================

    dates = [

        today - timedelta(
            days=i
        )

        for i in range(7)

    ]


    # =========================
    # 7개 API 병렬 실행
    # =========================

    with ThreadPoolExecutor(
        max_workers=7
    ) as executor:

        history = list(

            executor.map(
                fetch_history,
                dates
            )

        )


    # =========================
    # 오래된 날짜 → 최신 날짜
    # =========================

    history.reverse()


    # =========================
    # 성장량 계산
    # =========================

    for i in range(
        len(history)
    ):

        current = history[i]


        if i == 0:

            current[
                "experienceChange"
            ] = None

            current[
                "rankingChange"
            ] = None

            continue


        previous = history[
            i - 1
        ]


        # =========================
        # 경험치 증가량
        # =========================

        if (

            current[
                "experience"
            ] is not None

            and

            previous[
                "experience"
            ] is not None

        ):

            # 레벨업한 경우
            if (

                current[
                    "level"
                ] is not None

                and

                previous[
                    "level"
                ] is not None

                and

                current[
                    "level"
                ]

                >

                previous[
                    "level"
                ]

            ):

                # 경험치가 다음 레벨 기준으로 초기화되므로
                # 단순 뺄셈을 하지 않는다.
                current[
                    "experienceChange"
                ] = None

                current[
                    "levelUp"
                ] = True

                print(
                    "레벨업 감지:",
                    previous["date"],
                    previous["level"],
                    "→",
                    current["date"],
                    current["level"]
)

            else:

                current[
                    "experienceChange"
                ] = (

                    current[
                        "experience"
                    ]

                    -

                    previous[
                        "experience"
                    ]

                )

                current[
                    "levelUp"
                ] = False

        else:

            current[
                "experienceChange"
            ] = None

            current[
                "levelUp"
            ] = False


        # =========================
        # 랭킹 변화
        #
        # 이전 순위 - 현재 순위
        #
        # 양수 = 순위 상승
        # =========================

        if (

            current[
                "ranking"
            ] is not None

            and

            previous[
                "ranking"
            ] is not None

        ):

            current[
                "rankingChange"
            ] = (

                previous[
                    "ranking"
                ]

                -

                current[
                    "ranking"
                ]

            )

        else:

            current[
                "rankingChange"
            ] = None


    # =========================
    # 7일 평균 경험치
    # =========================

    experience_changes = [

        item[
            "experienceChange"
        ]

        for item in history

        if item[
            "experienceChange"
        ] is not None

    ]


    average_experience = None


    if experience_changes:

        average_experience = (

            sum(
                experience_changes
            )

            /

            len(
                experience_changes
            )

        )


    # =========================
    # 결과
    # =========================

    result = {

        "characterName":
            basic[
                "character_name"
            ],

        "worldName":
            world_name,

        "level":
            basic[
                "character_level"
            ],

        "history":
            history,

        "averageDailyExperience":
            average_experience

    }


    # =========================
    # 7일 기록 캐시 저장
    # =========================

    set_cache(
        cache_key,
        result,
        HISTORY_CACHE_TTL
    )


    return jsonify(
        result
    )

# =========================
# Gemini AI 성장 분석
# =========================

def generate_ai_analysis(character, history):
    if not gemini_client:
        return {
            "error": "Gemini API 키가 설정되지 않았습니다."
        }

    try:
        growth_data = []

        for item in history:
            growth_data.append({
                "date": item.get("date"),
                "level": item.get("level"),
                "experienceChange": item.get(
                    "experienceChange"
                ),
                "ranking": item.get("ranking"),
                "levelUp": item.get(
                    "levelUp",
                    False
                )
            })

        prompt = f"""
                너는 메이플스토리 캐릭터의 성장 데이터를 분석하는 AI야.

                다음 데이터를 바탕으로 최근 성장 패턴을 분석해줘.

                [캐릭터 정보]
                캐릭터명: {character.get("characterName")}
                월드: {character.get("worldName")}
                직업: {character.get("job")}
                현재 레벨: {character.get("level")}
                현재 경험치 진행률: {character.get("experienceRate")}%

                [최근 7일 성장 기록]
                {growth_data}

                [분석 규칙]
                - 반드시 제공된 데이터만 근거로 분석해.
                - 데이터에 없는 사냥 방식, 플레이 시간, 플레이 빈도, 플레이 스타일 등의 행동을 추측하지 마.
                - "꾸준하다", "안정적이다", "급격하다", "정체기" 등의 표현은 실제 데이터가 그 판단을 뒷받침할 때만 사용해.
                - 특정 날짜의 경험치 증가량이 다른 날짜보다 크거나 작은 경우 실제 데이터에 근거해서 설명해.
                - 랭킹 변화는 제공된 ranking 데이터를 기준으로만 설명해.
                - 레벨업 여부는 반드시 levelUp 값을 기준으로 판단해.
                - levelUp이 true인 경우 해당 날짜와 이전 레벨 및 현재 레벨의 변화를 반드시 언급해.
                - 최근 기록에 levelUp이 없다면 "최근 레벨업 없음"이라고 작성해.
                - 현재 경험치 진행률은 제공된 character 데이터의 값을 그대로 사용해.
                - 경험치 수치를 임의로 계산하거나 수정하지 마.
                - 다음 레벨까지 필요한 경험치나 레벨업 예상 시점을 별도로 계산하지 마.
                - 미래의 성장 결과를 단정하거나 예측하지 마.
                - 제공된 데이터만으로 확인할 수 없는 내용은 작성하지 마.
                - 단순히 숫자를 나열하지 말고, 실제 데이터에서 확인되는 변화와 특징을 중심으로 설명해.
                - 과장되거나 근거 없는 긍정적인 표현은 사용하지 마.
                - 분석은 자연스럽고 간결한 한국어로 작성해.

                다음 형식으로 답변해줘.

                [성장 패턴]
                최근 7일 데이터에서 확인되는 가장 뚜렷한 성장 패턴을 한 문장으로 설명

                [성장 분석]
                최근 성장 흐름을 2~3문장으로 설명.
                경험치 변화와 랭킹 변화가 실제 데이터에 나타난 경우 이를 함께 설명해.

                [레벨업]
                최근 레벨업이 있다면 날짜와 이전 레벨 → 현재 레벨의 변화를 설명.
                없다면 "최근 레벨업 없음"이라고 작성

                [AI 판단]
                제공된 성장 데이터를 바탕으로 현재 성장 흐름에 대한 종합적인 판단을 1~2문장으로 작성.
                미래의 레벨업 시점이나 결과를 예측하지 마.
                """

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        return {
            "analysis": response.text
        }

    except Exception as error:
        print(
            "Gemini 분석 실패:",
            repr(error)
        )

        return {
            "error": str(error)
        }

# =========================
# Gemini AI 분석 API
# =========================

@app.route("/api/ai-analysis")
def ai_analysis():

    character_name = request.args.get(
        "name",
        ""
    ).strip()

    if not character_name:
        return jsonify({
            "error": "캐릭터명을 입력해주세요."
        }), 400

    try:
        # 캐릭터 정보
        character_response = get_character()

        if character_response.status_code != 200:
            return jsonify({
                "error": "캐릭터 정보를 불러오지 못했습니다."
            }), character_response.status_code

        character = character_response.get_json()

        # 성장 기록
        history_response = get_history()

        if history_response.status_code != 200:
            return jsonify({
                "error": "성장 기록을 불러오지 못했습니다."
            }), history_response.status_code

        history_data = history_response.get_json()

        history = history_data.get(
            "history",
            []
        )

        # Gemini 분석
        result = generate_ai_analysis(
            character,
            history
        )

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result)

    except Exception as error:
        print(
            "Gemini AI 분석 API 오류:",
            error
        )

        return jsonify({
            "error": "AI 분석을 불러오지 못했습니다."
        }), 500

# =========================
# 서버 실행
# =========================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000

    )
