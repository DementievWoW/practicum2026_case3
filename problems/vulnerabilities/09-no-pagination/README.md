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

Риск 4 = «слабое звено», но в нашей задаче — **обязательный класс**, потому что аналитики GreenData часто пишут `SELECT ... FROM acc_number` (это таблица из `data_model_sql/`) без LIMIT и валят БД при первом запуске.

## PostgreSQL specifics

- **`statement_timeout`** — спасает от затянувшегося запроса, но не от запроса, который **успевает** вернуть много строк за 5 секунд (sequential scan может быть быстрым).
- **Курсоры** (`DECLARE CURSOR ... FOR SELECT`) — альтернатива пагинации для аналитики; стрим без удара по памяти.
- **`work_mem`** — лимит на оперативку запроса. Если задан низко — большой `ORDER BY` будет писать на диск (slow, но не upset).
- **`FETCH FIRST n ROWS ONLY`** — синоним `LIMIT n` (SQL стандарт).
- **`LIMIT n OFFSET m`** — для пагинации. На больших таблицах **`OFFSET`-пагинация дорогая**; правильная — keyset pagination (`WHERE id > $last_id LIMIT n`).
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

## Эталонный fix

**Опция 1 — простой LIMIT:**
```sql
SELECT id, name, balance FROM clients ORDER BY created_at DESC LIMIT 100;
```

**Опция 2 — keyset pagination:**
```sql
SELECT id, name FROM clients
WHERE id < $last_seen_id
ORDER BY id DESC
LIMIT 50;
```

**Опция 3 — серверный cursor для аналитики:**
```sql
BEGIN;
DECLARE c CURSOR FOR SELECT id, name FROM clients ORDER BY id;
FETCH 1000 FROM c;  -- итеративно
-- ...
CLOSE c;
COMMIT;
```

**Защита на уровне роли:**
```sql
ALTER ROLE analytics_role SET statement_timeout = '10s';
ALTER ROLE analytics_role SET work_mem = '32MB';
```

## Как мы детектим

### Phase 1 — `R004-no-limit` (ADR-0004)

```python
class NoLimit(Visitor):
    def visit_SelectStmt(self, ancestors, node):
        # Игнорируем агрегированные запросы (они возвращают мало строк)
        if has_group_by_or_aggregate(node):
            return
        # Игнорируем подзапросы — limit нужен на верхнем уровне
        if is_subquery(ancestors):
            return
        # Игнорируем CTE-внутренности
        if is_cte_query(ancestors):
            return
        if node.limitCount is None:
            yield Finding(
                rule_id="R004-no-limit",
                vuln_class="NO_PAGINATION",
                severity="low", risk_score=4,
                message="SELECT без LIMIT — потенциальный DoS на больших таблицах",
                evidence_refs=["CWE-770"],
            )
        else:
            # LIMIT есть, но абсурдно большой
            lim = eval_const(node.limitCount)
            if lim is not None and lim > 10000:
                yield Finding("R004-no-limit", severity="low", risk_score=3, message="LIMIT > 10000")
```

### Phase 1b — EXPLAIN cost check (`R010-heavy-plan`)

Связано с этим классом, но отдельное правило (см. ADR-0004 §3). Sandbox-EXPLAIN: если `Plan Rows > 100_000` — heavy plan finding. Часто срабатывает в комплекте с `R004`.

### Phase 2 — LLM-судья

RAG: PG docs про cursors, keyset-pagination статьи (можно добавить в `kb.postgres`).

LLM:
1. Проверяет, насколько таблица большая по контексту (если из `data_model_sql/` известно, что таблица справочник на 50 строк — FP, low severity).
2. Различает агрегацию (`COUNT`, `SUM`, `AVG`) от выборки строк — для агрегатов FP.
3. Рекомендует конкретный LIMIT или keyset.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == NO_PAGINATION`**:
- 5 `SELECT ... FROM big_table` без LIMIT.
- 3 с `LIMIT 1_000_000` (маскировка).
- 2 агрегата без LIMIT (для проверки FP — `COUNT`, `SUM`).

- Recall@iter1 ≥ 0.90.
- Precision ≥ 0.85 (агрегаты — главный источник FP; правило их игнорирует, но «GROUP BY с GROUPING SETS» может вернуть много строк → отдельный edge case).
- Δ risk_score: gold-fix с `LIMIT 100` → 0.

## Связи

- **ADR-0004** — правила `R004`, `R010-heavy-plan`.
- **PG docs** — `DECLARE CURSOR`, `FETCH`, `LIMIT`.
- **sqlfluff правило AM09** (`ambiguous.order_by_limit`) — cross-check (LIMIT без ORDER BY — не наш класс, но рядом).
- **Связанная проблема:** [03-sql-injection-time-blind](../03-sql-injection-time-blind/) — time-DoS через тяжёлые `generate_series` ловится тем же EXPLAIN cost-правилом.

## Известные слабости детектора

1. **`UNION ALL` без LIMIT** — каждая ветвь без LIMIT, объединённый result огромен. Текущий visitor flag'нет верхний SelectStmt, но не отдельные ветви. Достаточно.
2. **`SELECT ... INTO TEMP TABLE`** — без LIMIT тоже опасно (память), хотя строк меньше уйдёт в клиента. Расширить правило при желании.
3. **CTE-материализованные большие наборы** — `WITH huge AS (SELECT * FROM big_table) SELECT count(*) FROM huge` — Phase 1 не видит, что внутри CTE нет LIMIT. CTE мы пока не флагуем (CTE-аналитика часто легитимна).
4. **`SELECT * FROM generate_series(1, 10000000)`** — Phase 1 правило `R004` сработает (нет LIMIT), но это не «таблица» в обычном смысле. Phase 2 должен повысить severity, потому что это **намеренная** генерация (см. правила blind-injection в [03](../03-sql-injection-time-blind/)).
