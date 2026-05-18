# ADR-0004 — Hybrid auditor: deterministic AST checks + LLM as triager

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`):

- «Покрытие классов уязвимостей: Судья выявляет не менее 5 классов
  уязвимостей, по каждому формирует объяснение и оценку риска по
  шкале от 0 до 10» (**25 баллов** — наибольший вес).
- 9 классов уязвимостей зафиксированы в `baseline1.SecurityAuditor.VULN_CLASSES`:
  `SQL_INJ_CLASSIC`, `SQL_INJ_UNION`, `DML_NO_WHERE`, `SELECT_STAR`,
  `DIRECT_SENSITIVE`, `NO_PAGINATION`, `SQL_INJ_TIME`, `PRIV_ESCALATE`,
  `PLPGSQL_UNSAFE`.
- `RISK_THRESHOLD = 4.0` — порог одобрения.
- Контракт `AuditResult(approved, vulnerabilities, overall_risk_score, summary)`.

Из обзора:

- `research/01_multiagent_text2sql.md` (ToxicSQL, IEEE 2025):
  100 % evasion rate для SQLFluff/SQLLint/SonarQube по adversarial
  SQL-payloads → **один линтер не справляется**. Trend Micro
  «LLM as a Judge»: судья надёжен, **когда вся улика в промпте**.
- `research/03_deterministic_validators.md`: `pglast` (PostgreSQL
  native AST via libpg_query) — единственный точный парсер для
  PostgreSQL + поддерживает `parse_plpgsql()`. `sqlglot` слабее на
  PG-специфике. `sqlfluff` имеет AM04 (`SELECT *`), AM09 (`LIMIT без
  ORDER BY`), но **нет UPDATE/DELETE без WHERE** — нужны кастомные
  правила.
- `EXPLAIN (FORMAT JSON)` без ANALYZE безопасен для SELECT, но не для
  UPDATE/DELETE/INSERT (ANALYZE применяет). Песочница на Docker +
  tmpfs + faker — стандартный путь.

Ментор (`take1`):

> Валидация SQL. EXPLAIN плюс анализ warnings как минимум. Сверху —
> read-only песочница с синтетикой или временные запросы Postgres.

И отдельно:

> LLM-as-judge для оценки качества SQL сомнителен, лучше сравнивать
> результаты выполнения запросов на эталонных данных.

То же фактически говорит обзор: LLM хорош как **триажер findings**,
а не как первичный детектор уязвимостей.

## Decision

1. **Аудитор — двухфазный пайплайн внутри узла `auditor` (ADR-0002):**

   ```
   sql_candidate
       │
       ▼
   ┌─────────────────────────────────────────────┐
   │ Phase 1: deterministic checks                │
   │   1.1 pglast.parse_sql() / parse_plpgsql()  │
   │   1.2 AST-Visitor правила (см. ниже)        │
   │   1.3 EXPLAIN (FORMAT JSON) в sandbox       │
   │   1.4 sensitive-column regex поверх AST     │
   │ → list[Finding] (статические находки)        │
   └────────────────────┬────────────────────────┘
                        ▼
   ┌─────────────────────────────────────────────┐
   │ Phase 2: LLM-judge как триажер              │
   │   2.1 RAG-контекст из kb.cwe/capec/owasp    │
   │       по vuln_class из Phase 1 (ADR-0005)   │
   │   2.2 LLM получает: SQL + findings +        │
   │       RAG → классифицирует, отсеивает FP,   │
   │       выставляет risk_score 0–10,           │
   │       формирует description/recommendation  │
   │   2.3 Поиск нюансных уязвимостей, которые   │
   │       статика не ловит (логика, контекст)   │
   │ → AuditResult                                │
   └─────────────────────────────────────────────┘
   ```

2. **Парсер — `pglast`** (см. ADR-0001). Через
   `pglast.visitors.Visitor` пишем по одному классу на правило.
   Каждое правило возвращает `Finding(rule_id, vuln_class, severity,
   risk_score, location, snippet, message, evidence_refs)`.

   Стартовый набор правил (закрывает 8 из 9 классов baseline за счёт
   статики; SQL_INJ_CLASSIC ловится отдельно — см. п. 4):

   | rule_id | vuln_class (baseline) | Что детектится |
   |---|---|---|
   | `R001-select-star` | `SELECT_STAR` | `A_Star` в `targetList` любого SelectStmt |
   | `R002-update-no-where` | `DML_NO_WHERE` | `UpdateStmt.whereClause is None` |
   | `R003-delete-no-where` | `DML_NO_WHERE` | `DeleteStmt.whereClause is None` |
   | `R004-no-limit` | `NO_PAGINATION` | `SelectStmt.limitCount is None` для `SELECT` без агрегата |
   | `R005-union-suspicious` | `SQL_INJ_UNION` | `SelectStmt.op == SETOP_UNION` + неравное число target-колонок верхнего и нижнего select'а |
   | `R006-pg-sleep` | `SQL_INJ_TIME` | `FuncCall.funcname == 'pg_sleep'` или `pg_sleep_for/until` |
   | `R007-security-definer` | `PRIV_ESCALATE` | `CreateFunctionStmt` с `options` содержит `security definer` И нет `SET search_path` |
   | `R008-plpgsql-execute-concat` | `PLPGSQL_UNSAFE` | внутри `parse_plpgsql` встречается `EXECUTE` с `A_Expr op '\|\|'` или строковой склейкой; разрешён `EXECUTE format(...) USING ...` |
   | `R009-sensitive-columns` | `DIRECT_SENSITIVE` | имя колонки в `SELECT` matches `^(password|passwd|pwd|secret|token|api[_-]?key|card[_-]?(number|num|no)\|pan\|cvv\|ssn\|passport\|snils\|inn)$`, без `coalesce/mask/digest/hash` оборачивания |

3. **EXPLAIN-проверки** (для `R010-heavy-plan`, не из baseline
   списка, но даёт +1 к покрытию классов):

   - Sandbox: docker-compose `postgres:17` с прогнанным
     `data_model_sql/data_model.sql` + `faker`-сидинг (1000 строк
     на таблицу). `fsync=off`, tmpfs.
   - Только для read-only запросов: `EXPLAIN (FORMAT JSON, COSTS true)`.
     Для DML — заворачиваем в `BEGIN; EXPLAIN ...; ROLLBACK;` либо
     просто пропускаем EXPLAIN (см. *Risk*).
   - Метрики из JSON-плана:
     - `Seq Scan` на таблице с `Plan Rows > 10000` → severity:medium
       (risk_score=4).
     - `Nested Loop` без `Join Filter`/`Hash Cond`/`Index Cond` →
       severity:high (risk_score=6).
     - `Total Cost > 10000` → warning; `> 100000` → severity:high.

4. **`SQL_INJ_CLASSIC` (host-код)** мы технически НЕ ловим внутри
   `auditor`, потому что класс относится к коду приложения, а не к
   SQL-строке. Однако:

   - В UI/CLI входная задача может содержать SQL-фрагмент пользователя
     (например, «выгрузи пользователя по логину = '$login'»).
     В этом случае правило `R011-injection-marker`: если в
     `task_description` или в `sql_candidate` встречаются маркеры
     прямой конкатенации (`'\s*\|\|`, `format()` без `%I/%L`,
     `$1::text` склеенный с другими литералами) — статика помечает.
   - Полное покрытие SQLi в host-коде делается `semgrep p/sql-injection`
     **отдельным шагом CI** (вне runtime-цикла). См. ADR будет
     добавлен отдельно по CI, если нужно. На защите упоминаем
     как «security by design» вне рантайма.

