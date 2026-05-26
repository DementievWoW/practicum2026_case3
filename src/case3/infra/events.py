"""
@file events.py
@brief Лог событий пайплайна — для админ-статистики и RLHF-датасета.

@details
    Пишет CSV в data/events.csv (bind-mount в compose → переживает rebuild).
    Каждое обращение к /chat, /feedback, /run-sql добавляет одну строку.

    Identity берётся из заголовка `X-User` (UI шлёт имя пользователя из
    localStorage). Если заголовка нет — пишется `anonymous`. Это identity,
    НЕ security — любой может ввести любое имя. Реальная защита будет на
    уровне reverse-proxy / SSO в проде.

    Извлечение списка таблиц из SQL — через pglast (визитор RangeVar).
    На невалидном SQL — пусто. Это даёт точную статистику «к каким
    таблицам обращается user X».
"""
from __future__ import annotations

import csv
import datetime
import os
import threading
from typing import Iterable

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_EVENTS_CSV = os.path.join(_ROOT, "data", "events.csv")

_FIELDS = [
    "ts", "user", "endpoint", "task", "tables", "approved",
    "iterations", "vuln_classes", "rating", "comment", "trace_id"
]

_lock = threading.Lock()


def _extract_tables(sql: str) -> list[str]:
    """@brief Список таблиц в SQL (через pglast AST). Дедуп + порядок появления."""
    if not sql or not sql.strip():
        return []
    try:
        from pglast import parse_sql
        from pglast.visitors import Visitor
        out: list[str] = []
        seen: set[str] = set()

        class V(Visitor):
            def visit_RangeVar(self, ancestors, node):
                n = (node.relname or "").lower()
                if n and n not in seen:
                    seen.add(n)
                    out.append(n)

        V()(parse_sql(sql))
        return out
    except Exception:
        return []


def log_event(user: str | None, endpoint: str, *,
              task: str = "", sql: str = "", approved: bool | None = None,
              iterations: int | None = None,
              vuln_classes: Iterable[str] = (),
              rating: str | None = None, comment: str | None = None,
              trace_id: str | None = None) -> None:
    """@brief Дописать строку в data/events.csv. Идемпотентно (создаёт файл с заголовком)."""
    import logging
    try:
        tables = ",".join(_extract_tables(sql))
        vcs = ",".join(vuln_classes or [])
        row = {
            "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": (user or "anonymous").strip() or "anonymous",
            "endpoint": endpoint,
            "task": (task or "")[:500],
            "tables": tables,
            "approved": "" if approved is None else str(approved).lower(),
            "iterations": "" if iterations is None else str(iterations),
            "vuln_classes": vcs,
            "rating": rating or "",
            "comment": (comment or "")[:500],
            "trace_id": trace_id or "",
        }
        os.makedirs(os.path.dirname(_EVENTS_CSV), exist_ok=True)
        with _lock:
            new_file = not os.path.exists(_EVENTS_CSV)
            with open(_EVENTS_CSV, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=_FIELDS, quoting=csv.QUOTE_MINIMAL)
                if new_file:
                    w.writeheader()
                w.writerow(row)
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("events log failed: %r", e)


def read_events() -> list[dict]:
    """@brief Прочитать все события (для админ-статистики). Может быть много — ОК для демо."""
    if not os.path.exists(_EVENTS_CSV):
        return []
    with _lock:
        with open(_EVENTS_CSV, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))


def csv_path() -> str:
    return _EVENTS_CSV
