"""
@file generator.py
@brief Генератор SQL (реализует baseline.SQLGenerator).

@details
    Строит промпт (схема + reflection-уроки) и вызывает LLM через LLMClient.
    Сейчас LLM — MockLLMClient, в проде — реальный (Qwen). Контракт один.

    Reflection-уроки (in-context, ADR-0002) кладутся в системный промпт:
    генератор «видит» прошлые ошибки и не повторяет их — без обучения весов.
"""

from __future__ import annotations

import re

from case3.contracts import AuditResult, Lesson, SQLGenerator
from case3.llm.client import LLMClient


def _strip_sql_fence(text: str) -> str:
    """@brief Достаёт SQL из ```sql ... ``` (реальные LLM часто оборачивают в фенс)."""
    m = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


class LLMGenerator(SQLGenerator):
    """
    @brief Генератор поверх LLMClient.
    @param llm        Клиент LLM (mock или реальный).
    @param db_schema  Машиночитаемая схема (для промпта). Опц.
    @param store      Асимметричный few-shot store (ADR-0012). Генератору отдаём
                      ТОЛЬКО positives (безопасные эталоны «как надо»). Опц.
    @param k_shots    Сколько few-shot примеров подмешивать.
    """

    def __init__(self, llm: LLMClient, db_schema: dict | None = None,
                 store=None, k_shots: int = 3, **kwargs):
        super().__init__(db_schema=db_schema, **kwargs)
        self.llm = llm
        self.store = store
        self.k_shots = k_shots

    def _schema_block(self) -> str:
        """@brief Компактное описание схемы для промпта (строка / dict / Table-объекты)."""
        schema = getattr(self, "db_schema", None)
        if not schema:
            return ""
        if isinstance(schema, str):
            return "\n\n### Схема БД:\n" + schema
        lines = ["\n\n### Схема БД (используй ТОЛЬКО эти таблицы и колонки):"]
        for tname, tinfo in schema.items():
            if hasattr(tinfo, "column_names"):                 # schema.models.Table
                cols = ", ".join(tinfo.column_names())
            elif isinstance(tinfo, dict):
                raw = tinfo.get("columns", tinfo)
                seq = raw if isinstance(raw, (list, tuple)) else list(raw.keys())
                cols = ", ".join(c["name"] if isinstance(c, dict) else str(c) for c in seq)
            elif isinstance(tinfo, (list, tuple)):
                cols = ", ".join(str(c) for c in tinfo)
            else:
                cols = str(tinfo)
            lines.append(f"- {tname}({cols})")
        return "\n".join(lines)

    def _fewshot_block(self, task_description: str) -> str:
        """@brief Блок позитивных few-shot (безопасные NL→SQL) по близости к задаче."""
        if not self.store:
            return ""
        shots = self.store.retrieve_positive(task_description, k=self.k_shots)
        if not shots:
            return ""
        lines = ["\n\n### Примеры безопасных запросов (ориентир «как надо»):"]
        for ex in shots:
            lines.append(f"-- {ex.nl}\n{ex.sql}")
        return "\n".join(lines)

    def _system_prompt(self, reflection: list[Lesson], task_description: str) -> str:
        base = (
            "Ты — генератор PostgreSQL-запросов по описанию задачи и схеме БД. "
            "Возвращай только безопасный SQL в блоке ```sql."
        )
        base += self._schema_block()
        base += self._fewshot_block(task_description)
        if reflection:
            lessons = "\n".join(f"- {l}" for l in reflection)
            base += (
                "\n\n### Reflection memory (уроки прошлых попыток, НЕ повторяй):\n"
                + lessons
            )
        return base

    def generate(
        self,
        task_description: str,
        sql_history: list[str] | None = None,
        audit_feedback: AuditResult | None = None,
        iteration: int = 1,
        reflection: list[Lesson] | None = None,
    ) -> str:
        """
        @brief NL-задача (+ positive few-shot + reflection) → SQL.
        @param reflection  Накопленные уроки (in-context reflection-loop).
        @return SQL-строка.
        """
        messages = [
            {"role": "system", "content": self._system_prompt(reflection or [], task_description)},
            {"role": "user", "content": task_description},
        ]
        resp = self.llm.chat(messages, temperature=0.3)
        return _strip_sql_fence(resp.text)
