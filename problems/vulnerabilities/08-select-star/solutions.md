# Варианты решения: Избыточный SELECT *

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс `SELECT\s+\*` | 5 секунд | FP на `COUNT(*)`, `ROW(*)`, `row_to_json(t.*)`; не различает контекст | ❌ |
| B | **AST `SelectStmt.targetList` → `A_Star` в `ColumnRef.fields`** | Точно, отличает `COUNT(*)` (внутри FuncCall) | Не оценивает severity без знания таблицы | ✅ ядро |
| C | B + expand через `information_schema.columns` (sandbox) | Раскрывает в реальные колонки → подсветка чувствительных | Нужен sandbox-доступ; цена | ✅ расширение |
| D | `sqlfluff` правило **AM04** (`ambiguous.column_count`) | Готовое решение | Дублирует pglast, не даёт нам семантики (severity по контексту) | cross-validation |
| E | LLM-only | Гибкий | Дороже, FP/FN | вне нашей политики |

## Эталонный fix (что предлагает судья)

| Сценарий | Fix |
|---|---|
| Стандартный | Перечисление нужных колонок |
| JOIN с двумя таблицами | `SELECT a.col1, a.col2, b.col3 FROM ...` |
| ORM-генератор | Сменить настройку ORM на explicit columns |
| Backup / table copy | `INSERT INTO ... SELECT *` оправдан → low severity |
| Defence в глубину | Колоночные привилегии у роли (даже если SQL с `*`, БД отдаст только разрешённое) |

## Что выбрали и почему

**B + C** как Phase 1, **D — независимый CI-check для sanity validation**.

Аргументы:
- B детерминирован, near-100% Recall на правильно сформулированных AST-обходах.
- C даёт **семантику severity**: если в expanded списке нет чувствительных колонок — low severity (просто good practice); если есть — high severity и crosslink с [07-direct-sensitive-access](../07-direct-sensitive-access/).
- D добавляем как «второе мнение» в CI — если расхождение между pglast и sqlfluff, это сигнал на debug правила.

## Реализация

### Phase 1 — `R001-select-star` (ADR-0004)

```python
class SelectStar(Visitor):
    def visit_SelectStmt(self, ancestors, node):
        for target in node.targetList or []:
            if not isinstance(target.val, ColumnRef):
                continue
            fields = target.val.fields
            # СЛУЧАЙ 1: bare * → fields = [A_Star]
            # СЛУЧАЙ 2: t.* → fields = [String("t"), A_Star]
            if not any(isinstance(f, A_Star) for f in fields):
                continue
            if is_inside_func(ancestors, names={"count", "row", "row_to_json", "to_jsonb"}):
                # COUNT(*) допустим; row_to_json(t.*) — серьёзнее (JSON-сериализация всего)
                if is_inside_func(ancestors, names={"row_to_json", "to_jsonb"}):
                    yield Finding(rule_id="R001-select-star",
                                  severity="high", risk_score=7,
                                  note="row_to_json(t.*) сериализует всю строку, включая ПДн")
                continue
            yield Finding(
                rule_id="R001-select-star",
                vuln_class="SELECT_STAR",
                severity="medium", risk_score=5,
                snippet="SELECT *" if len(fields) == 1 else f"{fields[0].sval}.*",
                evidence_refs=["CWE-1295"],
            )
```

### Phase 1b — expand с sandbox

Если есть таблица в sandbox — раскрываем `*` в полный список колонок, прогоняем правило [07](../07-direct-sensitive-access/) на каждой. Если найдены чувствительные:
- Повысить severity `R001` до high.
- Выпустить дополнительный `R009-sensitive-columns` finding.
- В Phase 2 LLM соединит оба finding'а в один человеко-читаемый recommendation.

### Phase 2 — LLM-судья

RAG: OWASP ASVS V8 (information exposure), общие best practices.

Инструкция:
1. Контекст: `SELECT * INTO TEMP TABLE` для копирования — low severity.
2. Если expand даёт чувствительные колонки — high severity, рекомендация с явным списком.
3. Рекомендация ссылается на `task_description` — какие колонки реально нужны для задачи.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == SELECT_STAR`**:
- 3 базовых `SELECT *`.
- 3 `SELECT t.*` в JOIN.
- 2 `SELECT *` в подзапросе.
- 2 «good»-версии с явным списком + `COUNT(*)` для FP-проверки.

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.95 |
| Precision | ≥ 0.95 (главный FP — `COUNT(*)`) |
| `overall_risk_score` после fix | 0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| `COUNT(*)` ложный позитив | `is_inside_func({"count", "row", ...})` |
| `row_to_json(t.*)` — JSON-сериализация всей строки | Отдельная ветка правила с severity:high |
| `SELECT * EXCEPT (col)` (BigQuery-синтаксис, в PG нет) | pglast не распарсит, finding не появится |
| `CREATE TABLE AS SELECT *` | Не наш класс, но похожий — расширение `R001b` при желании |

## Связи с ADR

- **ADR-0004** — `R001`.
- **ADR-0007** — sandbox `information_schema` для expand.
- **Связанная проблема:** [07-direct-sensitive-access](../07-direct-sensitive-access/) — `R001` усиливает `R009` через expansion.
