# 01 — Большая схема (60 таблиц)

## Что

Реальная схема демо-БД GreenData — `data_model_sql/data_model.sql`, **60 таблиц**, 657 KB DDL:
- Банковско-ERP домен: `acc_number`, `credit_contract`, `business_segment`, `ic_application`, `mler_application`, `dict_product`, и т. д.
- Часть таблиц с «техническими» именами вроде `ms_0n8ohjyx7oszo6a47ca9g0s6f` — смысл вынесен только в `COMMENT ON TABLE`.
- Колонки на английском, `COMMENT ON COLUMN` — на русском (`'ID'`, `'Подразделение'`, `'Тип объекта'`, `'Last modified date'`).
- 60 таблиц × ~15 колонок × ~30 байт DDL = ~30K токенов **только на DDL без комментариев**. Полная схема не лезет в контекст разумной длины.

## Почему критично

Если генератор не «видит» схему — он галлюцинирует имена таблиц и колонок, EX обваливается до 30-40%. Это ставит крест на критерии **EX ≥ 70% (15 баллов)** и косвенно — на работе цикла (`02-reflection-memory-loop`), потому что reflection-память бесполезна, когда базовая структура SQL ломается на каждой итерации.

Из обзора (`research/02_text2sql_benchmarks.md`):
- F1 schema linking резко падает при **> 30 нерелевантных таблиц** в контексте.
- На Spider 2.0 (БД с тысячами колонок) даже SOTA-модели дают 17-36% EX **именно из-за schema linking**.

## Силы, тянущие в разные стороны

| Куда тянет | Аргумент |
|---|---|
| **Подать всю схему** | Не пропустим релевантную таблицу |
| **Подать минимум** | Промпт компактнее, меньше галлюцинаций, дешевле |
| **Подать DDL целиком** | Сохраняется тип, NOT NULL, FK |
| **Подать сжатое представление** | Меньше токенов, легче парсить |
| **Подать только английские имена** | Универсальнее |
| **Подать русские COMMENT** | Без них при русском вопросе модель не свяжет `'Подразделение'` ↔ `org_id` |

## Наше решение (ADR-0003)

Двухступенчатый schema linking:

### Шаг 1. Каталог (офлайн, один раз)
Из `data_model_sql/data_model.sql` парсим в `schema_catalog.json`:
```json
{
  "table": "acc_number",
  "table_comment": "ОСВ: Номер счета",
  "columns": [
    {"name": "id", "type": "bigint", "comment": "ID"},
    {"name": "name__ru", "type": "varchar(2000)", "comment": "Name, ru"},
    ...
  ],
  "foreign_keys": [{"from": "type_id", "to": "sys_obj_type.id"}, ...],
  "sample_values_by_column": {"type_id": [2471461, 2471462, ...]},
  "sample_rows": [...]
}
```

### Шаг 2. Эмбеддинг (офлайн, один раз)
- Каждая таблица → текстовый «карточный» документ:
  `"{table_comment}\nКолонки: {col_name} ({col_comment}), ..."`.
- Эмбеддинг через `intfloat/multilingual-e5-large` (русский + английский), 1024-dim.
- Индекс FAISS `IndexFlatIP`.

### Шаг 3. Retrieval (рантайм, на каждый вопрос)
1. Эмбеддим `task_description`.
2. Top-15 таблиц по cosine.
3. **Замыкание по FK**: для каждой таблицы в топе добавляем те, на которые она ссылается (по `foreign_keys`), даже если их скор ниже.
4. Финальный набор обрезается по бюджету: ≤ 20 таблиц на промпт.

### Шаг 4. Формат промпта (DAIL-SQL Code Representation)
```
-- table: acc_number  -- ОСВ: Номер счета
CREATE TABLE acc_number (
    id bigint, -- ID
    name__ru varchar(2000), -- Name, ru
    ...
);
-- foreign keys: acc_number.type_id = sys_obj_type.id
/* sample rows: (1, 'Расчётный счёт', 2471461, ...) */
```

## Trade-off, который мы приняли

**Риск:** FAISS top-15 может промахнуться (релевантная таблица не в top). Митигация — **замыкание по FK** + при провале аудита по причине «таблица не та» (через reflection-память [02](../02-reflection-memory-loop/)) принудительно добавляем эту таблицу в `state.db_schema_meta` на следующей итерации.

**Бюджет:** 20 таблиц × ~500 токенов = ~10K на DDL + 5K на few-shot + 2K на reflection = ~17K input-токенов. Влезает в 100K+ контекст Qwen-Coder с большим запасом.

## Что измеряем

| Метрика | Цель | Где |
|---|---|---|
| Schema-linking Recall@15 | ≥ 0.90 (нужная таблица в top-15 в 90% случаев) | `eval/run_schema_linking.py` |
| Доля задач с **полным** покрытием (все нужные таблицы в top-15 + FK-замыкание) | ≥ 0.80 | то же |
| EX до и после schema linking | дельта ≥ +15 п.п. | основной eval |

## Связи

- **ADR-0003** — Generator: prompt-engineering with schema linking.
- **ADR-0006** — синтезированный датасет (для эмбеддинга few-shot).
- **research/02_text2sql_benchmarks.md** § 2 — RASL, RSL-SQL, LinkAlign, DBCopilot, SchemaGraphSQL.
- **research/materials/01-generators-multiagent/mag-sql/** — Soft Schema Linker как референс.
- **research/materials/01-generators-multiagent/bappa/** — discussion pipeline с table selector.
- **Исходник схемы:** `data_model_sql/data_model.sql`.
- **Эмбеддинг:** https://huggingface.co/intfloat/multilingual-e5-large
