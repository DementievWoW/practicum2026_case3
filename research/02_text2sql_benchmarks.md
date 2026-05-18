# Круг 2 — Бенчмарки и базовая школа Text-to-SQL

Базовые техники, без которых генератор не пройдёт порог Execution Accuracy ≥ 70%.

## 1. Бенчмарки

- **Spider** (Yale, 2018) — кросс-доменный, 10 181 вопрос, 200 БД, 138 доменов. Метрики: Exact Match + Execution Accuracy. SOTA насыщен: DAIL-SQL 86.6%, MCS-SQL 89.6%. Слишком лёгкий.
  - https://yale-lily.github.io/spider
- **BIRD-SQL** (NeurIPS 2023) — 12 751 вопрос, 95 «грязных» БД (33 ГБ) с external knowledge evidence. Метрики: EX + Valid Efficiency Score. SOTA 2025: Agentar-Scale-SQL ≈ 81.67%, Arctic-Text2SQL-R1-32B — 71.83%, human expert ~92%. ~32% аннотационных ошибок в train.
  - https://bird-bench.github.io/
- **Spider 2.0** (ICLR 2025) — 632 enterprise-задачи; БД часто >3000 колонок, диалекты BigQuery/Snowflake/DuckDB. SOTA очень низкое: o1-preview 17.1%, ReFoRCE ≈ 36%.
  - https://spider2-sql.github.io/
  - https://arxiv.org/abs/2411.07763
- **KaggleDBQA** (Microsoft, ACL 2021) — 272 вопроса на 8 реальных Kaggle-БД.
  - https://www.microsoft.com/en-us/research/wp-content/uploads/2021/06/ACL2021_KaggleDBQA.pdf

**Ориентир для хакатона:** 70%+ на собственном датасете сопоставимо с открытыми baseline на BIRD.

## 2. Schema linking для 60+ таблиц

При размере схемы 60 таблиц подача всего DDL в промпт работает, но дорого и шумно.

- **RASL** (Amazon): https://assets.amazon.science/1b/95/8f62e89647348f4c4836f6c3040d/rasl-retrieval-augmented-schema-linking-for-massive-database-text-to-sql.pdf
  - Декомпозировать на семантические единицы (таблица, колонка, FK), эмбеддить каждую, top-k.
- **RSL-SQL**: https://arxiv.org/pdf/2411.00073 — bidirectional schema linking, устойчивый к шуму.
- **LinkAlign** (EMNLP 2025): https://aclanthology.org/2025.emnlp-main.51.pdf — SOTA Spider 2.0-Lite 33.09%.
- **DBCopilot**: https://openproceedings.org/2025/conf/edbt/paper-209.pdf — schema routing.
- **SchemaGraphSQL**: https://arxiv.org/pdf/2505.18363 — графовый обход по FK.
- **C3-SQL**: двухэтапное Table Recall + Column Recall.

**Практика:** эмбеддинги для каждой таблицы как «имя + COMMENT + список колонок с типами и комментариями» через `intfloat/multilingual-e5-large` (русский), FAISS top-15-20 таблиц по вопросу. **Обязательно** добавлять таблицы, на которые ссылаются FK выбранных.

## 3. RAG-over-DDL: DDL + COMMENT + сэмплы строк

Канон промпта (DAIL-SQL «Code Representation», AWS Bedrock, Pinterest):

```sql
-- table: clients
-- описание: Клиенты банка
CREATE TABLE clients (
    client_id BIGINT, -- уникальный идентификатор клиента
    full_name TEXT,   -- ФИО
    ...
);
/* 3 example rows: (1, 'Иванов И. И.'), ... */
```

**Влияние компонентов** (DAIL-SQL, nilenso, ICE/NYSE):
- **COMMENT ON** на колонки и таблицы критичны при русскоязычных вопросах против английских имён колонок — +5–10 п.п. EX.
- **Sample rows (2-5)** дают +3-4% EX за счёт разрешения формата значений. Для категориальных — список DISTINCT (LIMIT 20), а не случайные строки.
- **FK-связи** обязательно подавать явно (`-- foreign keys: a.x = b.y`).
- **Domain glossary** отдельным блоком как evidence/hints (как делает BIRD).

**Не подавать всю схему 60 таблиц сразу** — F1 schema linking падает при >30 нерелевантных таблиц в контексте.

## 4. Few-shot / CoT / decomposition

- **Few-shot**: 3-8 примеров `вопрос → SQL`. DAIL-SQL — отбор по embedding similarity даёт +3-5 % vs random.
- **Chain-of-Thought**: чистый «think step by step» хуже структурированных. Лучше работает Least-to-Most / Question Decomposition.
- **DIN-SQL**: классификация сложности → разные промпты (простые без CoT, сложные с разложением).
- **QDecomp**: https://arxiv.org/abs/2310.13575 — раскладывает NL-вопрос на под-вопросы.
- **C3-SQL**: Clear Prompting + Calibration Hints (запреты типа «не используй BETWEEN») + Consistent Output (голосование 10 семплов).
- **MCS-SQL**: 10-30 кандидатов разными промптами → confidence → LLM выбирает финал.

