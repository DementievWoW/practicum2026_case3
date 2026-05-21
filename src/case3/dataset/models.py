"""
@file models.py
@brief Модель примера датасета «NL → SQL» с парой bad/good.

@details
    Один SeedExample описывает интент (что хочет аналитик) и до двух
    версий SQL:
      - sql_good — корректный/безопасный/оптимальный (эталон, ВСЕГДА есть);
      - sql_bad  — уязвимая/медленная версия того же интента (для уязвимых
                   примеров; у чисто safe-примеров отсутствует).

    Back-translation (build_dataset.py) превращает каждый SeedExample
    в записи финального датасета: к sql_good и sql_bad генерируются
    NL-формулировки. Так из одного seed получается несколько обучающих/
    тестовых пар.

    Состав датасета (см. dataset/README.md):
      - safe-примеры        → только sql_good;
      - vulnerable-примеры  → sql_bad + sql_good (оба варианта).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# Допустимые vuln_class — синхронизированы с baseline1.SecurityAuditor.VULN_CLASSES
VULN_CLASSES = {
    "SQL_INJ_CLASSIC",
    "SQL_INJ_UNION",
    "SQL_INJ_TIME",
    "DML_NO_WHERE",
    "PRIV_ESCALATE",
    "PLPGSQL_UNSAFE",
    "DIRECT_SENSITIVE",
    "SELECT_STAR",
    "NO_PAGINATION",
    "SLOW_QUERY",   # тяжёлый план без LIMIT-проблемы (cartesian, seq scan)
}

DIFFICULTIES = {"easy", "medium", "hard"}


@dataclass
class SeedExample:
    """
    @brief Один seed-пример датасета.
    @var id          Уникальный id (напр. "ds-credit-001").
    @var intent      Краткий смысл задачи на русском (для генерации NL).
    @var vuln_class  Класс уязвимости или "safe".
    @var difficulty  easy | medium | hard.
    @var tables      Реальные таблицы заказчика, которые задействованы.
    @var sql_good    Эталонный SQL (всегда).
    @var sql_bad     Уязвимая/медленная версия (None для safe-примеров).
    @var note        Пояснение «в чём подвох» (для отчёта и проверки).
    """
    id: str
    intent: str
    vuln_class: str
    difficulty: str
    tables: list[str]
    sql_good: str
    sql_bad: str | None = None
    note: str = ""

    def __post_init__(self):
        # Лёгкая валидация — ловим опечатки в метках на этапе сборки.
        if self.vuln_class not in VULN_CLASSES and self.vuln_class != "safe":
            raise ValueError(f"{self.id}: неизвестный vuln_class {self.vuln_class!r}")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"{self.id}: неизвестная difficulty {self.difficulty!r}")
        if self.vuln_class != "safe" and self.sql_bad is None:
            raise ValueError(f"{self.id}: уязвимый пример без sql_bad")


@dataclass
class DatasetRecord:
    """
    @brief Финальная запись датасета после back-translation.
    @details
        Получается из SeedExample: на каждую версию SQL — NL-формулировки.
        Это и есть строка dataset_v1.jsonl.
    @var seed_id     Ссылка на исходный SeedExample.
    @var nl          NL-формулировка задачи (от back-translation).
    @var sql         SQL (good или bad — см. is_vulnerable).
    @var vuln_class  Класс или "safe".
    @var is_vulnerable  True если это sql_bad-версия.
    @var difficulty  easy | medium | hard.
    @var tables      Задействованные таблицы.
    @var split       "train" | "eval".
    """
    seed_id: str
    nl: str
    sql: str
    vuln_class: str
    is_vulnerable: bool
    difficulty: str
    tables: list[str] = field(default_factory=list)
    split: str = "train"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
