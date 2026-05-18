# PExA: Parallel Exploration Agent for Complex Text-to-SQL (Bloomberg AI)

- **Status:** verified (основная Bloomberg-страница вернула 403, но фреймворк подтверждён через WebSearch и вторичный источник aicerts.ai)
- **Тип:** blog (Bloomberg corporate story) + сопутствующий arXiv-препринт
- **Канонический URL:** https://www.bloomberg.com/company/stories/bloomberg-ai-researchers-advance-text-to-sql-accuracy-with-multi-agent-pexa-framework/
- **Альтернативный URL:** https://arxiv.org/abs/2604.22934 (arXiv ID присутствует в результатах поиска, но требует дополнительной верификации — год «2604» выглядит подозрительно, возможна ошибка индексации); https://www.aicerts.ai/news/how-the-pexa-ai-framework-redefines-text-to-sql-accuracy/
- **Год / venue:** 2025 (Bloomberg AI Research, корпоративный блог)

## Что это
PExA (Parallel Exploration Agent) — мульти-агентный фреймворк Bloomberg для генерации SQL по тексту с акцентом на сложные кейсы (Spider 2.0 Snow). Архитектура состоит из трёх кооперирующих агентов:
1. **Planner** — переписывает пользовательский запрос и порождает семантически осмысленные test-cases.
2. **Test Case Generator** — выполняет атомарные SQL-зонды против БД для сбора доказательств через structured multi-path search.
3. **SQL Proposer** — синтезирует и валидирует финальный SQL-запрос на основе результатов test-cases.

Ключевая идея — кастовать text-to-SQL как задачу прохождения test-coverage, аналогично software testing. Результат: 70.2% execution accuracy на Spider 2.0 (Snow).

## Почему релевантно нашему кейсу
Идея «генерировать тест-кейсы и валидировать SQL против них» прямо переносится в security-аудит: вместо тестов на корректность можно генерировать adversarial-зонды на инъекции/привилегии. Plan-test-propose как cycle pattern для генератор-судья.

## README-превью (только для GitHub репо)
Не применимо — PExA представлен как корпоративный блог-пост, публичного репозитория Bloomberg не предоставила (по состоянию на 2026-05-18).

## Источник
- WebFetch'нуто: 2026-05-18
  - https://www.bloomberg.com/company/stories/bloomberg-ai-researchers-advance-text-to-sql-accuracy-with-multi-agent-pexa-framework/ (HTTP 403 — bot-block)
  - https://www.aicerts.ai/news/how-the-pexa-ai-framework-redefines-text-to-sql-accuracy/ (успешно)
  - WebSearch query: "Bloomberg PExA multi-agent text-to-SQL framework"
- Цитаты:
  - "splits query generation into three cooperative agents" (aicerts.ai)
  - "Planner — crafts intent-aligned test plans", "Test Case Generator — executes SQL probes", "SQL Proposer — builds and checks final statement" (aicerts.ai)
  - "On the Spider 2.0 benchmark, PExA achieved 70.20% execution accuracy" (aicerts.ai)
