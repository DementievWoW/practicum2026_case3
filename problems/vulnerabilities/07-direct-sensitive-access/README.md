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

## PostgreSQL specifics

PostgreSQL даёт несколько механизмов для контроля доступа на уровне колонок:

| Механизм | Что делает | Когда применять |
|---|---|---|
| `GRANT SELECT (col1, col2) ON tbl TO role` | Колоночные привилегии | Контроль доступа |
| **Column-level Security** через `GRANT/REVOKE` | REVOKE с конкретной колонки | Запрет селекта |
| **Row-Level Security (RLS)** | Контроль на уровне строк | Multi-tenant |
| **Views** с маскированием | Презентация без чувств. данных | Аналитика |
| **`crypt()`/`pgp_sym_encrypt`** | Шифрование колонки | At-rest защита |
| **Маскирующие функции** (`anon` extension) | Динамическое маскирование | Тестовые БД |

Дефолтный setup в Postgres — `GRANT ALL` на роль приложения, без колоночных ограничений. Это распространённая ошибка.

## Чувствительные колонки

Из ADR-0005 (`kb.pii` коллекция RAG) и Microsoft Presidio:

| Категория | Регекс (имена колонок) | Серьёзность |
|---|---|---|
| Креды | `password\|passwd\|pwd\|secret\|api[_-]?key\|token\|access[_-]?token` | critical |
| Платёжные | `card[_-]?(number\|num\|no)\|pan\|cvv\|cvc` | critical |
| Идентификация (US) | `ssn\|social[_-]?security` | high |
| Идентификация (RU) | `passport\|inn\|snils\|ogrn` | high |
| Контакты | `email\|phone\|mobile\|tel\b` | medium |
| Демо/био | `dob\|birth(_?date\|day)\|biometric\|fingerprint` | medium |

В нашей схеме `data_model_sql/data_model.sql` (60 таблиц банк/ERP) колонок с явными чувствительными именами немного, но есть атрибутивные комбинации (`user_id` + `full_name`).

## Пример антипаттерна

```sql
SELECT id, login, password_hash, email FROM users;
SELECT * FROM clients WHERE passport_number = '4500123456';
SELECT card_number, cvv FROM payments WHERE created_at > now() - interval '1 day';
COPY (SELECT login, email, phone, passport FROM clients) TO '/tmp/clients.csv' CSV;
```

## Внешние ссылки

- **CWE-200**, **CWE-359** — в шапке.
- **research/materials/05-security-benchmarks-datasets/securesql-benchmark/** — 932 примера утечек, 34 домена. **Прямо нацелен на наш класс.**
- **research/materials/05-security-benchmarks-datasets/sqlqueryshield/** — CodeBERT-классификатор malicious-vs-benign.
- **Microsoft Presidio** — https://github.com/microsoft/presidio
- **152-ФЗ** — ст. 5, 18, 19.

## Варианты решения

См. [solutions.md](solutions.md).
