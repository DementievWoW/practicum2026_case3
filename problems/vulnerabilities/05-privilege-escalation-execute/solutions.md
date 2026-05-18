# Варианты решения: Privilege Escalation через SECURITY DEFINER

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс `SECURITY\s+DEFINER` | 20 секунд | Не отличает `SET search_path` от его отсутствия; не видит чёткой структуры | ❌ |
| B | **AST `CreateFunctionStmt`: проверка `options` на `security` + наличие `SET search_path`** | Точно, покрывает все формы DDL | Не покрывает динамическое создание функции (через `EXECUTE 'CREATE FUNCTION ...'`) | ✅ ядро |
| C | B + проверка квалифицированных имён в теле | Усиливает detection; находит «двойной грех» | Сложнее, можно вынести в Phase 2 | ⚠️ опция |
| D | B + проверка `REVOKE FROM PUBLIC` в той же миграции | Защита-в-глубину | Часто `REVOKE` в отдельном файле; FP | low-priority info |
| E | `plpgsql_check` в sandbox | Глубокий анализ внутри тела функции | Не проверяет `SECURITY DEFINER` атрибут как security finding | ⚠️ комплемент |

## Эталонный fix

Три обязательных слоя:
```sql
CREATE OR REPLACE FUNCTION public.get_user_balance(uid bigint)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp                       -- ← 1. фиксация схемы
AS $$
DECLARE bal numeric;
BEGIN
    SELECT balance INTO bal FROM public.accounts WHERE ...; -- ← 2. квалифицированные имена
    RETURN bal;
END;
$$;

REVOKE ALL ON FUNCTION public.get_user_balance(bigint) FROM PUBLIC;  -- ← 3. ограничение вызова
GRANT EXECUTE ON FUNCTION public.get_user_balance(bigint) TO app_role;
```

## Что выбрали и почему

**B (AST с проверкой `SET search_path`)** как Phase 1 ядро, **C и D — в Phase 2 (LLM-судья) как дополнительные signal'ы**.

Аргументы:
- Атрибут `SECURITY DEFINER` без `SET search_path` — единственный жёстко детектируемый маркер. PG docs прямо называют его «обязательная защита».
- Квалифицированные имена и `REVOKE FROM PUBLIC` — «good practice», но без них функция всё ещё может быть безопасной (если developer знает контекст). FP-rate выше, поэтому это рекомендация судьи, а не правило Phase 1.

## Реализация

### Phase 1 — `R007-security-definer-no-search-path` (ADR-0004)

```python
class SecurityDefinerNoSearchPath(Visitor):
    def visit_CreateFunctionStmt(self, ancestors, node):
        options = {opt.defname: opt for opt in (node.options or [])}
        is_definer = (
            "security" in options
            and options["security"].arg.boolval
        )
        if not is_definer:
            return
        has_search_path = any(
            opt.defname == "set" and opt.arg.name == "search_path"
            for opt in (node.options or [])
        )
        if not has_search_path:
            yield Finding(
                rule_id="R007-security-definer-no-search-path",
                vuln_class="PRIV_ESCALATE",
                severity="high", risk_score=8,
                message="SECURITY DEFINER без SET search_path — privilege escalation через search_path hijack",
                evidence_refs=["CWE-269", "CAPEC-470", "PG-docs#sql-createfunction"],
            )
```

### Phase 1b — дополнительные warnings

- Неквалифицированные имена объектов в теле функции (`users` вместо `public.users`) → severity:medium info-finding.
- Отсутствие `REVOKE FROM PUBLIC` в той же сессии → info-level (часто FP — REVOKE в отдельном файле).

### Phase 2 — LLM-судья

RAG: PG-docs «Writing SECURITY DEFINER Functions Safely», CAPEC-470, CWE-269.

Инструкция:
1. Подтвердить уязвимость или пометить FP (обоснованные wrapper-функции для admin-доступа).
2. Если TP — рекомендация с **конкретным синтаксисом** `SET search_path = pg_catalog, pg_temp` + `REVOKE FROM PUBLIC`.
3. Проверить, нет ли цепочки `SECURITY DEFINER → ... → SECURITY DEFINER` (известное ограничение Phase 1, опциональный recall в Phase 2).

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == PRIV_ESCALATE`** + 3 legitimate `SECURITY DEFINER` с правильным `SET search_path` для FP-проверки.

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.85 |
| Precision | ≥ 0.90 |
| `overall_risk_score` после fix | 0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| Динамический `search_path` через `EXECUTE 'SET search_path = ' \|\| param` | Phase 1 не видит; Phase 2 LLM-судья по контексту тела |
| Цепочки `SECURITY DEFINER` (A зовёт B зовёт C) | Каждая функция проверяется отдельно; цепочечный анализ — вне MVP |
| `SECURITY INVOKER` (дефолт) — не флагается | Это правильное поведение |
| Расширения с `SECURITY DEFINER` функциями (`pgcrypto`, и т.п.) | Если развёрнуто в БД — наша система не флагает (это not user code), но Phase 2 может предупредить |

## Связи с ADR

- **ADR-0004** — правило `R007`.
- **ADR-0005** — `kb.postgres` (SECURITY DEFINER section).
- **ADR-0010** — PL/pgSQL бонусный путь (`R007` усиливается через `plpgsql_check`).
