# Варианты решения: Неограниченный LIMIT

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс «нет LIMIT» | Тривиально | FP на агрегатах, на подзапросах, на CTE | ❌ |
| B | **AST `SelectStmt.limitCount is None` + игнор агрегатов/подзапросов/CTE** | Точно | Не оценивает «размер таблицы» — для маленьких справочников будет FP | ✅ ядро |
| C | B + EXPLAIN cost-check (`Plan Rows > N`) | Семантика, реальная оценка | Требует sandbox-данных; FP при faker'е | ⚠️ опциональный комплемент |
| D | B + знание размера таблицы из `information_schema.tables.reltuples` | Дёшево, точно | Не работает на пустых таблицах sandbox | ⚠️ опциональный комплемент |
| E | runtime detection: смотреть реальные latency | Самый точный | Не работает на статическом аудите | not applicable |
| F | `sqlfluff` правило AM09 (LIMIT без ORDER BY) | Готовое | Это РЯДОМ, но не наш класс | cross-check |

## Эталонный fix (что предлагает судья)

| Сценарий | Fix |
|---|---|
| UI-выборка | `LIMIT 100` + ORDER BY |
| Пагинация | Keyset: `WHERE id < $last_seen_id ORDER BY id DESC LIMIT 50` |
| Аналитика | Серверный курсор: `DECLARE c CURSOR FOR ...; FETCH 1000 FROM c` |
| Batch fetch на стороне клиента | `cursor.itersize = 1000` (psycopg3) |
| Защита роли | `ALTER ROLE analytics_role SET statement_timeout = '10s'`, `SET work_mem = '32MB'` |

## Что выбрали и почему

**B** как Phase 1; **C — опциональный комплемент при доступной sandbox**. На MVP сначала только B, потом расширяем.

Аргументы:
- B детерминирован, дешёв, понятен. На 90% задач достаточно.
- C даёт точную семантику, но требует sidekick (sandbox-БД). Включаем в P1.5, когда sandbox уже работает (нужен для других правил все равно).
- Знание размера таблицы (D) — overkill; faker-сидинг даёт ~1000 строк на таблицу, что не отражает прод.

## Реализация

### Phase 1 — `R004-no-limit` (ADR-0004)

```python
class NoLimit(Visitor):
    def visit_SelectStmt(self, ancestors, node):
        # Игнорируем агрегаты (мало строк)
        if has_group_by_or_aggregate(node):
            return
        # Игнорируем подзапросы (limit нужен на верхнем уровне)
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
                evidence_refs=["CWE-770"],
            )
        else:
            lim = eval_const(node.limitCount)
            if lim is not None and lim > 10000:
                yield Finding("R004-no-limit",
                              severity="low", risk_score=3,
                              note=f"LIMIT {lim} избыточен")
```

### Phase 1b — `R010-heavy-plan` (ADR-0004 §3)

Sandbox EXPLAIN:
- `Plan Rows > 100_000` → severity:medium, risk_score=5 (часто срабатывает в паре с `R004`).
- `Total Cost > 100_000` → severity:high, risk_score=6.

### Phase 2 — LLM-судья

RAG: PG docs про cursors, keyset-pagination статьи (в `kb.postgres`).

Инструкция:
1. Контекст: маленький справочник (по комментарию в схеме видно «справочник X») → понизить severity.
2. Агрегат уже игнорируется в Phase 1, но если `GROUP BY ... GROUPING SETS` возвращает много строк — обработать.
3. Рекомендация: конкретный `LIMIT` или keyset, в зависимости от `task_description`.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == NO_PAGINATION`**:
- 5 `SELECT ... FROM big_table` без LIMIT.
- 3 с `LIMIT 1_000_000` (маскировка).
- 2 агрегата без LIMIT (FP-проверка).

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.90 |
| Precision | ≥ 0.85 (агрегаты — главный FP) |
| `overall_risk_score` после fix | 0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| `UNION ALL` без LIMIT в каждой ветви | Phase 1 ловит верхний SelectStmt; достаточно |
| `SELECT * INTO TEMP TABLE` без LIMIT | Опасно (память), но другой класс; можно расширить |
| CTE-большие наборы (`WITH huge AS ...`) | Phase 1 не видит внутри CTE; legitimate analytics частая |
| `SELECT * FROM generate_series(1, 10000000)` | `R004` сработает (нет LIMIT); Phase 2 повышает severity (это намеренная генерация, ссылка на blind-injection [03](../03-sql-injection-time-blind/)) |

## Связи с ADR

- **ADR-0004** — `R004`, `R010-heavy-plan`.
- **ADR-0005** — `kb.postgres` (cursors, keyset).
- **ADR-0007** — sandbox EXPLAIN для `R010`.
