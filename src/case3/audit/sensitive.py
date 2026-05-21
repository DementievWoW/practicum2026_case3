"""
@file sensitive.py
@brief Детектор чувствительных колонок и PII — основа правила R009 (ADR-0004).

@details
    Два уровня чувствительности:
      1. По ИМЕНИ колонки — regex-словарь (англ + рус корни). Покрывает
         типовые PII/креды: password, passport, snils, card_number, phone...
      2. По ЯВНОМУ списку колонок заказчика — финансовые суммы как
         коммерческая тайна (credit_amount, turnover_*). Уточняется у заказчика.

    Плюс checksum-валидация PII В ЗНАЧЕНИЯХ (literals в SQL):
      - Luhn для номеров карт,
      - mod-101 для СНИЛС.

    Не флагуем колонку, если она обёрнута маскирующей функцией
    (left, substring, md5, coalesce, pgp_sym_decrypt...).

    @note Список EXPLICIT_SENSITIVE — placeholder, заменить реальным
          от заказчика (вопрос кураторам).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ── Уровень 1: чувствительные имена колонок ──────────────────────────────────
# (regex, категория, severity, risk_score)
SENSITIVE_PATTERNS: list[tuple[str, str, str, int]] = [
    (r"(?i)^(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token|password_hash|api_token)$",
     "credentials", "critical", 8),
    (r"(?i)^(card[_-]?(number|num|no)|pan|cvv|cvc)$",
     "payment", "critical", 8),
    (r"(?i)^(ssn|social[_-]?security)$",
     "national_id", "high", 7),
    (r"(?i)^(passport|inn|snils|ogrn)$",
     "national_id_ru", "high", 7),
    (r"(?i)^(паспорт|снилс|инн)$",
     "national_id_ru", "high", 7),
    (r"(?i)^(email|phone|mobile|tel|телефон)$",
     "contact", "medium", 5),
    (r"(?i)^(dob|birth_?date|birthday|birth_day|address|адрес)$",
     "personal", "medium", 5),
]

# ── Уровень 2: явный список колонок заказчика (коммерческая тайна) ────────────
# ⚠️ PLACEHOLDER — заменить реальным списком от заказчика.
EXPLICIT_SENSITIVE: dict[str, tuple[str, str, int]] = {
    "credit_amount":   ("financial", "medium", 6),
    "turnover_debit":  ("financial", "medium", 6),
    "turnover_credit": ("financial", "medium", 6),
    "salary":          ("financial", "high", 7),
}

# ── Маскирующие функции — если колонка внутри, не флагуем ─────────────────────
MASKING_FUNCS = {
    "coalesce", "mask", "digest", "hash", "md5",
    "left", "right", "substr", "substring", "pgp_sym_decrypt",
}


@dataclass
class SensitiveHit:
    """@brief Результат детекции чувствительной колонки."""
    column: str
    category: str
    severity: str
    risk_score: int


def detect_column(name: str) -> SensitiveHit | None:
    """
    @brief Проверяет имя колонки на чувствительность.
    @param name  Имя колонки (без таблицы).
    @return      SensitiveHit или None.
    """
    bare = name.strip().strip('"').lower()
    # Уровень 2 — явный список (точное совпадение)
    if bare in EXPLICIT_SENSITIVE:
        cat, sev, risk = EXPLICIT_SENSITIVE[bare]
        return SensitiveHit(name, cat, sev, risk)
    # Уровень 1 — regex
    for pattern, cat, sev, risk in SENSITIVE_PATTERNS:
        if re.match(pattern, bare):
            return SensitiveHit(name, cat, sev, risk)
    return None


# ── Checksum-валидация PII в значениях ───────────────────────────────────────
def luhn_valid(number: str) -> bool:
    """@brief Проверка номера карты по алгоритму Луна."""
    digits = [int(c) for c in re.sub(r"\D", "", number)]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def snils_valid(snils: str) -> bool:
    """@brief Проверка СНИЛС по контрольной сумме (mod-101)."""
    digits = re.sub(r"\D", "", snils)
    if len(digits) != 11:
        return False
    nums = [int(c) for c in digits[:9]]
    control = int(digits[9:])
    total = sum(n * (9 - i) for i, n in enumerate(nums))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        check = total % 101
        if check in (100, 101):
            check = 0
    return check == control


# Регулярки для поиска PII в литералах SQL
_PII_LITERAL_PATTERNS = [
    ("card",   re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"), luhn_valid),
    ("snils",  re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{3}[ -]?\d{2}\b"), snils_valid),
]


def detect_pii_in_literals(sql: str) -> list[str]:
    """
    @brief Ищет PII В ЗНАЧЕНИЯХ запроса (карты, СНИЛС) с checksum-валидацией.
    @param sql  Текст SQL.
    @return     Список найденных категорий PII (с подтверждённой контрольной суммой).
    """
    hits = []
    for kind, pattern, validator in _PII_LITERAL_PATTERNS:
        for m in pattern.findall(sql):
            if validator(m):
                hits.append(kind)
                break
    return hits
