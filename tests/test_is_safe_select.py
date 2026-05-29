"""
@file test_is_safe_select.py
@brief Тесты _is_safe_select — критический security-чек /run-sql.

@details
    Эндпоинт /run-sql разрешает исполнение ТОЛЬКО SELECT / WITH (+ EXPLAIN
    обёртки над ними). Любой DML/DDL должен отсекаться, в том числе при
    EXPLAIN-обёртке (`EXPLAIN DELETE FROM ...`).
    Эти тесты — guardrail от регрессий: ошибка здесь = потенциальная
    модификация demo_db через UI.
"""
from __future__ import annotations

import pytest

# _is_safe_select определён в src/case3/infra/service.py
from case3.infra.service import _is_safe_select


SAFE = [
    "SELECT 1",
    "SELECT * FROM t",
    "SELECT id FROM credit_contract WHERE status = 1",
    "WITH cte AS (SELECT 1) SELECT * FROM cte",
    "EXPLAIN SELECT 1",
    "EXPLAIN ANALYZE SELECT 1",
    "EXPLAIN (ANALYZE) SELECT 1",
    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT 1",
    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON, VERBOSE) SELECT id FROM t",
    "explain (analyze) select 1",   # case-insensitive
    "-- комментарий\nSELECT 1",     # ведущий комментарий
    "/* блочный */ SELECT 1",
    "SELECT 1;",                     # лишний ;
    "  SELECT 1  ",                  # с пробелами
]


UNSAFE = [
    "DELETE FROM t",
    "delete from t",
    "UPDATE t SET a=1",
    "INSERT INTO t VALUES (1)",
    "DROP TABLE t",
    "TRUNCATE t",
    "CREATE TABLE x (id int)",
    "GRANT ALL ON t TO public",
    "ALTER TABLE t ADD COLUMN x int",
    # DML под EXPLAIN-обёрткой обязательно блокировать — это исполнит DML!
    "EXPLAIN ANALYZE DELETE FROM t",
    "EXPLAIN (ANALYZE) UPDATE t SET a=1",
    "EXPLAIN (ANALYZE, BUFFERS) DROP TABLE t",
    "EXPLAIN ANALYZE INSERT INTO t VALUES (1)",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_passes(sql):
    assert _is_safe_select(sql) is True, f"safe should pass: {sql!r}"


@pytest.mark.parametrize("sql", UNSAFE)
def test_unsafe_blocked(sql):
    assert _is_safe_select(sql) is False, f"unsafe should be blocked: {sql!r}"
