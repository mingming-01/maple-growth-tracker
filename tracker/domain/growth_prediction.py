"""현재 레벨 진행률의 관측 기반 레벨업 전망."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from tracker.domain.growth_calculations import _effective_level


def _valid_rate(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace("%", "").replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or result < 0 or result > 100:
        return None
    return result


def _record_date(record):
    try:
        return date.fromisoformat(str(record.get("date") or ""))
    except (TypeError, ValueError):
        return None


def build_growth_prediction(records, character=None, reference_date=None, window_days=7):
    """최근 동일 레벨의 일일 진행률 변화로 남은 비율과 예상 일수를 계산한다.

    절대 필요 EXP는 반올림된 API 진행률로 역산하지 않는다. Nexon API가 제공한
    진행률과 연속 관측값만으로 예상 일수를 만들고 표본 수를 함께 반환한다.
    """
    reference = reference_date if isinstance(reference_date, date) else date.today()
    available = []
    for record in records if isinstance(records, (list, tuple)) else []:
        if not isinstance(record, dict) or record.get("recordStatus") != "available":
            continue
        record_date = _record_date(record)
        level = _effective_level(record)
        rate = _valid_rate(record.get("experienceRate"))
        if record_date is None or level is None or rate is None:
            continue
        if record_date <= reference:
            available.append((record_date, level, rate, record))

    available.sort(key=lambda item: item[0])
    latest = available[-1] if available else None
    character_rate = _valid_rate((character or {}).get("experienceRate"))
    if latest is None:
        current_rate = character_rate
        try:
            current_level = int((character or {}).get("level"))
        except (TypeError, ValueError):
            current_level = None
        observation_date = reference
    else:
        observation_date, current_level, current_rate, _ = latest
        if observation_date == reference and character_rate is not None:
            current_rate = character_rate

    if current_rate is None or current_level is None:
        return None

    remaining_rate = max(Decimal("0"), Decimal("100") - current_rate)
    window_start = observation_date - timedelta(days=max(1, int(window_days)))
    samples = []
    for previous, current in zip(available, available[1:]):
        previous_date, previous_level, previous_rate, _ = previous
        current_date, next_level, next_rate, current_record = current
        if current_date < window_start or (current_date - previous_date).days != 1:
            continue
        if previous_level != next_level or next_level != current_level:
            continue
        if current_record.get("levelUp") is True:
            continue
        change = next_rate - previous_rate
        if change < 0:
            continue
        samples.append(change)

    average_progress_rate = (
        sum(samples, Decimal("0")) / Decimal(len(samples)) if samples else None
    )
    days = None
    expected_date = None
    if remaining_rate == 0:
        days = 0.0
        expected_date = observation_date.isoformat()
    elif average_progress_rate is not None and average_progress_rate > 0:
        exact_days = remaining_rate / average_progress_rate
        days = float(exact_days)
        calendar_days = int(exact_days.to_integral_value(rounding=ROUND_CEILING))
        expected_date = (observation_date + timedelta(days=calendar_days)).isoformat()

    confidence = (
        "insufficient" if len(samples) == 0
        else "initial" if len(samples) < 4
        else "established"
    )
    return {
        "currentLevel": current_level,
        "nextLevel": current_level + 1 if current_level is not None else None,
        "currentRate": float(current_rate),
        "remainingRate": float(remaining_rate),
        "requiredExp": None,
        "averageDailyProgressRate": (
            float(average_progress_rate) if average_progress_rate is not None else None
        ),
        "progressSamples": len(samples),
        "confidence": confidence,
        "days": days,
        "date": expected_date,
        "estimatedDays": days,
        "estimatedDate": expected_date,
        "observationDate": observation_date.isoformat(),
        "method": "same_level_observed_progress_rate",
    }
