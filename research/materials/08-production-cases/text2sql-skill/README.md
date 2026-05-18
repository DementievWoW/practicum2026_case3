# text2sql-skill: Production-Ready Secure Text-to-SQL Engine

- **Status:** verified
- **Тип:** github (open-source engine)
- **Канонический URL:** https://github.com/ljq/text2sql-skill
- **Год / venue:** активный проект (35 коммитов, 10 stars на момент проверки); автор Jaco Liu (ljqlab@gmail.com).

## Что это
Production-ready Text-to-SQL движок для AI-агентов, ориентированный на enterprise-безопасность и производительность; явно не полагается на семантические способности LLM как на единственный источник истины. Архитектура:
- **Five-Layer Guard System**: semantic analysis, permission control, execution control, schema evolution, audit logging.
- **Security focus**: input validation, resource limits, read-only mode, token-based auth.
- **High performance**: интеллектуальный кеш (LRU / FIFO / LFU), async-обработка, connection pooling, сжатие результатов.
- **Multi-DB**: MySQL 5.7+ и **PostgreSQL 12+**.
- **MCP Protocol** для стандартизованной интеграции AI-инструментов.
- **Observability**: audit logs, health checks, structured logging.
- Stack: Go 1.21+, стандартные DB-драйверы.

## Почему релевантно
Второй кандидат на «жертву» для нашего аудита: явно описанные пять защитных слоёв (включая permission control и audit logging) — отличный объект для проверки судьёй. Поддержка PostgreSQL 12+ совпадает с нашим стеком. Read-only режим и MCP-протокол позволяют встроить engine в наш test-harness без дополнительной обвязки.

## README-превью (GitHub)
Секции README, подтверждённые WebFetch:
- Project description (production Text-to-SQL для AI-агентов)
- Five-Layer Guard System (semantic / permission / execution / schema / audit)
- Security features (validation, resource limits, read-only, token auth)
- Performance (caching strategies, async, pooling, compression)
- Multi-Database Support (MySQL, PostgreSQL)
- MCP Protocol Support
- Observability (audit, health, structured logs)
- Author / contact (Jaco Liu, ljqlab@gmail.com, blog wdft.com)

Активность: 35 коммитов, 10 stars, 0 forks, 0 PRs, 0 releases — moderate.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://github.com/ljq/text2sql-skill
- Цитаты: «Five-Layer Guard System: Semantic analysis, permission control, execution control, schema evolution, and audit logging»; «MySQL 5.7+ and PostgreSQL 12+»; «Go 1.21+».
