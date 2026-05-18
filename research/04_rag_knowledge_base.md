# Круг 4 — База знаний для RAG-судьи

Источники, на которые LLM-судья обязан ссылаться при классификации уязвимостей. **CAPEC/CWE-ID в выводе — критерий «прозрачности» (10 баллов).**

## 1. MITRE CAPEC (паттерны атак)

### CAPEC-66 — SQL Injection ⭐
- https://capec.mitre.org/data/definitions/66.html
- Корневой паттерн классического SQLi.
- Внутри: Execution Flow (Explore → Experiment → Exploit), Prerequisites, Indicators, Consequences, Mitigations, Examples, Taxonomy Mappings.

### CAPEC-7 — Blind SQL Injection
- https://capec.mitre.org/data/definitions/7.html
- Boolean-based и time-based вариации; извлечение данных по «yes/no».

### CAPEC-470 — Expanding Control over OS from Database
- https://capec.mitre.org/data/definitions/470.html
- Пост-эксплуатация (xp_cmdshell, `COPY ... PROGRAM`, UDF), эскалация на ОС.
- **Триггер critical-severity** при `COPY FROM PROGRAM`, `pg_read_server_files`, `lo_import`.

### CAPEC-108 — Command Line Execution through SQL Injection
- https://capec.mitre.org/data/definitions/108.html
- 2nd-order chain: данные через SQLi в БД → подставляются в shell backend.

### Скачать структурированные данные
- XML: https://capec.mitre.org/data/xml/capec_latest.xml
- JSON/STIX 2.1: https://github.com/mitre/cti/blob/master/capec/2.1/stix-capec.json
- Все downloads: https://capec.mitre.org/data/downloads.html

## 2. MITRE CWE (классы слабостей)

### CWE-89 — Improper Neutralization of Special Elements used in SQL ⭐
- https://cwe.mitre.org/data/definitions/89.html
- Корневая статья. 6 классов митигаций: parameterized queries, allowlist validation, output encoding, least privilege, vetted libs, error handling.
- Связи с CAPEC-66/7/108/109/470.

### CWE-564 — SQL Injection: Hibernate
- https://cwe.mitre.org/data/definitions/564.html
- Variant CWE-89 для HQL-конкатенации.

### CWE-943 — Improper Neutralization in Data Query Logic
- https://cwe.mitre.org/data/definitions/943.html
- Шире SQL — LDAP/XPath/NoSQL/XQuery. Родитель CWE-89.

### Скачать CWE
- https://cwe.mitre.org/data/downloads.html (XML/CSV/PDF/STIX)

## 3. OWASP

### SQL Injection Prevention Cheat Sheet ⭐
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- Primary Defense 1: Prepared Statements / Parameterized Queries.
- PD2: Stored Procedures.
- PD3: Allow-list Input Validation (для table/column names, ORDER BY).
- PD4: Escaping (STRONGLY DISCOURAGED).
- Additional: Least Privilege + secondary allow-list.

### OWASP ASVS
- https://owasp.org/www-project-application-security-verification-standard/
- v4 раздел V5: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x13-V5-Validation-Sanitization-Encoding.md
- v5.0 PDF: https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/OWASP_Application_Security_Verification_Standard_5.0.0_en.pdf
- Требования по SQLi (5.3.x в v4): parameterized queries / ORM; явно — table/column names и ORDER BY не параметризуются, нужен allowlist.

### OWASP Top 10 — A05:2025 Injection
- https://owasp.org/Top10/2025/A05_2025-Injection/

## 4. PostgreSQL official docs

### CREATE FUNCTION / SECURITY DEFINER ⭐
- https://www.postgresql.org/docs/current/sql-createfunction.html
- Критическая уязвимость через `search_path` и `pg_temp`.
- Обязательно: `SET search_path = admin, pg_temp`, `REVOKE ALL ... FROM PUBLIC; GRANT EXECUTE TO ...`.
- **Судья обязан флагать любую `SECURITY DEFINER` без `SET search_path` как high-risk.**

