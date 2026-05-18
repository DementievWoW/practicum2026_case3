# ADR-0010 — PL/pgSQL audit path via `plpgsql_check` (bonus track)

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`), Дополнительные критерии (на оценку «выше зачёта»):

> Поддержка PL/pgSQL и хранимых процедур. Система корректно генерирует
> и аудирует запросы с использованием PL/pgSQL; класс уязвимостей
> покрыт (**+10 баллов**).

В `baseline1.SecurityAuditor.VULN_CLASSES` уже зарезервирован класс
`PLPGSQL_UNSAFE` = «PL/pgSQL: небезопасный EXECUTE». То есть baseline
по сути просит реализовать это покрытие.

Из обзора:

- `research/03_deterministic_validators.md`:
  - `pglast` поддерживает `parse_plpgsql()` (редкость среди парсеров).
  - `plpgsql_check` (GitHub okbob/plpgsql_check) — расширение
    PostgreSQL, статанализатор PL/pgSQL: ловит SQL-injection в
    `EXECUTE`, mismatched return types, неиспользуемые переменные.
- `research/05_peripheral.md`:
  - EPAM Code Migration: на голых LLM покрытие PL/pgSQL низкое
    (58–69%), нужен fine-tune + цикл с компилятором.
  - SQLGenie (ACL 2025): компилятор/executor как внешний оракул в
    judge-loop.

Из `research/04_rag_knowledge_base.md`:
- PostgreSQL docs про `EXECUTE format() USING ...` — единственный
  безопасный паттерн.
- Про `SECURITY DEFINER` + `SET search_path` — обязательный
  defensive pattern.

Это даёт нам два независимых сигнала для PL/pgSQL: pglast (AST) +
`plpgsql_check` (расширение). Идеальная комбинация для бонусной
ветки.

## Decision

1. **PL/pgSQL — отдельный режим `auditor`** (вместо «обычной»
   фазы 1 из ADR-0004 включается параллельная PL/pgSQL-фаза, если в
   `sql_candidate` обнаружен `LANGUAGE plpgsql`).

   ```
   sql_candidate
       │
       ▼
   ┌─────────────────────────────────┐
   │ language detection (pglast)     │
   │ - есть ли CreateFunctionStmt    │
   │   с options.language == "plpgsql"
   │ - или DO $$ ... $$ блок         │
   └────────┬────────────────────────┘
            │
   ┌────────┴────────┐
   │                 │
   yes               no
   │                 │
   ▼                 ▼
   PL/pgSQL          обычный auditor (ADR-0004)
   режим
   ```

2. **PL/pgSQL Phase 1 (детерминированная):**

   - `pglast.parse_plpgsql(sql)` → дерево statement'ов.
   - Visitor-правила (продолжение списка из ADR-0004):

     | rule_id | Что детектится |
     |---|---|
     | `R012-plpgsql-execute-concat` | внутри тела функции `EXECUTE` с конкатенацией строк (`A_Expr op '\|\|'`) или f-string подобным — high (risk_score 8) |
     | `R013-plpgsql-execute-no-using` | `EXECUTE format(...)` без `USING` (литералы вшиты прямо в format) — high (risk_score 7) |
     | `R014-plpgsql-security-definer-no-search-path` | `CREATE FUNCTION ... SECURITY DEFINER` без `SET search_path = ...` — high (risk_score 8), CWE-89 + PG docs |
     | `R015-plpgsql-no-exception-handler` | в теле функции, которая исполняет динамический SQL, нет `EXCEPTION WHEN OTHERS THEN` — medium (risk_score 4) |
     | `R016-plpgsql-raise-without-level` | `RAISE 'msg'` без severity (NOTICE/WARNING/EXCEPTION) — low (info, risk_score 2) |
     | `R017-plpgsql-perform-side-effect` | `PERFORM` с side-effect функцией (UPDATE/DELETE inside) — medium |

3. **PL/pgSQL Phase 1b — `plpgsql_check` через расширение в
   sandbox**:

   - В sandbox-БД (ADR-0004) при сидинге выполняется
     `CREATE EXTENSION IF NOT EXISTS plpgsql_check;`.
   - Аудитор кодирует pred-функцию в sandbox с уникальным именем
     (`audit_tmp_$random`), ловит ошибки создания → если синтаксис
     невалиден, finding `PLPGSQL_INVALID`.
   - Если функция создалась — вызываем `SELECT *
     FROM plpgsql_check_function('audit_tmp_xxx()',
     fatal_errors := false);`
   - Полученные строки парсим в `Finding(rule_id="plpgsql-check-<code>",
     ...)`. Это даёт глубокие проверки, которые pglast не покрывает:
     ссылки на несуществующие колонки, dead-code, тип-mismatch
     `RETURN`.
   - После аудита функция дропается:
     `DROP FUNCTION audit_tmp_xxx CASCADE;`. В транзакции
     `BEGIN; ... ROLLBACK;` для гарантии отсутствия эффекта.

4. **PL/pgSQL Phase 2 (LLM-judge)** — тот же узел, что в ADR-0004,
   но RAG-контекст бустит коллекцию `kb.postgres`:
   - `kb.postgres` чанки про `SECURITY DEFINER`, `format()` с
     `%I/%L/USING`, `RAISE`, `EXCEPTION` — попадают в top
     с фильтром `source ∈ {pg-docs-security-definer, pg-docs-plpgsql-execute, ...}`.

5. **PL/pgSQL генерация (генератор узла)**:

   - В системный промпт генератора добавляется условный блок (если
     `task_description` явно про «функцию», «процедуру», «trigger»,
     «PL/pgSQL»):
     - «Используй `EXECUTE format(...) USING $1, $2` для динамического
       SQL.»
     - «Если функция SECURITY DEFINER — всегда добавляй `SET
       search_path = admin, pg_temp` и REVOKE EXECUTE FROM PUBLIC.»
     - «Все динамические идентификаторы — через `%I`,
       литералы — через `%L` (или `USING`).»
   - Few-shot для PL/pgSQL — отдельный pool из 10-15 пар (из
     ADR-0006 раздел `PLPGSQL_UNSAFE` + соответствующие «good»
     версии).

6. **UI demo** (вынесется в отдельный ADR):

   - Streamlit Tab «Procedure Audit» — отдельная вкладка от
     «Query Audit». Только её активируем, если detect показывает
     `LANGUAGE plpgsql`.
   - Подсветка: красным — `EXECUTE` с конкатенацией, зелёным —
     `format() USING`.

7. **Что НЕ берём в MVP**:

   - **Триггеры** и связанные `WHEN`-условия — это +0.5 ADR
     сложности, не стоит на хакатоне.
   - **`UNSAFE` функции через `LANGUAGE C` или `LANGUAGE
     plperlu`** — не в скоупе (там другая модель доверия).
   - **Анализ цепочек privilege escalation** через многоуровневые
     `SECURITY DEFINER` — для MVP отдельной функции достаточно.

## Consequences

**Положительные**

- Закрывается бонусный критерий **+10 баллов** без существенных
  усилий: дополнительные 5-6 правил pglast + интеграция с
  `plpgsql_check`.
- Совмещение pglast (AST) + `plpgsql_check` (компилятор) даёт
  глубокое покрытие — на защите хорошо звучит «гибридный анализ
  PL/pgSQL: AST + статанализатор Postgres».
- Демо-сценарий с правкой `SECURITY DEFINER` функции — наглядный
  пример «как генератор учится на замечаниях судьи» (наш
  исследовательский вопрос). Пригодится в live-demo.

**Отрицательные / Риски**

- `plpgsql_check` — расширение Postgres, его надо устанавливать в
  sandbox-контейнер. Решение: собственный Dockerfile
  `compose/postgres-plpgsql-check/Dockerfile`, основан на
  `postgres:17`, ставим из исходников или apt. CI build один раз,
  затем кеш.
- Тестирование PL/pgSQL медленнее (создание функции в БД +
  `plpgsql_check_function` + drop). Митигируем: запуск только
  в режиме PL/pgSQL (если в SQL нет `LANGUAGE plpgsql`,
  фаза не активируется).
- Создание функции в sandbox с произвольным именем теоретически
  может конфликтовать с параллельными тестами. Митигируем:
  уникальный suffix через `uuid4().hex[:8]`, и `ROLLBACK` после.
- `plpgsql_check` сам по себе не покрывает все возможные
  injection-паттерны (он ловит mismatched types и dead-code, но
  не каждое `EXECUTE` с конкатенацией). Поэтому **pglast-правила
  обязательны параллельно**.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Не делать PL/pgSQL вообще | Теряем +10 баллов. На фоне относительной дешевизны интеграции — нерациональный отказ. |
| Только pglast (без `plpgsql_check`) | pglast хорош, но `plpgsql_check` находит вещи, которые AST не видит (type mismatch, недостижимый код). Гибрид сильнее. |
| Только `plpgsql_check` (без pglast) | Не ловит «небезопасный EXECUTE с конкатенацией», если нет mismatched types. Это наш основной таргет (`PLPGSQL_UNSAFE`). |
| Fine-tune модели на PL/pgSQL миграциях (EPAM-стиль) | Дорого; результаты EPAM показывают ограниченный выигрыш; вне MVP. |
| Использовать `EXPLAIN` для функций | EXPLAIN не работает на CREATE FUNCTION; работает только на CALL/SELECT-вызовы. Не покрывает наши задачи. |
| `pgTAP` для тестирования функций | Это unit-test фреймворк, не статанализатор; полезен для нашего eval, но не для аудита. |

## Links

- ТЗ: `tusk` § «Дополнительные критерии» (+10 за PL/pgSQL)
- Baseline: `baseline1.py` `VULN_CLASSES["PLPGSQL_UNSAFE"]`
- Обзор: `research/03_deterministic_validators.md` § `plpgsql_check`;
  `research/05_peripheral.md` § 6 «PL/pgSQL в LLM»
- pglast PL/pgSQL parsing: https://pglast.readthedocs.io/en/latest/parser.html
- `plpgsql_check`: https://github.com/okbob/plpgsql_check
- PG docs PL/pgSQL EXECUTE: https://www.postgresql.org/docs/current/plpgsql-statements.html
- PG docs SECURITY DEFINER: https://www.postgresql.org/docs/current/sql-createfunction.html
- EPAM PL/SQL → PL/pgSQL migration: https://solutionshub.epam.com/blog/post/code-migration
- SQLGenie ACL 2025: https://aclanthology.org/2025.acl-industry.71.pdf
- Зависит от: ADR-0001 (Dockerfile/extensions), ADR-0004
  (Phase 1 расширяется), ADR-0005 (`kb.postgres` boost), ADR-0006
  (PL/pgSQL примеры в датасете)
