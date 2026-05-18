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

## Внешние ссылки

- **CAPEC-7** Blind SQL Injection — в шапке.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — Time-based payloads.
- **PortSwigger** «Conditional time delays».
- **sqlmap payloads/time_blind.xml** — regression set.
- **PG docs** — `pg_sleep` family.

## Варианты решения

См. [solutions.md](solutions.md).
