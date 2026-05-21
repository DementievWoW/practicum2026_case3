"""
@file sensitive.py
@brief ЗАГЛУШКА детектора чувствительных колонок (R009).  Роль: «Тулзы».

@warning ЭТО ЗАГЛУШКА (walking skeleton).
    Минимальный словарь имён + пустые checksum, чтобы пайплайн крутился.
    Реальную реализацию пишет роль «Тулзы».

    Реальная версия в git: тег `reference-impl-v1`
        git show reference-impl-v1:src/case3/audit/sensitive.py

@todo (роль «Тулзы»):
    1. Полный regex-словарь (англ + рус корни): password/passport/snils/
       card_number/cvv/inn/phone/email/...
    2. Явный список финансовых колонок заказчика (credit_amount, turnover_*).
    3. Учёт маскирующих обёрток (left/substring/md5/coalesce).
    4. Checksum в значениях: Luhn (карты), mod-101 (СНИЛС).
    Контракт фиксирован: detect_column(name)->SensitiveHit|None,
                         detect_pii_in_literals(sql)->list[str].
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SensitiveHit:
    """@brief Результат детекции чувствительной колонки (контракт)."""
    column: str
    category: str
    severity: str
    risk_score: int


# ЗАГЛУШКА: мини-словарь точных имён (реальный — расширяет роль «Тулзы»).
_STUB_SENSITIVE = {
    "password": ("credentials", "critical", 8),
    "password_hash": ("credentials", "critical", 8),
    "card_number": ("payment", "critical", 8),
    "cvv": ("payment", "critical", 8),
    "passport": ("national_id_ru", "high", 7),
    "snils": ("national_id_ru", "high", 7),
    "credit_amount": ("financial", "medium", 6),
}


def detect_column(name: str) -> SensitiveHit | None:
    """
    @brief ЗАГЛУШКА: точное совпадение по мини-словарю.
    @param name  Имя колонки.
    @return SensitiveHit или None.
    @warning Реальный regex+severity пишет роль «Тулзы».
    """
    bare = name.strip().strip('"').lower()
    if bare in _STUB_SENSITIVE:
        cat, sev, risk = _STUB_SENSITIVE[bare]
        return SensitiveHit(name, cat, sev, risk)
    return None


def luhn_valid(number: str) -> bool:
    """@brief ЗАГЛУШКА checksum карты. @todo роль «Тулзы»: реальный Луна."""
    return False


def snils_valid(snils: str) -> bool:
    """@brief ЗАГЛУШКА checksum СНИЛС. @todo роль «Тулзы»: mod-101."""
    return False


def detect_pii_in_literals(sql: str) -> list[str]:
    """
    @brief ЗАГЛУШКА: PII в значениях не ищет (всегда []).
    @warning Реальный поиск (карты/СНИЛС с checksum) пишет роль «Тулзы».
    """
    return []
