"""
@file schema_validator.py
@brief Schema-validator: ловит галлюцинации модели (несуществующие таблицы/колонки).

@details
    Независимый чекер для мульти-чекер мозаики (вместе с regex-правилами
    auditor.py и AST через pglast). NL→SQL модели часто «придумывают»:
        SELECT customer_name, contract_value FROM customers   -- нет такой схемы
    На реальной БД это упало бы синтаксически, но НАМ нельзя исполнять SQL —
    значит проверяем offline по `data/schema_catalog.json`.

    Источник правды: каталог 60 таблиц / 1877 колонок (имена + типы).

    Возвращает Finding'и класса SCHEMA_HALLUCINATION с уровнем medium/high
    в зависимости от того, выдумана таблица (high) или колонка (medium —
    может быть алиас CTE/подзапроса).

    Граница точности: regex-парсер SQL, не AST. Подзапросы/CTE/алиасы
    обрабатываются через белый список (allow-list). Полный парсер придёт
    с pglast — но даже простой match даёт сильный сигнал на типичных
    галлюцинациях NL→SQL.
"""
from __future__ import annotations

import json
import os
import re

from case3.contracts import Finding

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_CATALOG = os.path.join(_ROOT, "data", "schema_catalog.json")

# PG built-in identifiers, ключевые слова, агрегатные функции —
# их не флагуем как «несуществующую колонку».
_SQL_KEYWORDS = frozenset({
    "select", "from", "where", "and", "or", "not", "in", "between", "like", "ilike",
    "is", "null", "as", "on", "using", "join", "inner", "left", "right", "outer", "full",
    "group", "by", "order", "having", "limit", "offset", "asc", "desc", "distinct",
    "case", "when", "then", "else", "end", "exists", "union", "all", "intersect", "except",
    "with", "returning", "into", "values", "true", "false", "default",
    # агрегаты и функции
    "count", "sum", "avg", "min", "max", "round", "abs", "coalesce", "nullif",
    "lower", "upper", "trim", "ltrim", "rtrim", "length", "substr", "substring",
    "concat", "cast", "date", "extract", "now", "current_date", "current_timestamp",
    "string_agg", "array_agg", "lead", "lag", "row_number", "rank", "dense_rank",
    # типы
    "int", "integer", "bigint", "smallint", "text", "varchar", "boolean", "numeric",
    "timestamp", "interval", "bytea",
})


def _load_catalog() -> tuple[dict[str, set[str]], set[str]]:
    """@brief {таблица: {колонки}}, {все_таблицы}. Имена в lower-case."""
    if not os.path.exists(_CATALOG):
        return {}, set()
    cat = json.load(open(_CATALOG, encoding="utf-8"))["tables"]
    tables: dict[str, set[str]] = {}
    for t in cat:
        tname = t["name"].lower()
        tables[tname] = {c["name"].lower() for c in t["columns"]}
    return tables, set(tables.keys())


# Кэш на уровень модуля — каталог не меняется при работе приложения.
_TABLES, _ALL_TABLE_NAMES = _load_catalog()
_ALL_COLUMN_NAMES: set[str] = set().union(*_TABLES.values()) if _TABLES else set()


def _extract_table_refs(sql: str) -> list[tuple[str, str | None]]:
    """@brief Список (table_name, alias) из FROM/JOIN секций.

    Не делаем полный SQL-парсер: regex по FROM/JOIN. Для CTE добавляем
    их имена в allow-list (см. _extract_cte_names).
    """
    refs: list[tuple[str, str | None]] = []
    # FROM <table> [AS] <alias>?  и  JOIN <table> [AS] <alias>?
    pat = re.compile(
        r"\b(?:from|join)\s+"
        r"(?:public\.)?"                             # опциональная схема public
        r"([a-zA-Z_][a-zA-Z_0-9]*)"                  # имя таблицы
        r"(?:\s+(?:as\s+)?([a-zA-Z_][a-zA-Z_0-9]*))?",  # опциональный alias
        re.I,
    )
    for m in pat.finditer(sql):
        t = m.group(1)
        a = m.group(2)
        # alias не должен совпадать с SQL-ключевым словом (FROM x WHERE → 'WHERE' это не alias)
        if a and a.lower() in _SQL_KEYWORDS:
            a = None
        refs.append((t, a))
    return refs


