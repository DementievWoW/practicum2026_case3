# Simulations — 9 уязвимостей + 6 инженерных вызовов в виде Jupyter-ноутбуков

Каждый ноутбук — самодостаточный сценарий на одной уязвимости. Открывается в Google Colab, работает без внешних зависимостей (только stdlib + `sqlite3`, который есть в Colab из коробки).

## Что внутри каждого ноутбука

1. **🧒 Аналогия для ребёнка** — простыми словами, с метафорой.
2. **Setup** — мок-БД через `sqlite3` in-memory с тестовыми данными.
3. **Уязвимая функция** — реальный антипаттерн с Doxygen-комментариями.
4. **Атака** — конкретный payload, видим эффект (утекли данные / удалились строки / задержалась БД).
5. **Аудитор Phase 1** — упрощённый regex/AST-чек, выдаёт `Finding` с `risk_score`.
6. **Безопасная функция** — та же задача, но через параметризацию / WHERE / маскирование.
7. **Та же атака на безопасную версию** — видим, что атака уходит в пустоту.
8. **Итог + ссылки** на `problems/`, `docs/adr/`.

## Запуск локально

```bash
# Сгенерировать все 15 .ipynb
python simulations/build_notebooks.py

# Запустить ноутбук (если установлен jupyter):
jupyter notebook simulations/vulnerabilities/01_sql_injection_classic.ipynb
```

Структура:
```
simulations/
├── vulnerabilities/    9 ноутбуков (01-09) — атаки SQL и их детекция
├── engineering/        6 ноутбуков (10-15) — архитектурные вызовы MVP
└── build_*.py          генератор (не нужен для запуска ноутбуков)
```

Никаких `pip install` не нужно — sqlite3 в stdlib.

## Открытие в Google Colab

1. Зайди на https://colab.research.google.com/
2. **File → Upload notebook** → выбери нужный `.ipynb`.
3. Запускай ячейки кнопкой ▶ слева от каждой.

Если репозиторий публичный на GitHub:
```
https://colab.research.google.com/github/<USER>/<REPO>/blob/master/simulations/vulnerabilities/01_sql_injection_classic.ipynb
```

## Список ноутбуков

### Уязвимости SQL (1–9)

| # | Файл | Уязвимость | Риск | CWE |
|---|---|---|---|---|
| 01 | [01_sql_injection_classic.ipynb](vulnerabilities/01_sql_injection_classic.ipynb) | SQL Injection (классический) | 10/10 | CWE-89 |
| 02 | [02_sql_injection_union.ipynb](vulnerabilities/02_sql_injection_union.ipynb) | Union-based Injection | 9/10 | CWE-89 |
| 03 | [03_sql_injection_time_blind.ipynb](vulnerabilities/03_sql_injection_time_blind.ipynb) | Time-based Blind Injection | 8/10 | CWE-89 |
| 04 | [04_dml_no_where.ipynb](vulnerabilities/04_dml_no_where.ipynb) | UPDATE/DELETE без WHERE | 9/10 | CWE-1284 |
| 05 | [05_privilege_escalation.ipynb](vulnerabilities/05_privilege_escalation.ipynb) | SECURITY DEFINER без search_path | 8/10 | CWE-269 |
| 06 | [06_plpgsql_unsafe_execute.ipynb](vulnerabilities/06_plpgsql_unsafe_execute.ipynb) | PL/pgSQL: небезопасный EXECUTE | 9/10 | CWE-89 |
| 07 | [07_direct_sensitive_access.ipynb](vulnerabilities/07_direct_sensitive_access.ipynb) | Прямой доступ к чувствительным полям | 6/10 | CWE-200/359 |
| 08 | [08_select_star.ipynb](vulnerabilities/08_select_star.ipynb) | Избыточный SELECT * | 5/10 | CWE-1295 |
| 09 | [09_no_pagination.ipynb](vulnerabilities/09_no_pagination.ipynb) | Неограниченный LIMIT | 4/10 | CWE-770 |

### Инженерные вызовы (10–15)

| # | Файл | Проблема | Что симулируем (всё на mock-функциях) |
|---|---|---|---|
| 10 | [10_schema_linking.ipynb](engineering/10_schema_linking.ipynb) | Schema linking на 60 таблицах | bag-of-words эмбеддинг + cosine + FK-замыкание, сравнение бюджета токенов |
| 11 | [11_reflection_loop.ipynb](engineering/11_reflection_loop.ipynb) | Reflection-память: цикл учится | Mock generator+judge+reflector, A/B «с reflection vs без», % повторов rule_id |
| 12 | [12_synthetic_dataset.ipynb](engineering/12_synthetic_dataset.ipynb) | Синтез датасета (back-translation) | SQL→NL pattern-based, валидация в sandbox, quality-gate, train/eval split |
| 13 | [13_llm_judge_unreliability.ipynb](engineering/13_llm_judge_unreliability.ipynb) | LLM-as-judge ненадёжен | 4 кейса (FP/FN/TP/TN), сравнение rules-only vs LLM-only vs гибрид |
| 14 | [14_latency_budget.ipynb](engineering/14_latency_budget.ipynb) | Бюджет 40 секунд | Симуляция времён узлов, budget cap, graceful degradation, p50/p95/p99 |
| 15 | [15_model_size.ipynb](engineering/15_model_size.ipynb) | Модель ≤ 30B параметров | LLMClient контракт, 3 mock-модели (S/M/L), cost-калькулятор eval-set |

## Где «не на 100% реалистично»

SQLite — упрощённая модель PostgreSQL. Что мы **симулируем приближённо**:

| Что | Реально в Postgres | В наших ноутбуках |
|---|---|---|
| `pg_sleep(N)` | Встроенная функция | Симулируем через `time.sleep(N)` после исполнения |
| PL/pgSQL `EXECUTE format()` | Расширение языка | Имитируем Python-функцией, которая «играет роль» PL/pgSQL |
| `SECURITY DEFINER` + `search_path` | Атрибуты функции | Имитируем wrapper-функцией + объясняем атаку текстом |
| `COPY FROM PROGRAM` | Прямой RCE | Только показываем, не выполняем (соображения безопасности) |
| `EXPLAIN (FORMAT JSON)` | Реальный planner | Имитируем через мок-плана |

Это **не лишает демонстрации смысла** — все атаки **концептуально работают**, и наш аудитор детектит их одинаково и в SQLite, и в PostgreSQL.

## Связи с проектом

- **Под микроскопом каждая проблема:** [problems/](../problems/)
- **Архитектурные решения:** [docs/adr/](../docs/adr/)
- **Верифицированная литература:** [research/materials/](../research/materials/)
