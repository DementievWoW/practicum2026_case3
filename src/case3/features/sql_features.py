"""
@file sql_features.py
@brief ЗАГЛУШКА экстрактора признаков SQL.  Роль: «Тулзы».

@warning ЭТО ЗАГЛУШКА (walking skeleton).
    Возвращает минимальный feature-vector (несколько базовых полей),
    чтобы контракт работал. Полный набор (18 признаков на pglast AST)
    пишет роль «Тулзы».

    Реальная версия в git: тег `reference-impl-v1`
        git show reference-impl-v1:src/case3/features/sql_features.py

@todo (роль «Тулзы»): has_always_true_where, n_select_cols, subquery_depth,
    n_string_concat, n_sensitive_cols, has_pii_literal, EXPLAIN-фичи; перейти
    с regex на pglast AST. Использовать для риск-скоринга (ADR-0011).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class SqlFeatures:
    """@brief Вектор признаков SQL (контракт; в заглушке заполнен частично)."""
    stmt_type: str
    sql_length: int
    has_where: int
    has_limit: int
    has_select_star: int
    n_joins: int
    is_dml: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_features(sql: str) -> SqlFeatures:
    """
    @brief ЗАГЛУШКА: извлекает несколько базовых признаков регексом.
    @param sql  SQL-запрос.
    @return SqlFeatures (частично заполнен).
    @warning Полный extraction (18 фич, pglast) пишет роль «Тулзы».
    """
    low = sql.lower().strip()
    if low.startswith("select"):
        stmt = "SELECT"
    elif low.startswith("update"):
        stmt = "UPDATE"
    elif low.startswith("delete"):
        stmt = "DELETE"
    else:
        stmt = "OTHER"
    return SqlFeatures(
        stmt_type=stmt,
        sql_length=len(sql),
        has_where=int(bool(re.search(r"\bwhere\b", low))),
        has_limit=int(bool(re.search(r"\blimit\b", low))),
        has_select_star=int(bool(re.search(r"select\s+\*", low))),
        n_joins=len(re.findall(r"\bjoin\b", low)),
        is_dml=int(stmt in ("UPDATE", "DELETE")),
    )
