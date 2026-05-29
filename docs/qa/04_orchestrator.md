# Q&A · Оркестратор + датасет + инфра · Участник 4

100 вопросов про цикл, контракты, датасет, sandbox БД, Prometheus, Langfuse, deploy.

## LangGraph и цикл (1–10)
**1.** LangGraph или Python? — На MVP — Python; LangGraph — задел.
**2.** Почему Python? — Простота, меньше зависимостей, дебаг проще.
**3.** Что даст LangGraph? — Checkpoints, time-travel, conditional edges.
**4.** PostgresSaver? — Сохраняет состояние графа в Postgres → откат к итерации N.
**5.** Миграция? — Сейчас `SQLSecurityPipeline.run`; в LangGraph — узлы generate/audit/reflect/decide.
**6.** Где код цикла? — `src/case3/pipeline.py::SQLSecurityPipeline.run`.
**7.** Сколько строк? — ~50: for-loop с break на approved.
**8.** Что внутри? — Цикл: generate → audit → log → break-if-approved → reflect.
**9.** Streaming UI? — Через `on_event` callback → SSE-стрим итераций.
**10.** Параллельность? — Один запрос — sequential; multi-request — независимые run() в asyncio.

## Контракт baseline (11–20)
**11.** Что такое baseline? — `baseline1.py` от заказчика — контракт.
**12.** Что в baseline? — dataclasses + базовые классы + run_sql_security_pipeline.
**13.** Изменяем? — Нет, ни строки.
**14.** Где наши реализации? — `src/case3/contracts.py` — re-export baseline + наши добавки.
**15.** Что нового в Finding? — Расширенное представление vulnerability с rule_id, severity, recommendation.
**16.** Lesson? — Структура для in-context reflection (rule_id, error, recommendation).
**17.** Совместимость? — `Finding.to_vulnerability()` мапит в baseline.Vulnerability.
**18.** Зачем разделять? — Доменные сущности (для reflection) не загрязняют baseline.
**19.** Тесты на контракт? — `tests/contract.py` — assert импортов + работы SQLSecuritySystem.
**20.** Если заказчик обновит baseline? — Пересобираем `contracts.py`, наша логика не страдает.

## max_iterations и остановка (21–30)
**21.** max_iterations? — Default 5.
**22.** Почему 5? — Эмпирически: 3–4 достаточно для 90%+; 5 — буфер.
**23.** Больше — можно? — Да, в `SystemConfig`; за 5 покрываем большинство.
**24.** Если 5 не хватило? — `SystemResult.approved=False`; UI предлагает переформулировать.
**25.** Логируем причину выхода? — Да, в `metadata.exit_reason`: approved/max_iter/error.
**26.** Early exit? — На MVP нет; план — если risk не падает 2 итерации подряд.
**27.** Timeout per iteration? — LLM_TIMEOUT=120 сек на LLM-вызов.
**28.** Если audit падает? — try/except → risk 10, approved=False, finding `audit_failed`.
**29.** Если generator падает? — Аналог: SQL "", approved=False, finding `generator_failed`.
**30.** UI узнаёт об ошибке? — Из `SystemResult.metadata.error`.

## Reflection-loop реализация (31–40)
**31.** Где код? — `src/case3/nodes/reflector.py::Reflector.reflect`.
**32.** Что внутри? — `audit.vulnerabilities` → для каждого rule_id → шаблон → Lesson.
**33.** Сейчас заглушка? — Да: детерм. лук-up по vuln_class в `_LESSON_TEMPLATES`.
**34.** Реальная версия? — Маленькая T5 / 7B LLM, adaptive lessons.
**35.** Дедуп? — По rule_id — обновляем, не дублим.
**36.** Окно? — 5 последних; старше — выбрасываем.
**37.** Как уроки попадают в генератор? — `reflection=…` → `generator.generate` инжектит в промпт.
**38.** Несколько уроков для одного rule_id? — Свежий перезаписывает (rule_id уникален).
**39.** Где тесты? — `tests/test_reflector.py` (план).
**40.** Reflexion на следующий запрос? — Не на MVP; per-user memory — план.

## Датасет (41–50)
**41.** Что в датасете? — 14 seed + back-translation синтетика + sensitive overlay.
**42.** Где seed? — `dataset/seed_examples.py::SEED_EXAMPLES`.
**43.** Поля SeedExample? — task_nl, target_sql, vuln_class (или CLEAN), tables_used.
**44.** Зачем 14? — Покрытие 9 классов + SLOW_QUERY + happy paths.
**45.** Что такое back-translation? — Корректный SQL → LLM пишет NL → пара (NL, SQL) пополняет датасет.
**46.** Подход? — OmniSQL / SING-SQL (SQL-first).
**47.** Объём синтетики? — Цель ~500 пар; старт — 100.
**48.** Sensitive overlay? — В реальной схеме нет очевидных PII колонок — добавляем синтетические таблицы (sim_client, sim_payment_card, sim_employee_account).
**49.** Зачем overlay? — Тест DIRECT_SENSITIVE без модификации схемы заказчика.
**50.** Где overlay? — `dataset/sensitive_overlay.sql`.

