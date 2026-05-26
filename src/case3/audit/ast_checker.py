"""
@file ast_checker.py
@brief AST-валидатор через pglast — второй чекер мульти-чекер мозаики.

@details
    Regex-правила (auditor.py) — быстрые, но грубые: путаются в CTE,
    вложенных подзапросах, многострочных JOIN. AST-парсер от Postgres
    (`pglast` → libpg_query) даёт точное дерево: всё видно, никаких
    регексп-эвристик.

    Стратегия:
      1. PARSE_ERROR (R019, critical) — SQL не парсится Postgres'ом.
         Это значит он точно НЕ исполнится; неважно по какой причине
         (модель сгенерила мусор, забыла кавычку и т.д.). Сильный сигнал.
      2. JOIN_NO_ON (R020, high) — JOIN-узел в дереве без quals/USING.
         Картезианское произведение, regex это часто пропускает.
      3. SUBQUERY_NO_LIMIT (R021, low) — подзапрос в IN/FROM без LIMIT.
         Потенциальный DoS, но low — иногда легитимно (фильтрация).

    Это INDEPENDENT сигнал к regex-правилам:
    при совпадении (regex+AST оба указывают на SELECT_STAR) — высокий confidence.
    AST может появляться там где regex молчит (вложенные подзапросы).

    Если pglast не установлен — модуль молчит (см. AST_OK).
"""
from __future__ import annotations

from case3.contracts import Finding

try:
    from pglast import parse_sql, parser
    from pglast.visitors import Visitor
    AST_OK = True
except ImportError:
    AST_OK = False


def _join_no_on(tree) -> bool:
    """@brief Есть ли в дереве JoinExpr без quals и без USING?"""
    found = []

    class V(Visitor):
        def visit_JoinExpr(self, ancestors, node):
            if node.quals is None and node.usingClause is None:
                found.append(True)

    V()(tree)
    return bool(found)


def _subquery_without_limit(tree) -> int:
    """@brief Считает подзапросы (SubLink/RangeSubselect), у которых нет LIMIT."""
    bad = 0

    class V(Visitor):
        def visit_SubLink(self, ancestors, node):
            nonlocal bad
            sub = getattr(node, "subselect", None)
            if sub is not None and getattr(sub, "limitCount", None) is None:
                bad += 1

        def visit_RangeSubselect(self, ancestors, node):
            nonlocal bad
            sub = getattr(node, "subquery", None)
            if sub is not None and getattr(sub, "limitCount", None) is None:
                bad += 1

    V()(tree)
    return bad


def check(sql: str) -> list[Finding]:
    """@brief AST-проверка. Возвращает Finding'и или пусто (если pglast недоступен)."""
    if not AST_OK or not sql or not sql.strip():
        return []
    findings: list[Finding] = []

    # 1. PARSE_ERROR — SQL не парсится
    try:
        tree = parse_sql(sql)
    except parser.ParseError as e:
        return [Finding(
            "R019-parse-error", "PARSE_ERROR", "critical", 9.0,
            f"SQL не парсится Postgres'ом: {str(e)[:120]}",
            ["CWE-1284"],
        )]
    except Exception:
        # любые иные ошибки — не фейлим аудит, просто молчим (см. fail-safe в run_phase1)
        return []

    # 2. JOIN_NO_ON — картезианское произведение через JOIN без условий
    if _join_no_on(tree):
        findings.append(Finding(
            "R020-join-no-on", "SLOW_QUERY", "high", 7.0,
            "JOIN без ON/USING — картезианское произведение",
            ["CWE-1176"],
        ))

    # 3. SUBQUERY_NO_LIMIT — подзапрос без LIMIT
    n = _subquery_without_limit(tree)
    if n > 0:
        findings.append(Finding(
            "R021-subquery-no-limit", "NO_PAGINATION", "low", 3.0,
            f"Подзапрос(ы) без LIMIT ({n}) — потенциальная неограниченная выгрузка",
            ["CWE-770"],
        ))

    return findings
