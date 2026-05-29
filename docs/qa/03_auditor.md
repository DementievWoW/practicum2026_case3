# Q&A · Аудитор (судья) · Участник 2

100 вопросов про 9 классов уязвимостей, гибрид правил/моделей, sensitive-детектор, RAG.

## 9 классов уязвимостей (1–10)
**1.** Перечисли 9. — SQL_INJ_CLASSIC, SQL_INJ_UNION, SQL_INJ_TIME, DML_NO_WHERE, PRIV_ESCALATE, PLPGSQL_UNSAFE, DIRECT_SENSITIVE, SELECT_STAR, NO_PAGINATION.
**2.** SQL_INJ_CLASSIC? — Простая инъекция через комментарий/escape (`' OR '1'='1`).
**3.** SQL_INJ_UNION? — UNION SELECT … для эксфильтрации (часто поверх classic).
**4.** SQL_INJ_TIME? — Blind через `pg_sleep`, `CASE WHEN … THEN pg_sleep`.
**5.** DML_NO_WHERE? — UPDATE/DELETE без WHERE — массовая модификация.
**6.** PRIV_ESCALATE? — GRANT/ALTER USER/ROLE; DDL вроде DROP/CREATE без разрешения.
**7.** PLPGSQL_UNSAFE? — Динамический SQL EXECUTE с user input; SECURITY DEFINER.
**8.** DIRECT_SENSITIVE? — Прямой SELECT/SHOW колонок с PII (паспорта, СНИЛС, карты).
**9.** SELECT_STAR? — `SELECT *` — утечка sensitive + перегруз.
**10.** NO_PAGINATION? — Запрос без LIMIT/OFFSET на потенциально большой результат.

## Phase 1 правила (11–20)
**11.** Где правила? — `src/case3/audit/rules.py` (каркас).
**12.** Сколько работающих? — На MVP — 2 (SELECT *, no LIMIT) + sensitive; остальные 7 — TODO Уч.2.
**13.** R001 SELECT *? — Regex/AST: `SELECT \*`; risk 3.
**14.** R002 no LIMIT? — Нет `LIMIT N` в SELECT; risk 2.
**15.** R003 DML no WHERE? — UPDATE/DELETE/INSERT без WHERE; risk 7.
**16.** R004 DDL? — DROP/CREATE/ALTER — risk 10.
**17.** R005 UNION? — UNION с подозрительными литералами; risk 8.
**18.** R006 sleep? — `pg_sleep`/`SLEEP` — risk 9.
**19.** R007 PLPGSQL EXECUTE? — Динамический SQL в функции; risk 8.
**20.** R008 cross-database? — REFERENCES в чужие БД; risk 7.

## pglast vs regex (21–30)
**21.** Зачем pglast? — Корректный AST PostgreSQL — устойчив к обфускации (комментарии, разный case, переводы строк).
**22.** Минусы pglast? — GPLv3 + C-расширение.
**23.** Что покрывает regex? — Простые случаи (SELECT *, LIMIT). Обфускацию пропускает.
**24.** Пример обфускации? — `SE/**/LECT */**/FROM …` — regex может проморгать.
**25.** AST-правило — пример? — Все RangeVar (таблицы) без условий в JOIN → cartesian flag.
**26.** Заменить pglast на sqlglot? — Можно; Apache-2.0. Меньше PG-специфики.
**27.** Финальный выбор? — Если решим GPL — pglast; иначе sqlglot.
**28.** Fallback? — pglast не парсит → regex + флаг «syntax-suspect» в AuditResult.
**29.** EXPLAIN-узел как сигнал? — Phase 1+: cost/seq scan/cartesian как доп. источники.
**30.** Что НЕ покрывает AST? — Семантику (что таблица содержит PII).

## Sensitive детектор (31–40)
**31.** Что детектит? — Прямой SELECT колонок с PII по имени + Luhn для карт + СНИЛС-формат.
**32.** Список sensitive-имён? — `password`, `passport`, `snils`, `card_number`, `cvv`, `email` (опц.), `birth_date` (опц.).
**33.** Luhn? — Контрольная сумма номера карты — ловит литералы `WHERE card='4111…'`.
**34.** СНИЛС? — 11 цифр (XXX-XXX-XXX YY) + контрольная сумма.
**35.** Нестандартное имя? — Словарь синонимов (passport_no, passport_number, …).
**36.** Где словарь? — `src/case3/audit/sensitive.py::_STUB_SENSITIVE` (заглушка).
**37.** False positives? — `password_hint_id` ловится на «password»; лечим списком разрешённых суффиксов.
**38.** DISTINCT на sensitive — опасно? — Да: утечка уникальных значений (профилирование).
**39.** SELECT count(*) — ок? — Агрегаты ок; флагим только проекцию значений.
**40.** Sensitive в WHERE? — `WHERE passport='…'` — опасно (литерал PII).

## Phase 1.5 CodeBERT (41–50)
**41.** Зачем? — Ловит «странные» SQL, что правила пропускают (обфускация, экзотика).
**42.** Модель? — CodeBERT (microsoft/codebert-base) + classification head.
**43.** Датасет? — SQLQueryShield или свой (синтетика + публичные инъекции).
**44.** Размер? — ~125M, ~500 MB на CPU.
**45.** Latency? — ~50–100 мс CPU, ~5–10 мс GPU.
**46.** Что выдаёт? — P(malicious) 0–1.
**47.** Как используем? — > 0.6 → risk += 3 в агрегаторе.
**48.** Калибровка? — Платт-скейл на validation → порог 0.5 ↔ риск 5.0.
**49.** Альтернатива? — CatBoost на фичах (быстрее, но скромнее). На MVP CodeBERT — задел.
**50.** Roadmap? — Сейчас ⬜ не написано; задача Уч.2.

