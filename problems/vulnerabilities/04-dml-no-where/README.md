# 04 — UPDATE / DELETE без WHERE

- **`vuln_class`:** `DML_NO_WHERE`
- **Риск:** 9/10
- **CWE:** [CWE-1284 — Improper Validation of Specified Quantity in Input](https://cwe.mitre.org/data/definitions/1284.html) (косвенно), либо общий «Logic / Authorization Errors».
- **CAPEC:** прямой паттерна нет, концептуально близко к **CAPEC-66** (если попало через injection) или к классу «Destructive operation due to missing predicate».

## Что

Запрос `UPDATE table SET ...` или `DELETE FROM table` **без условия `WHERE`** (или с предикатом, который всегда истинный, типа `WHERE 1=1`). Применяется ко всем строкам таблицы. Часто результат опечатки или копипасты — в проде сразу инцидент.

## Почему опасно (риск 9)

Прямой data integrity disaster:
- **`UPDATE clients SET balance = 0`** — обнулить все балансы.
- **`DELETE FROM orders`** — потеря исторических данных.
- **`DELETE FROM audit_log`** — удаление улик, anti-forensics.

Восстановление возможно только из бэкапа. SLA нарушается, репутационный ущерб высокий. По шкале baseline = 9 (на ступень выше SELECT-уязвимостей, не нарушающих integrity).

В ТЗ (`tusk`) описание: «Модификация или удаление всех строк таблицы из-за отсутствия условия фильтрации».

## PostgreSQL specifics

Postgres даёт несколько «защитных» механизмов, которыми **никто не пользуется по умолчанию**:

- **`SET default_transaction_read_only = on`** для роли — снимает право DML вообще. Применимо для аналитических ролей.
- **Триггеры** `BEFORE UPDATE/DELETE FOR EACH STATEMENT WHEN (NEW.id IS NULL)` — самопальная защита, неуклюжая.
- **Row-Level Security (RLS)** — мощная, но требует явной policy на каждую таблицу.
- **`pg_safeupdate`** (расширение) — отказывает `UPDATE`/`DELETE` без `WHERE`. Не дефолтное.

**Семантические ловушки:**
- `DELETE FROM t USING t2 WHERE ...` — есть `WHERE`, но если `t2` пуст или join cartesian, эффект может быть таким же.
- `UPDATE t SET x = y FROM t2` без `WHERE` — то же.
- `DELETE FROM t WHERE id IN (SELECT id FROM t2)` где `t2` пуст → нулевое удаление. Не наша проблема, но похоже.
- `WHERE 1=1` / `WHERE true` — синтаксически WHERE есть, семантически нет.

## Пример антипаттерна

**Тривиальный:**
```sql
DELETE FROM orders;
UPDATE clients SET balance = 0;
```

**С маскировкой:**
```sql
UPDATE clients SET balance = 0 WHERE 1 = 1;
DELETE FROM orders WHERE TRUE;
DELETE FROM orders WHERE created_at < now();  -- всегда истинно, фактически удаляет всё
```

**JOIN cartesian:**
```sql
-- Намерение: «удалить orders клиентов из чёрного списка»
DELETE FROM orders USING blacklist;  -- забыли ON-условие, удалит всё
```

## Внешние ссылки

- **CWE-1284** — в шапке.
- **PG docs** — `pg_safeupdate` extension, `default_transaction_read_only`.
- **OWASP ASVS V8** — Least Privilege.
- **research/materials/07-deterministic-tools/valk-guard/** — независимая реализация того же чек-листа.

## Варианты решения

См. [solutions.md](solutions.md).
