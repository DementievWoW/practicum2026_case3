"""
@file reflector.py
@brief Reflector — превращает findings судьи в уроки (in-context reflection-loop).

@details
    После провального аудита берёт vulnerabilities и формирует list[Lesson].
    Уроки кладутся в промпт генератора на следующей итерации — генератор
    не повторяет ошибку (ADR-0002, Reflexion-паттерн, без обучения весов).

    Сейчас — детерминированный lookup по vuln_class (быстро, надёжно для MVP).
    В проде reflector может быть LLM (Qwen-7B) или encoder-decoder (FLAN-T5)
    для парафраза — контракт reflect() тот же.

    Дедуп по rule_id, окно последних N уроков (защита от зашумления).
"""

from __future__ import annotations

from case3.contracts import AuditResult, Lesson


# Шаблоны уроков по классам уязвимостей (детерминированный reflector).
_LESSON_TEMPLATES: dict[str, Lesson] = {
    "SELECT_STAR": Lesson(
        "SELECT_STAR", "Не используй SELECT *, перечисляй нужные колонки явно.",
        "SELECT * FROM credit_contract", "SELECT id, status FROM credit_contract"),
    "DML_NO_WHERE": Lesson(
        "DML_NO_WHERE", "UPDATE/DELETE всегда требует WHERE с predicate по PK.",
        "UPDATE credit_contract SET status=0",
        "UPDATE credit_contract SET status=0 WHERE id=$1"),
    "NO_PAGINATION": Lesson(
        "NO_PAGINATION", "Любой SELECT строк должен иметь LIMIT.",
        "SELECT id FROM credit_contract", "SELECT id FROM credit_contract LIMIT 100"),
    "DIRECT_SENSITIVE": Lesson(
        "DIRECT_SENSITIVE", "Чувствительные поля маскируй или агрегируй, не выбирай сырыми.",
        "SELECT passport FROM sim_client",
        "SELECT LEFT(passport,4)||'***' FROM sim_client"),
    "SQL_INJ_CLASSIC": Lesson(
        "SQL_INJ_CLASSIC", "Не склеивай ввод в SQL, используй параметры $1.",
        "WHERE x = '\"+v+\"'", "WHERE x = $1"),
    "SQL_INJ_UNION": Lesson(
        "SQL_INJ_UNION", "Параметризуй ввод; не давай дотянуться UNION до чужих таблиц.",
        "... UNION SELECT ... FROM users", "WHERE name LIKE $1"),
    "SQL_INJ_TIME": Lesson(
        "SQL_INJ_TIME", "Параметризуй; не допускай pg_sleep из пользовательского ввода.",
        "OR pg_sleep(5)", "WHERE id = $1"),
    "PRIV_ESCALATE": Lesson(
        "PRIV_ESCALATE", "SECURITY DEFINER требует SET search_path и квалифицированных имён.",
        "SECURITY DEFINER AS $$ ... users ... $$",
        "SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$ ... public.users ... $$"),
    "PLPGSQL_UNSAFE": Lesson(
        "PLPGSQL_UNSAFE", "В EXECUTE используй USING/format(%L), не конкатенацию ||.",
        "EXECUTE '...' || v", "EXECUTE '... $1' USING v"),
    "PARSE_ERROR": Lesson(
        "PARSE_ERROR",
        "SQL не парсится Postgres'ом. Проверь порядок клауз "
        "(WHERE → GROUP BY → HAVING → ORDER BY → LIMIT — именно в этом порядке), "
        "скобки и кавычки. Без LIMIT в конце ORDER BY работает; с LIMIT — ORDER BY обязан стоять ПЕРЕД LIMIT.",
        "SELECT id FROM t WHERE x=1 LIMIT 1 ORDER BY id",
        "SELECT id FROM t WHERE x=1 ORDER BY id LIMIT 1"),
    "SCHEMA_HALLUCINATION": Lesson(
        "SCHEMA_HALLUCINATION",
        "Не выдумывай таблицы и колонки. Используй ТОЛЬКО те, что есть в блоке «Схема БД» выше.",
        "SELECT phantom_col FROM imaginary_table",
        "SELECT id, name FROM credit_contract  -- эта таблица есть в схеме"),
    "SCHEMA_INTROSPECT": Lesson(
        "SCHEMA_INTROSPECT",
        "Не обращайся к системным каталогам (pg_catalog/information_schema/pg_authid/pg_user) — "
        "это реверс-инжиниринг схемы, аудитор отклонит.",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT id, name FROM credit_contract  -- бизнес-таблица из схемы"),
}


def _fallback_lesson(v) -> Lesson:
    """@brief Generic-урок, если для vuln_class нет шаблона — берём description/recommendation как есть."""
    return Lesson(
        v.vuln_class,
        v.description or f"Аудитор отметил {v.vuln_class}.",
        "(см. предыдущий запрос)",
        (v.recommendation or "переформулируй так, чтобы избежать этого класса"),
    )


class Reflector:
    """
    @brief Формирует уроки из аудита.
    @param window  Сколько последних уроков держать (дедуп по rule_id).
    """

    def __init__(self, window: int = 5):
        self.window = window

    def reflect(self, audit: AuditResult, prev: list[Lesson] | None = None) -> list[Lesson]:
        """
        @brief AuditResult → обновлённый список уроков.
        @param audit  Результат провального аудита.
        @param prev   Ранее накопленные уроки.
        @return Обновлённый list[Lesson] (дедуп + окно).
        """
        prev = prev or []
        new = []
        for v in audit.vulnerabilities:
            tmpl = _LESSON_TEMPLATES.get(v.vuln_class)
            new.append(tmpl if tmpl else _fallback_lesson(v))
        # дедуп по rule_id (последний выигрывает), окно последних N
        combined: dict[str, Lesson] = {}
        for l in prev + new:
            combined[l.rule_id] = l
        return list(combined.values())[-self.window:]
