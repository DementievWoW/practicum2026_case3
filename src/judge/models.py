from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# Finding от deterministic rules / detectors
# ─────────────────────────────────────────────────────────────

class RuleFinding(BaseModel):
    """
    Промежуточный finding от rule engine.

    Это НЕ финальный verdict judge.
    Это сигналы, которые потом использует judge.
    """

    # Название правила / класса уязвимости
    rule: str = Field(
        ...,
        description="Класс уязвимости, найденный rule engine."
    )

    # Severity конкретного finding
    severity: int = Field(
        ...,
        ge=0,
        le=10,
        description="Уровень риска по шкале 0-10."
    )

    # Человеческое описание
    message: str = Field(
        ...,
        description="Описание найденной проблемы."
    )

    # Подозрительный фрагмент SQL
    evidence: Optional[str] = Field(
        default=None,
        description="Фрагмент SQL, вызвавший finding."
    )

    # Кто нашел проблему
    rule_source: str = Field(
        default="deterministic_rule",
        description="Источник finding."
    )


# ─────────────────────────────────────────────────────────────
# Вход judge agent
# ─────────────────────────────────────────────────────────────

class JudgeInput(BaseModel):
    """
    Входные данные для Judge Agent.
    """

    # Что хотел пользователь
    task: str = Field(
        ...,
        description="Описание задачи на естественном языке."
    )

    # SQL от generator/fixer
    generated_sql: str = Field(
        ...,
        description="SQL-запрос для аудита."
    )

    # Номер итерации
    iteration: int = Field(
        default=1,
        ge=1,
        description="Номер итерации judge pipeline."
    )

    # Findings от deterministic rules
    rule_findings: List[RuleFinding] = Field(
        default_factory=list,
        description="Список findings от rule engine."
    )

    # Дополнительные сигналы
    auxiliary_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные сигналы и feature-флаги."
    )


# ─────────────────────────────────────────────────────────────
# Финальный finding judge
# ─────────────────────────────────────────────────────────────

class Finding(BaseModel):
    """
    Финальный finding judge agent.
    Уходит в audit log и fixer agent.
    """

    # Уникальный id finding
    id: str = Field(
        ...,
        description="Уникальный идентификатор finding."
    )

    # Класс уязвимости
    vuln_class: str = Field(
        ...,
        description="Тип найденной уязвимости."
    )

    # Насколько опасна проблема
    severity: int = Field(
        ...,
        ge=0,
        le=10,
        description="Severity finding."
    )

    # Уверенность judge
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уверенность judge в finding."
    )

    # Объяснение проблемы
    message: str = Field(
        ...,
        description="Человеческое описание проблемы."
    )

    # Проблемный фрагмент SQL
    evidence: Optional[str] = Field(
        default=None,
        description="Фрагмент SQL, вызвавший finding."
    )

    # Рекомендация по исправлению
    recommendation: str = Field(
        ...,
        description="Как исправить проблему."
    )

    # Кто нашел проблему
    rule_source: str = Field(
        default="judge",
        description="Источник finding."
    )


# ─────────────────────────────────────────────────────────────
# Финальный output judge
# ─────────────────────────────────────────────────────────────

class JudgeOutput(BaseModel):
    """
    Финальный verdict judge agent.
    """

    # Одобрен ли SQL
    approved: bool = Field(
        ...,
        description="Считается ли SQL безопасным."
    )

    # Номер итерации
    iteration: int = Field(
        ...,
        ge=1,
        description="Номер итерации."
    )

    # Общий риск SQL
    risk_score: int = Field(
        ...,
        ge=0,
        le=10,
        description="Итоговый риск SQL."
    )

    # Найденные проблемы
    findings: List[Finding] = Field(
        default_factory=list,
        description="Список найденных проблем."
    )

    # Краткое summary
    summary: str = Field(
        ...,
        description="Краткое описание результата аудита."
    )

    # Почему approved=true
    approved_reason: Optional[str] = Field(
        default=None,
        description="Причина одобрения SQL."
    )