# Problems — каталог проблем под микроскопом

Каждая папка — одна проблема, разобранная по структуре:

- **Что** — формальное определение.
- **Почему опасно** — реальный impact + обоснование риск-скора.
- **PostgreSQL specifics** — диалект-специфичные нюансы (`pg_sleep`, `EXECUTE format`, `SECURITY DEFINER`, и т.п.).
- **Пример атаки / антипаттерн** — реальный вредоносный/плохой SQL.
- **Эталонный fix** — что должен предложить судья.
- **Как мы детектим** — связка Phase 1 (детерминированные правила, ADR-0004) + Phase 2 (LLM-судья поверх findings + RAG).
- **Метрика покрытия** — что будем мерить в eval-set.
- **Связи** — ADR, materials/, CWE/CAPEC/OWASP.

## Две группы проблем

### 1. [Уязвимости SQL](vulnerabilities/) — 9 классов из `baseline1.VULN_CLASSES`

Это «продуктовая» поверхность кейса. Минимум для зачёта — покрыть 5 классов (25 баллов).

| # | Класс | `vuln_class` | Риск | Mandatory |
|---|---|---|---|---|
| 01 | [SQL Injection (классический)](vulnerabilities/01-sql-injection-classic/) | `SQL_INJ_CLASSIC` | 10 | ⭐ |
| 02 | [Union-based Injection](vulnerabilities/02-sql-injection-union/) | `SQL_INJ_UNION` | 9 | ⭐ |
| 03 | [Time-based Blind Injection](vulnerabilities/03-sql-injection-time-blind/) | `SQL_INJ_TIME` | 8 |  |
| 04 | [UPDATE/DELETE без WHERE](vulnerabilities/04-dml-no-where/) | `DML_NO_WHERE` | 9 | ⭐ |
| 05 | [Privilege Escalation через EXECUTE](vulnerabilities/05-privilege-escalation-execute/) | `PRIV_ESCALATE` | 8 |  |
| 06 | [PL/pgSQL: небезопасный EXECUTE](vulnerabilities/06-plpgsql-unsafe-execute/) | `PLPGSQL_UNSAFE` | 9 | бонус +10 |
| 07 | [Прямой доступ к чувствительным полям](vulnerabilities/07-direct-sensitive-access/) | `DIRECT_SENSITIVE` | 6 | ⭐ |
| 08 | [Избыточный SELECT *](vulnerabilities/08-select-star/) | `SELECT_STAR` | 5 | ⭐ |
| 09 | [Неограниченный LIMIT](vulnerabilities/09-no-pagination/) | `NO_PAGINATION` | 4 |  |

«⭐ Mandatory» = в minimum-set из 5 классов для зачёта (рекомендуемый набор).

### 2. [Инженерные вызовы](engineering/) — 6 системных проблем

Это «архитектурная» поверхность. На них держится способность вообще довести MVP до защиты.

| # | Вызов | Влияет на критерии |
|---|---|---|
| 01 | [Большая схема (60 таблиц)](engineering/01-large-schema-linking/) | EX ≥ 70 % |
| 02 | [Reflection-память: цикл реально учится](engineering/02-reflection-memory-loop/) | Работа цикла (25 баллов) |
| 03 | [Синтез датасета без эталона](engineering/03-synthetic-dataset/) | EX, Recall, бонус +10 |
| 04 | [Ненадёжность LLM-as-judge](engineering/04-llm-judge-unreliability/) | Покрытие уязвимостей (25 баллов) |
| 05 | [Бюджет латентности 40 секунд](engineering/05-latency-budget/) | Качество live-demo |
| 06 | [Целевая модель ≤ 30B параметров](engineering/06-on-prem-model-size/) | Обоснованность архитектуры |

## Как читать

Если ты впервые открыл проект — начни с [vulnerabilities/](vulnerabilities/), потом [engineering/](engineering/). В каждой проблеме в конце — ссылки на конкретный ADR (`docs/adr/`) и верифицированные материалы (`research/materials/`).
