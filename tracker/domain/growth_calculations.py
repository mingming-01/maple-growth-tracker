"""성장 기록의 날짜 간 변화 계산을 담당한다."""


def is_experience_rate_reset(previous_rate, current_rate):
    """진행률이 레벨업 경계에서 높은 값에서 초기 구간으로 내려갔는지 판정한다."""
    try:
        previous = float(str(previous_rate).replace("%", "").replace(",", "").strip())
        current = float(str(current_rate).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return False
    return 90.0 <= previous <= 100.0 and 0.0 <= current <= 2.0


def _mark_level_up(current, previous_level, current_level):
    """이벤트 날짜와 실제 레벨 전환을 분리해 기록한다."""
    current["levelUp"] = True
    current["levelUpPreviousLevel"] = previous_level
    try:
        previous_number = int(previous_level)
    except (TypeError, ValueError):
        previous_number = None
    try:
        current_number = int(current_level)
    except (TypeError, ValueError):
        current_number = None
    if previous_number is not None and (
        current_number is None or current_number <= previous_number
    ):
        current_number = previous_number + 1
    current["levelUpCurrentLevel"] = current_number


def calculate_recent_history_changes(history):
    """최근 7일 기록의 경험치·랭킹 변화와 레벨업 여부를 계산한다."""
    for index, current in enumerate(history):
        current["levelUp"] = False
        current["levelUpPreviousLevel"] = None
        current["levelUpCurrentLevel"] = None
        current["levelUpCatchUp"] = False
        if index == 0:
            current["experienceChange"] = None
            current["rankingChange"] = None
            continue

        previous = history[index - 1]
        records_available = (
            current.get("recordStatus") in (None, "available")
            and previous.get("recordStatus") in (None, "available")
        )
        try:
            level_changed = (
                current.get("level") is not None
                and previous.get("level") is not None
                and int(current["level"]) > int(previous["level"])
            )
        except (TypeError, ValueError):
            level_changed = False

        rate_reset = is_experience_rate_reset(
            previous.get("experienceRate"), current.get("experienceRate")
        )
        duplicate_level_catch_up = (
            previous.get("levelUp") is True and level_changed
        )
        transition = records_available and (level_changed or rate_reset)
        if transition and not duplicate_level_catch_up:
            _mark_level_up(
                current, previous.get("level"), current.get("level")
            )
        elif duplicate_level_catch_up:
            current["levelUpCatchUp"] = True

        if transition or duplicate_level_catch_up:
            # The reset day and the following ranking-metadata catch-up are
            # both excluded from daily EXP deltas.
            current["experienceChange"] = None
        elif current.get("experience") is not None and previous.get("experience") is not None:
            current["experienceChange"] = current["experience"] - previous["experience"]
        else:
            current["experienceChange"] = None

        if current.get("ranking") is not None and previous.get("ranking") is not None:
            current["rankingChange"] = previous["ranking"] - current["ranking"]
        else:
            current["rankingChange"] = None

    return history

def calculate_archive_history_changes(history):
    """30일·90일 기록에서 연속으로 확인된 날짜 사이의 변화만 계산한다."""
    for index, current in enumerate(history):
        current["experienceChange"] = None
        current["rankingChange"] = None
        current["levelUp"] = False
        current["levelUpPreviousLevel"] = None
        current["levelUpCurrentLevel"] = None
        current["levelUpCatchUp"] = False

        if index == 0:
            continue

        previous = history[index - 1]
        if current.get("recordStatus") != "available" or previous.get("recordStatus") != "available":
            continue

        try:
            level_changed = (
                current.get("level") is not None
                and previous.get("level") is not None
                and int(current["level"]) > int(previous["level"])
            )
        except (TypeError, ValueError):
            level_changed = False
        rate_reset = is_experience_rate_reset(
            previous.get("experienceRate"), current.get("experienceRate")
        )
        duplicate_level_catch_up = (
            previous.get("levelUp") is True and level_changed
        )
        transition = level_changed or rate_reset
        if transition and not duplicate_level_catch_up:
            _mark_level_up(
                current, previous.get("level"), current.get("level")
            )
        elif duplicate_level_catch_up:
            current["levelUpCatchUp"] = True

        if not duplicate_level_catch_up and not transition:
            if (
                current.get("experience") is not None
                and previous.get("experience") is not None
            ):
                current["experienceChange"] = (
                    current["experience"] - previous["experience"]
                )

        if current.get("ranking") is not None and previous.get("ranking") is not None:
            current["rankingChange"] = previous["ranking"] - current["ranking"]

    return history