"""현재 레벨의 필요 EXP 역산과 관측 기반 레벨업 전망."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from tracker.domain.growth_calculations import _effective_level, to_exact_integer


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace("%", "").replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _valid_rate(value):
    result = _decimal(value)
    if result is None or result < 0 or result > 100:
        return None
    return result


def _record_date(record):
    try:
        return date.fromisoformat(str(record.get("date") or ""))
    except (TypeError, ValueError):
        return None


def build_growth_prediction(records, character=None, reference_date=None, window_days=7):
    """API의 현재 EXP/진행률로 남은 EXP를 역산하고 동일 레벨의 관측 속도로 예측한다.

    Nexon이 반환한 진행률은 표시 정밀도로 반올림되어 있을 수 있으므로
    requiredExp는 절대 기준값이 아닌 역산 추정치로 반환한다.
    """
    reference = reference_date if isinstance(reference_date, date) else date.today()
    available = []
    for record in records if isinstance(records, (list, tuple)) else []:
        if not isinstance(record, dict) or record.get("recordStatus") != "available":
            continue
        record_date = _record_date(record)
        level = _effective_level(record)
        experience = to_exact_integer(record.get("experience"))
        rate = _valid_rate(record.get("experienceRate"))
        if record_date is None or level is None or experience is None or experience < 0:
            continue
        if record_date <= reference:
            available.append((record_date, level, experience, rate, record))

    available.sort(key=lambda item: item[0])
    latest = available[-1] if available else None
    profile = character if isinstance(character, dict) else {}

    profile_level = to_exact_integer(profile.get("level"))
    profile_experience = to_exact_integer(profile.get("experience"))
    profile_rate = _valid_rate(profile.get("experienceRate"))

    latest_level = latest[1] if latest else None

    # EXP, rate, and level must come from the same snapshot. Never combine a
    # current profile rate with an older history EXP (or vice versa).
    if profile_experience is not None and profile_rate is not None:
        current_level = profile_level if profile_level is not None else latest_level
        current_experience = profile_experience
        current_rate = profile_rate
        observation_date = reference
    elif latest is not None:
        current_level = latest_level
        current_experience = latest[2]
        current_rate = latest[3]
        observation_date = latest[0]
    else:
        current_level = profile_level
        current_experience = profile_experience
        current_rate = profile_rate
        observation_date = reference

    if current_rate is None or current_level is None:
        return None

    remaining_rate = max(Decimal("0"), Decimal("100") - current_rate)
    estimated_total_experience = None
    required_experience = None
    if current_experience is not None and current_experience >= 0 and current_rate > 0:
        estimated_total_experience = (
            Decimal(current_experience) * Decimal("100") / current_rate
        )
        remaining = max(Decimal("0"), estimated_total_experience - Decimal(current_experience))
        required_experience = int(
            remaining.to_integral_value(rounding=ROUND_HALF_UP)
        )

    window_start = observation_date - timedelta(days=max(1, int(window_days)))
    experience_samples = []
    progress_samples = []
    for previous, current in zip(available, available[1:]):
        previous_date, previous_level, previous_exp, previous_rate, _ = previous
        current_date, next_level, next_exp, next_rate, current_record = current
        if current_date < window_start or (current_date - previous_date).days != 1:
            continue
        if previous_level != next_level or next_level != current_level:
            continue
        if current_record.get("levelUp") is True:
            continue

        raw_change = current_record.get("experienceChange")
        change = _decimal(raw_change)
        if change is None:
            # History records produced by older clients may not carry the
            # derived field. Reconstruct only a consecutive same-level delta.
            change = Decimal(next_exp) - Decimal(previous_exp)
        if change >= 0:
            experience_samples.append(change)

        if previous_rate is not None and next_rate is not None:
            rate_change = next_rate - previous_rate
            if rate_change >= 0:
                progress_samples.append(rate_change)

    average_daily_experience = (
        sum(experience_samples, Decimal("0")) / Decimal(len(experience_samples))
        if experience_samples else None
    )
    average_daily_progress_rate = (
        sum(progress_samples, Decimal("0")) / Decimal(len(progress_samples))
        if progress_samples else None
    )

    days = None
    expected_date = None
    if required_experience == 0:
        days = 0.0
        expected_date = observation_date.isoformat()
    elif required_experience is not None and average_daily_experience is not None and average_daily_experience > 0:
        exact_days = Decimal(required_experience) / average_daily_experience
        days = float(exact_days)
        calendar_days = int(exact_days.to_integral_value(rounding=ROUND_CEILING))
        expected_date = (observation_date + timedelta(days=calendar_days)).isoformat()

    sample_count = len(experience_samples)
    confidence = (
        "insufficient" if sample_count == 0
        else "initial" if sample_count < 4
        else "established"
    )
    return {
        "currentLevel": current_level,
        "nextLevel": current_level + 1,
        "currentExperience": current_experience,
        "currentRate": float(current_rate),
        "remainingRate": float(remaining_rate),
        "estimatedTotalExp": (
            int(estimated_total_experience.to_integral_value(rounding=ROUND_HALF_UP))
            if estimated_total_experience is not None else None
        ),
        "requiredExp": required_experience,
        "requiredExpEstimated": required_experience is not None,
        "requiredExpMethod": "experience_rate_reverse_estimate",
        "averageGrowth": (
            float(average_daily_experience)
            if average_daily_experience is not None else None
        ),
        "experienceSamples": sample_count,
        "averageDailyProgressRate": (
            float(average_daily_progress_rate)
            if average_daily_progress_rate is not None else None
        ),
        "progressSamples": len(progress_samples),
        "confidence": confidence,
        "days": days,
        "date": expected_date,
        "estimatedDays": days,
        "estimatedDate": expected_date,
        "observationDate": observation_date.isoformat(),
        "method": "experience_rate_reverse_estimate",
    }
