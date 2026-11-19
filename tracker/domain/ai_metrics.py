"""서버가 보관한 성장 기록으로 AI 입력 지표를 다시 계산한다."""
from datetime import date, timedelta
from math import isfinite

from tracker.domain.growth_calculations import (
    calculate_observed_experience_change,
    is_experience_rate_reset,
    to_exact_integer,
)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def build_server_growth_metrics(character, records, reference_date=None, period_days=7):
    """클라이언트가 보낸 계산 결과를 사용하지 않고 저장된 관측 기록만 계산한다."""
    today = reference_date if isinstance(reference_date, date) else date.today()
    by_date = {}
    for record in records if isinstance(records, (list, tuple)) else []:
        if not isinstance(record, dict) or record.get("recordStatus") != "available":
            continue
        try:
            record_date = date.fromisoformat(str(record.get("date", "")))
        except (TypeError, ValueError):
            continue
        level = to_exact_integer(record.get("level"))
        experience = to_exact_integer(record.get("experience"))
        if record_date > today or level is None or experience is None:
            continue
        raw_rank = _number(record.get("ranking"))
        try:
            ranking_source_date = date.fromisoformat(
                str(record.get("rankingSourceDate") or "")
            )
        except (TypeError, ValueError):
            ranking_source_date = None
        rank_is_verified = (
            record.get("rankingScope") == "overall"
            and ranking_source_date == record_date
            and raw_rank is not None
            and raw_rank > 0
            and raw_rank.is_integer()
        )
        by_date[record_date] = {
            "date": record_date.isoformat(),
            "level": int(level),
            "experience": int(experience),
            "experienceRate": _number(record.get("experienceRate")),
            "ranking": int(raw_rank) if rank_is_verified else None,
            "rankingScope": "overall" if rank_is_verified else None,
            "rankingSourceDate": record_date.isoformat() if rank_is_verified else None,
            "recordStatus": "available",
            "experienceChange": None,
            "rankingChange": None,
            "levelUp": False,
            "levelUpPreviousLevel": None,
            "levelUpCurrentLevel": None,
            "levelUpCatchUp": False,
        }

    history = [by_date[key] for key in sorted(by_date)]
    changes = []
    level_ups = []
    for index, current in enumerate(history):
        if index == 0:
            continue
        previous = history[index - 1]
        previous_date = date.fromisoformat(previous["date"])
        current_date = date.fromisoformat(current["date"])
        # Events are date-scoped and require consecutive daily snapshots.
        if (current_date - previous_date).days != 1:
            continue

        if current.get("ranking") is not None and previous.get("ranking") is not None:
            current["rankingChange"] = previous["ranking"] - current["ranking"]

        level_changed = current["level"] > previous["level"]
        rate_reset = is_experience_rate_reset(
            previous.get("experienceRate"), current.get("experienceRate")
        )
        duplicate_level_catch_up = previous.get("levelUp") is True and level_changed
        if duplicate_level_catch_up:
            current["levelUpCatchUp"] = True
        if (level_changed or rate_reset) and not duplicate_level_catch_up:
            current["levelUp"] = True
            current["levelUpPreviousLevel"] = previous["level"]
            current["levelUpCurrentLevel"] = (
                current["level"] if level_changed else previous["level"] + 1
            )
            level_ups.append({
                "date": current["date"],
                "previousLevel": current["levelUpPreviousLevel"],
                "currentLevel": current["levelUpCurrentLevel"],
            })

        # 레벨업 경계에서는 레벨별 필요 EXP 원본이 없으면 일일 획득량을 계산하지 않는다.
        change = calculate_observed_experience_change(previous, current)
        if change is None:
            continue
        current["experienceChange"] = change
        changes.append({"date": current_date, "experience": change})
    values = [item["experience"] for item in changes]
    midpoint = len(values) // 2
    earlier = values[:midpoint]
    recent = values[midpoint:]
    earlier_average = sum(earlier) / len(earlier) if earlier else None
    recent_average = sum(recent) / len(recent) if recent else None
    if earlier_average is None or recent_average is None:
        direction = "insufficient_data"
    elif recent_average > earlier_average:
        direction = "increased"
    elif recent_average < earlier_average:
        direction = "decreased"
    else:
        direction = "stable"

    verified_ranks = [
        item for item in history if item["ranking"] is not None
    ]
    ranking_change = (
        verified_ranks[-2]["ranking"] - verified_ranks[-1]["ranking"]
        if len(verified_ranks) >= 2
        and (
            date.fromisoformat(verified_ranks[-1]["date"])
            - date.fromisoformat(verified_ranks[-2]["date"])
        ).days == 1
        else None
    )
    current_rate = _number((character or {}).get("experienceRate"))
    if current_rate is not None and not 0 <= current_rate <= 100:
        current_rate = None

    period_start = today - timedelta(days=max(1, int(period_days)) - 1)
    period_records = [
        item for item in history
        if period_start <= date.fromisoformat(item["date"]) <= today
    ]
    period_changes = [
        item["experienceChange"] for item in period_records
        if item["experienceChange"] is not None
    ]
    expected_days = (today - period_start).days + 1
    period_summary = {
        "startDate": period_start.isoformat(),
        "endDate": today.isoformat(),
        "expectedSnapshots": expected_days,
        "availableSnapshots": len(period_records),
        "coveragePercent": round(len(period_records) / expected_days * 100, 1) if expected_days else 0,
        "validGrowthIntervals": len(period_changes),
        "averageDailyExperience": round(sum(period_changes) / len(period_changes), 2) if period_changes else None,
        "observedExperienceSum": sum(period_changes) if period_changes else None,
        "levelUpIntervals": sum(1 for item in period_records if item["levelUp"]),
    }

    return {
        "history": history,
        "metrics": {
            "validGrowthDays": sum(1 for value in values if value > 0),
            "observedChangeDays": len(values),
            "zeroGrowthDays": sum(1 for value in values if value == 0),
            "negativeGrowthDays": sum(1 for value in values if value < 0),
            "recordedDays": len(history),
            "latestDailyGrowth": values[-1] if values else None,
            "averageDailyGrowth": sum(values) / len(values) if values else None,
            "highestDailyGrowth": max(values) if values else None,
            "lowestDailyGrowth": min(values) if values else None,
            "sevenDayGrowth": sum(
                item["experience"] for item in changes
                if item["date"] >= today - timedelta(days=6)
            ) if changes else None,
            "rankingChange": ranking_change,
            "levelProgress": {
                "currentRate": current_rate,
                "remainingRate": round(100 - current_rate, 4) if current_rate is not None else None,
            },
            "growthComparison": {
                "earlierAverage": earlier_average,
                "recentAverage": recent_average,
                "direction": direction,
            },
            "levelUps": level_ups,
            "prediction": None,
        },
        "periodSummary": period_summary,
    }
