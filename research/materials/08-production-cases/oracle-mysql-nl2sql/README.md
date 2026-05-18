# NL2SQL available with MySQL (Oracle blog)

- **Status:** verified (corrected URL) — оригинальный URL вернул 403, нашлись релевантные посты в blogs.oracle.com/mysql
- **Тип:** blog (vendor announcement)
- **Канонический URL:** https://blogs.oracle.com/mysql/natural-language-to-sql-available-with-mysql (403 при WebFetch, индексируется поисковиками)
- **Альтернативные URL:**
  - https://blogs.oracle.com/mysql/introducing-natural-language-to-sql-for-mysql-heatwave
  - https://blogs.oracle.com/mysql/announcing-mysql-ai
  - https://dasini.net/blog/2025/09/30/ask-your-database-anything-natural-language-to-sql-in-mysql-heatwave/ (внешний rewrite)
- **Год / venue:** 2025, Oracle MySQL Engineering Blog (релиз HeatWave 9.4.1 — 2025-08-25)

## Что это
Анонс Oracle о добавлении NL2SQL-функции в MySQL HeatWave (доступно на OCI, AWS, Azure) и Enterprise Edition в рамках MySQL AI. По данным WebSearch: фича переводит вопросы на естественном языке в SQL через in-database LLM с обогащением schema-контекстом и пост-обработкой результата LLM. Часть набора AI Engine: Generative AI, Vector Engine, AutoML, NL2SQL.

## Почему релевантно
Продакшен-кейс крупного вендора — пример того, что NL2SQL вышел из исследовательской фазы и встраивается прямо в СУБД. Подтверждает enterprise-спрос на безопасный NL→SQL и проектирование с учётом schema-контекста, что согласуется с архитектурой GreenData SQL Security.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, основной URL отдал HTTP 403, информация собрана через WebSearch ("Oracle MySQL NL2SQL HeatWave GenAI 2025") + страница InfoQ и dasini.net
- Цитаты (по результатам поиска):
  - "Oracle announced the release of a new Natural Language to SQL (NL2SQL) feature in version 9.4.1 for MySQL HeatWave on OCI, AWS, and Azure"
  - "NL2SQL leverages in-database LLMs and MySQL enhancements that refine and augment LLM output for higher accuracy and performance"
