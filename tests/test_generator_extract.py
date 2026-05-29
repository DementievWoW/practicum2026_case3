"""
@file test_generator_extract.py
@brief Юнит-тесты пост-процессинга вывода LLM в LLMGenerator.

@details
    Реальные LLM редко возвращают «чистый» SQL — обычно SQL в markdown-фенсе,
    с приветствием в начале и пояснением в конце. _strip_sql_fence должна:
      1) извлечь содержимое первого ```sql … ``` (если есть);
      2) обрезать всё до первого SQL-стейтмента;
      3) обрезать хвост после последнего `;`.
    Также проверяем парсер clarify-JSON.
"""
from __future__ import annotations

from case3.nodes.generator import (
    _SQL_KEYWORDS,
    _extract_clarify_json,
    _strip_sql_fence,
)


class TestStripSqlFence:
    def test_plain_select_passes_through(self):
        assert _strip_sql_fence("SELECT 1") == "SELECT 1"

    def test_select_with_semicolon_kept(self):
        assert _strip_sql_fence("SELECT 1;") == "SELECT 1;"

    def test_strips_markdown_fence_with_sql_tag(self):
        text = "```sql\nSELECT a FROM t\n```"
        assert _strip_sql_fence(text) == "SELECT a FROM t"

    def test_strips_markdown_fence_without_tag(self):
        text = "```\nSELECT a FROM t\n```"
        assert _strip_sql_fence(text) == "SELECT a FROM t"

    def test_strips_postgres_fence_tag(self):
        text = "```postgres\nSELECT 1\n```"
        assert _strip_sql_fence(text) == "SELECT 1"

    def test_strips_postgresql_fence_tag(self):
        text = "```postgresql\nSELECT 1\n```"
        assert _strip_sql_fence(text) == "SELECT 1"

    def test_strips_greeting_before_sql(self):
        text = "Понял, исправляю запрос:\nSELECT id FROM t"
        assert _strip_sql_fence(text) == "SELECT id FROM t"

    def test_strips_markdown_header_and_fence(self):
        text = "### Задача\n```sql\nSELECT 1\n```"
        assert _strip_sql_fence(text) == "SELECT 1"

    def test_strips_tail_after_last_semicolon(self):
        text = "SELECT id FROM t WHERE a=1; -- объяснение и markdown"
        assert _strip_sql_fence(text) == "SELECT id FROM t WHERE a=1;"

    def test_keeps_internal_semicolons_in_with(self):
        # WITH-выражения могут содержать ;-подобные конструкции,
        # но `;` мы рассматриваем именно как разделитель в конце.
        text = "WITH t AS (SELECT 1) SELECT * FROM t;"
        out = _strip_sql_fence(text)
        assert out.endswith(";")
        assert "WITH" in out and "SELECT * FROM t" in out

    def test_keyword_case_insensitive(self):
        text = "select id from t"
        assert _strip_sql_fence(text).lower().startswith("select")

    def test_empty_input_returns_empty(self):
        assert _strip_sql_fence("") == ""
        assert _strip_sql_fence(None) == ""

    def test_non_sql_text_passes_through(self):
        # Если SQL-keyword отсутствует — текст возвращается as-is (после strip).
        # _has_sql_keyword в pipeline отдельно решит, что делать.
        text = "Привет! Как могу помочь?"
        assert _strip_sql_fence(text) == "Привет! Как могу помочь?"

    def test_with_explain_keyword_recognized(self):
        text = "EXPLAIN ANALYZE SELECT 1"
        assert _strip_sql_fence(text).startswith("EXPLAIN")

    def test_multiline_sql_inside_fence(self):
        text = "Конечно, вот:\n```sql\nSELECT a,\n  b,\n  c\nFROM credit_contract\nWHERE id=1\n```\nПояснение..."
        out = _strip_sql_fence(text)
        assert "SELECT a," in out
        assert "FROM credit_contract" in out
        assert "Пояснение" not in out

    def test_known_keywords_constant_is_subset_of_real_grammar(self):
        # Защита от случайного «удаления» keyword'а в будущем.
        for kw in ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "DROP", "EXPLAIN"):
            assert kw in _SQL_KEYWORDS


class TestExtractClarifyJson:
    def test_valid_clarify_json(self):
        text = '```json\n{"clarify": true, "question": "что такое X?", "options": ["a", "b"]}\n```'
        d = _extract_clarify_json(text)
        assert d is not None
        assert d.get("clarify") is True
        assert d["question"] == "что такое X?"
        assert d["options"] == ["a", "b"]

    def test_no_clarify_returns_none(self):
        text = "SELECT 1 FROM t"
        assert _extract_clarify_json(text) is None

    def test_clarify_false_returns_none_or_signals_sql(self):
        # Если LLM явно сказал clarify=false — это не clarify-ответ.
        text = '{"clarify": false, "question": "", "options": []}'
        d = _extract_clarify_json(text)
        # допускаем None или dict с clarify=False
        assert d is None or d.get("clarify") is False

    def test_malformed_json_returns_none(self):
        text = '{"clarify": true, "question": "тест"'  # незакрытая скобка
        assert _extract_clarify_json(text) is None
