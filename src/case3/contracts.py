"""
@file contracts.py
@brief Контракты системы — мост между baseline1.py и нашими внутренними типами.

@details
    baseline1.py (от заказчика) фиксирует ВХОД/ВЫХОД системы:
      Vulnerability, AuditResult, IterationLog, SystemResult + классы-интерфейсы.
    Мы их НЕ меняем — реализуем под них.

    Здесь добавляем два ВНУТРЕННИХ типа, которых нет в baseline:
      - Finding — находка одного правила Phase 1 (потом маппится в Vulnerability);
      - Lesson  — «урок» reflector'а для in-context reflection-loop.

    Так весь наш код работает с типизированными объектами, а на границе
    системы отдаёт ровно то, что ждёт baseline (SystemResult).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

# baseline1.py лежит в корне репозитория — добавляем его в путь импорта.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Ре-экспорт контрактов заказчика (единая точка импорта для всего кода).
from baseline1 import (  # noqa: E402
    Vulnerability,
    AuditResult,
    IterationLog,
    SystemResult,
    SQLGenerator,
    SecurityAuditor,
    SQLSecuritySystem,
)

__all__ = [
    "Vulnerability", "AuditResult", "IterationLog", "SystemResult",
    "SQLGenerator", "SecurityAuditor", "SQLSecuritySystem",
    "Finding", "Lesson",
]


@dataclass
class Finding:
    """
    @brief Находка одного правила аудита (внутренний тип Phase 1).
    @details
        Phase 1 (детерминированные правила) возвращает list[Finding].
        Phase 2 (LLM-судья) их триажит и маппит в baseline.Vulnerability.
    @var rule_id        Идентификатор правила (напр. "R002-update-no-where").
    @var vuln_class     Ключ из baseline.SecurityAuditor.VULN_CLASSES.
    @var severity       info | low | medium | high | critical.
    @var risk_score     0.0..10.0.
    @var message        Человекочитаемое пояснение.
    @var evidence_refs  Ссылки на стандарты (CWE/CAPEC/OWASP).
    @var line_hint      Позиция в SQL (опц.).
    """
    rule_id: str
    vuln_class: str
    severity: str
    risk_score: float
    message: str
    evidence_refs: list[str] = field(default_factory=list)
    line_hint: int = 0

    def to_vulnerability(self, recommendation: str = "") -> Vulnerability:
        """@brief Маппинг во внешний контракт baseline.Vulnerability."""
        return Vulnerability(
            vuln_class=self.vuln_class,
            risk_score=self.risk_score,
            description=self.message,
            recommendation=recommendation or "См. рекомендации по классу.",
            line_hint=self.line_hint,
        )


@dataclass
class Lesson:
    """
    @brief Урок reflector'а для in-context reflection-loop (ADR-0002).
    @details
        После провала аудита reflector формирует Lesson из findings.
        Уроки кладутся в промпт генератора на следующей итерации —
        генератор не повторяет ошибку. Веса модели не трогаем.
    @var rule_id      По какому классу урок.
    @var lesson       Короткая инструкция «не делай так».
    @var example_bad  Фрагмент проблемного SQL.
    @var example_good Как надо.
    """
    rule_id: str
    lesson: str
    example_bad: str = ""
    example_good: str = ""

    def __str__(self) -> str:
        return f"[{self.rule_id}] {self.lesson}"
