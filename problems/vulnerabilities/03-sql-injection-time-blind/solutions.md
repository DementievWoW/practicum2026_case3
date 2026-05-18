# Варианты решения: Time-based Blind SQL Injection

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс `pg_sleep\(` по строке | 30 секунд имплементации | Промахи на форматировании; FP на legitimate `pg_sleep` в миграциях | ❌ |
| B | AST: `FuncCall` с именем в списке timing-функций | Робастно к формату; точное имя функции | Не покрывает тяжёлые вычисления без `pg_sleep` (`generate_series` + `md5`) | ⚠️ core |
| C | EXPLAIN cost-check (если plan имеет high cost) | Ловит DoS-вычисления без `pg_sleep` | EXPLAIN без ANALYZE даёт оценку, не реальность; для `pg_sleep` cost не показывает | ⚠️ комплемент |
| D | **AST (B) + EXPLAIN cost (C) + LLM-триаж на контекст** | Покрывает оба класса; FP-фильтр через LLM | Дороже | ✅ **выбрали** |
| E | Runtime detection (мониторить реальные latencies) | Самый точный | Нужны прод-логи, не работает на статическом аудите | not applicable |

## Эталонный fix

| Слой | Что | Пример |
|---|---|---|
| Application | Параметризация (как в [01](../01-sql-injection-classic/)) | `cursor.execute("UPDATE ... WHERE user_id = %s", (uid,))` |
| Database role | `statement_timeout` | `ALTER ROLE app_user SET statement_timeout = '5s'` |
| Database role | Запрет `pg_sleep` для роли (опционально) | `REVOKE EXECUTE ON FUNCTION pg_sleep, pg_sleep_for, pg_sleep_until FROM PUBLIC` |

Защита через `statement_timeout` — **обязательная** (см. ADR-0007 §2). Защита через REVOKE — опциональная: ломает legitimate cases в миграциях.

## Что выбрали и почему

Гибрид B+C+D. `pg_sleep` — очевидный маркер blind-injection, AST-правило (B) ловит его надёжно. Но атакующий, увидев REVOKE на `pg_sleep`, переключится на `generate_series`+`md5` — это уже не функция-маркер, а cost-вопрос, → нужно правило (C) от EXPLAIN.

LLM-триаж (D) нужен для редкого FP: `pg_sleep` в legitimate миграциях или тестах latency. Без него мы будем флагать каждый CI-тест.

## Реализация

### Phase 1 — `R006-pg-sleep` (ADR-0004)

```python
TIMING_FUNCS = {"pg_sleep", "pg_sleep_for", "pg_sleep_until"}

class PgSleepDetect(Visitor):
    def visit_FuncCall(self, ancestors, node):
        name = ".".join(n.sval for n in node.funcname)
        if name in TIMING_FUNCS:
            inside_case = any(isinstance(a, CaseExpr) for a in ancestors)
            risk = 9 if inside_case else 8  # CASE-обёртка = классический blind
            yield Finding(rule_id="R006-pg-sleep",
                          vuln_class="SQL_INJ_TIME",
                          severity="high", risk_score=risk,
                          evidence_refs=["CWE-89", "CAPEC-7"])
```

### Phase 1b — `R010-heavy-plan` (ADR-0004 §3)

EXPLAIN (FORMAT JSON) в sandbox:
- `Total Cost > 100_000` → severity:high, risk_score=6.
- `generate_series(1, N)` с `N > 1_000_000` в подзапросе → независимое правило (`R006b`), severity:high.

### Phase 2 — LLM-судья

RAG: CAPEC-7 (Blind), PortSwigger Time delays, PG docs `pg_sleep`.

Инструкция:
- Legitimate `pg_sleep` (миграции, тесты) → понизить severity до low/info.
- `pg_sleep` в `WHERE`/`SELECT`/`CASE` под conditional → подтвердить high.
- Доп. рекомендация: `statement_timeout` на роли.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == SQL_INJ_TIME`** + 2 legitimate `pg_sleep` для FP-проверки.

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.90 (правило простое) |
| Precision | ≥ 0.95 |
| `overall_risk_score` после fix | < 4.0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| Тяжёлые вычисления без `pg_sleep` (`generate_series` + `md5`) | `R010-heavy-plan` через EXPLAIN cost |
| `statement_timeout` обходится через много мелких запросов | Это уже rate-limiting проблема, вне нашего scope |
| Custom timing через `bcrypt cost=31` (~30 сек на хеш) | Не учитываем, marginal случай |
| Расширения с heavy-функциями (`pgcrypto`) | Можно расширить `TIMING_FUNCS` при необходимости |

## Связи с ADR

- **ADR-0004** — `R006-pg-sleep`, `R010-heavy-plan`.
- **ADR-0005** — `kb.capec` CAPEC-7, `kb.postgres` (pg_sleep docs).
- **ADR-0007** — Sandbox с `statement_timeout` для EXPLAIN.
