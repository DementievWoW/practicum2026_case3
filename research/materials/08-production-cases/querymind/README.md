# QueryMind: Enterprise Text-to-SQL Agent Framework

- **Status:** verified
- **Тип:** github (open-source framework)
- **Канонический URL:** https://github.com/Tangxihong0922/QueryMind
- **Год / venue:** активно разрабатывается; последний changelog — май 2026.

## Что это
Фреймворк для LLM-агентов, специализирующихся на natural-language → SQL в enterprise-окружении, с упором на retrieval и security. Ключевые особенности по README:
- Multi-layer memory architecture: раздельные слои для conversation history, agent knowledge и database schema.
- Четыре режима schema retrieval: hybrid, vector, graph, expand — адаптивные стратегии поиска.
- Schema management tools с UI-компонентами для поддержки метаданных БД.
- SQL security features: row-level access control и injection detection.
- Multi-backend: OpenAI, Anthropic, vLLM на стороне моделей; PostgreSQL, SQLite, Neo4j на стороне БД.
- Лицензия MIT; вдохновлено проектом Vanna.

Stack: Python (74.7%) + TypeScript (frontend), Neo4j для graph-схемы, Mem0 для vector-memory. Stars: 32, forks: 5 (на момент проверки).

## Почему релевантно
Готовый production-style baseline-агент для **PostgreSQL** с уже заявленными security-механизмами (row-level access, injection detection). Подходит как «жертва» для нашего генератор-судья пайплайна: проверяем, насколько встроенные защиты QueryMind ловят P2SQL / schema-inference атаки, и сравниваем с нашим валидатором.

## README-превью (GitHub)
Разделы, заявленные в README:
- Project overview (NL2SQL для enterprise)
- Multi-layer memory architecture
- Schema retrieval modes (hybrid / vector / graph / expand)
- Schema management UI
- SQL security (row-level access, injection detection)
- Supported model backends (OpenAI / Anthropic / vLLM)
- Supported DB backends (PostgreSQL / SQLite / Neo4j)
- Changelog (запись от 2026-05-11: unified context assembly, governance, input cache hit rate 44.28% → 69.35%)
- Acknowledgements (Vanna)

## Источник
- WebFetch'нуто: 2026-05-18, URL https://github.com/Tangxihong0922/QueryMind
- Цитаты: «SQL security features including row-level access controls and injection detection»; changelog «input cache hit rates increased from 44.28% to 69.35%».
