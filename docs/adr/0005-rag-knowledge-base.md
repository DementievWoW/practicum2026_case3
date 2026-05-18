# ADR-0005 — RAG knowledge base structure for the judge

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

Из ADR-0004: Phase 2 (LLM-судья) принимает SQL + findings + **RAG-контекст
по vuln_class**. От качества этого контекста зависит:

- Точность классификации (правильный `vuln_class`, корректный
  `risk_score`).
- Содержательность `description` и `recommendation` в
  `Vulnerability`.
- Наличие `evidence.cwe_id`, `evidence.capec_id`, `evidence.owasp_ref`
  — без этого «прозрачность для пользователя» (10 баллов) проваливается.

ТЗ (`tusk`):

> RAG по SQL-инъекциям и MITRE для валидатора, инфа по уровням доступа.

Ментор (`take1`):

> Тулы для агента: ... RAG по SQL-инъекциям и MITRE для валидатора,
> инфа по уровням доступа.

Из `research/04_rag_knowledge_base.md`:

- CWE-89/564/943 — слабости, скачивается XML/CSV/STIX.
- CAPEC-66/7/470/108 — паттерны атак, XML/STIX.
- OWASP SQLi Cheat Sheet + ASVS V5.
- PostgreSQL docs: SECURITY DEFINER, PL/pgSQL EXECUTE/format,
  GRANT/REVOKE, RLS.
- PII: Presidio + российские валидаторы (СНИЛС/ИНН/паспорт).
- Payloads: PortSwigger, sqlmap, SecLists — **только как negative
  test corpus, не для RAG в few-shot**.

## Decision

1. **Векторное хранилище — Qdrant** (Docker, persistent volume).
   Альтернативы — Chroma и pgvector. Qdrant выбран потому, что:
   - Удобные именованные коллекции и filterable metadata.
   - Гибридный поиск (BM25 + dense) встроен в `qdrant-client`
     0.5.x+.
   - Бесплатный self-host, OSS Apache 2.0.

2. **6 коллекций (namespaces):**

   | Коллекция | Источник | Назначение |
   |---|---|---|
   | `kb.cwe` | CWE-89, 564, 943 | Классификация vuln_class |
   | `kb.capec` | CAPEC-66, 7, 470, 108 | Attack patterns, execution flow |
   | `kb.owasp` | OWASP SQLi Cheat Sheet, ASVS V5 | Recommendations, compliance |
   | `kb.postgres` | PG docs: SECURITY DEFINER, PL/pgSQL, GRANT, RLS | Postgres-specific «как правильно» |
   | `kb.pii` | Presidio + RU валидаторы | Detection чувствительных полей |
   | `kb.payloads` | PortSwigger + sqlmap XML | **Только для regression-тестов**, не для контекста судьи в проде |

3. **Чанкинг.**

   - **CWE / CAPEC**: один документ = один CWE/CAPEC, чанки по
     секциям (Description, Common Consequences, Mitigations,
     Examples, Relationships), 300–800 токенов. Парсим XML/STIX
     **офлайн** (`scripts/build_kb.py`), не пытаемся ремонтировать
     при каждом старте.
   - **OWASP Cheat Sheets**: чанк = «один Defense Option» целиком,
     ~500 токенов.
   - **ASVS**: чанк = одно verification requirement (V5.x.y),
     100–200 токенов. ID requirement ОБЯЗАТЕЛЬНО в метаданных.
   - **Postgres docs**: чанк = подсекция; код-примеры держим
     целиком (400–1000 токенов).
   - **PII**: один чанк = одна entity:
     `{name, regex, checksum_algo, examples, false_positive_notes,
       severity, legal_ref}`. Сгенерировать офлайн из Presidio +
     ручные RU-сущности (СНИЛС, ИНН, паспорт, телефон).
   - **Payloads**: один payload = один чанк (короткий) с меткой
     `kind: malicious_sample`.

4. **Эмбеддинг**:

   - Dense: `intfloat/multilingual-e5-large` (тот же, что и в
     schema-linking ADR-0003 — экономим на загрузке модели).
     1024-dim.
   - Sparse: встроенный BM25 в Qdrant. Гибрид BM25+dense через
     `qdrant_client.models.Prefetch` + `FusionQuery(RRF)`. На
     CAPEC/CWE-ID и аббревиатурах чистый dense промахивается.

5. **Минимальный набор метаданных на чанк (обязателен):**

   ```json
   {
     "source": "cwe-89" | "capec-66" | "owasp-cs-sqli" | "asvs-v5.3.4" | "pg-docs-security-definer" | "presidio-snils" | "portswigger-time-blind-pg",
     "source_type": "weakness" | "attack_pattern" | "defense" | "requirement" | "official_doc" | "pii_entity" | "payload",
     "section": "description" | "mitigations" | "execution_flow" | ...,
     "vuln_class": ["sqli", "blind-sqli", "second-order", "privilege-escalation", "pii-exposure", ...],
     "dbms": ["postgresql"] | ["any"],
     "severity_hint": "info|low|medium|high|critical",
     "language": "en" | "ru",
     "version": "CWE-4.14" | "CAPEC-3.9" | "ASVS-5.0" | "PG-17",
     "url": "<canonical-link>",
     "license": "CC-BY-4.0 | Apache-2.0 | MIT | MITRE Terms",
     "purpose": "knowledge" | "detection_signature",
     "last_updated": "2026-05-18"
   }
   ```

