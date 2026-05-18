# 08 — Избыточный SELECT *

- **`vuln_class`:** `SELECT_STAR`
- **Риск:** 5/10
- **CWE:** [CWE-1295 — Debug Messages Revealing Unnecessary Information](https://cwe.mitre.org/data/definitions/1295.html) (косвенно), общий — «Information Exposure».
- **CAPEC:** нет (это слабая практика, не атака).

## Что

Запрос вида `SELECT * FROM table` / `SELECT t.* FROM table t`. Вместо явного перечисления колонок выбирается всё. Само по себе SELECT * не уязвимость, **но** в production-коде это чаще всего:
- Выбирает чувствительные колонки, которые ни приложению, ни UI не нужны.
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
- **`SELECT *, computed_col FROM ...`** — `*` + дополнительная колонка. Тоже flag.
- **`SELECT COUNT(*) FROM ...`** — **НЕ** этот класс. `COUNT(*)` — псевдо-аргумент, не реальная звёздочка.
- **`INSERT INTO t SELECT * FROM s`** — переносит все колонки, включая возможно чувствительные. Тот же flag.

## Пример антипаттерна

```sql
-- Базовый
SELECT * FROM users WHERE active = true;

-- В подзапросе
SELECT id, name FROM (SELECT * FROM users) u;

-- В composition с JOIN
SELECT * FROM orders o JOIN clients c ON o.client_id = c.id;
-- сразу утечка ВСЕХ колонок clients (PII!) и orders
```

## Внешние ссылки

- **CWE-1295** — в шапке.
- **research/materials/05-security-benchmarks-datasets/securesql-benchmark/** — содержит примеры утечек через SELECT *.
- **sqlfluff правило AM04** (`ambiguous.column_count`) — независимый чек, cross-validation.

## Варианты решения

См. [solutions.md](solutions.md).
