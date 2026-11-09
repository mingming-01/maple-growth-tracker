"""AI 응답을 화면에 전달하기 전 표시 형식과 문장 품질을 검증한다."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation


REQUIRED_GROWTH_SECTIONS = (
    "[성장 패턴]",
    "[성장 변화]",
    "[레벨업 분석]",
    "[성장 전망]",
    "[AI 코멘트]",
)

# 도메인 문맥에서 의미가 크게 달라지거나 사용자에게 잘못된 상태를 전달하는 표현.
INVALID_GROWTH_TERMS = (
    "경보",
    "API를 호출",
    "모델을 호출",
    "프롬프트",
    "RESOURCE_EXHAUSTED",
    "undefined",
)



_SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def _format_experience_amount(raw_value):
    """큰 경험치 숫자를 한국어 단위로 바꿔 읽기 쉽게 표시한다."""
    try:
        value = Decimal(str(raw_value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return str(raw_value)
    if abs(value) >= Decimal("1e12"):
        amount, unit = value / Decimal("1e12"), "조"
    elif abs(value) >= Decimal("1e8"):
        amount, unit = value / Decimal("1e8"), "억"
    else:
        return str(raw_value)
    rendered = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{rendered}{unit}"


def _format_scientific_experience(match):
    raw = match.group(0).strip()
    normalized = raw.translate(_SUPERSCRIPT_DIGITS)
    normalized = re.sub(r"\s*[×x]\s*10\s*\^?\s*", "e", normalized, flags=re.I)
    normalized = re.sub(r"\s*\*\s*10\s*\^\s*", "e", normalized, flags=re.I)
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return raw
    return _format_experience_amount(value) if abs(value) >= Decimal("1e8") else raw


def validate_growth_report(value):
    """필수 항목·한국어·기본 문장 품질을 검사한다."""
    text = str(value or "").strip()
    if not text:
        return False

    positions = [text.find(section) for section in REQUIRED_GROWTH_SECTIONS]
    if any(position < 0 for position in positions):
        return False
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        return False

    # 모든 항목에 설명이 있어야 하며, 다음 제목 전까지의 본문이 비어 있으면 거부한다.
    for index, section in enumerate(REQUIRED_GROWTH_SECTIONS):
        body_start = positions[index] + len(section)
        body_end = positions[index + 1] if index + 1 < len(positions) else len(text)
        body = text[body_start:body_end].strip()
        if len(re.sub(r"[\s.!?…·]", "", body)) < 4:
            return False

    # CJK 한자/가나 문자가 섞인 응답은 그대로 노출하거나 캐시하지 않는다.
    if re.search(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF]", text):
        return False
    if any(term.casefold() in text.casefold() for term in INVALID_GROWTH_TERMS):
        return False
    if re.search(r"(?:×|\b[xX]\b|\*)\s*10\s*\^?\s*[0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+|\b\d+(?:\.\d+)?e[+-]?\d+\b", text, re.I):
        return False

    # 같은 문장을 연속으로 반복하는 저품질 응답을 차단한다.
    sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]
    for previous, current in zip(sentences, sentences[1:]):
        if len(previous) >= 12 and previous == current:
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
        r"관측\s*구간": "기록이 남은 날짜",
        r"관측\s*기록": "성장 기록",
        r"관측된": "기록된",
        r"관측": "기록",
        r"표본": "기록",
        r"결측\s*날짜": "기록이 없는 날짜",
        r"기록\s*충실도": "기록이 남은 날짜",
        r"유효\s*구간": "확인된 날짜",
        r"조건부\s*전망": "성장 예상",
        r"신뢰도\s*있게": "정확하게",
        r"분석\s*데이터": "성장 기록",
        r"데이터": "기록",
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
    # 과학적 표기와 긴 원본 정수를 조 단위·억 단위로 읽기 쉽게 변환한다.
    text = re.sub(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:[×x]\s*10\s*\^?\s*[0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+|\*\s*10\s*\^\s*\d+|e[+-]?\d+)",
        _format_scientific_experience,
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\(?\s*)(\d{1,3}(?:,\d{3}){2,}|\d{10,})(?:\.\d+)?(\s*\)?)",
        lambda match: (
            f"{match.group(1)}{_format_experience_amount(match.group(2))}{match.group(3)}"
        ),
        text,
    )
    if expected_date:
        try:
            prediction_date = date.fromisoformat(str(expected_date))
            date_label = f"{prediction_date.month}월 {prediction_date.day}일"

            def normalize_iso_date(match):
                try:
                    matched_date = date.fromisoformat(match.group(0))
                except ValueError:
                    return match.group(0)
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

            text = re.sub(r"(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)", normalize_iso_date, text)
            text = re.sub(
                r"\b(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
                normalize_korean_date,
                text,
            )
            text = re.sub(r"\b(\d{1,2})\s*월\s*(\d{1,2})\s*일", normalize_month_day, text)
        except (TypeError, ValueError):
            pass
    text = re.sub(r"[*_~\x60]", "", text)
    text = re.sub(r"(?m)^\s*#+\s*", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
