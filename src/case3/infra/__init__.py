"""
@file __init__.py
@brief Инфраструктура (Участник 4): БД-песочница, метрики, трейсинг — заглушки.

@details
    Боевые интерфейсы + фейковые реализации (walking skeleton):
      · db.StubDatabase    — EXPLAIN по эвристикам, без Postgres;
      · metrics            — Prometheus-экспозиция /metrics на stdlib;
      · tracing.StubTracer — Langfuse-совместимый трейсер в память;
      · runtime.run_instrumented — прогон пайплайна с метриками и трейсом.

    Grafana-«заглушка» — это поднимаемый стек в deploy/observability/
    (Prometheus + Grafana с провиженингом дашборда), а не Python-код.
"""
from case3.infra import metrics
from case3.infra.db import Database, ExplainPlan, StubDatabase
from case3.infra.tracing import StubTracer, Tracer, get_tracer

__all__ = [
    "metrics",
    "Database",
    "ExplainPlan",
    "StubDatabase",
    "Tracer",
    "StubTracer",
    "get_tracer",
]
