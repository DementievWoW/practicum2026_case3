"""
@file knowledge.py
@brief RAG #2 — база знаний судьи (CWE/CAPEC/OWASP + объяснение + фикс).

@details
    Лёгкий knowledge-RAG для Phase 2 (ADR-0005, минимальная версия без Qdrant):
    по найденному vuln_class достаём верифицируемые ссылки (CWE/CAPEC/OWASP),
    краткое «почему опасно» и «как чинить». Это закрывает требование
    «прозрачность» — судья ссылается на стандарт, а не выдумывает (no-hallucination).

    Контракт ретрива тот же, что у векторного RAG в проде:
        retrieve(classes) -> list[Knowledge]
    → позже подменяется на Qdrant + e5 (CWE/CAPEC/OWASP/PG-docs), узлы не меняются.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Knowledge:
    """@brief Запись знания по классу уязвимости (источник evidence + рекомендации)."""
    vuln_class: str
    title: str
    cwe: list[str] = field(default_factory=list)
    capec: list[str] = field(default_factory=list)
    owasp: str = ""
    why: str = ""
    fix: str = ""

    def evidence(self) -> list[str]:
        refs = list(self.cwe) + list(self.capec)
        if self.owasp:
            refs.append(self.owasp)
        return refs


# ── База знаний по 10 классам (placeholder под реальный Qdrant-RAG ADR-0005) ──
KNOWLEDGE: dict[str, Knowledge] = {
    "SQL_INJ_CLASSIC": Knowledge(
        "SQL_INJ_CLASSIC", "SQL-инъекция (классическая)",
        ["CWE-89"], ["CAPEC-66"], "OWASP A03:2021-Injection",
        "Пользовательский ввод склеивается в текст запроса — можно изменить логику SQL.",
        "Только параметризованные запросы ($1) / prepared statements; не конкатенировать ввод.",
    ),
    "SQL_INJ_UNION": Knowledge(
        "SQL_INJ_UNION", "Union-based инъекция",
        ["CWE-89"], ["CAPEC-66"], "OWASP A03:2021-Injection",
        "UNION SELECT дотягивается до системных/чужих таблиц и крадёт данные.",
        "Параметризация + белый список колонок; запретить UNION в пользовательском вводе.",
    ),
    "SQL_INJ_TIME": Knowledge(
        "SQL_INJ_TIME", "Time-based blind инъекция",
        ["CWE-89"], ["CAPEC-7"], "OWASP A03:2021-Injection",
        "pg_sleep() в условии даёт blind-эксфильтрацию по времени отклика.",
        "Параметризация + statement_timeout; запретить вызовы pg_sleep из ввода.",
    ),
    "DML_NO_WHERE": Knowledge(
        "DML_NO_WHERE", "UPDATE/DELETE без WHERE",
        ["CWE-1284"], [], "OWASP A04:2021-Insecure Design",
        "Без WHERE операция затрагивает ВСЕ строки таблицы — массовая порча данных.",
        "Обязательный WHERE по первичному ключу; выполнять в транзакции, проверять rowcount.",
    ),
    "PRIV_ESCALATE": Knowledge(
        "PRIV_ESCALATE", "Privilege escalation (SECURITY DEFINER)",
        ["CWE-269"], ["CAPEC-470"], "OWASP A01:2021-Broken Access Control",
        "SECURITY DEFINER без фиксированного search_path → подмена объектов (hijack).",
        "SET search_path = pg_catalog, pg_temp; квалифицировать имена схемой (public.*).",
    ),
    "PLPGSQL_UNSAFE": Knowledge(
        "PLPGSQL_UNSAFE", "Небезопасный EXECUTE в PL/pgSQL",
        ["CWE-89"], ["CAPEC-66"], "OWASP A03:2021-Injection",
        "EXECUTE с конкатенацией || или format(%s) = инъекция внутри функции.",
        "EXECUTE ... USING $1; для идентификаторов format(%I), для литералов %L.",
    ),
    "DIRECT_SENSITIVE": Knowledge(
        "DIRECT_SENSITIVE", "Прямой доступ к чувствительным данным",
        ["CWE-200", "CWE-359"], [], "OWASP A01:2021-Broken Access Control",
        "Выгрузка PII/коммерческой тайны (паспорт, карта, суммы) нарушает 152-ФЗ/PCI DSS.",
        "Маскирование/агрегация, минимизация полей; CVV/пароли не выдавать никогда.",
    ),
    "SELECT_STAR": Knowledge(
        "SELECT_STAR", "Избыточный SELECT *",
        ["CWE-1295"], [], "OWASP A01:2021-Broken Access Control",
        "SELECT * тащит все колонки, включая потенциально чувствительные и внутренние.",
        "Перечислять только нужные колонки явно.",
    ),
    "NO_PAGINATION": Knowledge(
        "NO_PAGINATION", "Отсутствие пагинации / LIMIT",
        ["CWE-770"], [], "OWASP A04:2021-Insecure Design",
        "Безусловная выгрузка может вернуть миллионы строк — отказ в обслуживании.",
        "Добавить LIMIT/OFFSET или keyset-пагинацию; ограничить размер выборки.",
    ),
    "SLOW_QUERY": Knowledge(
        "SLOW_QUERY", "Тяжёлый план запроса",
        ["CWE-1176"], [], "OWASP A04:2021-Insecure Design",
        "Декартово произведение / leading-wildcard / функция на колонке убивают индексы.",
        "JOIN ... ON вместо запятой; sargable-предикаты; keyset вместо большого OFFSET.",
    ),
    "DDL_DESTRUCTIVE": Knowledge(
        "DDL_DESTRUCTIVE", "Деструктивный DDL (DROP/TRUNCATE)",
        ["CWE-1284"], ["CAPEC-176"], "OWASP A04:2021-Insecure Design",
        "DROP TABLE/SCHEMA/DATABASE и TRUNCATE безвозвратно удаляют данные.",
        "NL→SQL не должен генерировать DDL. Только в migration-инструментах с code review.",
    ),
    "DCL_LEAK": Knowledge(
        "DCL_LEAK", "Опасный DCL (GRANT/REVOKE)",
        ["CWE-732", "CWE-269"], [], "OWASP A01:2021-Broken Access Control",
        "GRANT ALL TO PUBLIC / REVOKE FROM owner — обход модели доступа.",
        "DCL — задача администратора БД; NL→SQL пользователю это не делает.",
    ),
    "SCHEMA_INTROSPECT": Knowledge(
        "SCHEMA_INTROSPECT", "Доступ к системным каталогам",
        ["CWE-200"], ["CAPEC-545"], "OWASP A01:2021-Broken Access Control",
        "SELECT из pg_catalog/information_schema/pg_authid/pg_shadow раскрывает "
        "структуру БД, пользователей и потенциально хэши паролей.",
        "Не возвращать запросы к pg_*/information_schema из NL-интерфейса для конечных "
        "пользователей. Для админ-задач — отдельный канал и аудит.",
    ),
}


class KnowledgeBase:
    """@brief Knowledge-RAG: ретрив по vuln_class. Интерфейс под векторный RAG."""

    def lookup(self, vuln_class: str) -> Knowledge | None:
        return KNOWLEDGE.get(vuln_class)

    def retrieve(self, classes: list[str]) -> list[Knowledge]:
        """@brief Записи знаний по списку найденных классов (дедуп, порядок сохранён)."""
        out, seen = [], set()
        for vc in classes:
            if vc in seen:
                continue
            seen.add(vc)
            k = KNOWLEDGE.get(vc)
            if k:
                out.append(k)
        return out
