# 03 — Time-based Blind SQL Injection

- **`vuln_class`:** `SQL_INJ_TIME`
- **Риск:** 8/10
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html) (вариант blind).
- **CAPEC:** [CAPEC-7 — Blind SQL Injection](https://capec.mitre.org/data/definitions/7.html).

## Что

Атакующий **не видит результата запроса напрямую**, но управляет временем ответа. Внедряет `pg_sleep(N)` или тяжёлые вычисления внутри условного выражения; по задержке делает выводы о структуре БД и значениях, бит за битом.

## Почему опасно (риск 8)

Чуть ниже UNION (9), потому что:
- Эксфильтрация бит-за-битом → медленная (≈ 1 бит / 0.5-1 сек). Для извлечения 32-символьного хеша нужно часы.
- Заметна в логах БД и в latency-мониторинге.

Но всё ещё опасна:
- **Работает даже без UI-отображения** — на API, который возвращает только статус.
- Может **парализовать БД** через тяжёлые payloads (DoS, см. [09-no-pagination](../09-no-pagination/) — близкий мотив).
- Часто **первый этап в Reconnaissance** — атакующий узнаёт структуру через blind, потом переключается на UNION/error-based.

## PostgreSQL specifics

PostgreSQL даёт несколько time-функций:
- **`pg_sleep(N)`** — sleep N секунд.
- **`pg_sleep_for(INTERVAL '1 second')`** — то же через interval.
- **`pg_sleep_until(timestamp)`** — sleep до момента.
- **Тяжёлые вычисления**: `generate_series(1, 100000000)` + `md5()` × N.
- **`pg_database_size('large_db')`** — медленный на больших БД.
- **`(SELECT count(*) FROM huge_table) > 0`** — sleep через тяжёлый count.

Особенность: PostgreSQL **не имеет встроенного механизма для отключения `pg_sleep`** на уровне роли. Управление — только через `statement_timeout` и quotas.

## Пример атаки

**Антипаттерн (даже не вижу результат, только HTTP 200/500):**
```python
user_id = request.args.get("uid")
db.execute(f"UPDATE last_seen SET ts=now() WHERE user_id = {user_id}")
return "ok", 200
```

**Payload (тривиальный):**
```
uid = "1 OR (SELECT pg_sleep(5))"
```
→ если ответ за 5 секунд = injection работает.

**Payload (boolean exfiltration через time):**
```
uid = "1 OR (SELECT CASE WHEN substr((SELECT password FROM users WHERE id=1), 1, 1) = 'a' THEN pg_sleep(5) ELSE pg_sleep(0) END)"
```
→ время ответа 5с = первый символ пароля = 'a', иначе перебираем дальше.

**Payload через тяжёлое вычисление (если `pg_sleep` запрещён):**
```
uid = "1 OR (SELECT count(*) FROM generate_series(1,10000000) WHERE md5(random()::text)::text ~ '0')"
```

## Эталонный fix

Параметризация (как и в [01](../01-sql-injection-classic/)). Плюс несколько защит на уровне роли БД:
```sql
-- Жёсткий лимит на одиночный запрос
ALTER ROLE app_user SET statement_timeout = '5s';

-- (Опционально) запрет на pg_sleep через перехват
REVOKE EXECUTE ON FUNCTION pg_sleep FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_sleep_for FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION pg_sleep_until FROM PUBLIC;
```

Защита через `statement_timeout` — обязательная (см. ADR-0007 §2).

## Как мы детектим

### Phase 1 — `R006-pg-sleep` (ADR-0004)

`pglast.Visitor` ищет `FuncCall` с именем в списке timing-функций:

```python
TIMING_FUNCS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until",
}

def visit_FuncCall(self, ancestors, node):
    name = ".".join(n.sval for n in node.funcname)
    if name in TIMING_FUNCS:
        yield Finding("R006-pg-sleep", risk_score=8, ...)
```

Дополнительные эвристики:
- `generate_series(1, N)` с большим N (>1_000_000) в подзапросе — подозрительно (даже не SQLi, а DoS).
- `CASE WHEN ... THEN pg_sleep(N) ELSE ...` — почти всегда blind-injection.

### Phase 2 — LLM-судья

RAG: CAPEC-7 (Blind SQLi), PortSwigger «Time delays», PG docs про `pg_sleep`.

LLM-судья инструктируется отличать:
- **Legitimate** `pg_sleep` (миграции с задержкой, тесты latency) — FP, понизить severity.
- **Suspicious** — `pg_sleep` в `SELECT`/`WHERE`, или внутри `CASE` под conditional — TP, risk_score=8-9.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == SQL_INJ_TIME`** (`pg_sleep` в разных контекстах + 2 «легитимных» для проверки precision).

- Recall@iter1 ≥ 0.90 (правило простое, AST-имя функции).
- Precision ≥ 0.95 (легитимные `pg_sleep` редки; FP стоит дёшево).
- Δ risk_score: gold-fix (параметризация + `statement_timeout`) → < 4.0.

## Связи

- **ADR-0004** — правило `R006-pg-sleep`.
- **ADR-0005** — RAG: CAPEC-7, PortSwigger Time delays, PG docs.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — Time-based payloads (6 классов атак включают time).
- **PortSwigger** «Conditional time delays» — `kb.payloads`.
- **sqlmap payloads/time_blind.xml** — regression-тест.

## Известные слабости детектора

1. **Тяжёлые вычисления без `pg_sleep`** (`generate_series` + `md5`) — правило `R006` их не покрывает. Дополнительно надо смотреть EXPLAIN cost (см. правило `R010-heavy-plan`, [09-no-pagination](../09-no-pagination/)).
2. **`statement_timeout` обходится через много мелких запросов** — но это уже отдельный класс атак (rate-limiting проблема).
3. Custom timing через расширения (`pgcrypto.crypt(... 'bf', gen_salt('bf', 31))` — bcrypt cost 31 секунды) — теоретически возможно, в нашем eval-set не учитываем.
