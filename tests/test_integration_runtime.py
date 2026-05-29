"""
@file test_integration_runtime.py
@brief Интеграционный smoke run_instrumented: пайплайн + метрики + трейсы.

@details
    Минимальный E2E на моках: дёргаем run_instrumented и проверяем,
    что метрики Prometheus инкрементируются, а трейс попадает в StubTracer.
"""
from __future__ import annotations

from case3.infra import metrics as m
from case3.infra.runtime import run_instrumented
from case3.infra.tracing import StubTracer


class TestRunInstrumentedSmoke:
    def test_returns_system_result_with_pipeline_ms(self):
        tracer = StubTracer()
        res = run_instrumented("Покажи договоры", tracer=tracer)
        # Контракт baseline
        assert res.final_sql is not None
        assert isinstance(res.iterations_used, int)
        # Доп. поле в metadata: pipeline_ms
        assert "pipeline_ms" in res.metadata
        assert res.metadata["pipeline_ms"] >= 0

    def test_tracer_records_at_least_one_trace(self):
        tracer = StubTracer()
        run_instrumented("Покажи договоры", tracer=tracer)
        assert len(tracer.traces) >= 1
        last = tracer.traces[-1]
        assert last.name == "sql_security_pipeline"
        # Скоринги попадают в трейс
        assert "final_risk" in last.scores
        assert "approved" in last.scores

    def test_metrics_runs_total_incremented(self):
        # Берём текущее значение и проверяем, что после прогона счётчик вырос
        # хотя бы на 1 в каком-то labelset.
        tracer = StubTracer()
        before = sum(m.RUNS._values.values()) if m.RUNS._values else 0
        run_instrumented("Покажи договоры", tracer=tracer)
        after = sum(m.RUNS._values.values())
        assert after >= before + 1

    def test_metrics_latency_observed(self):
        tracer = StubTracer()
        before = m.LATENCY._count.get((), 0)
        run_instrumented("Покажи договоры", tracer=tracer)
        after = m.LATENCY._count.get((), 0)
        assert after == before + 1
