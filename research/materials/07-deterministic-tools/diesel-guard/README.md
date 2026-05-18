# Diesel Guard

- **Status:** verified
- **Тип:** tool (PostgreSQL migration linter)
- **Канонический URL:** https://github.com/ayarotsky/diesel-guard (crates.io: https://crates.io/crates/diesel-guard; Show HN: https://news.ycombinator.com/item?id=46194916)
- **Год / venue / CVE-ID:** ~2025; MIT

## Что это
Линтер опасных паттернов миграций PostgreSQL для Rust-стеков Diesel и SQLx. Цель — предотвратить downtime из-за небезопасных schema changes. Под капотом использует **libpg_query** (C-библиотека, скомпилированная из самого PostgreSQL), что даёт парсинг, идентичный собственному парсеру PostgreSQL. Поддерживает написание собственных правил на **Rhai** с полным доступом к SQL AST. Подключение к БД не требуется — анализирует SQL-файлы напрямую в CI. Имеет механизм safety-assured блоков для подтверждённо безопасных операций. Лицензия — MIT.

Существуют пакеты под Cargo, Homebrew, shell-скрипты, PowerShell, Docker и pre-commit. По данным WebSearch — «detects 24 different issues»; по README — список встроенных проверок включает блокировочные операции, table rewrites и т.д.

## Почему релевантно
Релевантный пример CI-валидатора для PostgreSQL-миграций: показывает, как использовать `libpg_query` для надёжного парсинга и Rhai-скрипты для кастомных правил — обе техники применимы в нашей задаче (детерминированная часть LLM-судьи). Хороший образец архитектуры расширяемого линтера без зависимости от живой БД.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из README репозитория `ayarotsky/diesel-guard`: «Linter for dangerous Postgres migration patterns in Diesel and SQLx. Prevents downtime caused by unsafe schema changes.» Ключевое: «Diesel Guard embeds libpg_query — the C library compiled into Postgres itself»; «You can write project-specific rules in Rhai with full access to the SQL AST»; «No database connection is required».

## Источник
- WebFetch'нуто: 2026-05-18, URL https://github.com/ayarotsky/diesel-guard
- Цитаты: «Prevent downtime caused by unsafe schema changes»; «embeds libpg_query»; «write project-specific rules in Rhai with full access to the SQL AST»; «MIT license».