5. **Phase 2 (LLM-судья)** — отдельный LLM-вызов с промптом:

   ```
   Ты — security-аудитор PostgreSQL-запросов. Тебе подан SQL,
   список findings от статического анализатора и набор статей знаний
   (CWE/CAPEC/OWASP). Сделай три вещи:
   1. Подтверди или отклони каждое finding (FP / TP с обоснованием).
   2. Найди уязвимости, которые статика не уловила (логика, контекст).
   3. Для каждого подтверждённого finding верни структуру:
      {vuln_class, risk_score (0..10), description, recommendation,
       line_hint, evidence: {cwe_id, capec_id, owasp_ref}}
   В конце посчитай overall_risk_score = sum(risk_scores) / N_findings
   (или 0, если findings пуст) и approved = overall_risk_score < 4.0.
   ```

   Возвращаемый JSON парсится в `AuditResult` и в
   `list[Vulnerability]` из `baseline1`.

6. **`overall_risk_score`** — переопределить как **MAX** по найденным
   уязвимостям (а не среднее или сумма), потому что одна критическая
   уязвимость не должна «размываться» десятком info-уровневых. В
   `baseline1` дефиниция «итоговый риск 0..10», нет требования
   суммировать. Дополнительно сохраняем `metadata.risk_score_components`
   со всеми компонентами для отчётности.

