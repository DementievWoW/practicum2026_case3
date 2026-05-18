# 07 — Прямой доступ к чувствительным полям

- **`vuln_class`:** `DIRECT_SENSITIVE`
- **Риск:** 6/10
- **CWE:** [CWE-200 — Exposure of Sensitive Information](https://cwe.mitre.org/data/definitions/200.html), [CWE-359 — Exposure of Private Personal Information](https://cwe.mitre.org/data/definitions/359.html).
- **CAPEC:** нет прямого паттерна (это не атака, а слабая практика).
- **Compliance** (российский контекст): 152-ФЗ «О персональных данных».

## Что

Запрос напрямую выбирает (или модифицирует) колонки, которые содержат **чувствительные данные**: пароли, токены, номера карт, СНИЛС/ИНН/паспорт, телефоны, email, биометрию — **без маскирования, хеширования или ограничения по роли**. Часто наблюдается:
- `SELECT password_hash FROM users` — экспорт хешей для «миграции» (на самом деле — утечка).
- `SELECT card_number FROM payments` — выгрузка реквизитов в Excel.
- `SELECT passport FROM clients WHERE ...` — отчёт «по всем клиентам».

В ТЗ (`tusk`): «Запрос полей password_hash, token, ssn, card_number без маскировки или ограничения прав».

## Почему опасно (риск 6)

Не такой деструктивный, как SQLi/DML без WHERE (поэтому не 9-10), но:
- **Compliance-нарушение** — обработка ПДн вне ясной цели (152-ФЗ ст. 5, 18).
- **Аналитики копируют данные в локальные файлы** — utility-выгрузки превращаются в data leak.
- **Регулярные «отчёты»** с PII — частая причина инцидентов класса insider risk.
- При успешной эксфильтрации (через [01-sql-injection-classic](../01-sql-injection-classic/) или [02-sql-injection-union](../02-sql-injection-union/)) — атакующий получает именно эти колонки.

Риск 6 = умеренный, но **отражается во всех итеративных запусках** (классы выше 6 могут быть реже, этот — почти в каждом отчёте аналитика).

## PostgreSQL specifics

PostgreSQL даёт несколько механизмов для контроля доступа на уровне колонок:

| Механизм | Что делает | Когда применять |
|---|---|---|
| `GRANT SELECT (col1, col2) ON tbl TO role` | Колоночные привилегии | Контроль доступа |
| **Column-level Security** через `GRANT/REVOKE` | То же, но REVOKE с конкретной колонки | Запрет селекта |
| **Row-Level Security (RLS)** | Контроль на уровне строк | Multi-tenant |
| **Views** с маскированием | Презентация без чувств. данных | Аналитика |
| **`crypt()`/`pgp_sym_encrypt`** | Шифрование колонки | At-rest защита |
| **Маскирующие функции** (`anon` extension) | Динамическое маскирование | Тестовые БД |

Дефолтный setup в Postgres — `GRANT ALL` на роль приложения, без колоночных ограничений. Это распространённая ошибка.

## Чувствительные колонки (наш регекс-словарь)

Из ADR-0005 (`kb.pii` коллекция RAG) и Microsoft Presidio:

| Категория | Регекс (имена колонок) | Серьёзность |
|---|---|---|
| Креды | `password\|passwd\|pwd\|secret\|api[_-]?key\|token\|access[_-]?token` | critical |
| Платёжные | `card[_-]?(number\|num\|no)\|pan\|cvv\|cvc` | critical |
| Идентификация (US) | `ssn\|social[_-]?security` | high |
| Идентификация (RU) | `passport\|inn\|snils\|ogrn` | high |
| Контакты | `email\|phone\|mobile\|tel\b` | medium |
| Демо/био | `dob\|birth(_?date\|day)\|biometric\|fingerprint` | medium |

В нашей схеме `data_model_sql/data_model.sql` (60 таблиц банк/ERP) колонок с явными чувствительными именами немного, но есть:
- `user_id`, `created_emp_id`, `last_modified_emp_id` — указывают на employee; сами по себе не PII, но в связке с `users.full_name` дают атрибуцию.
- `account_name`, `name__ru`, `name__en` — близко к PII при работе с физлицами.

## Пример антипаттерна

```sql
-- УЯЗВИМО (если password_hash правда лежит в schema)
SELECT id, login, password_hash, email FROM users;
SELECT * FROM clients WHERE passport_number = '4500123456';
SELECT card_number, cvv FROM payments WHERE created_at > now() - interval '1 day';
```

И типичный «утечковый отчёт»:
```sql
COPY (SELECT login, email, phone, passport FROM clients) TO '/tmp/clients.csv' CSV;
```

## Эталонный fix

**Если данные нужны для UI пользователя:** маскирование на уровне view:
```sql
CREATE VIEW v_clients_masked AS
SELECT
    id,
    login,
    CONCAT(LEFT(email, 2), '***@', SUBSTRING(email FROM '@(.+)$')) AS email_masked,
    -- паспорт — только первые 4 цифры
    LEFT(passport, 4) || '******' AS passport_masked
FROM clients;
```

**Если нужен агрегат:** только агрегат, не сырые значения:
```sql
SELECT count(*) FROM payments WHERE created_at > now() - interval '1 day';
-- вместо SELECT card_number, cvv FROM payments
```

**Если нужен полный доступ для конкретной задачи:** колоночные привилегии:
```sql
REVOKE ALL ON users FROM analytics_role;
GRANT SELECT (id, login, email) ON users TO analytics_role;  -- без password_hash
```

**Шифрование at-rest для критичных колонок:**
```sql
-- Хранение
INSERT INTO payments (card_number) VALUES (pgp_sym_encrypt('4500...', current_setting('app.key')));
-- Чтение (только привилегированной роли)
SELECT pgp_sym_decrypt(card_number::bytea, current_setting('app.key')) FROM payments;
```

## Как мы детектим

### Phase 1 — `R009-sensitive-columns` (ADR-0004)

`pglast.Visitor` по `SelectStmt`:

```python
SENSITIVE_PATTERNS = [
    (r"(?i)^(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token)$", "critical", 8),
    (r"(?i)^(card[_-]?(number|num|no)|pan|cvv|cvc)$", "critical", 8),
    (r"(?i)^(ssn|social[_-]?security)$", "high", 7),
    (r"(?i)^(passport|inn|snils|ogrn)$", "high", 7),
    (r"(?i)^(email|phone|mobile|tel)$", "medium", 5),
    (r"(?i)^(dob|birth(_?date|day))$", "medium", 5),
]

def visit_ColumnRef(self, ancestors, node):
    col_name = node.fields[-1].sval
    for pat, severity, score in SENSITIVE_PATTERNS:
        if re.match(pat, col_name):
            # проверяем, нет ли обёртки маскирующей функцией
            if is_inside_func(ancestors, names={"coalesce", "mask", "digest", "hash", "left", "substring", "pgp_sym_decrypt"}):
                continue
            yield Finding(
                rule_id="R009-sensitive-columns",
                vuln_class="DIRECT_SENSITIVE",
                severity=severity, risk_score=score,
                location=node.location,
                message=f"Прямой доступ к чувствительной колонке {col_name}",
                evidence_refs=["CWE-200", "CWE-359"],
            )
```

**Дополнительная стадия** (отдельный visitor): обходим `SELECT *` (`A_Star`) и связываем их с `information_schema.columns` из sandbox-БД. Если в expanded списке колонок есть чувствительные имена — finding с тем же `vuln_class`.

### Phase 2 — LLM-судья

RAG: `kb.pii` (наша коллекция с регексами + примерами), CWE-200, CWE-359, OWASP ASVS V8.

LLM:
1. Подтверждает, что колонка действительно чувствительная (FP-проверка: `password_reset_at` — не пароль, это timestamp).
2. Проверяет контекст: есть ли в `WHERE` фильтр по `user_id = current_user_id` (тогда low — legitimate self-access).
3. Формирует рекомендацию: маскирование / view / колоночные привилегии.

### Phase 1bis — детект ПДн в literals

Если в `WHERE` или `VALUES` встречается значение, похожее на ПДн (по regex + checksum):
- Номер карты → Luhn-валидация.
- СНИЛС → mod-101 валидация.
- ИНН (10/12 цифр) → контрольная сумма.

Это `R009b-pii-in-literal` (variant правила). Часто означает: либо тестовые данные просочились в код, либо реальный PII попал в SQL через ввод. Risk_score = 6-7.

## Метрика покрытия

В eval-set: **15 примеров с `vuln_class == DIRECT_SENSITIVE`**:
- 8 запросов к чувствительным колонкам без маскирования (разные категории).
- 5 запросов к ним же с правильным маскированием (для проверки FP).
- 2 запроса с PII в literals.

- Recall@iter1 ≥ 0.85.
- Precision ≥ 0.80 (FP высок: легко спутать `customer_email` (PII) с `system_notification_email` (общий ящик)).
- Δ risk_score: gold-fix через маскирование → < 4.

## Связи

- **ADR-0004** — правило `R009`, `R009b`.
- **ADR-0005** — `kb.pii` коллекция RAG (Presidio regex + RU валидаторы).
- **research/materials/05-security-benchmarks-datasets/sqlqueryshield/** — модель для классификации.
- **research/materials/05-security-benchmarks-datasets/securesql-benchmark/** — 932 примера утечек, 34 домена. **Прямо нацелен на наш класс уязвимостей.**
- **Microsoft Presidio** — https://github.com/microsoft/presidio
- **152-ФЗ** — ст. 5 (принципы обработки), ст. 18 (получение согласия), ст. 19 (меры защиты).

## Известные слабости детектора

1. **Не-английские имена колонок** — `номер_паспорта_клиента` regex не поймает. План: расширить словарь русскими корнями (`паспорт`, `номер_карты`, ...).
2. **Aliasing**: `SELECT u.password_hash AS x FROM users u` — Phase 1 видит `password_hash`, всё ок. Но `SELECT col_a FROM v_users` где `v_users` определена как `SELECT password_hash AS col_a FROM users` — мы не видим. Нужно резолвить через `information_schema.views`.
3. **Boolean masking flags**: иногда столбец `password` — это `BOOLEAN has_password`, а не сам хеш. Текущий regex такой кейс пометит. Phase 2 должен подтвердить по типу из sandbox-схемы.
4. **JOIN-leaks**: запрос к view, не раскрывающему PII, но с JOIN к таблице, у которой PII — Phase 1 не видит. Это side-channel, оставляем как known limitation.
