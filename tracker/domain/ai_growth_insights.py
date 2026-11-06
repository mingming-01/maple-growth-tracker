"""Deterministic growth insights for AI reports.

All values in this module are derived from observed daily snapshots. Missing
calendar days and level-up transitions are never interpolated or estimated.
"""
from datetime import date, timedelta
from math import isfinite


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _is_available(record):
    if not isinstance(record, dict):
        return False
    if record.get("recordStatus") not in (None, "available"):
        return False
    return (
        _number(record.get("level")) is not None
        and _number(record.get("experience")) is not None
    )


def _period_summary(by_date, start_date, end_date):
    expected_days = (end_date - start_date).days + 1
    available_snapshots = sum(
        _is_available(by_date.get(start_date + timedelta(days=offset), {}))
        for offset in range(expected_days)
    )
    changes = []
    level_ups = 0

    for offset in range(expected_days):
        current_date = start_date + timedelta(days=offset)
        previous_date = current_date - timedelta(days=1)
        current = by_date.get(current_date)
        previous = by_date.get(previous_date)
        if not _is_available(current) or not _is_available(previous):
            continue

        current_level = _number(current.get("level"))
        previous_level = _number(previous.get("level"))
        current_exp = _number(current.get("experience"))
        previous_exp = _number(previous.get("experience"))

        if current_level > previous_level:
            level_ups += 1
            continue
        if current_level != previous_level or current_exp < previous_exp:
            continue

        changes.append({
            "date": current_date,
            "experience": current_exp - previous_exp,
            "weekday": current_date.weekday(),
        })

    average = (
        sum(item["experience"] for item in changes) / len(changes)
        if changes else None
    )
    return {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "expectedSnapshots": expected_days,
        "availableSnapshots": available_snapshots,
        "validGrowthIntervals": len(changes),
        "levelUpIntervals": level_ups,
        "averageDailyExperience": round(average, 2) if average is not None else None,
        "observedExperienceSum": round(
            sum(item["experience"] for item in changes), 2
        ) if changes else None,
        "_changes": changes,
    }


def build_growth_insights(records, reference_date=None, window_days=7):
    """Build a comparable recent/prior period summary from saved snapshots.

    A complete pair of seven-day windows requires fifteen snapshots: the
    snapshot immediately before the comparison window plus fourteen days.
    """
    if window_days != 7:
        raise ValueError("Only seven-day comparison windows are supported.")

    requested_reference = _parse_date(reference_date) or date.today()
    by_date = {}
    for record in records if isinstance(records, (list, tuple)) else []:
        if not isinstance(record, dict):
            continue
        record_date = _parse_date(record.get("date"))
        if record_date is None:
            continue
        current = by_date.get(record_date)
        # Prefer a confirmed record over an empty/unavailable duplicate.
        if current is None or (_is_available(record) and not _is_available(current)):
            by_date[record_date] = record

    available_dates = [
        record_date for record_date, record in by_date.items()
        if _is_available(record)
    ]
    effective_reference = min(requested_reference, max(available_dates)) if available_dates else requested_reference

    recent_end = effective_reference
    recent_start = recent_end - timedelta(days=window_days - 1)
    previous_end = recent_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=window_days - 1)
    snapshot_start = previous_start - timedelta(days=1)
    expected_snapshots = (effective_reference - snapshot_start).days + 1

    recent = _period_summary(by_date, recent_start, recent_end)
    previous = _period_summary(by_date, previous_start, previous_end)

    recent_changes = recent.pop("_changes")
    previous_changes = previous.pop("_changes")
    combined_changes = previous_changes + recent_changes
    weekday_changes = [item for item in combined_changes if item["weekday"] < 5]
    weekend_changes = [item for item in combined_changes if item["weekday"] >= 5]

    total_available = sum(
        _is_available(by_date.get(snapshot_start + timedelta(days=offset), {}))
        for offset in range(expected_snapshots)
    )
    missing_snapshots = max(0, expected_snapshots - total_available)
    coverage_percent = (
        total_available / expected_snapshots * 100
        if expected_snapshots else 0
    )

    comparison_ready = (
        recent["validGrowthIntervals"] >= 4
        and previous["validGrowthIntervals"] >= 4
        and recent["averageDailyExperience"] is not None
        and previous["averageDailyExperience"] is not None
        and previous["averageDailyExperience"] > 0
    )
    change_percent = None
    direction = "insufficient"
    if comparison_ready:
        change_percent = (
            (recent["averageDailyExperience"] - previous["averageDailyExperience"])
            / abs(previous["averageDailyExperience"])
        ) * 100
        direction = (
            "increase" if change_percent > 0.5
            else "decrease" if change_percent < -0.5
            else "stable"
        )

    weekday_average = (
        sum(item["experience"] for item in weekday_changes) / len(weekday_changes)
        if weekday_changes else None
    )
    weekend_average = (
        sum(item["experience"] for item in weekend_changes) / len(weekend_changes)
        if weekend_changes else None
    )
    weekend_total = sum(item["experience"] for item in weekend_changes)
    all_total = sum(item["experience"] for item in combined_changes)
    weekday_weekend_ready = (
        len(weekday_changes) >= 4 and len(weekend_changes) >= 2 and all_total > 0
    )

    if total_available >= 12 and recent["validGrowthIntervals"] >= 4 and previous["validGrowthIntervals"] >= 4:
        quality = "high"
        quality_label = "높음"
    elif total_available >= 8 and len(combined_changes) >= 4:
        quality = "medium"
        quality_label = "보통"
    else:
        quality = "low"
        quality_label = "낮음"

    return {
        "basis": {
            "referenceDate": effective_reference.isoformat(),
            "periodStartDate": previous_start.isoformat(),
            "periodEndDate": recent_end.isoformat(),
            "snapshotStartDate": snapshot_start.isoformat(),
            "windowDays": window_days,
            "expectedSnapshots": expected_snapshots,
            "availableSnapshots": total_available,
            "missingSnapshots": missing_snapshots,
            "coveragePercent": round(coverage_percent, 1),
            "dataQuality": quality,
            "dataQualityLabel": quality_label,
        },
        "recentPeriod": recent,
        "previousPeriod": previous,
        "weekOverWeek": {
            "status": "available" if comparison_ready else "insufficient_data",
            "averageDailyGrowthChangePercent": round(change_percent, 1) if change_percent is not None else None,
            "direction": direction,
        },
        "weekdayWeekend": {
            "status": "available" if weekday_weekend_ready else "insufficient_data",
            "weekdaySamples": len(weekday_changes),
            "weekendSamples": len(weekend_changes),
            "weekdayAverageExperience": round(weekday_average, 2) if weekday_average is not None else None,
            "weekendAverageExperience": round(weekend_average, 2) if weekend_average is not None else None,
            "weekendSharePercent": round(weekend_total / all_total * 100, 1) if weekday_weekend_ready else None,
        },
    }