**Для хакатона:** few-shot (5-8 по similarity) + CoT «сначала таблицы и колонки, потом SQL» + self-consistency на 3-5 семплов.

## 5. Методология Execution Accuracy

Базовая EX — бинарно: «множество строк ответа == gold». Нюансы:

- **Order**: если в gold нет `ORDER BY` — multisets. Если есть — list.
- **Duplicates**: multiset (с учётом повторов). `set()` нельзя — теряется DISTINCT.
- **NULL**: NULL == NULL при сравнении (привести к sentinel).
- **Column order**: BIRD сравнивает по позициям; для хакатона — лучше как множества кортежей по значениям.
- **Типы/формат**: даты → ISO, float → round 4 знака, строки strip.
- **Недетерминизм**: при tie фиксировать вторичный sort в gold; либо **test-suite execution accuracy** (несколько вариантов БД).
- **Soft-F1** (Snowflake Cortex): https://www.snowflake.com/en/engineering-blog/cortex-analyzer-text-to-sql-accuracy-bi/ — % пересечения строк, устойчивее к мелким ошибкам.

**Безопасность evaluator-а:** timeout 30-60с, read-only пользователь, исключения = 0.

Эталонные скрипты:
- Test-Suite Semantic Evaluation (EMNLP 2020): https://aclanthology.org/2020.emnlp-main.29.pdf

## 6. Open-source baselines

| Метод | Репо | Запуск | Требования |
|---|---|---|---|
| **RESDSQL** (AAAI 2023) | https://github.com/RUCKBReasoning/RESDSQL | fine-tune T5-3B | GPU 24 GB+ |
| **DAIL-SQL** ⭐ | https://github.com/BeachWang/DAIL-SQL | python-скрипты, GPT-4 API | OpenAI ключ |
| **C3-SQL** | https://github.com/bigbigwatermalon/C3SQL | 3 файла последовательно | OpenAI |
| **MAC-SQL** | https://github.com/wbbeyourself/MAC-SQL | docker-compose | LLM API |
| **BASE-SQL** (2025) | https://github.com/CycloneBoy/base_sql | open-source fine-tuned | GPU |
| **PremSQL** | https://github.com/premAI-io/premsql | end-to-end local | local LLM |
| **Arctic-Text2SQL-R1** | Snowflake | RL-32B, 71.83% BIRD | GPU/endpoint |

Стартовать дешевле всего с **DAIL-SQL** или **C3-SQL** поверх внешнего LLM-API.

## Чеклист: минимальный T2SQL пайплайн за хакатон

1. Датасет 300+ пар, разбивка по сложности (easy/medium/hard), gold-SQL проверены исполнением.
2. DDL-каталог: `CREATE TABLE` + все `COMMENT ON` для 60 таблиц + FK-секции + DISTINCT-20 для категориальных + 2-3 sample rows для остальных.
3. Schema linking через `intfloat/multilingual-e5-large` + FAISS, top-15 таблиц + замыкание по FK.
4. Few-shot: top-5-8 по cosine из train.
5. Промпт Code-Representation (DAIL-SQL стиль) + CoT шаги.
6. LLM: GPT-4o-mini / Claude Haiku / Qwen2.5-Coder-32B; self-consistency × 5, temperature 0.2-0.5.
7. Self-correction по ошибке Postgres (1-2 итерации).
8. Evaluator: запуск в Postgres с timeout, multiset-сравнение с нормализацией.
9. Ablation-логи: вклад schema linking, few-shot, CoT, self-consistency.
10. Safety: read-only роль, `statement_timeout = 30000`, никаких DDL/DML.

## Доп. источники

- [Text-to-SQL Benchmarks are Broken (VLDB 2026)](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf)
- [Agentar-Scale-SQL](https://arxiv.org/html/2509.24403v1)
- [Arctic-Text2SQL-R1](https://www.snowflake.com/en/engineering-blog/arctic-text2sql-r1-sql-generation-benchmark/)
- [NL2SQL Handbook (HKUSTDial)](https://github.com/HKUSTDial/NL2SQL_Handbook)
- [Awesome-LLM-based-Text2SQL (TKDE 2025 survey)](https://github.com/DEEP-PolyU/Awesome-LLM-based-Text2SQL)
- [AWS Bedrock RAG Text-to-SQL](https://aws.amazon.com/blogs/machine-learning/build-your-gen-ai-based-text-to-sql-application-using-rag-powered-by-amazon-bedrock-claude-3-sonnet-and-amazon-titan-for-embedding/)
- [nilenso: RAG-based Text-to-SQL](https://blog.nilenso.com/blog/2025/05/15/exploring-rag-based-approach-for-text-to-sql/)
- [Pinterest RAG-Enhanced Table Selection](https://www.zenml.io/llmops-database/text-to-sql-system-with-rag-enhanced-table-selection)
- [QueryCraft eval framework](https://medium.com/towards-generative-ai/querycraft-evaluation-framework-for-nl2sql-generation-8c5f461e7b05)
- [Trust3: evaluating Text-to-SQL](https://trust3.ai/blog/bridging-the-language-gap-evaluating-text-to-sql-performance/)
