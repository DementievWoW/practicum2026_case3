# Варианты решения: Schema Linking на 60+ таблиц

## Альтернативные подходы

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Подать всю схему в промпт | Не пропустим ни одной таблицы | Не лезет в контекст; F1 падает при >30 нерелевантных таблиц | ❌ |
| B | Manual rules: ключевые слова в `task_description` → таблицы | Прозрачно | Хрупкое, ломается на парафразе и русско-английских терминах | ❌ |
| C | **Эмбеддинг таблиц + FAISS top-K по вопросу** | Семантический поиск, языко-независимо | Может промахнуться (top-K не содержит нужную таблицу) | ✅ ядро |
| D | C + замыкание по FK | Восстанавливает JOIN-связи | Доп. логика, но дешёвая | ✅ обязательное расширение |
| E | RASL: разложение на семантические единицы (таблица + колонки + FK отдельно) | Tighter retrieval | Усложнение индекса | для v2 |
| F | DBCopilot: lightweight router-модель | Производительность | Нужен fine-tune; вне MVP | для v2 |
| G | SchemaGraphSQL: графовый обход FK | Гарантирует связность | Сложнее имплементировать | для v2 |
| H | LinkAlign: multi-pass semantic filtering | Лучший SOTA на open-source | Дорого по времени | вне MVP |

## Эталонный формат промпта генератору

**DAIL-SQL Code Representation** (см. ADR-0003 §3):

```
-- table: acc_number  -- ОСВ: Номер счета
CREATE TABLE acc_number (
    id bigint, -- ID
    name__ru varchar(2000), -- Name, ru
    type_id bigint, -- Тип объекта
    ...
);
-- foreign keys: acc_number.type_id = sys_obj_type.id
/* sample rows: (1, 'Расчётный счёт', 2471461, ...) */
```

## Что выбрали и почему

**C + D (FAISS top-15 + замыкание по FK)** — минимально работающий baseline для 60-табличной схемы.

Аргументы:
- C+D просто реализуется и легко отлаживается (видно в логе, какие таблицы вернулись).
- Для 60 таблиц top-15 даёт хорошее покрытие (research показывает: при <30 нерелевантных в контексте F1 не падает).
- FK-замыкание — must-have: модель часто пишет JOIN, забыв справочник, и без замыкания SQL не компилируется.
- E/F/G/H — оптимизации для v2; на хакатоне нет ресурса на fine-tune router'а.

## Реализация (ADR-0003)

### Шаг 1. Каталог (офлайн)
Из `data_model_sql/data_model.sql` парсим в `schema_catalog.json`:
```json
{
  "table": "acc_number",
  "table_comment": "ОСВ: Номер счета",
  "columns": [{"name": "id", "type": "bigint", "comment": "ID"}, ...],
  "primary_key": ["id"],
  "foreign_keys": [{"from": "type_id", "to": "sys_obj_type.id"}, ...],
  "sample_values_by_column": {"type_id": [2471461, ...]},
  "sample_rows": [...]
}
```

### Шаг 2. Эмбеддинг (офлайн)
- Каждая таблица → текстовый «карточный» документ: `"{table_comment}\nКолонки: {col_name} ({col_comment}), ..."`.
- Эмбеддинг через `intfloat/multilingual-e5-large` (русский + английский), 1024-dim.
- Индекс FAISS `IndexFlatIP`.

### Шаг 3. Retrieval (рантайм)
```python
def schema_link(task_description: str) -> list[str]:
    q_emb = model.encode([task_description])[0]
    scores, ids = faiss.search(q_emb, k=15)
    selected = {tables[i] for i in ids}
    # FK-замыкание
    for t in list(selected):
        for fk in catalog[t]["foreign_keys"]:
            referenced = fk["to"].split(".")[0]
            selected.add(referenced)
    # Бюджет
    return list(selected)[:20]
```

### Шаг 4. Сборка промпта
Берём DDL только выбранных таблиц + FK-секции + sample rows.

## Что измеряем

| Метрика | Цель |
|---|---|
| Schema-linking Recall@15 (нужная таблица в top-15) | ≥ 0.90 |
| Доля задач с полным покрытием (все нужные таблицы + FK) | ≥ 0.80 |
| EX до и после schema linking | дельта ≥ +15 п.п. |
| Token budget на промпт DDL | ≤ 10K |

## Что может пойти не так

| Проблема | Митигация |
|---|---|
| FAISS top-15 промахнулся (нужная таблица не в top) | Reflection-память ([02](../02-reflection-memory-loop/)) принудительно добавит на retry-итерации |
| Sample rows из реальной демо-БД содержат ПДн | Снимаем sample только из faker-sandbox (ADR-0004 §5), не из боевой |
| Бюджет токенов превышен на retry с большой reflection | Per-iteration budget cap + truncation reflection до 5 lessons |
| Schema linking сам по себе медленный (FAISS over 60 docs) | 60 docs тривиально быстро (~10 мс), не bottleneck |
| Эмбеддинг-модель забывает редкие термины (`ОСВ`, `РКО`) | Можно сделать domain-specific finetune `multilingual-e5`; вне MVP |

## Связи с ADR

- **ADR-0003** — главный design doc; промпт-инжиниринг и schema linking.
- **ADR-0006** — train-set для few-shot отбора по similarity (тот же FAISS).
- **ADR-0001** — `sentence-transformers` + `faiss-cpu` в зависимостях.
