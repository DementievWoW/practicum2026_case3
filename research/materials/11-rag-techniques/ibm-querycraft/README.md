# IBM QueryCraft: Evaluation Framework for NL2SQL Generation

- **Status:** verified
- **Тип:** blog (Medium) + сопутствующий open-source проект (IBM Ecosystem Engineering)
- **Канонический URL:** https://medium.com/towards-generative-ai/querycraft-evaluation-framework-for-nl2sql-generation-8c5f461e7b05
- **Год / venue:** 10 июня 2024, Medium (Towards Generative AI)

## Что это
Статья Shivam Solanki описывает QueryCraft — open-source фреймворк для оценки и доработки NL2SQL пайплайнов, поддерживаемый IBM Ecosystem Engineering. Ключевые компоненты:
1. Query Correction Service — исправление синтаксических ошибок LLM-генераций.
2. Execution Evaluation — проверка корректности результатов на реальных БД.
3. Query Analysis Dashboard — визуализация метрик и паттернов ошибок.

Execution-evaluator поддерживает SQLite и IBM DB2: error handling, SQL-валидация, unordered row comparison, генерация перестановок для column-order вариаций, multiset equality.

## Почему релевантно
Хороший образец архитектуры **evaluator-as-a-service** — отдельный сервис, который не зависит от модели и даёт честные метрики + дашборд. Можно перенять идеи (особенно permutation-aware comparison и multiset equality) для GreenData evaluator-слоя.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL статьи на Medium
- Цитаты:
  - "Accuracy in SQL generation is meaningless without executable queries that yield the correct results."
  - "Query Correction Service – Fixes syntactic errors in SQL queries that LLMs generate"
  - "Execution evaluator employs sophisticated comparison logic including error handling, SQL validation, unordered row comparison, permutation generation for column-order variations, and multiset equality checking. It supports both SQLite and IBM DB2 databases."