### PL/pgSQL: EXECUTE и format() с USING ⭐
- https://www.postgresql.org/docs/current/plpgsql-statements.html
- `EXECUTE ... USING $1, $2` — единственный безопасный способ.
- `format('...%I...', name)` — для идентификаторов (`quote_ident`), `%L` — для литералов (`quote_nullable`).
- Прямая склейка через `||` — антипаттерн.
- Для NULL — `IS NOT DISTINCT FROM`.

### Privileges / GRANT-REVOKE
- https://www.postgresql.org/docs/current/ddl-priv.html
- Default privileges: PUBLIC получает CONNECT/TEMPORARY на БД и EXECUTE на функции — часто упускают.
- ACL-нотация `arwdDxtm`.

### Row-Level Security
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- `CREATE POLICY ... USING (...) WITH CHECK (...)`.
- PERMISSIVE (OR) vs RESTRICTIVE (AND).
- `FORCE ROW LEVEL SECURITY` для владельцев; `BYPASSRLS`.
- FK всегда обходят RLS.

## 5. Таксономии PII / чувствительных полей

### Microsoft Presidio ⭐
- https://github.com/microsoft/presidio/tree/main/presidio-analyzer/presidio_analyzer/predefined_recognizers
- Generic: CreditCard, Email, Phone, IP, IBAN, URL.
- US: SSN, ITIN, driver's license, passport, bank account, medical license.
- Country-specific: UK NHS/NINO, DE tax ID, ES NIF/NIE, IT codice fiscale, PL PESEL, SE personnummer, IN Aadhaar/PAN/GSTIN, KR RRN, SG FIN/UEN, AU ABN/ACN/TFN.
- Под Apache 2.0 — забираем регексы.

### Российские реалии (regex + контрольные суммы)

Регекс без КС — слабая проверка; для production нужны обе ступени.

- **СНИЛС**: `\b\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{2}\b` + mod-101 КС.
- **ИНН физлица**: `\b\d{12}\b`; **ИНН юрлица**: `\b\d{10}\b` + КС.
- **Паспорт РФ**: серия+номер `\b\d{4}\s?\d{6}\b`; код подразделения `\b\d{3}-\d{3}\b`.
- **Телефон РФ**: `\b(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b`.
- **Карта** (Luhn): generic из Presidio.
- **Email**: generic из Presidio.

Валидаторы:
- https://github.com/kdmatrosov/validation-codes
- https://github.com/Sigiller/validators

## 6. Корпуса вредоносных SQL (для тестирования судьи)

### PortSwigger SQL Injection Cheat Sheet ⭐
- https://portswigger.net/web-security/sql-injection/cheat-sheet
- 12 категорий × DBMS (Oracle/MSSQL/PG/MySQL): string concat, substring, comments, version, schema enumeration, conditional errors, error-based, batched, time delays, conditional time delays, DNS lookups, DNS exfil.

### sqlmap payloads (XML)
- https://github.com/sqlmapproject/sqlmap/tree/master/data/xml/payloads
- Файлы: `boolean_blind.xml`, `error_based.xml`, `inline_query.xml`, `stacked_queries.xml`, `time_blind.xml`, `union_query.xml`.
- Tamper-scripts: https://github.com/sqlmapproject/sqlmap/tree/master/tamper

### SecLists
- https://github.com/danielmiessler/SecLists/tree/master/Fuzzing/Databases
- Внимание: содержит destructive payloads.

### PayloadsAllTheThings
- https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/SQL%20Injection
- PostgreSQL Injection.md — особо ценный.

## Структура RAG-коллекции

### Коллекции (namespaces в Qdrant/Milvus/pgvector)

1. `kb.cwe` — слабости (источник классификации vuln-class).
2. `kb.capec` — паттерны атак (attack-class, execution flow).
3. `kb.owasp` — defensive patterns + ASVS (рекомендации, compliance).
4. `kb.postgres` — официальная документация.
5. `kb.pii` — таксономия с регексами и КС.
6. `kb.payloads` — корпус атак (`purpose: detection`, **не в few-shot**).

