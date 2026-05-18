# 09 — Неограниченный LIMIT / отсутствие пагинации

- **`vuln_class`:** `NO_PAGINATION`
- **Риск:** 4/10
- **CWE:** [CWE-770 — Allocation of Resources Without Limits or Throttling](https://cwe.mitre.org/data/definitions/770.html).
- **CAPEC:** нет прямого; концептуально близко к DoS-классу.

## Что

Запрос вида `SELECT ... FROM big_table` (или `SELECT ... FROM big_table ORDER BY ts`) **без `LIMIT`**. На больших таблицах возвращает миллионы строк, что:
- Парализует приложение (нет памяти на result-set).
- Парализует БД (network + planner thrashing).
- Приводит к таймаутам апстрима (load balancer 502, потеря соединения).

В ТЗ (`tusk`): «Запрос без LIMIT может вернуть миллионы строк, вызвав DoS на уровне БД или приложения».

## Почему опасно (риск 4)

На пороге одобрения (`RISK_THRESHOLD = 4.0`). По умолчанию один такой запрос **проходит**, но если рядом есть ещё одна проблема (`SELECT *` 5 + `NO_PAGINATION` 4 = 9 → не одобрен).

Опасно потому что:
- **DoS amplification** — атакующий через UI может многократно вызывать запрос → исчерпание connection pool.
- **Cold-start кеша** — большой `SELECT` вымывает hot-data из shared_buffers, страдают остальные пользователи.
- **Утечка через time** (см. [03-sql-injection-time-blind](../03-sql-injection-time-blind/)) — время выполнения = пропускная способность атакующего.

Риск 4 — но **обязательный класс**: аналитики GreenData часто пишут `SELECT ... FROM acc_number` без LIMIT и валят БД при первом запуске.

## PostgreSQL specifics

- **`statement_timeout`** — спасает от затянувшегося запроса, но не от запроса, который **успевает** вернуть много строк за 5 секунд (sequential scan может быть быстрым).
- **Курсоры** (`DECLARE CURSOR ... FOR SELECT`) — альтернатива пагинации для аналитики; стрим без удара по памяти.
- **`work_mem`** — лимит на оперативку запроса.
- **`FETCH FIRST n ROWS ONLY`** — синоним `LIMIT n` (SQL стандарт).
- **`LIMIT n OFFSET m`** — для пагинации. На больших таблицах **`OFFSET`-пагинация дорогая**; правильная — keyset (`WHERE id > $last_id LIMIT n`).
- **Серверный side cursor** vs **клиентский batch fetch** — psycopg3 даёт `cursor.itersize`. Часто `LIMIT` не нужен, если приложение читает батчами.

## Пример антипаттерна

```sql
-- УЯЗВИМО (большие таблицы)
SELECT id, name, balance FROM clients ORDER BY created_at DESC;
SELECT * FROM acc_number WHERE status = 1;

-- Псевдо-пагинация
SELECT id, name FROM clients ORDER BY id OFFSET 100000;  -- забыт LIMIT
```

И «маскировочный» вариант:
```sql
SELECT id, name FROM clients ORDER BY created_at DESC LIMIT 1000000;
-- LIMIT есть, но огромный = ровно та же проблема
```

## Внешние ссылки

- **CWE-770** — в шапке.
- **PG docs** — `DECLARE CURSOR`, `FETCH`, `LIMIT`.
- **sqlfluff правило AM09** (`ambiguous.order_by_limit`) — cross-check (LIMIT без ORDER BY).
- **Связанная проблема:** [03-sql-injection-time-blind](../03-sql-injection-time-blind/) — time-DoS через тяжёлые `generate_series`.

## Варианты решения

См. [solutions.md](solutions.md).
