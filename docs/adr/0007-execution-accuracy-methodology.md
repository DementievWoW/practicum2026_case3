# ADR-0007 — Execution Accuracy methodology and evaluator safety

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`):

> Точность генерации SQL: Execution Accuracy на тестовом наборе
> составляет не менее **70%**; результат измерен и задокументирован
> (15 баллов).

> Аналитика и отчётность: ... динамика снижения оценки риска
> по итерациям, среднее число итераций до одобрения (15 баллов).

Из `take1` (ментор):

> Метрики. Качество генерации (сравнение выдачи с эталонной, **не
> LLM-as-Judge по самому SQL**), безопасность (суммарный риск-скор,
> доля опасных запросов), эффективность (токены, время — лимит 40
> секунд).

ТЗ напрямую запрещает исполнять SQL «у клиента»:

> Система не исполняет запросы самостоятельно — цикл завершается при
> одобрении судьи или исчерпании лимита итераций.

Но для **измерения качества генерации** исполнение в **песочнице**
не запрещено — без него Execution Accuracy не посчитать.
Это уточняли у ментора (см. `take1` § «Скоуп MVP под вопросом»).

Из `research/02_text2sql_benchmarks.md`:

- Нюансы EX: order-aware vs multiset; NULL == NULL; column order;
  типы / round; недетерминизм при ties.
- Soft-F1 (Snowflake Cortex) — устойчивее к мелким ошибкам.
- Test-suite Execution Accuracy (EMNLP 2020) — несколько вариантов БД
  для устойчивости к недетерминизму.

## Decision

1. **Eval-set — из ADR-0006**: 60 SQL × 2 NL = 120 пар, со
   стратификацией по vuln_class и difficulty, сплит фиксирован
   `seed=42`.

2. **Eval-исполнение — в изолированной sandbox-БД** (отдельный
   docker-контейнер от рантайма аудитора):

   - `postgres:17`, `tmpfs`, faker-сидинг.
   - Read-only роль `case3_eval`.
   - `statement_timeout = 30s`, `lock_timeout = 5s`.
   - `default_transaction_read_only = on` на уровне роли.
   - Сидинг детерминированный (фикс seed faker), снэпшот тестовой
     базы кешируется как pg_dump.
   - **На прод/реальную demo-БД EXPLAIN-only.**

3. **Метрика Execution Accuracy (EX-strict)**:

   - Для каждой пары (gold_sql, pred_sql) исполняем оба:
     `cursor.execute(gold_sql)` и `cursor.execute(pred_sql)`.
   - Сравниваем результаты как **multisets кортежей значений**:
     - Преобразуем `None → "__NULL__"` (sentinel).
     - Float-ы округляем до 4 знаков.
     - Даты → ISO-формат.
     - Строки → `strip()`.
   - **ORDER BY-aware**:
     - Если в `gold_sql` есть `ORDER BY` (детектируем через `pglast`),
       сравниваем как list (порядок важен).
     - Иначе — как multiset (`collections.Counter`).
   - Сравнение — по значениям, **не по именам колонок**. Это
     устойчивее к синонимам типа `SELECT name__ru AS name` vs
     `SELECT name__ru`.

4. **Метрика Soft-F1** (как дополнительная):

   - Для каждой строки gold-результата ищем «ближайшую» в
     pred-результате по multiset intersection на значениях.
     `precision = matched / |pred|`, `recall = matched / |gold|`,
     `F1 = 2pr/(p+r)`.
   - Полезна для частичного кредита: например, верные колонки, но
     лишний фильтр.

5. **Обработка ошибок исполнения**:

   - Если `pred_sql` бросает `psycopg.Error` — EX = 0, Soft-F1 = 0,
     `error_class = type(exc).__name__`.
   - Если `gold_sql` бросает ошибку — пример выкидывается из eval
     (это баг в датасете, требует ручной правки; в репорте отдельный
     счётчик `eval_dataset_errors`).
   - Timeout → EX = 0, `error_class = "timeout"`.

6. **Связанные runtime-метрики** (для критерия «Аналитика и
   отчётность»):

   - `iterations_used` (медиана и распределение).
   - `risk_score_trajectory` — серия `[overall_risk_score]` по
     `iterations_log` (для динамики snijения риска по итерациям).
   - `latency_seconds_total` и per-iteration; алёрт при >40 с
     (ограничение из `take1`).
   - `tokens_in / tokens_out` (по модели и по узлу).
   - `approved_rate` — доля задач, где `SystemResult.approved == True`.
   - **Recall судьи по vuln_class** — доля корректно
     детектированных уязвимостей в eval-наборе с известными метками:
     для каждой задачи с `gt_vuln_class != "safe"` судья должен
     поднять `Vulnerability` с тем же `vuln_class` хотя бы на одной
     итерации.

7. **Stat-test для сравнения версий** (для критерия «Аналитика»
   и для бонусной защиты):

   - **McNemar** на бинарной EX между двумя версиями цикла (с/без
     reflection, с/без RAG и т. п.).
   - **Paired bootstrap** (1000 ресемплов) на Soft-F1 для CI разности.
   - Реализация — `scipy.stats.contingency.mcnemar` +
     самописная функция bootstrap.

8. **Eval-pipeline — отдельный скрипт `eval/run_eval.py`**:

   - На вход: путь к датасету `data/dataset_v1.jsonl`, конфигурация
     системы (модель, флаги).
   - На выход: `reports/eval_<timestamp>/`:
     - `per_example.jsonl` (gold, pred, EX, F1, vulns, iters, latency)
     - `summary.json` (агрегаты)
     - `summary.md` (человеко-читаемый отчёт для презы)
   - Воспроизводимость: фикс `seed=42` для faker и для LLM
     temperature.

9. **Никогда не исполняем `pred_sql` из untrusted input в demo**.
   В Streamlit demo (отдельный ADR позже) — только показ EXPLAIN-плана
   и аудит-лога, без исполнения по умолчанию. Чекбокс «execute in
   sandbox» — только для разработчиков, не на defence-демо.

## Consequences

**Положительные**

- Прямо отвечает на критерий «EX ≥ 70%» с задокументированной
  методологией.
- Soft-F1 даёт устойчивое сравнение версий, когда EX-strict
  «дребезжит» от мелочей.
- Sandbox изолирована от prod-демо — заказчик доволен с точки
  зрения безопасности данных.
- Stat-test → доказательная защита: «версия B статистически
  значимо лучше A (p<0.01)».
- Логирование per-iteration риска + tokens + latency покрывает
  критерий «Аналитика» (15 баллов).

**Отрицательные / Риски**

- EX зависит от качества датасета (gold_sql). Если gold некорректен,
  даже идеальный pred получит EX=0. Митигируем quality-gate из
  ADR-0006.
- Faker-данные не покрывают реальные распределения значений →
  некоторые SQL могут вернуть пустые результаты, что даёт «случайно
  совпадение EX = 1» (две пустые выборки). Митигируем: для
  каждой задачи проверяем `len(gold_result) > 0` при сидинге —
  если ноль, корректируем seed или меняем задачу.
- ORDER BY-detection через pglast не покроет случаи неявного
  упорядочивания через `DISTINCT ON` или window-функции —
  пометим как known limitation.
- 40 с time-limit может ломаться при cold-start LLM-провайдера.
  Митигируем: warm-up call в начале эксперимента.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| LLM-as-judge для оценки SQL (без исполнения) | Ментор прямо запретил; смещения LLM-judge документированы (Trend Micro). |
| Exact Match (EM) по AST | Жёсткий, штрафует валидные синонимы (`name AS x` vs `name`). Useful как diagnostic, не как main metric. |
| Test-Suite EX (несколько БД-снэпшотов) | Дорого по seeding и времени; для 60 примеров не оправдано. На бонус — можно добавить позже. |
| Сравнение по именам колонок | Промахивается на синонимах и AS-алиасах. По значениям корректнее. |
| Не использовать sandbox, оценивать только AST-метрики | Нет реального EX → проваливаем 15-балльный критерий. |
| Использовать `unittest.assertEqual(gold_rows, pred_rows)` без нормализации | Сломается на NULL/float/order/whitespace. |
| Запускать eval на реальной demo-БД GreenData | Опасно (ПДн), запрещено инструкциями (read-only). |

## Links

- ТЗ: `tusk` § «Точность генерации SQL», § «Аналитика и отчётность»
- Ментор: `take1` § «Метрики»
- Обзор: `research/02_text2sql_benchmarks.md` § 5 «Методология EX»
- Snowflake Soft-F1: https://www.snowflake.com/en/engineering-blog/cortex-analyst-text-to-sql-accuracy-bi/
- Test-Suite EX (EMNLP 2020): https://aclanthology.org/2020.emnlp-main.29.pdf
- McNemar's test для ML: https://machinelearningmastery.com/mcnemars-test-for-machine-learning/
- Paired bootstrap: https://medium.com/ai-enthusiast/comparing-nlp-models-with-confidence-the-paired-bootstrap-test-explained-c9a88532ea3d
- Зависит от: ADR-0001 (стек), ADR-0004 (sandbox-инфра),
  ADR-0006 (датасет)