## Phase 2 LLM-судья (51–60)
**51.** Модель? — Qwen2.5-7B-Instruct.
**52.** Зачем 7B, а не 32B? — Триаж/объяснение — простая задача; дешевле.
**53.** Промпт? — System: «security expert»; user: SQL + Phase 1 findings + RAG.
**54.** Выход? — JSON: list[Vulnerability] + объяснение.
**55.** Почему JSON? — Парсинг и валидация.
**56.** Что в JSON? — `{vuln_class, risk_score, description, recommendation, cwe}`.
**57.** Self-critique? — Не используем; разделение ролей дешевле.
**58.** Когда вызывается? — Всегда после Phase 1+1.5; не блокирующий.
**59.** Если судья «всё ок»? — Только если правила и CodeBERT тоже чистые (MAX-агрегатор).
**60.** Multi-judge (PoLL)? — Тестировали — не помогло на наших данных; 1 Qwen-судья даёт 27/27 recall на 95% accuracy.

## RAG (61–70)
**61.** Что в RAG-базе? — CWE-89 (SQL injection), CAPEC-66, OWASP A03, наши кейсы.
**62.** Где хранится? — Vector store + текстовый bank (md/jsonl).
**63.** Чем эмбедим? — multilingual-e5 / bge-m3 (тот же, что для схемы).
**64.** Сколько найдёт? — top-3 chunk-ов.
**65.** Что отдаёт LLM-судье? — Текст уязвимости + примеры + рекомендация.
**66.** Hybrid (BM25+dense)? — План; на MVP — dense.
**67.** Когда не использовать RAG? — Если Phase 1 одобрил с risk 0 — судью можно скипнуть.
**68.** Обновление базы? — Раз в N дней (CWE редко) + наши уроки.
**69.** Где код? — `src/case3/audit/rag.py` (план Уч.2).
**70.** Альтернатива? — Tools/function-call к OWASP API; на MVP — embedded.

## Агрегатор + threshold (71–80)
**71.** Что делает? — Сводит findings со всех слоёв в один risk.
**72.** Формула? — MAX (самый опасный finding определяет общий риск).
**73.** Почему MAX? — Безопасность: один реальный SQL_INJ затмевает 10 FP.
**74.** SUM/WEIGHTED? — 10 мелких затмят критический; не подходит.
**75.** Threshold 4.0? — Эмпирически: 0–3 info, 4–6 warn (reject), 7–10 critical.
**76.** Per-tenant threshold? — Да, через config.
**77.** Вес правила vs LLM? — Не комбинируем; оба → vulnerability со своим risk → MAX.
**78.** Что отдаём в audit_log? — Полный список findings, не только MAX.
**79.** Risk 3.9 — approved? — Да; UI помечает «на грани», LLM-судья объясняет.
**80.** Финальный verdict? — `AuditResult(overall_risk_score, approved, vulnerabilities, summary)`.

## FP / FN (81–90)
**81.** FP? — Аудитор флагит корректный SQL.
**82.** FN? — Аудитор пропускает уязвимый.
**83.** Цена FP? — Лишняя итерация / отказ.
**84.** Цена FN? — Безопасностный инцидент — дороже.
**85.** Стратегия? — Допускаем FP > FN; threshold 4.0 — консервативный.
**86.** Как меряем? — Confusion matrix на размеченном датасете.
**87.** Источники FP? — Sensitive FP (имя похоже на PII), LLM-судья (галлюцинирует уязвимости).
**88.** Источники FN? — Обфускация (regex пропускает), редкие классы (PLPGSQL_UNSAFE).
**89.** Как лечим? — pglast (AST), CodeBERT (странное), reflection (адресные уроки).
**90.** Где сбор FP/FN? — Из user-feedback (👍/👎 в UI) → Langfuse score.

## Объяснимость и альтернативы (91–100)
**91.** Кто пишет объяснение? — LLM-судья — естественный язык.
**92.** Что видит юзер? — vuln_class, risk_score, description, recommendation, ссылка на CWE.
**93.** Аудит-лог в Langfuse? — Целиком: SQL по итерациям, findings, scores.
**94.** Whitelist SQL? — Да, через manual override admin (логируется).
**95.** Только LLM-судья — почему нет? — Дорого, нестабильно, не объяснимо.
**96.** Только правила — почему нет? — Покрытие плохо, не ловят обфускацию.
**97.** Почему гибрид? — Дёшево (правила), точно (AST), адаптивно (LLM+RAG), explained (CWE).
**98.** Чем мы лучше SQLQueryShield? — Они только классификатор; мы — гибрид с правилами и CWE-объяснением.
**99.** Roadmap Уч.2? — pglast + 7 TODO правил + sensitive расширить + CodeBERT + RAG + LLM-судья.
**100.** Что демонстрирует Уч.2? — Пример уязвимого SQL → audit_log с расписанными findings; видны какие правила сработали + LLM-объяснение + MAX-агрегация → risk.
