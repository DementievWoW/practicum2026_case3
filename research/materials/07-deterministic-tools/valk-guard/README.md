# Valk Guard

- **Status:** verified
- **Тип:** tool (SAST / SQL-линтер)
- **Канонический URL:** https://github.com/ValkDB/valk-guard (Show HN: https://news.ycombinator.com/item?id=48006682)
- **Год / venue / CVE-ID:** ~2025 (Show HN release); Apache 2.0

## Что это
Статический анализатор SQL и кода приложений: парсит исходный код в AST, синтезирует SQL из паттернов ORM/query-builder (SQLAlchemy — Python, Goqu — Go, а также сырые `db.Query/Exec/QueryRow` в Go), прогоняет через настоящий PostgreSQL-грамматический парсер и применяет правила. Работает без подключения к БД, может публиковать находки прямо в PR. Согласно README на репозитории: ~19 правил по валидации запросов, индексам и schema drift. Поддерживает только PostgreSQL. Лицензия — Apache 2.0.

Заявленные классы проблем:
- DELETE/UPDATE без WHERE;
- SELECT * и запросы без LIMIT;
- «index-killing» паттерны (например, leading-wildcard в LIKE);
- расхождения между ORM-моделями и миграциями.

## Почему релевантно
Прямой аналог детерминированной части предлагаемого решения: AST-разбор + PostgreSQL grammar + правила. Полезен как референс для разработки собственных детерминированных проверок (валидаторов) и в качестве baseline для сравнения с LLM-судьёй на «дешёвых» правилах (no-WHERE DELETE, unbounded SELECT и т.д.).

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из репозитория ValkDB/valk-guard: «Valk Guard scans raw SQL plus application code and catches risky queries before they merge. It parses real source code, synthesizes SQL from supported ORM/query-builder patterns, runs PostgreSQL-aware checks, and can post findings directly into pull requests.» Технические свойства: «No database connection. Runs in CI in seconds», вывод в JSON/SARIF/rdjsonl, установка через pre-built binaries или `go install`.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://github.com/ValkDB/valk-guard
- Цитаты: «catches production disasters at PR time»; «19 rules across query validation, index awareness, and schema drift detection»; «PostgreSQL only»; «Licensed under Apache 2.0»; «Reads Goqu builder chains, SQLAlchemy ORM calls, and Go db.Query invocations ... by parsing the actual abstract syntax tree».
