# 01 — Большая схема (60 таблиц)

## Что

Реальная схема демо-БД GreenData — `data_model_sql/data_model.sql`, **60 таблиц**, 657 KB DDL:
- Банковско-ERP домен: `acc_number`, `credit_contract`, `business_segment`, `ic_application`, `mler_application`, `dict_product`, и т. д.
- Часть таблиц с «техническими» именами вроде `ms_0n8ohjyx7oszo6a47ca9g0s6f` — смысл вынесен только в `COMMENT ON TABLE`.
- Колонки на английском, `COMMENT ON COLUMN` — на русском (`'ID'`, `'Подразделение'`, `'Тип объекта'`, `'Last modified date'`).
- 60 таблиц × ~15 колонок × ~30 байт DDL = ~30K токенов **только на DDL без комментариев**. Полная схема не лезет в контекст разумной длины.

## Почему критично

Если генератор не «видит» схему — он галлюцинирует имена таблиц и колонок, EX обваливается до 30-40%. Это ставит крест на критерии **EX ≥ 70% (15 баллов)** и косвенно — на работе цикла ([02-reflection-memory-loop](../02-reflection-memory-loop/)), потому что reflection-память бесполезна, когда базовая структура SQL ломается на каждой итерации.

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

## Внешние ссылки

- **Исходник схемы:** `data_model_sql/data_model.sql`.
- **research/02_text2sql_benchmarks.md** § 2 — RASL, RSL-SQL, LinkAlign, DBCopilot, SchemaGraphSQL.
- **research/materials/01-generators-multiagent/mag-sql/** — Soft Schema Linker.
- **research/materials/01-generators-multiagent/bappa/** — discussion pipeline с table selector.
- **Эмбеддинг:** https://huggingface.co/intfloat/multilingual-e5-large

## Варианты решения

См. [solutions.md](solutions.md).
