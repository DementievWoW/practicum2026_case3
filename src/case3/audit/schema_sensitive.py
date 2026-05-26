"""
@file schema_sensitive.py
@brief Schema-grounded детекция PII (портировано из идеи аудитора snb, баги исправлены).

@details
    Идея Серафима (SQLAlchemySchemaContext): знать чувствительность по РЕАЛЬНОЙ
    схеме, а не только по имени колонки в тексте запроса. Здесь — корректная
    реализация на нашем data/schema_catalog.json:

      - колонка считается PII, если её ИМЯ ловится словарём (sensitive.detect_column,
        risk≥5) ИЛИ её COMMENT содержит PII-ключ (паспорт/инн/счёт/телефон/…).
        → ловит колонки с невнятным именем, но говорящим комментарием.
      - `SELECT *` из таблицы, в которой ЕСТЬ PII-колонки → DIRECT_SENSITIVE
        (звёздочка вытащит и их).

    Исправлены баги исходника:
      BUG-1 (краш на схеме) — fail-safe загрузка (нет каталога → пустые множества);
      BUG-2 (детекция не срабатывала) — корректный разбор select-list и таблиц.

    Зависимость односторонняя: audit → schema_sensitive → sensitive (без циклов).
"""
from __future__ import annotations

import json
import os
import re

from case3.contracts import Finding
from case3.audit.sensitive import detect_column, MASKING_FUNCS

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_CATALOG = os.path.join(_ROOT, "data", "schema_catalog.json")

# PII-ключи в КОММЕНТАРИЯХ (рус + en), высокая чувствительность
_PII_COMMENT = re.compile(
    r"(?i)(паспорт|снилс|\bинн\b|огрн|\bбик\b|телефон|\bтел\b|e[- ]?mail|почт|"
    r"счёт|счет|карт|cvv|парол|фио|passport|phone|email)")

_state: dict | None = None


def _load() -> dict:
    """@brief Ленивая fail-safe загрузка: {tables_with_pii:set, pii_cols:set}."""
    global _state
    if _state is not None:
        return _state
    tables_with_pii: set[str] = set()
    pii_cols: set[str] = set()          # имена PII-колонок (по имени ИЛИ комментарию)
    try:
        cat = json.load(open(_CATALOG, encoding="utf-8"))["tables"]
        for t in cat:
            has = False
            for c in t.get("columns", []):
                name = c.get("name", "")
                com = c.get("comment") or ""
                hit = detect_column(name)
                is_pii = (hit is not None and hit.risk_score >= 5) or bool(_PII_COMMENT.search(com))
                if is_pii:
                    pii_cols.add(name.lower())
                    has = True
            if has:
                tables_with_pii.add(t["name"].lower())
    except Exception:
        pass                             # нет каталога/ошибка → работаем без schema-слоя
    _state = {"tables": tables_with_pii, "cols": pii_cols}
    return _state


def table_has_pii(table: str) -> bool:
    return table.strip().strip('"').lower() in _load()["tables"]


def findings(sql: str) -> list[Finding]:
    """@brief Schema-grounded находки PII (дополняют name-based правило аудитора)."""
    st = _load()
    out: list[Finding] = []

    # 1. SELECT * из таблицы с PII (схема знает, что звёздочка вытащит PII)
    if re.search(r"select\s+\*", sql, re.I) or re.search(r"\b\w+\.\*", sql):
        for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_]\w*)", sql, re.I):
            if t.lower() in st["tables"]:
                out.append(Finding("R009s-star-pii-table", "DIRECT_SENSITIVE", "high", 7.0,
                                   f"SELECT * из таблицы {t!r} с PII-колонками (по схеме)",
                                   ["CWE-200", "CWE-359"]))
                break

    # 2. PII-колонки по КОММЕНТАРИЮ схемы (имя невнятное — name-regex их пропускает)
    sel = re.search(r"select\s+(.*?)\s+from\b", sql, re.I | re.S)
    if sel:
        sel_part = re.sub(r"\bas\s+\w+", " ", sel.group(1), flags=re.I)
        for token in re.findall(r"\b[a-zA-Z_]\w*\b", sel_part):
            if token.lower() in st["cols"] and not detect_column(token):  # detect_column уже не ловит → значит «по комментарию»
                if not re.search(rf"\b({'|'.join(MASKING_FUNCS)})\s*\([^)]*{re.escape(token)}", sel_part, re.I):
                    out.append(Finding("R009s-comment-pii", "DIRECT_SENSITIVE", "high", 7.0,
                                       f"Колонка {token!r} помечена как PII в схеме (COMMENT)",
                                       ["CWE-200"]))
    # дедуп по (rule_id, message)
    seen, dedup = set(), []
    for f in out:
        k = (f.rule_id, f.message)
        if k not in seen:
            seen.add(k); dedup.append(f)
    return dedup
