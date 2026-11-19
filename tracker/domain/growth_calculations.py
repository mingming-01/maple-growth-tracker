"""성장 기록의 날짜 간 변화 계산을 담당한다."""

from datetime import date
from decimal import Decimal, InvalidOperation


def to_exact_integer(value):
    """정확한 정수로 확인할 수 있는 값만 변환한다."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        # 2**53 이상인 float는 원래 정수의 정밀도를 잃었을 수 있다.
        if abs(value) >= 2**53 or not value.is_integer():
            return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    return int(number)


def is_experience_rate_reset(previous_rate, current_rate):
    """진행률이 높은 값에서 초기 구간으로 내려갔는지 판정한다."""
    try:
        previous = Decimal(str(previous_rate).replace("%", "").replace(",", "").strip())
        current = Decimal(str(current_rate).replace("%", "").replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return False
    return (
        Decimal("90") <= previous <= Decimal("100")
        and Decimal("0") <= current <= Decimal("2")
    )


def _record_date(record):
    value = record.get("date") if isinstance(record, dict) else None
    if type(value) is date:
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _are_consecutive_records(previous, current):
    previous_date = _record_date(previous)
    current_date = _record_date(current)
    return (
        previous_date is not None
        and current_date is not None
        and (current_date - previous_date).days == 1
    )


def calculate_observed_experience_change(previous, current):
    """동일 레벨의 연속 스냅샷에서만 확인 가능한 EXP 차이를 반환한다.

    레벨업 경계는 서로 다른 레벨의 EXP 기준을 가로지른다. 레벨별 필요 EXP
    원본이 없으면 경계 전후 획득량을 복원할 수 없으므로 추정하지 않고 None을 반환한다.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    if previous.get("recordStatus") not in (None, "available"):
        return None
    if current.get("recordStatus") not in (None, "available"):
        return None
    if not _are_consecutive_records(previous, current):
        return None

    previous_level = to_exact_integer(previous.get("level"))
    current_level = to_exact_integer(current.get("level"))
    if previous_level is None or current_level is None or previous_level != current_level:
        return None
    if is_experience_rate_reset(
        previous.get("experienceRate"), current.get("experienceRate")
    ):
        return None

    previous_experience = to_exact_integer(previous.get("experience"))
    current_experience = to_exact_integer(current.get("experience"))
    if previous_experience is None or current_experience is None:
        return None
    if current_experience < previous_experience:
        return None
    return current_experience - previous_experience



def calculate_observed_experience_rate_change(previous, current):
    """연속된 동일 레벨 스냅샷에서 확인된 진행률 차이(%p)를 반환한다."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    if previous.get("recordStatus") not in (None, "available"):
        return None
    if current.get("recordStatus") not in (None, "available"):
        return None
    if not _are_consecutive_records(previous, current):
        return None
    previous_level = to_exact_integer(previous.get("level"))
    current_level = to_exact_integer(current.get("level"))
    if previous_level is None or current_level is None or previous_level != current_level:
        return None
    if is_experience_rate_reset(previous.get("experienceRate"), current.get("experienceRate")):
        return None
    try:
        previous_rate = Decimal(str(previous.get("experienceRate")).replace("%", "").strip())
        current_rate = Decimal(str(current.get("experienceRate")).replace("%", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if (
        not previous_rate.is_finite()
        or not current_rate.is_finite()
        or not Decimal("0") <= previous_rate <= Decimal("100")
        or not Decimal("0") <= current_rate <= Decimal("100")
    ):
        return None
    change = current_rate - previous_rate
    return float(change) if change >= 0 else None


def _mark_level_up(current, previous_level, current_level):
    """이벤트 날짜와 실제 레벨 전환을 분리해 기록한다."""
    current["levelUp"] = True
    current["levelUpPreviousLevel"] = previous_level
    previous_number = to_exact_integer(previous_level)
    current_number = to_exact_integer(current_level)
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
            current["experienceRateChange"] = None
            current["rankingChange"] = None
            continue

        previous = history[index - 1]
        records_available = (
            current.get("recordStatus") in (None, "available")
            and previous.get("recordStatus") in (None, "available")
        )
        consecutive = records_available and _are_consecutive_records(previous, current)
        previous_level = to_exact_integer(previous.get("level"))
        current_level = to_exact_integer(current.get("level"))
        level_changed = (
            previous_level is not None
            and current_level is not None
            and current_level > previous_level
        )
        rate_reset = is_experience_rate_reset(
            previous.get("experienceRate"), current.get("experienceRate")
        )
        duplicate_level_catch_up = (
            consecutive and previous.get("levelUp") is True and level_changed
        )
        transition = consecutive and (level_changed or rate_reset)
        if transition and not duplicate_level_catch_up:
            _mark_level_up(current, previous.get("level"), current.get("level"))
        elif duplicate_level_catch_up:
            current["levelUpCatchUp"] = True

        current["experienceChange"] = (
            calculate_observed_experience_change(previous, current)
            if records_available else None
        )
        current["experienceRateChange"] = (
            calculate_observed_experience_rate_change(previous, current)
            if records_available else None
        )

        if (
            consecutive
            and current.get("ranking") is not None
            and previous.get("ranking") is not None
        ):
            current["rankingChange"] = previous["ranking"] - current["ranking"]
        else:
            current["rankingChange"] = None

    return history


def calculate_archive_history_changes(history):
    """30일·90일 기록에서 연속으로 확인된 날짜 사이의 변화만 계산한다."""
    for index, current in enumerate(history):
        current["experienceChange"] = None
        current["experienceRateChange"] = None
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

        consecutive = _are_consecutive_records(previous, current)
        previous_level = to_exact_integer(previous.get("level"))
        current_level = to_exact_integer(current.get("level"))
        level_changed = (
            previous_level is not None
            and current_level is not None
            and current_level > previous_level
        )
        rate_reset = is_experience_rate_reset(
            previous.get("experienceRate"), current.get("experienceRate")
        )
        duplicate_level_catch_up = (
            consecutive and previous.get("levelUp") is True and level_changed
        )
        transition = consecutive and (level_changed or rate_reset)
        if transition and not duplicate_level_catch_up:
            _mark_level_up(current, previous.get("level"), current.get("level"))
        elif duplicate_level_catch_up:
            current["levelUpCatchUp"] = True

        current["experienceChange"] = calculate_observed_experience_change(
            previous, current
        )
        current["experienceRateChange"] = calculate_observed_experience_rate_change(
            previous, current
        )

        if (
            consecutive
            and current.get("ranking") is not None
            and previous.get("ranking") is not None
        ):
            current["rankingChange"] = previous["ranking"] - current["ranking"]

    return history