7. **Конфигурация порога** — `RISK_THRESHOLD = 4.0` из baseline
   оставляем. При желании настраивается через конструктор `SecurityAuditor`.

## Consequences

**Положительные**

- Статика → дешёвая, детерминированная, аудируемая. На защите можно
  показать unit-тесты на каждое правило (`pytest` + фикстуры SQL).
- LLM → закрывает «логические» и «контекстные» уязвимости, которых
  статика не видит (например, чтение `password_hash` через JOIN с
  правомерной таблицей).
- RAG-контекст из CWE/CAPEC/OWASP даёт верифицируемые ссылки в
  отчёте (`evidence.cwe_id`, и т. п.) — закрывает критерий
  «Прозрачность для пользователя» (10 баллов).
- Покрытие 9/9 классов из baseline достигается комбинацией Phase 1 +
  Phase 2.

**Отрицательные / Риски**

- `pglast` — GPLv3 (см. ADR-0001). Если потребуется не-GPL — переход
  на `sqlglot` с потерей PL/pgSQL парсинга. Этот риск фиксируется.
- Sandbox с реальной демо-БД может содержать ПДн — используем
  только `faker`-сидинг, никогда не загружаем prod-данные в
  test-контейнер.
- EXPLAIN на UPDATE/DELETE без транзакции реально исполняет —
  обязательная `BEGIN; ... ROLLBACK;` обёртка, иначе мы рискуем
  что-то «реально» написать в sandbox. Покрыто тестом.
- LLM может вернуть невалидный JSON. Митигируем: structured output
  через `response_format={"type": "json_object"}` (OpenAI compat),
  fallback — Pydantic-валидатор с retry × 2.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Чистый LLM-as-judge (без статики) | По обзору и IEEE 2025: высокая FP/FN rate, легко обойти; ментор явно отметил «сомнителен». |
| Чистая статика (без LLM) | Не закрывает контекстные уязвимости, нет связных «человеческих» обоснований (требование `Vulnerability.description`). |
| `sqlglot` как основной парсер | Хуже на PG-специфике, не поддерживает PL/pgSQL → провалит бонусный путь (ADR-0010). |
| `sqlfluff` как основной валидатор | Не покрывает половину наших классов из коробки; кастомные плагины писать дольше, чем pglast Visitor'ы. |
| `pgsanity` | Только синтаксис, проект полузаброшен. |
| CodeQL / Semgrep как первичный аудитор | Они для host-кода, а не для отдельных SQL-строк. Используем `semgrep` как side-check в CI. |
| `plpgsql_check` как обязательный компонент | Поднимаем до бонусного пути (ADR-0010); зависимость от расширения Postgres усложняет MVP. |
| `overall_risk_score = sum` (как намекает ТЗ метрика безопасности) | Малозначимые findings будут превышать threshold; max+per-component-логирование информативнее. Если жюри потребует sum — переключается одной строкой кода. |

## Links

- ТЗ: `tusk` § Классы уязвимостей, § Критерии оценивания
- Skeleton: `baseline1.py` (`VULN_CLASSES`, `RISK_THRESHOLD=4.0`,
  `AuditResult`, `Vulnerability`)
- Ментор: `take1` § «Валидация SQL»
- Обзор: `research/03_deterministic_validators.md`,
  `research/01_multiagent_text2sql.md` (Блок 4)
- pglast: https://pglast.readthedocs.io/en/latest/visitors.html
- EXPLAIN docs: https://www.postgresql.org/docs/current/using-explain.html
- ToxicSQL: https://arxiv.org/abs/2503.05445
- IEEE 2025 evasion: https://ieeexplore.ieee.org/document/11355472/
- Зависит от: ADR-0001 (стек), ADR-0002 (state),
  ADR-0005 (RAG для Phase 2)
