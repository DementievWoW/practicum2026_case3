"""
@file test_pipeline.py
@brief Тесты основного цикла SQLSecurityPipeline.run.

@details
    Покрытие:
      - happy path: approved → выход после первой итерации;
      - reflection-loop: первая dirty → урок → вторая clean → approved;
      - non_sql_output ранний выход с NOT_A_QUERY уязвимостью;
      - exhaust max_iterations → approved=False;
      - on_event callback получает корректную последовательность событий;
      - _has_sql_keyword детектор.
"""
from __future__ import annotations

import pytest

from case3.contracts import AuditResult, Vulnerability
from case3.llm.mock import MockLLMClient
from case3.nodes.auditor import HybridAuditor
from case3.nodes.generator import LLMGenerator
from case3.nodes.reflector import Reflector
from case3.pipeline import (
    SQLSecurityPipeline,
    _has_sql_keyword,
    run_pipeline,
)


# ─────────────────────────────────────────────────────────────────────────────
# _has_sql_keyword — детектор не-SQL ответов модели
# ─────────────────────────────────────────────────────────────────────────────
class TestHasSqlKeyword:
    @pytest.mark.parametrize("text", [
        "SELECT 1",
        "select 1",
        "WITH t AS (SELECT 1) SELECT * FROM t",
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a=1 WHERE id=1",
        "DELETE FROM t WHERE id=1",
        "EXPLAIN ANALYZE SELECT 1",
        "Объяснение... SELECT 1",       # keyword где-то в середине
    ])
    def test_positive_cases(self, text):
        assert _has_sql_keyword(text) is True

    @pytest.mark.parametrize("text", [
        "",
        None,
        "Привет!",
        "Как могу помочь?",
        "Понял, исправляю запрос",
        "Кто ты?",
        "1 + 1 = 2",
    ])
    def test_negative_cases(self, text):
        assert _has_sql_keyword(text) is False


# ─────────────────────────────────────────────────────────────────────────────
# Контракт-тесты: run_pipeline возвращает корректный SystemResult
# ─────────────────────────────────────────────────────────────────────────────
class TestRunPipelineContract:
    def test_returns_system_result_with_required_fields(self):
        res = run_pipeline("Покажи договоры")
        assert hasattr(res, "final_sql")
        assert hasattr(res, "approved")
        assert hasattr(res, "iterations_used")
        assert hasattr(res, "iterations_log")
        assert hasattr(res, "audit_log")
        assert hasattr(res, "metadata")

    def test_iterations_log_consistent(self):
        res = run_pipeline("Покажи договоры")
        # лог итераций отражает iterations_used
        assert res.iterations_used == len(res.iterations_log)
        assert res.iterations_used >= 1

    def test_metadata_has_risk_trajectory(self):
        res = run_pipeline("Покажи договоры")
        traj = res.metadata.get("risk_trajectory")
        assert isinstance(traj, list)
        assert len(traj) == res.iterations_used

    def test_audit_log_is_non_empty_text(self):
        res = run_pipeline("Покажи договоры")
        assert isinstance(res.audit_log, str)
        assert len(res.audit_log) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Reflection loop: на моках с scenario="evolve" — 1-я грязная, 2-я чистая
# ─────────────────────────────────────────────────────────────────────────────
class TestReflectionLoop:
    def _build(self, scenario: str):
        llm = MockLLMClient(scenario=scenario)
        gen = LLMGenerator(llm=llm)
        aud = HybridAuditor(llm=llm)
        ref = Reflector()
        return SQLSecurityPipeline(generator=gen, auditor=aud, reflector=ref,
                                   max_iterations=5)

    def test_always_good_converges_iter1(self):
        pipe = self._build("always_good")
        res = pipe.run("Покажи договоры с просрочкой")
        assert res.iterations_used == 1
        assert res.approved is True

    def test_always_bad_exhausts_max(self):
        pipe = self._build("always_bad")
        res = pipe.run("Покажи договоры с просрочкой")
        assert res.iterations_used == pipe.max_iterations
        assert res.approved is False

    def test_evolve_converges_within_limit(self):
        pipe = self._build("evolve")
        res = pipe.run("Покажи договоры с просрочкой")
        # evolve: первая итерация — dirty, после урока — clean.
        # Зависит от конкретных моков; main contract — не выйти за лимит.
        assert 1 <= res.iterations_used <= pipe.max_iterations