## Sandbox БД + EXPLAIN (51–60)
**51.** Что такое sandbox? — Postgres-контейнер с data_model.sql + faker-данными.
**52.** Зачем? — EXPLAIN-эвристика + будущий smoke (валидность SQL).
**53.** EXPLAIN без ANALYZE? — Не исполняет; даёт план и cost.
**54.** Cost интерпретируем? — Высокий cost + seq scan → подсказка R-NO_PAGINATION/R-DML_NO_WHERE.
**55.** Данные настоящие? — Faker по структуре + sensitive_overlay для PII-тестов.
**56.** SEED_N? — 500 строк per table.
**57.** Где seeder? — `deploy/seed/Dockerfile` + python-скрипт faker.
**58.** Идемпотентность? — One-shot контейнер; запуск при первой инициализации БД.
**59.** Как пересеять? — `docker compose run --rm seeder`.
**60.** Что в init-db? — `deploy/init-db/01_schema.sql` (DDL заказчика, 657 KB).

## Метрики Prometheus (61–70)
**61.** Какие метрики? — `sqlsec_runs_total{approved}`, `sqlsec_iterations`, `sqlsec_latency_seconds`, `sqlsec_last_risk`, `sqlsec_findings_total{vuln_class}`.
**62.** Где код? — `src/case3/infra/metrics.py`.
**63.** На чём написано? — stdlib (http.server, threading) → Prometheus exposition format.
**64.** Реальный prometheus_client? — Drop-in: те же имена; меняется только импорт.
**65.** Где /metrics? — :19100 на хосте, :9100 в контейнере.
**66.** scrape_interval? — 5 сек.
**67.** Где Grafana? — `deploy/observability/grafana/dashboards/sql-security.json`.
**68.** Что в дашборде? — Стат-карточки (прогоны, % approved, риск, медиана итераций) + latency p95 timeseries + bar по vuln_class.
**69.** PromQL p95? — `histogram_quantile(0.95, sum(rate(sqlsec_latency_seconds_bucket[1m])) by (le))`.
**70.** Алерты? — План: alert если approved-rate < 0.5 за 1 час.

## Langfuse (71–80)
**71.** Что это? — Open-source LLM-observability: трейсы, скоринг, A/B.
**72.** Версия? — v2 (single-container; v3 требует ClickHouse/Redis/Minio — тяжело).
**73.** Где код? — `src/case3/infra/tracing.py::LangfuseTracer`.
**74.** Когда подключается? — Если есть `LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` в env. Иначе StubTracer.
**75.** Что трейсим? — Trace на запрос: спаны generate/audit/reflect, scores final_risk и approved.
**76.** Где UI? — http://localhost:13001.
**77.** Deep-link? — `trace_id` в `SystemResult.metadata` → UI делает ссылку.
**78.** Persist? — В `langfuse_db` (отдельный Postgres).
**79.** Скоринг? — `tr.score("final_risk", value)`, `tr.score("approved", 1/0)`.
**80.** PII в Langfuse? — Юзер-вход (NL), SQL — да. Локально, не cloud. Для прода — выбираем cloud или self-host.

## Deploy / Docker Compose (81–90)
**81.** Сколько сервисов? — 7: db, seeder, app, prometheus, grafana, langfuse-db, langfuse.
**82.** Порты на хост? — 18000 (app), 19100 (metrics), 19090 (prom), 13000 (grafana), 13001 (langfuse), 15432 (db).
**83.** Почему нестандартные? — Чтобы не конфликтовать с другими docker-стеками на машине.
**84.** Где compose? — Корень репо.
**85.** Где Dockerfile app? — Корень репо.
**86.** Образ Python? — python:3.11-slim.
**87.** Размер app-образа? — ~800 MB (с зависимостями).
**88.** Volumes? — db_data, langfuse_db_data + bind `./data:/app/data` + bind конфигов prom/grafana.
**89.** Secrets? — docker secret `llm_api_key` (файл `./secrets/llm_api_key`, gitignored).
**90.** Сети? — Один compose-network; сервисы видят друг друга по имени.

## setup.sh + масштабирование (91–100)
**91.** Что делает setup.sh? — Проверки → .env из шаблона → запросить LLM-ключ → docker compose up -d --build → ждать /healthz.
**92.** Идемпотентен? — Да: не перетирает .env и заполненный ключ.
**93.** Windows-перевод строки? — Чистится `${KEY//$'\r'/}`.
**94.** Если ключа нет? — Пустой файл → MockLLMClient.
**95.** Обновить ключ? — `echo "new" > secrets/llm_api_key && docker compose restart app`.
**96.** Полная очистка? — `docker compose down -v` (снесёт volume).
**97.** Масштабирование app? — `--scale app=3` + балансер; на проде — k8s + HPA.
**98.** Postgres в проде? — Managed (RDS/CloudSQL) + read-replica.
**99.** LLM в проде? — vLLM на GPU-узле + autoscaling по очереди.
**100.** Что демонстрирует Уч.4? — `./setup.sh` → стек поднялся → запрос в UI → дашборд Grafana → трейс Langfuse.