### Чанкинг

- **CWE/CAPEC**: один документ = один CWE/CAPEC; чанки по секциям (Description, Consequences, Mitigations, Examples, Relationships) — 300-800 токенов.
- **OWASP Cheat Sheets**: чанк = «один defense option» целиком, ~500 токенов.
- **ASVS**: чанк = одно verification requirement (V5.x.y), ~100-200 токенов. ID requirement в метаданных.
- **Postgres docs**: чанк = подсекция; код-примеры целиком, ~400-1000 токенов.
- **PII**: один чанк = одна entity `{name, regex, checksum_algo, examples, false_positive_notes, severity, legal_ref}`.
- **Payloads**: один payload = один чанк (короткий) с меткой `kind: malicious_sample`.

### Метаданные на чанк (минимум)

```json
{
  "source": "cwe-89" | "capec-66" | "owasp-cs-sqli" | "asvs-v5.3.4" | ...,
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
  "last_updated": "2026-05-..."
}
```

### Retrieval

- Гибрид BM25 + dense (BGE-M3 / multilingual-e5-large). Чистый dense промахивается на CAPEC/CWE-ID и именах.
- Per-query фильтр `purpose != "detection_signature"` для основного контекста.
- Payloads подтягивать отдельным запросом с пометкой «образец атаки, не образец рекомендации».
- **Судья всегда возвращает `source` из метаданных** (CAPEC-ID / CWE-ID / ASVS-ID) → верифицируемые ссылки в отчёте.
- Для PG-вопросов поднимать вес `kb.postgres` через rerank `dbms=postgresql`.

## Все источники

- [CAPEC-66](https://capec.mitre.org/data/definitions/66.html) · [CAPEC-7](https://capec.mitre.org/data/definitions/7.html) · [CAPEC-470](https://capec.mitre.org/data/definitions/470.html) · [CAPEC-108](https://capec.mitre.org/data/definitions/108.html)
- [CAPEC downloads](https://capec.mitre.org/data/downloads.html) · [capec_latest.xml](https://capec.mitre.org/data/xml/capec_latest.xml) · [STIX JSON](https://github.com/mitre/cti/blob/master/capec/2.1/stix-capec.json)
- [CWE-89](https://cwe.mitre.org/data/definitions/89.html) · [CWE-564](https://cwe.mitre.org/data/definitions/564.html) · [CWE-943](https://cwe.mitre.org/data/definitions/943.html)
- [OWASP SQLi Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) · [ASVS v4 V5](https://github.com/OWASP/ASVS/blob/master/4.0/en/0x13-V5-Validation-Sanitization-Encoding.md) · [ASVS v5.0 PDF](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/OWASP_Application_Security_Verification_Standard_5.0.0_en.pdf)
- [OWASP Top 10 2025 A05](https://owasp.org/Top10/2025/A05_2025-Injection/)
- [PG SECURITY DEFINER](https://www.postgresql.org/docs/current/sql-createfunction.html) · [PG PL/pgSQL](https://www.postgresql.org/docs/current/plpgsql-statements.html) · [PG Privileges](https://www.postgresql.org/docs/current/ddl-priv.html) · [PG RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Presidio recognizers](https://github.com/microsoft/presidio/tree/main/presidio-analyzer/presidio_analyzer/predefined_recognizers)
- [RU валидаторы (kdmatrosov)](https://github.com/kdmatrosov/validation-codes) · [Sigiller/validators](https://github.com/Sigiller/validators)
- [PortSwigger SQLi](https://portswigger.net/web-security/sql-injection/cheat-sheet)
- [sqlmap payloads](https://github.com/sqlmapproject/sqlmap/tree/master/data/xml/payloads) · [sqlmap tamper](https://github.com/sqlmapproject/sqlmap/tree/master/tamper)
- [SecLists Fuzzing](https://github.com/danielmiessler/SecLists/tree/master/Fuzzing) · [PayloadsAllTheThings SQLi](https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/SQL%20Injection)
