# 08 — Избыточный SELECT *

- **`vuln_class`:** `SELECT_STAR`
- **Риск:** 5/10
- **CWE:** [CWE-1295 — Debug Messages Revealing Unnecessary Information](https://cwe.mitre.org/data/definitions/1295.html) (косвенно), общий — «Information Exposure».
- **CAPEC:** нет (это слабая практика, не атака).

## Что

Запрос вида `SELECT * FROM table` / `SELECT t.* FROM table t`. Вместо явного перечисления колонок выбирается всё. Само по себе SELECT * не уязвимость, **но** в production-коде это чаще всего:
- Выбирает чувствительные колонки, которые ни приложению ни UI не нужны.
- Ломается при `ALTER TABLE ADD COLUMN` (поведение меняется молча).
- Тащит лишний трафик и память.
- Усиливает риски при composition с другими уязвимостями (SQLi → `UNION SELECT *` крадёт всё, не нужно угадывать колонки).

В ТЗ (`tusk`): «Выборка всех полей таблицы, включая потенциально чувствительные (пароли, токены, персональные данные)».

## Почему опасно (риск 5)

«Среднее зло». Не разрушает данные, не даёт прямого RCE, но:
- **Превращает `DIRECT_SENSITIVE` (риск 6) в постоянного спутника** — если хоть одна чувствительная колонка есть в таблице, SELECT * её утянет.
- **Защита depth-in-defense проваливается**: даже если на host-уровне фильтруется поле, SQL уже его выбрал → попало в логи, prepared-statement cache, query stats.
- **Аналитические дашборды** (BI tools часто пишут SELECT * через ORM) — главный канал утечки PII в практике.

Риск 5 = на пороге одобрения (4.0). Один `SELECT *` сам по себе пройдёт; в комбинации с `DIRECT_SENSITIVE` — превышает порог.

## PostgreSQL specifics

- **`SELECT *` в подзапросе** часто оптимизатор переписывает (column pruning), но это поведенческая оптимизация, не семантика.
- **`SELECT t.* FROM table t JOIN other o ON ...`** — `t.*` ограничен таблицей `t`. Менее опасно, чем `SELECT *` с JOIN.
- **`SELECT *, computed_col FROM ...`** — `*` + дополнительная колонка. Тоже flag'ить.
- **`SELECT ROW(*) FROM ...`** — крайне редко, но возможно.
- **`SELECT COUNT(*) FROM ...`** — это **НЕ** этот класс. `COUNT(*)` — псевдо-аргумент, не реальная звёздочка. Phase 1 правило должно их различать.
- **`INSERT INTO t SELECT * FROM s`** — переносит все колонки, включая возможно чувствительные. Тот же flag.

## Пример антипаттерна

```sql
-- Базовый
SELECT * FROM users WHERE active = true;

-- В подзапросе
SELECT id, name FROM (SELECT * FROM users) u;

-- В composition с JOIN
SELECT * FROM orders o JOIN clients c ON o.client_id = c.id;
-- сразу утечка ВСЕХ колонок clients (PII!) ВСЕХ колонок orders
```

## Эталонный fix

Перечисление нужных колонок:
```sql
SELECT id, login, email FROM users WHERE active = true;

SELECT o.id, o.amount, c.full_name
FROM orders o
JOIN clients c ON o.client_id = c.id;
```

**Защита на уровне роли:** колоночные привилегии (см. [07-direct-sensitive-access](../07-direct-sensitive-access/)) — даже если запрос с `*`, БД отдаст только разрешённые колонки. Это самая надёжная защита, потому что не зависит от автора SQL.

## Как мы детектим

### Phase 1 — `R001-select-star` (ADR-0004)

`pglast.Visitor` по `SelectStmt`:

```python
class SelectStar(Visitor):
    def visit_SelectStmt(self, ancestors, node):
        for target in node.targetList or []:
            # ResTarget с val — ColumnRef, проверим .fields на A_Star
            if isinstance(target.val, ColumnRef):
                fields = target.val.fields
                # СЛУЧАЙ 1: bare * → fields = [A_Star]
                # СЛУЧАЙ 2: t.* → fields = [String("t"), A_Star]
                if any(isinstance(f, A_Star) for f in fields):
                    is_count = is_inside_count_func(ancestors)
                    if is_count:
                        continue
                    yield Finding(
                        rule_id="R001-select-star",
                        vuln_class="SELECT_STAR",
                        severity="medium", risk_score=5,
                        location=target.val.location,
                        snippet="SELECT *" if len(fields) == 1 else f"{fields[0].sval}.*",
                        evidence_refs=["CWE-1295", "OWASP-DR-DefenseInDepth"],
                    )
```

### Phase 1b — expand с информацией из sandbox

Если в sandbox-БД есть таблица — раскрываем `*` в полный список колонок и проверяем на чувствительные имена (правило [07-direct-sensitive-access](../07-direct-sensitive-access/) reuse). Если есть совпадения — **повышаем severity** найденного `R001` до high и **выпускаем дополнительный `R009-sensitive-columns`** finding.

### Phase 2 — LLM-судья

RAG: OWASP ASVS V8 (information exposure), общие best practices.

LLM:
1. Проверяет контекст — не находится ли SELECT * в SELECT INTO для копирования таблицы (тогда может быть оправдано).
2. Если есть expand — формирует рекомендацию с **конкретным списком колонок**, которые нужны для задачи (опираясь на `task_description`).

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == SELECT_STAR`**:
- 3 базовых `SELECT *` (разные таблицы).
- 3 `SELECT t.*` в JOIN.
- 2 `SELECT *` в подзапросе.
- 2 «good»-версии с явным списком колонок (для проверки FP на `COUNT(*)`, `ROW(*)`).

- Recall@iter1 ≥ 0.95 (правило тривиальное).
- Precision ≥ 0.95 (главный FP — `COUNT(*)`, надо различать).
- Δ risk_score: gold-fix с явными колонками → 0.

## Связи

- **ADR-0004** — правило `R001`.
- **ADR-0005** — RAG: OWASP CS, общие best practices.
- **Связанная проблема:** [07-direct-sensitive-access](../07-direct-sensitive-access/) — `R001` усиливает `R009` через expansion.
- **research/materials/05-security-benchmarks-datasets/securesql-benchmark/** — содержит примеры утечек через SELECT *.
- **sqlfluff** правило **AM04** (`ambiguous.column_count`) — тот же класс, можно использовать как cross-check.

## Известные слабости детектора

1. **`COUNT(*)` ложный позитив** — критично различать. Правило проверяет `is_inside_count_func`.
2. **`row_to_json(t.*)`** или `to_jsonb(t.*)` — `t.*` внутри функции. Раскрытие в JSON. Phase 1 ловит как `R001`, severity high (JSON-сериализация ПДн — отдельный вектор утечки).
3. **`SELECT ARRAY[*]`** — не валидный синтаксис в Postgres, не наш кейс.
4. **`SELECT * EXCEPT (col)`** — этого синтаксиса в Postgres нет (BigQuery/DuckDB). Если встретится в input — pglast не распарсит, finding не появится.
5. **DDL `CREATE TABLE AS SELECT *`** — не наш класс, но похожий «бездумный copy». Можно расширить правилом `R001b` при необходимости.
