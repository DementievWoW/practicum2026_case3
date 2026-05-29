"""
@file test_infra_db.py
@brief Тесты StubDatabase: эвристика EXPLAIN, флаги seq_scan/cartesian, ping.
"""
from __future__ import annotations

from case3.infra.db import ExplainPlan, StubDatabase


class TestStubDatabaseProtocol:
    def test_executes_queries_is_false(self):
        # ТЗ: система НЕ исполняет SQL. Это инвариант стаба.
        assert StubDatabase().executes_queries is False

    def test_ping_returns_true_when_available(self):
        assert StubDatabase(available=True).ping() is True

    def test_ping_returns_false_when_unavailable(self):
        assert StubDatabase(available=False).ping() is False


class TestStubExplainHeuristics:
    def test_select_with_where_uses_index_scan(self):
        plan = StubDatabase().explain(
            "SELECT id, status FROM credit_contract WHERE status = 1"
        )
        assert isinstance(plan, ExplainPlan)
        assert plan.has_seq_scan is False

    def test_select_without_where_triggers_seq_scan(self):
        plan = StubDatabase().explain("SELECT id FROM credit_contract")
        assert plan.has_seq_scan is True

    def test_cartesian_join_detected(self):
        # Две таблицы во FROM без ON/WHERE = декартово произведение
        plan = StubDatabase().explain(
            "SELECT * FROM credit_contract, acc_number"
        )
        assert plan.has_cartesian is True

    def test_no_cartesian_when_join_has_on(self):
        # JOIN с ON-условием не должен считаться декартовым
        plan = StubDatabase().explain(
            "SELECT a.id FROM credit_contract a JOIN acc_number b ON a.acc_id = b.id"
        )
        assert plan.has_cartesian is False

    def test_seq_scan_makes_cost_higher_than_index_scan(self):
        seq = StubDatabase().explain("SELECT * FROM credit_contract")
        idx = StubDatabase().explain(
            "SELECT id FROM credit_contract WHERE status = 1"
        )
        assert seq.total_cost > idx.total_cost

    def test_explain_raw_string_mentions_mock(self):
        plan = StubDatabase().explain("SELECT 1")
        # raw содержит маркер мока — чтобы было видно, что это не настоящий план
        assert "MOCK" in plan.raw.upper()
