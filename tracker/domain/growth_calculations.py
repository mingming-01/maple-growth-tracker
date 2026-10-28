"""성장 기록의 날짜 간 변화 계산을 담당한다."""


def calculate_recent_history_changes(history):
    """최근 7일 기록의 경험치·랭킹 변화와 레벨업 여부를 계산한다."""
    for index, current in enumerate(history):
        if index == 0:
            current["experienceChange"] = None
            current["rankingChange"] = None
            continue

        previous = history[index - 1]
        current["levelUp"] = False

        if current["experience"] is not None and previous["experience"] is not None:
            if (
                current["level"] is not None
                and previous["level"] is not None
                and current["level"] > previous["level"]
            ):
                current["experienceChange"] = None
                current["levelUp"] = True
            else:
                current["experienceChange"] = current["experience"] - previous["experience"]
        else:
            current["experienceChange"] = None

        if current["ranking"] is not None and previous["ranking"] is not None:
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

        if index == 0:
            continue

        previous = history[index - 1]
        if current["recordStatus"] == "available" and previous["recordStatus"] == "available":
            if (
                current["level"] is not None
                and previous["level"] is not None
                and current["level"] > previous["level"]
            ):
                current["levelUp"] = True
            elif current["experience"] is not None and previous["experience"] is not None:
                current["experienceChange"] = current["experience"] - previous["experience"]

            if current["ranking"] is not None and previous["ranking"] is not None:
                current["rankingChange"] = previous["ranking"] - current["ranking"]

    return history