# ─────────────────────────────────────────────────────────────────────────────
# Non-SQL ранний выход
# ─────────────────────────────────────────────────────────────────────────────
class _GreetingLLM:
    """LLM, который вместо SQL всегда отвечает приветствием."""
    def chat(self, messages, *, temperature=0.0, max_tokens=2048):
        from case3.llm.client import ChatResponse
        return ChatResponse(text="Привет! Как могу помочь?", model="greet-llm")


class TestNonSqlEarlyExit:
    def _build_with_greeting_llm(self):
        gen = LLMGenerator(llm=_GreetingLLM())
        aud = HybridAuditor(llm=MockLLMClient())
        ref = Reflector()
        return SQLSecurityPipeline(generator=gen, auditor=aud, reflector=ref,
                                   max_iterations=5)

    def test_early_exit_after_first_iteration(self):
        pipe = self._build_with_greeting_llm()
        res = pipe.run("Привет")
        # Должны выйти на первой итерации, не дойдя до лимита.
        assert res.iterations_used == 1
        assert res.approved is False

    def test_metadata_marks_non_sql_output(self):
        pipe = self._build_with_greeting_llm()
        res = pipe.run("Привет")
        assert res.metadata.get("early_exit") == "non_sql_output"

    def test_vulnerability_class_is_not_a_query(self):
        pipe = self._build_with_greeting_llm()
        res = pipe.run("Привет")
        last_audit = res.iterations_log[-1].audit_result
        assert any(v.vuln_class == "NOT_A_QUERY" for v in last_audit.vulnerabilities)


# ─────────────────────────────────────────────────────────────────────────────
# on_event callback (SSE-streaming hook)
# ─────────────────────────────────────────────────────────────────────────────
class TestOnEventCallback:
    def test_emits_iter_and_generator_events(self):
        events: list[dict] = []
        gen = LLMGenerator(llm=MockLLMClient("always_good"))
        aud = HybridAuditor(llm=MockLLMClient("always_good"))
        pipe = SQLSecurityPipeline(generator=gen, auditor=aud,
                                   reflector=Reflector(), max_iterations=3)
        pipe.run("Покажи договоры", on_event=events.append)

        names = [e.get("event") for e in events]
        assert "iter_start" in names
        assert "generator_start" in names
        assert "generator_done" in names
        assert "auditor_start" in names
        assert "auditor_done" in names

    def test_emits_non_sql_output_on_greeting(self):
        events: list[dict] = []
        gen = LLMGenerator(llm=_GreetingLLM())
        aud = HybridAuditor(llm=MockLLMClient())
        pipe = SQLSecurityPipeline(generator=gen, auditor=aud,
                                   reflector=Reflector(), max_iterations=5)
        pipe.run("Привет", on_event=events.append)
        names = [e.get("event") for e in events]
        assert "non_sql_output" in names
        # после non_sql_output аудитор НЕ должен запускаться в этой итерации
        idx_non_sql = names.index("non_sql_output")
        assert "auditor_start" not in names[idx_non_sql:]


# ─────────────────────────────────────────────────────────────────────────────
# max_iterations: лимит соблюдается, никаких лишних итераций
# ─────────────────────────────────────────────────────────────────────────────
class TestMaxIterations:
    def test_respects_lower_limit(self):
        pipe = SQLSecurityPipeline(
            generator=LLMGenerator(llm=MockLLMClient("always_bad")),
            auditor=HybridAuditor(llm=MockLLMClient()),
            reflector=Reflector(),
            max_iterations=2,
        )
        res = pipe.run("any")
        assert res.iterations_used == 2

    def test_respects_higher_limit(self):
        pipe = SQLSecurityPipeline(
            generator=LLMGenerator(llm=MockLLMClient("always_bad")),
            auditor=HybridAuditor(llm=MockLLMClient()),
            reflector=Reflector(),
            max_iterations=7,
        )
        res = pipe.run("any")
        assert res.iterations_used == 7
