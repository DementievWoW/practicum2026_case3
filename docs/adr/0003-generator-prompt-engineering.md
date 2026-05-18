# ADR-0003 — SQL generator: prompt-engineering with schema linking, no fine-tuning

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`):

- «выбрать и реализовать метод формирования запросов
  (промпт-инжиниринг, RAG или fine-tuning)».
- Execution Accuracy ≥ 70 % (15 баллов).
- Целевая модель ≤ 30B параметров, контекстное окно 100–256 K токенов.

Схема (`data_model_sql/data_model.sql`):

- 60 таблиц, банк/ERP домен.
- Русскоязычные `COMMENT ON` (`'Подразделение'`, `'ОСВ: Номер счета'`,
  `'Тип объекта'` и т. п.) против английских имён колонок
  (`org_id`, `acc_number`, `type_id`).
- Имена части таблиц — «технические» (`ms_0n8ohjyx7oszo6a47ca9g0s6f`),
  смысл вынесен в `COMMENT ON TABLE`.
- 657 KB DDL целиком в промпт не лезет даже в 256 K (с учётом
  few-shot, истории итераций, reflection-памяти).

Из обзора (`research/02_text2sql_benchmarks.md`):

- DAIL-SQL «Code Representation» промпт даёт SOTA 86.6 % на Spider.
- Schema linking обязателен при >30 таблиц (F1 schema-linking резко
  падает на больших схемах).
- COMMENT ON в DDL даёт +5–10 п.п. EX, особенно когда вопросы
  русскоязычные, а имена колонок английские — наш случай.
- Sample rows (2-5) — +3-4 % EX.
- Few-shot по embedding similarity — +3-5 % vs random.

Из `take1` (ментор): «Лайфхак: SQL-to-Text проще, чем Text-to-SQL»
— это про синтез датасета (ADR-0006), но косвенно подтверждает идею
многократного использования few-shot из синтезированного корпуса.

Fine-tuning требует:
- размеченный датасет 5-50 K качественных пар (у нас будет 300-500);
- GPU и время;
- разрешения от заказчика на использование данных в обучении (см.
  `tusk`: «Данные тестовой базы могут содержать условно
  конфиденциальную информацию»).

При том, что Qwen2.5-Coder 32B даёт 70%+ EX на BIRD «из коробки»
(ADR-0008), fine-tuning — это лишний риск ради сомнительного выигрыша
на MVP-горизонте.

## Decision

1. **Метод формирования запроса — prompt-engineering + RAG (over DDL)
   + few-shot in-context learning.** Без fine-tuning на этапе MVP.

2. **Schema linking** двухступенчатый:

   - **Каталог таблиц.** Из `data_model.sql` офлайн собирается
     `schema_catalog.json` со структурой:
     ```json
     {
       "table": "acc_number",
       "table_comment": "ОСВ: Номер счета",
       "columns": [
         {"name": "id", "type": "bigint", "comment": "ID"},
         {"name": "name__ru", "type": "varchar(2000)", "comment": "Name, languageSchema=ru"},
         ...
       ],
       "primary_key": ["id"],
       "foreign_keys": [{"from": "type_id", "to": "sys_obj_type.id"}, ...],
       "sample_values_by_column": {
         "type_id": [2471461, 2471462, ...]  // top-20 DISTINCT
       },
       "sample_rows": [...]  // 3 строки
     }
     ```
   - **Эмбеддинг.** Каждая таблица превращается в текстовый «карточный»
     документ: `"{table_comment}\nКолонки: {col_name} ({col_comment}), ..."`.
     Эмбедды через `intfloat/multilingual-e5-large` (русский +
     английский), хранение в FAISS (`IndexFlatIP`).
   - **Retrieval.** На каждый вопрос пользователя:
     - top-15 таблиц по cosine,
     - замыкание по FK (если таблица A в топе и у неё `FK → B`, B
       добавляется автоматически, даже если её скор ниже),
     - финальный набор обрезается по бюджету (≤ 20 таблиц на промпт).

3. **Формат промпта генератора — DAIL-SQL Code Representation**:

   ```
   ### Task
   Сгенерируй PostgreSQL SQL-запрос по описанию задачи и схеме БД.
   ВАЖНО: ...правила безопасности из reflection памяти... (см. ADR-0002)

   ### Database schema (DDL with comments)
   -- table: acc_number  -- ОСВ: Номер счета
   CREATE TABLE acc_number (
       id bigint, -- ID
       name__ru varchar(2000), -- Name, ru
       ...
   );
   -- foreign keys: acc_number.type_id = sys_obj_type.id
   /* sample rows: (1, 'Расчётный счёт', 2471461, ...) */

   ### Few-shot examples (top-5 по similarity)
   Q: ...
   SQL: ...

   ### Reflection memory (lessons from previous attempts)
   - DML_NO_WHERE: любой UPDATE/DELETE по clients требует predicate по PK
   - ...

   ### Current question
   {task_description}

   ### Output
   - Сначала перечисли таблицы и колонки, которые планируешь использовать.
   - Затем верни единственный SQL-запрос в блоке ```sql ... ```.
   ```

4. **Few-shot отбор.** Эмбеддим вопросы из синтезированного датасета
   (ADR-0006), для каждой новой задачи берём top-5 по cosine. На первой
   итерации (пустая reflection-память) — 5 шотов; на retry-итерации,
   когда память не пустая, — снижаем до 3 шотов, чтобы освободить место
   под reflection и findings.

5. **Self-consistency** — внутри узла `generator` n=3 семпла с
   `temperature=0.3`, отбор по простому criterion: парсится ли
   `pglast.parse_sql` (то есть синтаксически валиден). Из оставшихся —
   тот, у которого больше всего общих токенов с few-shot примерами
   (proxy: похож на стиль эталонов). Этот выбор формальный и заменяется
   на голосование по execution-результату, как только появится
   sandbox-исполнение (ADR-0007). На MVP исполнение строго запрещено
   на проде → используем proxy-критерий.

6. **CoT-инструкция «сначала таблицы, потом SQL»** — не отдельный
   chain-of-thought шаг, а часть формата output (пункт «Output» в
   промпте). Это снижает вероятность галлюцинаций имён колонок.

7. **DIN-SQL-стиль классификация сложности — НЕ ВНЕДРЯЕМ на MVP.**
   В schema на 60 таблиц редко появляются «trivial easy»-вопросы,
   расход на классификацию не окупается. Если останется время —
   ADR расширяется.

## Consequences

**Положительные**

- Никакого fine-tuning — нет рисков с лицензированием данных
  заказчика и GPU-инфраструктурой.
- Качество масштабируется заменой модели (см. ADR-0008): тот же
  промпт работает на Qwen, DeepSeek, GPT-4o-mini.
- Schema linking даёт линейное масштабирование на схемы 100+ таблиц
  в будущем.
- Reflection-память (ADR-0002) встроена в системный блок промпта —
  это прямой ответ на «исследовательский вопрос» ТЗ.

**Отрицательные / Риски**

- Schema linking сам по себе может промахнуться (вернуть не ту таблицу,
  если COMMENT беден). Митигируем: при провале аудита по причине
  «таблица не та» — добавляем эту таблицу в `state.db_schema_meta`
  принудительно на следующей итерации.
- Sample rows из реальной демо-БД могут содержать ПДн (ТЗ:
  «условно конфиденциальная информация»). Митигируем: sample-rows
  снимаем только из `faker`-сгенерированной sandbox-копии (ADR-0004),
  не из боевой БД.
- Бюджет промпта на 20 таблиц + DDL + few-shot + reflection ≈
  30-40 K токенов. Запас по контексту (100K+ у Qwen-Coder) есть, но
  на retry-итерациях с накопленной reflection-памятью надо следить за
  токенами. Митигируем: per-iteration token budget cap (logged
  в state).

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Fine-tuning Qwen-Coder на синтезированном датасете | 300-500 пар недостаточно; fine-tuning требует GPU и времени; промпт-инжиниринг даёт 70%+ EX без обучения; риск лицензирования. |
| Подавать всю схему 60 таблиц целиком | DDL ~650 KB, в токенах ≫ 100K на одних только `CREATE TABLE`. Не помещается + F1 schema linking падает при >30 нерелевантных таблиц. |
| Schema linking без замыкания по FK | Ломаются JOIN'ы: топ-таблица найдена, но связанная справочная не попала в контекст. |
| LangChain SQL Toolkit (`get_table_info`) | Тащит весь DDL в промпт без selection — ровно та проблема, которую мы хотим обойти. |
| MCS-SQL (10-30 кандидатов с разными промптами) | Стоимость в 10-30× — не вписывается в требование «время ответа 40 секунд» из `take1`. Можно дешевле через `self-consistency=3`. |
| DIN-SQL classification of complexity | Слишком много инженерии ради малого выигрыша; вернёмся, если время останется. |

## Links

- ТЗ: `tusk` § «В рамках решения кейса вам будет необходимо», п. 3
- Схема: `data_model_sql/data_model.sql`
- Обзор: `research/02_text2sql_benchmarks.md` (Блок 2, 3, 4)
- DAIL-SQL: https://github.com/BeachWang/DAIL-SQL
- RASL: https://assets.amazon.science/1b/95/8f62e89647348f4c4836f6c3040d/rasl-retrieval-augmented-schema-linking-for-massive-database-text-to-sql.pdf
- MAC-SQL Selector: https://github.com/wbbeyourself/MAC-SQL
- Эмбеддинг: https://huggingface.co/intfloat/multilingual-e5-large
- Зависит от: ADR-0001 (стек), ADR-0002 (контракты state),
  ADR-0006 (датасет few-shot), ADR-0008 (LLM)
