"""AI 응답을 화면에 전달하기 전 표시 형식과 내부 필드명을 정리한다."""
import re
from datetime import date



def validate_growth_report(value):
    """성장 리포트의 필수 구분과 한국어 출력 여부를 검사한다."""
    text = str(value or "")
    required_sections = (
        "[성장 패턴]",
        "[성장 변화]",
        "[레벨업 분석]",
        "[성장 전망]",
        "[AI 코멘트]",
    )
    if any(section not in text for section in required_sections):
        return False
    # CJK 한자/가나 문자가 섞인 응답은 그대로 노출하거나 캐시하지 않는다.
    if re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF]", text):
        return False
    return True

def sanitize_ai_text(value, expected_date=None):
    """모델 응답의 마크다운과 내부 표현을 정리해 일반 문장만 화면에 전달한다."""
    text = str(value or "")
    text = re.sub(r"\x60\x60\x60[\w-]*", "", text)
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    internal_terms = {
        r"\bmetrics\.prediction\b": "성장 전망",
        r"\brankingChange\b": "랭킹 변화",
        r"\bvalidGrowthDays\b": "성장 기록",
        r"\brecordedDays\b": "기록된 날짜",
        r"\blatestDailyGrowth\b": "최근 성장 흐름",
        r"\baverageDailyGrowth\b": "평균 성장 흐름",
        r"\bhighestDailyGrowth\b": "높은 성장 기록",
        r"\blowestDailyGrowth\b": "낮은 성장 기록",
        r"\bsevenDayGrowth\b": "최근 성장 기록",
        r"\bgrowthComparison\b": "성장 흐름 비교",
        r"\bearlierAverage\b": "이전 성장 흐름",
        r"\brecentAverage\b": "최근 성장 흐름",
        r"\blevelUps\b": "레벨업 기록",
        r"\bestimatedDays\b": "예상 기간",
        r"\bestimatedDate\b": "예상 날짜",
        r"\brequiredExperience\b": "필요 경험치",
        r"\binsufficient_data\b": "기록 부족",
        r"\bincreased\b": "증가한 흐름",
        r"\bdecreased\b": "감소한 흐름",
        r"\bstable\b": "일정한 흐름",
        r"\bnull\b|\bundefined\b": "확인되지 않음",
    }
    for pattern, replacement in internal_terms.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(
        r"\(?\s*(?:\d{1,3}(?:,\d{3}){2,}|\d{10,})(?:\.\d+)?\s*\)?",
        "해당 경험치 수치",
        text,
    )
    if expected_date:
        try:
            prediction_date = date.fromisoformat(str(expected_date))
            date_label = f"{prediction_date.month}월 {prediction_date.day}일"

            # Normalize only the actual prediction date. Historical event dates
            # in the same AI response must remain tied to their source records.
            def normalize_iso_date(match):
                try:
                    matched_date = date.fromisoformat(match.group(0))
                except ValueError:
                    return match.group(0)
                # Keep unrelated historical ISO dates unchanged; only the
                # exact forecast date receives the Korean display label.
                return date_label if matched_date == prediction_date else match.group(0)

            def normalize_korean_date(match):
                year, month, day = match.groups()
                try:
                    matched_date = date(int(year), int(month), int(day))
                except ValueError:
                    return match.group(0)
                return date_label if matched_date == prediction_date else match.group(0)

            def normalize_month_day(match):
                month, day = match.groups()
                return (
                    date_label
                    if (int(month), int(day)) == (prediction_date.month, prediction_date.day)
                    else match.group(0)
                )

            text = re.sub(
                r"(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)",
                normalize_iso_date,
                text,
            )
            text = re.sub(
                r"\b(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
                normalize_korean_date,
                text,
            )
            text = re.sub(
                r"\b(\d{1,2})\s*월\s*(\d{1,2})\s*일",
                normalize_month_day,
                text,
            )
        except (TypeError, ValueError):
            pass
    text = re.sub(r"[*_~\x60]", "", text)
    text = re.sub(r"(?m)^\s*#+\s*", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