def _extract_cte_names(sql: str) -> set[str]:
    """@brief Имена WITH-CTE — добавляем их в allow-list для validate_tables."""
    out = set()
    # WITH cte1 AS (...), cte2 AS (...) SELECT ...
    for m in re.finditer(r"\bwith\s+([a-zA-Z_][\w]*)\s+as\s*\(", sql, re.I):
        out.add(m.group(1).lower())
    # Добавляем последующие через запятую: ), cte2 AS (
    for m in re.finditer(r"\),\s*([a-zA-Z_][\w]*)\s+as\s*\(", sql, re.I):
        out.add(m.group(1).lower())
    return out


def validate(sql: str) -> list[Finding]:
    """@brief Проверка SQL против каталога. Возвращает Finding'и."""
    if not _TABLES:
        return []
    findings: list[Finding] = []
    refs = _extract_table_refs(sql)
    ctes = _extract_cte_names(sql)
    real_tables = {t.lower() for t, _ in refs if t.lower() in _ALL_TABLE_NAMES}
    aliases = {a.lower(): t.lower() for t, a in refs if a}

    # 1. Несуществующие таблицы (исключая CTE)
    seen_tables: set[str] = set()
    for tname, _ in refs:
        tl = tname.lower()
        if tl in seen_tables or tl in ctes:
            continue
        seen_tables.add(tl)
        if tl not in _ALL_TABLE_NAMES:
            findings.append(Finding(
                "R017-schema-unknown-table",
                "SCHEMA_HALLUCINATION", "high", 7.0,
                f"Таблица {tname!r} отсутствует в каталоге БД (галлюцинация модели)",
                ["CWE-1284"],
            ))

    # 2. Несуществующие колонки. Включаем только когда SQL ссылается на ОДНУ
    #    реальную таблицу (без CTE и без второй таблицы из реального каталога)
    #    — иначе alias-разрешение неоднозначно без полного парсера.
    if len(real_tables) == 1 and not ctes:
        only_table = next(iter(real_tables))
        cols = _TABLES[only_table]
        # вырезаем строковые литералы '...' и "..." — там не идентификаторы
        sql_no_lit = re.sub(r"'(?:[^']|'')*'", " ", sql)
        sql_no_lit = re.sub(r'"(?:[^"]|"")*"', " ", sql_no_lit)

        bad: list[tuple[str, str]] = []   # (alias_or_solo, col)

        # 2a. alias.col паттерн
        for alias_or_table, col in re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", sql_no_lit):
            base = aliases.get(alias_or_table.lower(), alias_or_table.lower())
            if base != only_table:
                continue
            if col.lower() in _SQL_KEYWORDS or col == "*":
                continue
            if col.lower() not in cols:
                bad.append((alias_or_table, col))

        # 2b. одиночные идентификаторы в SELECT-листе и WHERE/GROUP/ORDER —
        #     полезно когда SQL ссылается на единственную таблицу без алиаса.
        sel = re.search(r"\bselect\s+(.+?)\s+from\b", sql_no_lit, re.I | re.S)
        if sel:
            sel_part = sel.group(1)
            # выкидываем алиасы `... AS x`
            sel_part = re.sub(r"\bas\s+\w+", " ", sel_part, flags=re.I)
            for tok in re.findall(r"\b[a-zA-Z_][\w]*\b", sel_part):
                tl = tok.lower()
                if tl in _SQL_KEYWORDS or tl == only_table or tl in aliases:
                    continue
                if tl.isdigit() or "." in tok:    # числа и alias.col уже обработаны
                    continue
                # подозреваем колонку только если она НЕ есть ни в одной реальной таблице
                # (иначе это может быть колонка из другой таблицы через UNION/CTE)
                if tl not in _ALL_COLUMN_NAMES:
                    bad.append((only_table, tok))

        for alias_or_solo, col in bad:
            findings.append(Finding(
                "R018-schema-unknown-column",
                "SCHEMA_HALLUCINATION", "medium", 5.0,
                f"Колонка {col!r} отсутствует в таблице {only_table!r}",
                ["CWE-1284"],
            ))

    # дедуп по (rule_id, message)
    seen, out = set(), []
    for f in findings:
        k = (f.rule_id, f.message)
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out
