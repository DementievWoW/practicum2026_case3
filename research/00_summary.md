# GreenData Case 3 — итоговая сводка по 5 кругам поиска

Дата: 2026-05-18

## Контекст проекта

Хакатон/практикум GreenData — мультиагентная система генерации и аудита SQL для PostgreSQL.
Цикл: `Генератор → Судья безопасности → исправление` (до 5 итераций или одобрения).
Артефакт = SQL + audit-log (НЕ исполнять SQL на проде).

**В репо:**
- `case_3.txt`, `tusk` — описание кейса + критерии (мин. 42 балла).
- `take1` — конспект с ментором 05.05.
- `baseline1.py` — скелет: `Vulnerability`, `AuditResult`, `IterationLog`, `SystemResult`, `SQLGenerator`, `SecurityAuditor`, `SQLSecuritySystem`. 9 классов уязвимостей, `RISK_THRESHOLD=4.0`.
- `data_model_sql/data_model.sql` — реальная схема GreenData: **60 таблиц** банковско-ERP домена, `COMMENT ON` по-русски.

**Ключевое:** диалект только PostgreSQL; Execution Accuracy ≥ 70%; ≥ 5 классов уязвимостей; модели ≤ 30B (Qwen-Coder 32B); 4 роли (данные/тулы/LLM/аналитика).
Бонусы: PL/pgSQL поддержка (+10), авторский датасет ≥ 50 (+10).

## TL;DR — что брать в работу

| Слой | Решение |
|---|---|
| Архитектура цикла | **MAC-SQL** (прототип Selector + Decomposer + Refiner), заменить execution-feedback на security-feedback |
| Каркас оркестрации | **LangGraph** + `PostgresSaver` + **Langfuse** для трейсов и A/B |
| Генератор | DAIL-SQL Code-Representation + schema linking (e5-multilingual + FAISS, top-15 таблиц + замыкание по FK) + few-shot по similarity + self-consistency ×3-5 |
| Аудитор-1 (детерминированный) | **`pglast`** visitor (SELECT \*, UPDATE/DELETE без WHERE, отсутствие LIMIT, SECURITY DEFINER без search_path, EXECUTE с \|\|) + `EXPLAIN (FORMAT JSON)` для тяжёлых планов + `semgrep p/sql-injection` для host-кода |
| Аудитор-2 (LLM-судья) | Поверх findings из Аудитора-1 + RAG (CWE-89, CAPEC-66/7/470/108, OWASP SQLi, PG docs) |
| Датасет | **SQL-to-Text back-translation** (OmniSQL/SynSQL): 300+ SQL → GPT-4o-mini пишет NL |
| Модель | **Qwen2.5-Coder 32B** через DeepInfra/OpenRouter ($0.66/$1.00 за 1M tok) |
| Метрика EX | Multiset кортежей с нормализацией (NULL, float-round, ORDER BY-aware); timeout 30с; Soft-F1 как смягчённый вариант |
| Бонусы (+20) | PL/pgSQL через **`plpgsql_check`**; собственный датасет в формате SynSQL |
| Демо | **Streamlit + streamlit-ace** + expander с timeline судьи + цветные бейджи severity |

## Карта 5 кругов

- [01_multiagent_text2sql.md](01_multiagent_text2sql.md) — Круг 1 (ядро): MAC-SQL, CHESS, DIN-SQL, Reflexion, LangGraph generator-critic, ToxicSQL.
- [02_text2sql_benchmarks.md](02_text2sql_benchmarks.md) — Круг 2 (база): BIRD/Spider, schema linking, RAG-DDL, Execution Accuracy.
- [03_deterministic_validators.md](03_deterministic_validators.md) — Круг 3 (инструменты): pglast, sqlfluff, semgrep, EXPLAIN.
- [04_rag_knowledge_base.md](04_rag_knowledge_base.md) — Круг 4 (знания): CWE/CAPEC/OWASP/PG-docs/PII/payloads.
- [05_peripheral.md](05_peripheral.md) — Круг 5 (косвенное): back-translation, code-LLM сравнение, AB-тесты, Streamlit, PL/pgSQL.

## 3 «дешёвых вина» на защите

1. **Back-translation eval-set + McNemar p-value на слайде.** ~2 ч, ~$5.
2. **Langfuse self-host + трейс цикла в UI.** Закрывает «лог аудита для пользователя».
3. **PL/pgSQL-режим через `plpgsql_check`.** Прямой +10 за бонус.

## Подводные камни (триангуляция)

- **LLM-as-judge на голом SQL ненадёжен** (круг 1 — ToxicSQL/IEEE 2025; круг 3 — 100% evasion линтеров). Лечится **гибридом** AST + RAG.
- **Schema linking на 60 таблицах — узкое место** (круг 2). Без него генератор плывёт.
- **`EXPLAIN ANALYZE` на UPDATE/DELETE/INSERT реально исполняет** (круг 3). Только `BEGIN; ... ROLLBACK;` или `EXPLAIN` без ANALYZE.
- **CAPEC/CWE-ID в выводе судьи обязателен** (круг 4) — иначе теряем баллы за «прозрачность» (10 баллов).
- **Reflexion memory-of-mistakes** (круг 1) + **DAIL-SQL Code-Representation** (круг 2) — обязательный минимум промпта.
