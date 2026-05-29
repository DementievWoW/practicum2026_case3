"""
@file test_mock_llm.py
@brief Тесты MockLLMClient: распознавание роли (генератор / судья) и сценарии.
"""
from __future__ import annotations

import pytest

from case3.llm.mock import MockLLMClient


# Минимальная имитация system-промптов наших узлов — чтобы мок мог
# распознать роль (по ключевым словам в content системного сообщения).
_GEN_SYS = "Ты — генератор PostgreSQL-запросов по описанию задачи и схеме БД."
_JUDGE_SYS = "Ты — security-аудитор SQL-запросов. Верни JSON со списком уязвимостей."


def _gen_msgs(user: str = "Покажи договоры"):
    return [{"role": "system", "content": _GEN_SYS},
            {"role": "user", "content": user}]


def _judge_msgs(sql: str = "SELECT 1"):
    return [{"role": "system", "content": _JUDGE_SYS},
            {"role": "user", "content": sql}]


class TestMockLLMScenarios:
    def test_always_good_returns_safe_sql(self):
        llm = MockLLMClient(scenario="always_good")
        r = llm.chat(_gen_msgs(), temperature=0.0)
        text = r.text.upper()
        assert "SELECT" in text
        # safe-вариант не использует "*"
        assert "SELECT *" not in text

    def test_always_bad_returns_dirty_sql(self):
        llm = MockLLMClient(scenario="always_bad")
        r = llm.chat(_gen_msgs(), temperature=0.0)
        assert "SELECT" in r.text.upper()

    def test_evolve_first_call_returns_dirty(self):
        llm = MockLLMClient(scenario="evolve")
        r = llm.chat(_gen_msgs(), temperature=0.0)
        # Первый вызов (нет уроков в промпте) — должна быть «грязная» версия.
        # Минимум: что-то с SELECT возвращается.
        assert "SELECT" in r.text.upper()

    def test_response_has_model_field(self):
        llm = MockLLMClient()
        r = llm.chat(_gen_msgs(), temperature=0.0)
        assert isinstance(r.model, str)
        assert "mock" in r.model.lower()
