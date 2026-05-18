# Варианты решения: LLM-as-judge ненадёжен

## Альтернативные подходы

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | **LLM-as-judge only** (sql + промпт «найди SQLi») | Гибкий, понимает контекст | 100% evasion на adversarial-payloads; галлюцинирует CWE-ID; inconsistent | ❌ |
| B | **Статика-only** (AST + regex + EXPLAIN) | Детерминированно, аудируемо | Не покрывает «логические» уязвимости (контекст-зависимые) | ❌ |
| C | **Гибрид: статика → findings → LLM-триаж + RAG** | Покрывает оба слоя; LLM работает с уликами в промпте | Дороже в инженерии | ✅ выбрали |
| D | Multi-judge consensus (3 LLM голосуют) | Снижает inconsistency | × 3 латентность; вне 40-сек бюджета | для v2 |
| E | **RobustJudge** для evaluation устойчивости судьи | Систематическое тестирование 15 attacks | Только evaluation, не runtime защита | в нашем regression-тесте |
| F | **RAVEN/ProveRAG/AgentAuditor** как альтернативные RAG-фреймворки | SOTA на security tasks | Сложно интегрировать в LangGraph; своя архитектура | для v2 |

## Что выбрали и почему

**C — гибрид «AST → LLM-триаж с RAG»** (ADR-0004). Это единственный подход, дающий обе характеристики:
- **Низкий FN** на классических payloads (статика).
- **Низкий FP** на легитимных запросах (LLM-триаж с контекстом).
- **Верифицируемые ссылки** на стандарты (RAG → `evidence.cwe_id`).

Логика «LLM как триажер findings, а не как первичный детектор» подтверждена:
- IEEE 2025: одиночные SAST с 100% evasion → нужен LLM поверх.
- Trend Micro: LLM-судья работает, когда улика в промпте → даём ему findings.
- Ментор: «LLM-as-judge сомнителен» → не полагаемся на голую LLM.

## Реализация (ADR-0004)

### Phase 1 — детерминированный слой
- **11 правил** pglast Visitor (`R001`...`R011`).
- **6 PL/pgSQL правил** через `pglast.parse_plpgsql` (ADR-0010).
- **EXPLAIN cost-checks** через sandbox Postgres.
- Возвращает `list[Finding(rule_id, vuln_class, severity, risk_score, location, snippet, evidence_refs)]`.
- **Обязательный нижний слой**: даже если LLM упадёт, мы что-то покажем.

### Phase 2 — LLM-судья **поверх findings**
LLM **не делает обнаружение с нуля**, а:
1. **Триажирует findings** — подтверждает или помечает как FP.
2. **Выставляет финальный `risk_score`** на каждый подтверждённый finding.
3. **Формирует `description` + `recommendation`** на естественном языке.
4. **Ищет дополнительные уязвимости**, которые правила в принципе не могут поймать (логика, контекст).

### RAG в Phase 2 (ADR-0005)
LLM получает top-5 чанков из `kb.cwe` ∪ `kb.capec` ∪ `kb.owasp` по `vuln_class`. Это даёт:
- **Верифицируемые ссылки** в `evidence.cwe_id`, `evidence.capec_id`.
- **Снижение галлюцинаций** ID.

### Антигаллюцинационный валидатор
Регексом `CWE-\d+` / `CAPEC-\d+` извлекаем ID из ответа judge. Если нет в `kb.cwe` / `kb.capec` → заменяем `evidence` на пустое + `metadata.unverified = true`.

### Structured output
`response_format = {"type": "json_object"}` (OpenAI-совместимый mode у DeepInfra). Fallback — Pydantic-валидатор + retry × 2.

### `risk_score = MAX`, не SUM
ADR-0004 §6: один критический finding не должен размываться десятком info-уровневых. Документируем; переключение на SUM — одна строка.

## Что измеряем

| Метрика | Цель | Источник истины |
|---|---|---|
| Recall судьи по каждому `vuln_class` | ≥ 0.80 на iter1, ≥ 0.90 на iterAny | eval-set (ADR-0006) |
| Precision судьи (нет FP на безопасных) | ≥ 0.85 | eval-set |
| Кол-во unverified evidence | ≤ 5% | антигаллюцинационный валидатор |
| Consistency (3 прогона дают одинаковый `vuln_class`) | ≥ 0.95 | отдельный test-run |
| Recall на adversarial payloads (sqlmap, PortSwigger) | ≥ 0.70 | `kb.payloads` regression set |

## Что может пойти не так

| Проблема | Митигация |
|---|---|
| Adversarial payloads (GSQLi и т.п.) обходят Phase 1 | Документируем как известное ограничение; в roadmap — RobustJudge-стиль regression |
| LLM возвращает невалидный JSON | retry × 2; если третий раз — degraded mode (findings-only без LLM-объяснений) |
| RAG не подтянул релевантный чанк (cosine miss) | `evidence: {}` + `unverified: true`; на UI помечаем |
| Backdoor-атаки на LLM (ToxicSQL) | Regression-тесты на стабильных payloads каждый билд |
| Phase 2 «перетриажирует» все findings как FP | Калибровка промпта; A/B-тест по Recall |
| Дорогой latency на retry × 2 | Token budget cap, graceful degradation |

## Связи с ADR

- **ADR-0004** — гибридный аудитор (главный design doc).
- **ADR-0005** — RAG (антигаллюцинационная защита).
- **ADR-0010** — расширение для PL/pgSQL.
- **ADR-0007** — измерение Recall/Precision.
