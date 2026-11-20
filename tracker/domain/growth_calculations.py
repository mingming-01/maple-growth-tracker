"""성장 기록의 날짜 간 변화 계산을 담당한다."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


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


def _effective_level(record):
    """진행률 초기화로 확인된 레벨업을 랭킹 레벨 필드 지연보다 우선한다."""
    level = to_exact_integer(record.get("level")) if isinstance(record, dict) else None
    if isinstance(record, dict) and record.get("levelUp") is True:
        event_level = to_exact_integer(record.get("levelUpCurrentLevel"))
        if event_level is not None and (level is None or event_level >= level):
            return event_level
    return level


def calculate_observed_experience_change(previous, current):
    """연속된 동일 유효 레벨 스냅샷의 원본 EXP 차이를 반환한다.

    레벨업 당일에는 EXP 기준이 바뀌므로 그 날짜의 차이는 산출하지 않는다.
    다만 직전 날짜가 레벨업 이벤트이고 랭킹의 level 필드만 하루 늦게 갱신됐다면,
    직전 날짜의 levelUpCurrentLevel을 사용해 다음 날부터 새 레벨 내부의 증가량을
    계산한다.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    if previous.get("recordStatus") not in (None, "available"):
        return None
    if current.get("recordStatus") not in (None, "available"):
        return None
    if not _are_consecutive_records(previous, current):
        return None

    if is_experience_rate_reset(
        previous.get("experienceRate"), current.get("experienceRate")
    ):
        return None
    previous_level = _effective_level(previous)
    current_level = _effective_level(current)
    if previous_level is None or current_level is None or previous_level != current_level:
        return None
    previous_experience = to_exact_integer(previous.get("experience"))
    current_experience = to_exact_integer(current.get("experience"))
    if previous_experience is None or current_experience is None:
        return None
    if current_experience < previous_experience:
        return None
    return current_experience - previous_experience




def calculate_level_up_experience_change(previous, current):
    """레벨업 당일 총 획득량을 진행률 반올림 범위와 함께 계산한다.

    이전 레벨 잔여 EXP와 새 레벨의 현재 EXP를 합친다.
    진행률의 표시 정밀도는 원본 JSON에서 별도로 보존되지 않으므로,
    확인 가능한 소수 자릿수의 반 단위를 적용해 하한·상한을 계산한다.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    if previous.get("recordStatus") not in (None, "available"):
        return None
    if current.get("recordStatus") not in (None, "available"):
        return None
    if not _are_consecutive_records(previous, current):
        return None

    previous_level = _effective_level(previous)
    current_level = _effective_level(current)
    rate_reset = is_experience_rate_reset(
        previous.get("experienceRate"), current.get("experienceRate")
    )
    level_difference = (
        current_level - previous_level
        if previous_level is not None and current_level is not None else None
    )
    if not rate_reset and level_difference != 1:
        return None
    if level_difference is not None and level_difference not in (0, 1):
        return None

    try:
        previous_rate = Decimal(
            str(previous.get("experienceRate")).replace("%", "").replace(",", "").strip()
        )
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not previous_rate.is_finite() or not Decimal("0") < previous_rate <= Decimal("100"):
        return None

    previous_experience = to_exact_integer(previous.get("experience"))
    current_experience = to_exact_integer(current.get("experience"))
    if (
        previous_experience is None or previous_experience < 0
        or current_experience is None or current_experience < 0
    ):
        return None

    # JSON 숫자 파싱과 저장 과정에서 끝의 0은 보존되지 않는다.
    # 보이는 소수 자릿수보다 더 높은 정밀도를 가정하지 않는다.
    visible_resolution = Decimal(1).scaleb(previous_rate.as_tuple().exponent)
    rate_resolution = max(visible_resolution, Decimal("0.001"))
    half_resolution = rate_resolution / Decimal("2")
    minimum_rate = max(Decimal("0.000001"), previous_rate - half_resolution)
    maximum_rate = min(Decimal("100"), previous_rate + half_resolution)

    previous_exp = Decimal(previous_experience)
    new_level_exp = Decimal(current_experience)

    def daily_gain(rate):
        return previous_exp * Decimal("100") / rate - previous_exp + new_level_exp

    point = daily_gain(previous_rate)
    lower = max(Decimal("0"), daily_gain(maximum_rate))
    upper = max(lower, daily_gain(minimum_rate))

    return {
        "value": int(point.to_integral_value(rounding=ROUND_HALF_UP)),
        "lowerBound": int(lower.to_integral_value(rounding=ROUND_FLOOR)),
        "upperBound": int(upper.to_integral_value(rounding=ROUND_CEILING)),
        "rateResolution": str(rate_resolution),
        "method": "previous_level_remaining_plus_new_level_exp",
    }


def _set_experience_change_metadata(record, result, kind):
    record["experienceChange"] = result["value"] if result else None
    record["experienceChangeKind"] = kind if result else "unavailable"
    record["experienceChangeLowerBound"] = result["lowerBound"] if result else None
    record["experienceChangeUpperBound"] = result["upperBound"] if result else None
    record["experienceChangeMethod"] = result["method"] if result else None
    record["experienceChangeRateResolution"] = result["rateResolution"] if result else None


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
    if is_experience_rate_reset(previous.get("experienceRate"), current.get("experienceRate")):
        return None
    previous_level = _effective_level(previous)
    current_level = _effective_level(current)
    if previous_level is None or current_level is None or previous_level != current_level:
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
        _set_experience_change_metadata(current, None, "unavailable")
        if index == 0:
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

        if records_available and current.get("levelUp"):
            boundary_change = calculate_level_up_experience_change(previous, current)
            _set_experience_change_metadata(current, boundary_change, "level_up_reconstructed")
        elif records_available:
            observed_change = calculate_observed_experience_change(previous, current)
            observed_result = ({
                "value": observed_change,
                "lowerBound": observed_change,
                "upperBound": observed_change,
                "method": "same_level_snapshot_delta",
                "rateResolution": None,
            } if observed_change is not None else None)
            _set_experience_change_metadata(current, observed_result, "same_level_snapshot")
        else:
            _set_experience_change_metadata(current, None, "unavailable")

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
        _set_experience_change_metadata(current, None, "unavailable")

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

        if current.get("levelUp"):
            boundary_change = calculate_level_up_experience_change(previous, current)
            _set_experience_change_metadata(current, boundary_change, "level_up_reconstructed")
        else:
            observed_change = calculate_observed_experience_change(previous, current)
            observed_result = ({
                "value": observed_change,
                "lowerBound": observed_change,
                "upperBound": observed_change,
                "method": "same_level_snapshot_delta",
                "rateResolution": None,
            } if observed_change is not None else None)
            _set_experience_change_metadata(current, observed_result, "same_level_snapshot")

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
