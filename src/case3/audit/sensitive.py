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
# (regex по re.search, категория, severity, risk_score)
# Substring-формы `(?:^|_)...(?:$|_)` ловят префиксы заказчика: contact_phone,
# attr_email, и т.п. Имена-персоны — строго (иначе ловили бы generic `name`).
SENSITIVE_PATTERNS: list[tuple[str, str, str, int]] = [
    (r"(?i)(?:^|_)(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|token)(?:$|_)",
     "credentials", "critical", 8),
    (r"(?i)(?:^|_)(card[_-]?(?:number|num|no)|pan|cvv|cvc)(?:$|_)",
     "payment", "critical", 8),
    (r"(?i)^(ssn|social[_-]?security|passport|inn|snils|ogrn|паспорт|снилс|инн)$",
     "national_id", "high", 7),
    (r"(?i)(?:^|_)(e[_-]?mail|email|phone|mobile|telephone|tel|телефон)(?:$|_)",
     "contact", "medium", 5),
    (r"(?i)^(first|second|sur|last|full|middle|maiden)_name$",
     "personal", "medium", 5),
    (r"(?i)(?:^|_)(address|адрес)(?:$|_)",
     "personal", "medium", 5),
]

# ── Уровень 2: явный список колонок заказчика ────────────────────────────────
# Текстовые поля коммерческой тайны (в безопасной аналитике не светятся) → блокируют.
EXPLICIT_SENSITIVE: dict[str, tuple[str, str, int]] = {
    "special_purpose":    ("financial_secret", "medium", 6),
    "financial_position": ("financial_secret", "medium", 6),
    "salary":             ("financial", "high", 7),
}

# Числовые суммы — НЕОДНОЗНАЧНЫ: легитимная аналитика их выбирает (top-N, отчёты),
# поэтому помечаем как info (risk 2) — фиксируем в логе, но НЕ отклоняем запрос.
# Реальный список «коммерческой тайны» — уточнить у заказчика (ADR-0006, README).
FINANCIAL_NUMERIC: set[str] = {
    "credit_amount", "reserve_size", "turnover_debit", "turnover_credit",
    "output_balance_debit", "output_balance_credit",
    "input_balance_debit", "input_balace_credit",
    "max_loan_amount_ever", "vat",
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
    # Числовые финансовые суммы — info-уровень (детектим, но не блокируем)
    if bare in FINANCIAL_NUMERIC:
        return SensitiveHit(name, "financial_numeric", "info", 2)
    # Уровень 1 — regex (substring/anchored)
    for pattern, cat, sev, risk in SENSITIVE_PATTERNS:
        if re.search(pattern, bare):
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