6. **Retrieval-стратегия для судьи:**

   - Вход — `findings_static: list[Finding]` от Phase 1
     (ADR-0004). Каждый Finding содержит `vuln_class`.
   - На каждый `vuln_class` делаем **гибридный запрос** к
     `kb.cwe ∪ kb.capec ∪ kb.owasp ∪ kb.postgres` с фильтром
     `purpose != "detection_signature"` и
     `vuln_class @> [<finding.vuln_class>]`. Top-5 чанков.
   - Для PG-специфики (vuln_class в {`PRIV_ESCALATE`,
     `PLPGSQL_UNSAFE`}) бустим коллекцию `kb.postgres`
     (`dbms == "postgresql"`).
   - Для каждого Finding отдельно — top-2 из `kb.pii`, если
     `vuln_class == "DIRECT_SENSITIVE"`.
   - Bundle в промпт: max 12 чанков, дедуп по `source`,
     суммарный budget ≤ 8000 токенов.

7. **Источник истины для evidence-ID.** Судья в своём JSON-ответе
   обязан вернуть `evidence.cwe_id` и `evidence.capec_id` строго из
   `source`-метаданных подтянутых чанков. Если ни одного релевантного
   чанка не подтянуто — судья пишет `evidence: {}` и помечает
   finding как `metadata.unverified=true` (это сигнал для аналитика,
   что классификация по «общим знаниям» без ссылки).

8. **Сборка базы** — офлайн скриптом `scripts/build_kb.py`:
   - тянет XML CWE / CAPEC (`mitre/cti`),
   - тянет markdown ASVS / OWASP CS из их репозиториев,
   - копирует фрагменты PG docs (HTML → markdown через `html2text`),
   - вытягивает regex-ы из Presidio (`predefined_recognizers`),
   - билдит чанки и аплоадит в Qdrant.
   - **Версионируем коллекции** (`kb.cwe-v2026-05-18`), чтобы можно
     было откатиться, если новая выкатка испортила retrieval.

9. **Payloads** (`kb.payloads`) собираются отдельно и используются
   ТОЛЬКО как regression-датасет для тестирования судьи (см. ADR-0006
   для общего датасета и ADR-0007 для метрик). В runtime-судью они
   не подтягиваются — иначе модель начнёт «учиться» и предлагать
   опасный SQL.

## Consequences

**Положительные**

- Судья в каждом отчёте указывает CWE/CAPEC/ASVS-ID — это и есть
  «прозрачный лог» из критериев (10 баллов).
- Версионирование коллекций даёт безопасный rebuild (новые версии
  CWE/CAPEC выходят регулярно).
- Гибрид BM25+dense спасает от провалов на ID-токенах
  (CAPEC-66 чисто семантически плохо ищется).
- PII-коллекция отдельно даёт быстрый ответ на «прямой доступ к
  чувствительным полям» — это и `R009-sensitive-columns` из
  ADR-0004, и отдельный класс уязвимостей.

**Отрицательные / Риски**

- MITRE-данные лицензируются по «MITRE Terms» — формально не
  Apache/MIT. Для open-source демо это ок, для интеграции в платформу
  GreenData фиксируется заказчиком.
- Qdrant — отдельный сервис (Docker). Если деплой потребует
  «pure Python без сервисов» — переключаемся на `pgvector` (LangChain
  имеет интеграцию). Решение фиксируется ADR.
- Реальный объём данных небольшой (~1000-5000 чанков), но
  билдинг занимает ~5 минут — не делать в каждом тесте. Кешируем
  слепок коллекции, в CI поднимаем from snapshot.
- Если LLM «придумает» CWE-ID — это серьёзная ошибка отчёта.
  Митигируем валидатором: после ответа судьи прогоняем regex
  `CWE-\d+` через `kb.cwe` и проверяем, что ID реально есть в
  коллекции. Если нет — заменяем на пустое evidence + флаг
  `unverified`.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Chroma вместо Qdrant | Хуже работает с filterable metadata и hybrid search; больше падает в Docker на нагрузке. |
| pgvector в той же sandbox-БД | Дёшево, но Postgres в test-контейнере уже занят sandbox-данными (ADR-0004). Изоляция Qdrant удобнее. |
| Загрузить всю CWE/CAPEC одним документом | Чанки >2000 токенов резко портят retrieval (нерелевантные секции в топе). Сечение по секциям — стандарт. |
| Использовать payloads в RAG-контексте судьи | Опасно: судья «учится» опасным паттернам и может предлагать их как варианты. Только regression. |
| LLM без RAG, полагаясь на знания pre-training | Нет верифицируемых ссылок → проваливается «прозрачность». |
| BM25-only | Хорошо для CWE-ID, плохо для семантики на русском. |
| Dense-only | Промахивается на технических ID, аббревиатурах. |
| Версионирование через MLflow / DVC | Лишний слой для MVP; именованных коллекций в Qdrant хватает. |

## Links

- ТЗ: `tusk` § «инструменты ... RAG по SQL-инъекциям»
- Обзор: `research/04_rag_knowledge_base.md`
- CWE-89: https://cwe.mitre.org/data/definitions/89.html
- CAPEC-66: https://capec.mitre.org/data/definitions/66.html
- OWASP SQLi CS: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- PG SECURITY DEFINER: https://www.postgresql.org/docs/current/sql-createfunction.html
- Presidio: https://github.com/microsoft/presidio
- mitre/cti (STIX): https://github.com/mitre/cti/blob/master/capec/2.1/stix-capec.json
- Зависит от: ADR-0001 (стек), ADR-0004 (auditor Phase 2 → потребитель)
