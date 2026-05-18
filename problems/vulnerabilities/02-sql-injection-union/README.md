# 02 — Union-based Injection

- **`vuln_class`:** `SQL_INJ_UNION`
- **Риск:** 9/10
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html) (вариант)
- **CAPEC:** [CAPEC-66](https://capec.mitre.org/data/definitions/66.html), частный случай.

## Что

Вариант SQLi, где атакующий через `UNION SELECT` дописывает к легитимному запросу второй, извлекая данные **из других таблиц**, не предусмотренных оригинальной выборкой. Атакующий подбирает совместимое число и типы колонок, затем читает что хочет.

## Почему опасно (риск 9)

Чуть ниже «классики» (10) потому, что:
- Требует, чтобы оригинальный запрос выводил данные пользователю.
- Не даёт сразу `UPDATE`/`DELETE` (для этого нужен stacked-injection, см. [01-sql-injection-classic](../01-sql-injection-classic/)).

Но всё ещё критичен:
- **Сквозное чтение** любой таблицы в схеме.
- Через `information_schema.columns` — полная enumeration схемы → дальнейшая атака точечно.
- Через `pg_authid` (если роль имеет `SELECT`) — хеши паролей superuser.

## PostgreSQL specifics

- **Типы должны совпадать** — `UNION` требует, чтобы типы колонок были совместимы. Атакующий обходит через `NULL`, `CAST('...' AS text)`, `::text`.
- **`information_schema` доступна `PUBLIC`** по умолчанию — атакующий всегда может прочитать структуру схемы.
- **`pg_catalog` доступен `PUBLIC`** — атакующий узнаёт имена ролей, owner'ов таблиц.
- **`UNION ALL` vs `UNION`** — оба подходят, `UNION ALL` быстрее и не дедуплицирует.
- В payload часто комментарий `--` в конце — отрезает «хвост» оригинального запроса.

## Пример атаки

**Антипаттерн:**
```python
search = request.args.get("q")
cursor.execute(f"SELECT id, title FROM products WHERE title ILIKE '%{search}%'")
```

**Payload (определение числа колонок):**
```
q = "x' UNION SELECT NULL, NULL --"
q = "x' UNION SELECT NULL, NULL, NULL --"
```
→ когда не падает «UNION queries must have the same number of columns» — нашли число.

**Payload (определение строкового индекса):**
```
q = "x' UNION SELECT 'a', NULL --"
q = "x' UNION SELECT NULL, 'a' --"
```
→ когда возвращается видимое `'a'` — нашли строковый столбец, доступный пользователю.

**Payload (эксфильтрация):**
```
q = "x' UNION SELECT username, password_hash FROM auth.users --"
q = "x' UNION SELECT table_name, NULL FROM information_schema.tables --"
q = "x' UNION SELECT current_user, version() --"
```

## Эталонный fix

То же что и в [01](../01-sql-injection-classic/) — параметризация:
```python
cursor.execute(
    "SELECT id, title FROM products WHERE title ILIKE %s",
    (f"%{search}%",),
)
```

Дополнительно — **отзыв `SELECT` на чувствительные таблицы у роли приложения**. Принцип наименьших привилегий из OWASP ASVS V8.

## Как мы детектим

### Phase 1 — `R005-union-suspicious` (ADR-0004)

`pglast.Visitor` обходит `SelectStmt`:

```python
def visit_SelectStmt(self, ancestors, node):
    if node.op == enums.SetOperation.SETOP_UNION:
        upper_cols = count_targets(node.larg)
        lower_cols = count_targets(node.rarg)
        if upper_cols != lower_cols:
            yield Finding("R005-union-suspicious", ...)  # типовая попытка
        if has_information_schema_or_pg_catalog(node.rarg):
            yield Finding("R005-union-suspicious", risk_score=9, ...)
        if has_null_only_select(node.rarg) and is_user_input(snippet):
            yield Finding("R005-union-suspicious", ...)  # probe-payload
```

Эвристики Phase 1:
1. Несогласованное число колонок в `UNION` (часто остаток от probe).
2. Доступ к `information_schema.*` или `pg_catalog.*` в нижней части `UNION`.
3. `SELECT NULL, NULL, ...` (probe-payload).
4. `UNION SELECT` с литералом, идентичным значению в `WHERE` верхнего select'а (попытка отзеркалить колонку для эксфильтрации).

### Phase 2 — LLM-судья

RAG-контекст: CAPEC-66 (Union variant), PortSwigger «Retrieving data from other tables» chapter.
Промпт инструктирует судью **различать**:
- Легитимный `UNION` в аналитическом запросе (например, объединение акт. и архивных таблиц) → FP.
- Подозрительный `UNION` с probe-паттернами или системными каталогами → TP.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == SQL_INJ_UNION`** (адаптации из sqlmap `union_query.xml`).

- Recall@iter1 ≥ 0.80.
- Precision ≥ 0.85 (легитимные `UNION` в datawarehouse-стиле не должны помечаться).
- Δ risk_score: gold-fix должен снизить до < 4.0.

## Связи

- **ADR-0004** — Phase 1 правило `R005`.
- **ADR-0005** — RAG-чанки CAPEC-66, OWASP SQLi CS.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — datasets с union-payloads.
- **PortSwigger SQLi cheat sheet** — `kb.payloads` (Union-based section).
- **sqlmap payloads/union_query.xml** — для regression-теста.

## Известные слабости детектора

1. **Обфускация комментариями**: `UNION/*comment*/SELECT` — Phase 1 регулярка может промахнуться, но pglast AST ловит независимо от форматирования.
2. **Двухступенчатые атаки**: `UNION` собирается не в одном запросе, а через несколько API-вызовов с накоплением state. Невозможно поймать на одном SQL.
3. **Легитимные analytical-`UNION`** — будут FP без точной настройки правила; полагаемся на Phase 2 для отфильтровки.
