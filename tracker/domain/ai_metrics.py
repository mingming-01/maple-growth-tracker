"""서버가 보관한 성장 기록으로 AI 입력 지표를 계산한다."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

from tracker.domain.growth_calculations import (
    calculate_recent_history_changes,
    to_exact_integer,
)
from tracker.domain.growth_prediction import build_growth_prediction


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _build_long_period_growth_trend(period_records, period_start, period_end):
    """선택 기간을 달력 기준 앞·뒤 절반으로 나누고 실제 일별 변화만 비교한다."""
    total_days = (period_end - period_start).days + 1
    first_half_days = total_days // 2
    if first_half_days < 1 or total_days - first_half_days < 1:
        return None

    first_start = period_start
    first_end = first_start + timedelta(days=first_half_days - 1)
    second_start = first_end + timedelta(days=1)
    second_end = period_end

    def summarize(start_date, end_date):
        changes = []
        for record in period_records:
            try:
                record_date = date.fromisoformat(str(record.get("date", "")))
            except (TypeError, ValueError):
                continue
            if not start_date <= record_date <= end_date:
                continue
            change = to_exact_integer(record.get("experienceChange"))
            if change is not None and change >= 0:
                changes.append(change)

        expected_intervals = (end_date - start_date).days + 1
        # 각 구간의 달력 일수 중 40% 이상, 최소 4개의 실제 변화가 있어야
        # 초반·후반의 평균을 비교 가능한 표본으로 취급한다.
        minimum_samples = max(4, (expected_intervals * 2 + 4) // 5)
        return {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "expectedIntervals": expected_intervals,
            "minimumRequiredIntervals": minimum_samples,
            "validGrowthIntervals": len(changes),
            "observedExperienceSum": sum(changes) if changes else None,
        }

    first_half = summarize(first_start, first_end)
    second_half = summarize(second_start, second_end)
    first_count = first_half["validGrowthIntervals"]
    second_count = second_half["validGrowthIntervals"]
    first_sum = first_half["observedExperienceSum"] or 0
    second_sum = second_half["observedExperienceSum"] or 0

    result = {
        "status": "insufficient_data",
        "comparisonMethod": "calendar_halves",
        "firstHalf": first_half,
        "secondHalf": second_half,
        "direction": "insufficient_data",
        "strength": None,
        "changePercent": None,
    }
    if (
        first_count < first_half["minimumRequiredIntervals"]
        or second_count < second_half["minimumRequiredIntervals"]
    ):
        return result

    # 분모를 곱해 평균끼리 비교하므로 큰 경험치 값을 float로 바꾸지 않는다.
    difference = second_sum * first_count - first_sum * second_count
    if difference == 0:
        direction = "stable"
        strength = None
    elif first_sum == 0:
        direction = "increase" if difference > 0 else "decrease"
        strength = "unknown"
    else:
        change_percent = (
            Decimal(difference) * Decimal("100")
            / Decimal(first_sum * second_count)
        )
        if change_percent > Decimal("5"):
            direction = "increase"
            strength = "strong" if change_percent >= Decimal("20") else "moderate"
        elif change_percent < Decimal("-5"):
            direction = "decrease"
            strength = "strong" if change_percent <= Decimal("-20") else "moderate"
        else:
            direction = "stable"
            strength = None
        result["changePercent"] = float(
            change_percent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        )

    result.update({
        "status": "available",
        "direction": direction,
        "strength": strength,
    })
    return result


def build_server_growth_metrics(character, records, reference_date=None, period_days=7):
    """저장된 스냅샷을 한 번 정규화한 뒤 기간별 통계를 파생한다."""
    today = reference_date if isinstance(reference_date, date) else date.today()
    period_days = max(1, int(period_days))
    by_date = {}
    source_by_date = {}
    for record in records if isinstance(records, (list, tuple)) else []:
        if not isinstance(record, dict):
            continue
        try:
            record_date = date.fromisoformat(str(record.get("date", "")))
        except (TypeError, ValueError):
            continue
        if record_date > today:
            continue
        source_by_date[record_date] = record
        if record.get("recordStatus") != "available":
            continue
        level = to_exact_integer(record.get("level"))
        experience = to_exact_integer(record.get("experience"))
        if level is None or experience is None:
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
    period_source_records = [
        record for record_date, record in source_by_date.items()
        if period_start <= record_date <= today
    ]
    not_ready_days = sum(
        record.get("recordStatus") == "not_ready" for record in period_source_records
    )
    not_collected_days = sum(
        record.get("recordStatus") == "not_collected" for record in period_source_records
    )
    unavailable_days = sum(
        record.get("recordStatus") == "unavailable" for record in period_source_records
    )
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
    prediction = build_growth_prediction(
        history,
        character=character,
        reference_date=today,
        window_days=7,
    )
    current_rate = (
        prediction.get("currentRate") if prediction is not None
        else _number((character or {}).get("experienceRate"))
    )
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
    verified_period_ranks = [
        item for item in period_records if item["ranking"] is not None
    ]
    period_ranking_change = (
        verified_period_ranks[0]["ranking"] - verified_period_ranks[-1]["ranking"]
        if len(verified_period_ranks) >= 2 else None
    )
    positive_period_changes = [
        (item["date"], item["experienceChange"])
        for item in period_records
        if item["experienceChange"] is not None and item["experienceChange"] > 0
    ]
    best_period_growth = max(positive_period_changes, key=lambda pair: pair[1]) if positive_period_changes else None

    timeline = []
    for item in period_records:
        if item["levelUp"]:
            level_up_description = (
                f"Lv. {item['levelUpPreviousLevel']}에서 레벨업"
                if item["levelUpPreviousLevel"] is not None else "레벨업 기록 확인"
            )
            if item["experienceChange"] is None:
                level_up_description += " · 당일 경험치 증가량 미확인"
            timeline.append({
                "type": "level-up", "date": item["date"],
                "title": f"Lv. {item['levelUpCurrentLevel'] or item['level']} 달성",
                "description": level_up_description,
                "priority": 0,
            })
    if best_period_growth:
        timeline.append({
            "type": "best-growth", "date": best_period_growth[0],
            "title": "기간 최고 성장일",
            "description": f"+{best_period_growth[1] / 1_000_000_000_000:.2f}조 경험치",
            "priority": 1,
        })
    ranking_records = [
        item for item in period_records
        if item["rankingChange"] is not None and item["rankingChange"] > 0
    ]
    if ranking_records:
        best_ranking = max(ranking_records, key=lambda item: item["rankingChange"])
        timeline.append({
            "type": "ranking", "date": best_ranking["date"],
            "title": "랭킹 최고 상승일",
            "description": f"전일 대비 {best_ranking['rankingChange']:,}위 상승",
            "priority": 2,
        })
    latest_available = period_records[-1] if period_records else None
    if latest_available and not any(
        event["date"] == latest_available["date"] and event["type"] == "level-up"
        for event in timeline
    ):
        timeline.append({
            "type": "latest", "date": latest_available["date"],
            "title": "최근 정상 기록",
            "description": (
                f"Lv. {latest_available['level']} · 경험치 "
                f"{latest_available['experience']:,}"
            ),
            "priority": 3,
        })
    timeline = sorted(
        timeline,
        key=lambda event: (event["date"], -event["priority"]),
        reverse=True,
    )[:8]

    period_trend = (
        _build_long_period_growth_trend(period_records, period_start, today)
        if period_days in (30, 90) else None
    )

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
        "growth": sum(period_changes) if period_changes else None,
        "averageGrowth": sum(period_changes) / len(period_changes) if period_changes else None,
        "confirmedChangeDays": len(period_changes),
        "bestDailyGrowth": best_period_growth[1] if best_period_growth else None,
        "bestDailyGrowthDate": best_period_growth[0] if best_period_growth else None,
        "growthDays": sum(value > 0 for value in period_changes),
        "zeroGrowthDays": sum(value == 0 for value in period_changes),
        "negativeGrowthDays": sum(value < 0 for value in period_changes),
        "levelUpCount": len(level_ups),
        "levelUpDates": [item["date"] for item in level_ups],
        "rankingChange": period_ranking_change,
        "availableDays": len(period_records),
        "notReadyDays": not_ready_days,
        "notCollectedDays": not_collected_days,
        "unavailableDays": unavailable_days,
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
                "dailyProgressRate": (
                    prediction.get("averageDailyProgressRate")
                    if prediction is not None else None
                ),
            },
            "growthComparison": {
                "earlierAverage": earlier_average,
                "recentAverage": recent_average,
                "direction": direction,
            },
            "periodTrend": period_trend,
            "levelUps": level_ups,
            "timeline": timeline,
            "prediction": prediction,
        },
        "periodSummary": period_summary,
    }
