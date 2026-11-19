"""서버가 보관한 성장 기록으로 AI 입력 지표를 계산한다."""
from datetime import date, timedelta
from math import isfinite

from tracker.domain.growth_calculations import (
    calculate_recent_history_changes,
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
    """저장된 스냅샷을 한 번 정규화한 뒤 기간별 통계를 파생한다."""
    today = reference_date if isinstance(reference_date, date) else date.today()
    period_days = max(1, int(period_days))
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
            "level": level,
            "experience": experience,
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

    # /api/history와 동일한 정규화 함수를 사용해 날짜 간 변화를 한 번만 계산한다.
    history = [by_date[key] for key in sorted(by_date)]
    calculate_recent_history_changes(history)

    period_start = today - timedelta(days=period_days - 1)
    period_records = [
        item for item in history
        if period_start <= date.fromisoformat(item["date"]) <= today
    ]
    period_changes = [
        item["experienceChange"] for item in period_records
        if item["experienceChange"] is not None
    ]
    all_changes = [
        {
            "date": date.fromisoformat(item["date"]),
            "experience": item["experienceChange"],
        }
        for item in history
        if item["experienceChange"] is not None
    ]

    # 성장 흐름 비교는 최근 14일의 정규화된 변화량을 앞뒤 기간으로 나눈다.
    comparison_start = today - timedelta(days=13)
    comparison_values = [
        item["experience"] for item in all_changes
        if comparison_start <= item["date"] <= today
    ]
    midpoint = len(comparison_values) // 2
    earlier = comparison_values[:midpoint]
    recent = comparison_values[midpoint:]
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

    seven_day_start = today - timedelta(days=6)
    seven_day_changes = [
        item["experience"] for item in all_changes
        if seven_day_start <= item["date"] <= today
    ]
    level_ups = [
        {
            "date": item["date"],
            "previousLevel": item["levelUpPreviousLevel"],
            "currentLevel": item["levelUpCurrentLevel"],
        }
        for item in period_records if item["levelUp"]
    ]

    period_summary = {
        "startDate": period_start.isoformat(),
        "endDate": today.isoformat(),
        "expectedSnapshots": period_days,
        "availableSnapshots": len(period_records),
        "coveragePercent": round(len(period_records) / period_days * 100, 1),
        "validGrowthIntervals": len(period_changes),
        "averageDailyExperience": (
            round(sum(period_changes) / len(period_changes), 2)
            if period_changes else None
        ),
        "observedExperienceSum": sum(period_changes) if period_changes else None,
        "levelUpIntervals": len(level_ups),
    }

    period_values = period_changes
    return {
        "history": history,
        "metrics": {
            "validGrowthDays": sum(1 for value in period_values if value > 0),
            "observedChangeDays": len(period_values),
            "zeroGrowthDays": sum(1 for value in period_values if value == 0),
            "negativeGrowthDays": sum(1 for value in period_values if value < 0),
            "recordedDays": len(period_records),
            "latestDailyGrowth": period_values[-1] if period_values else None,
            "averageDailyGrowth": (
                sum(period_values) / len(period_values) if period_values else None
            ),
            "highestDailyGrowth": max(period_values) if period_values else None,
            "lowestDailyGrowth": min(period_values) if period_values else None,
            "sevenDayGrowth": sum(seven_day_changes) if seven_day_changes else None,
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
