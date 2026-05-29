"""
@file test_infra_tracing.py
@brief Тесты StubTracer: trace/span/score, контекст-менеджеры, export().
"""
from __future__ import annotations

import time

from case3.infra.tracing import Span, StubTracer, Trace


class TestStubTracerBasics:
    def test_trace_recorded_in_memory(self):
        t = StubTracer()
        tr = t.trace("pipeline", input="hello")
        assert tr.name == "pipeline"
        assert tr in t.traces
        assert tr.input == "hello"
        # id — короткая строка
        assert isinstance(tr.id, str)
        assert len(tr.id) >= 4

    def test_trace_context_manager_sets_end(self):
        t = StubTracer()
        with t.trace("x") as tr:
            time.sleep(0.005)
        assert tr.end is not None
        assert tr.duration_ms > 0

    def test_span_inside_trace(self):
        t = StubTracer()
        with t.trace("pipeline") as tr:
            with tr.span("generate") as sp:
                time.sleep(0.005)
            with tr.span("audit"):
                pass
        assert len(tr.spans) == 2
        assert tr.spans[0].name == "generate"
        assert tr.spans[1].name == "audit"
        assert tr.spans[0].duration_ms > 0

    def test_score_stored(self):
        t = StubTracer()
        with t.trace("x") as tr:
            tr.score("risk", 4.2)
            tr.score("approved", 1.0)
        assert tr.scores["risk"] == 4.2
        assert tr.scores["approved"] == 1.0

    def test_update_sets_output_and_metadata(self):
        t = StubTracer()
        with t.trace("x") as tr:
            tr.update(output="result", iter=3)
        assert tr.output == "result"
        assert tr.metadata.get("iter") == 3


class TestStubTracerExport:
    def test_export_returns_dict_per_trace(self):
        t = StubTracer()
        with t.trace("a") as tr:
            tr.score("s", 1.0)
        with t.trace("b"):
            pass
        out = t.export()
        assert len(out) == 2
        assert {row["name"] for row in out} == {"a", "b"}
        # все дикты содержат duration_ms
        assert all("duration_ms" in row for row in out)

    def test_export_includes_spans(self):
        t = StubTracer()
        with t.trace("a") as tr:
            with tr.span("s1"):
                pass
            with tr.span("s2"):
                pass
        out = t.export()
        assert len(out[0]["spans"]) == 2
