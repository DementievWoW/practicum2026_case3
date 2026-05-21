"""
@file mock.py
@brief MockLLMClient — заглушка LLM для walking skeleton (без API-ключей).

@details
    Имитирует поведение LLM по СЦЕНАРИЯМ, не делая реальных вызовов.
    Назначение:
      - разблокировать E2E-цикл, пока реальный клиент не написан;
      - давать УПРАВЛЯЕМЫЕ ответы (в т.ч. «плохие») для теста аудитора
        и reflection-loop;
      - быть детерминированным (для тестов и CI).

    Главный сценарий — «эволюция генератора»: на первой итерации мок
    возвращает уязвимый SQL, а получив reflection-уроки в промпте —
    «исправляется». Так на моках виден весь reflection-loop (ADR-0002).

    ⚠️ Это НЕ настоящая модель. Реальный клиент (DeepInfra/vLLM/Colab)
       подменит мок, реализуя тот же контракт LLMClient.
"""

from __future__ import annotations

import re
import time

from .client import ChatResponse


class MockLLMClient:
    """
    @brief Заглушка LLM. Распознаёт роль вызова по системному промпту
           и возвращает заготовку.
    @param scenario  Поведение генератора:
        - "evolve" (по умолчанию): сначала уязвимый SQL, потом чинит по reflection;
        - "always_good": сразу безопасный SQL;
        - "always_bad": всегда уязвимый (для проверки лимита итераций).
    """

    def __init__(self, scenario: str = "evolve", model: str = "mock-llm"):
        self.scenario = scenario
        self.model = model

    # ── основной метод контракта ──────────────────────────────────────────
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> ChatResponse:
        t0 = time.time()
        system = " ".join(m["content"] for m in messages if m["role"] == "system").lower()
        user = " ".join(m["content"] for m in messages if m["role"] == "user")
        full = (system + " " + user).lower()

        if "reflector" in system or "урок" in system:
            text = self._mock_reflector(user)
        elif "судья" in system or "auditor" in system or "judge" in system:
            text = self._mock_judge(user)
        else:
            text = self._mock_generator(full)

        dt = time.time() - t0
        return ChatResponse(
            text=text,
            tokens_in=len(user) // 4,
            tokens_out=len(text) // 4,
            latency_seconds=dt,
            model=self.model,
        )

    # ── мок генератора ────────────────────────────────────────────────────
    def _mock_generator(self, prompt: str) -> str:
        """
        @brief Имитирует генератор SQL.
        @details
            Если в промпте есть reflection-уроки (значит это retry),
            «исправляет» соответствующие ошибки. Так виден reflection-loop.
        """
        fixed_star = "select_star" in prompt or "select *" in prompt
        fixed_where = "dml_no_where" in prompt or "where" in prompt and "predicate" in prompt
        fixed_limit = "no_pagination" in prompt or "limit" in prompt

        if self.scenario == "always_good":
            return "SELECT id, credit_amount FROM credit_contract WHERE status = 1 LIMIT 100"
        if self.scenario == "always_bad":
            return "SELECT * FROM credit_contract"

        # scenario == "evolve": чиним по накопленным урокам
        cols = "id, credit_amount" if fixed_star else "*"
        where = " WHERE status = 1" if fixed_where else ""
        limit = " LIMIT 100" if fixed_limit else ""
        return f"SELECT {cols} FROM credit_contract{where}{limit}".strip()

    # ── мок Phase 2 (LLM-судья) — формирует JSON-объяснение ───────────────
    def _mock_judge(self, prompt: str) -> str:
        """@brief Имитирует триаж: возвращает короткое объяснение/рекомендацию."""
        return (
            "Подтверждаю находки статического анализа. "
            "Рекомендация: перечислить колонки явно, добавить WHERE по PK и LIMIT."
        )

    # ── мок reflector ─────────────────────────────────────────────────────
    def _mock_reflector(self, prompt: str) -> str:
        """@brief Имитирует формулировку урока (в реальности — Qwen-7B)."""
        return "Не используй SELECT * и DML без WHERE; всегда добавляй LIMIT."
