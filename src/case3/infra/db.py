"""
@file db.py
@brief Заглушка БД-песочницы (Postgres sandbox). Участник 4 (инфраструктура).

@details
    ТЗ: система НЕ исполняет запросы самостоятельно. Поэтому БД нужна
    только для вспомогательных вещей:
      1. EXPLAIN — оценка тяжести плана БЕЗ выполнения запроса;
      2. источник схемы (data_model.sql);
      3. faker-данные для будущих smoke-проверок.

    Это МОК: explain() возвращает детерминированный фейковый план по
    эвристикам над текстом SQL (seq scan если нет WHERE, cartesian если
    несколько таблиц без условия соединения). Реальная версия —
    psycopg + `EXPLAIN (FORMAT JSON)` на поднятом Postgres; интерфейс
    (Protocol Database) тот же, поэтому подмена drop-in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ExplainPlan:
    """@brief Упрощённый план запроса (подмножество EXPLAIN FORMAT JSON)."""
    total_cost: float
    rows_estimate: int
    has_seq_scan: bool
    has_cartesian: bool
    node_types: list[str] = field(default_factory=list)
    raw: str = ""


class Database(Protocol):
    """
    @brief Контракт песочницы. Реальная реализация — psycopg к Postgres.
    @note executes_queries=False кодирует требование ТЗ: не исполнять SQL.
    """
    executes_queries: bool

    def ping(self) -> bool: ...
    def explain(self, sql: str) -> ExplainPlan: ...


class StubDatabase:
    """
    @brief МОК БД-песочницы: EXPLAIN по эвристикам, без реального Postgres.
    @param available  Если False — ping() вернёт False (симуляция недоступной БД).
    """

    executes_queries = False  # @brief ТЗ: система не исполняет SQL

    def __init__(self, available: bool = True) -> None:
        self._available = available

    def ping(self) -> bool:
        """@brief Жив ли коннект. В моке — флаг из конструктора."""
        return self._available

    def explain(self, sql: str) -> ExplainPlan:
        """
        @brief Фейковый план: грубая оценка стоимости по тексту запроса.
        @details Эвристики:
                 · нет WHERE → seq scan (дорого, много строк);
                 · ≥2 таблиц без ON/условия → cartesian (очень дорого).
        @return ExplainPlan с total_cost/rows/флагами.
        """
        s = " " + sql.lower() + " "
        # comma-separated FROM table_a, table_b, ... — все считаются за отдельные таблицы
        froms_raw = re.findall(
            r"\bfrom\s+([a-z_][a-z0-9_]*(?:\s*,\s*[a-z_][a-z0-9_]*)*)", s
        )
        from_tables: set[str] = set()
        for group in froms_raw:
            for tname in group.split(","):
                t = tname.strip()
                if t:
                    from_tables.add(t)
        joins = re.findall(r"\bjoin\s+([a-z_][a-z0-9_]*)", s)
        n_tables = len(from_tables) + len(joins)
        has_where = " where " in s
        has_join_cond = " on " in s or (has_where and "=" in s)

        has_seq_scan = not has_where
        has_cartesian = n_tables >= 2 and not has_join_cond

        cost = 1000.0 * (5.0 if has_seq_scan else 1.0) * (10.0 if has_cartesian else 1.0)
        rows = 100_000 if has_seq_scan else 100

        nodes = ["Seq Scan" if has_seq_scan else "Index Scan"]
        if has_cartesian:
            nodes.append("Nested Loop (no join cond)")

        return ExplainPlan(
            total_cost=cost,
            rows_estimate=rows,
            has_seq_scan=has_seq_scan,
            has_cartesian=has_cartesian,
            node_types=nodes,
            raw=f"[MOCK EXPLAIN] cost={cost:.0f} rows={rows} nodes={nodes}",
        )


if __name__ == "__main__":  # быстрый ручной прогон
    db = StubDatabase()
    for q in [
        "SELECT id FROM credit_contract WHERE status = 1",
        "SELECT * FROM credit_contract",
        "SELECT * FROM credit_contract, acc_number",
    ]:
        print(q, "→", db.explain(q).raw)
