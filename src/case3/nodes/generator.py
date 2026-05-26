"""
@file generator.py
@brief Генератор SQL (реализует baseline.SQLGenerator).

@details
    Строит промпт (схема + reflection-уроки) и вызывает LLM через LLMClient.
    Сейчас LLM — MockLLMClient, в проде — реальный (Qwen). Контракт один.

    Reflection-уроки (in-context, ADR-0002) кладутся в системный промпт:
    генератор «видит» прошлые ошибки и не повторяет их — без обучения весов.
"""

from __future__ import annotations

import re

from case3.contracts import AuditResult, Lesson, SQLGenerator
from case3.llm.client import LLMClient


def _strip_sql_fence(text: str) -> str:
    """@brief Достаёт SQL из ```sql ... ``` (реальные LLM часто оборачивают в фенс)."""
    m = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


class LLMGenerator(SQLGenerator):
    """
    @brief Генератор поверх LLMClient.
    @param llm        Клиент LLM (mock или реальный).
    @param db_schema  Машиночитаемая схема (для промпта). Опц.
    @param store      Асимметричный few-shot store (ADR-0012). Генератору отдаём
                      ТОЛЬКО positives (безопасные эталоны «как надо»). Опц.
    @param k_shots    Сколько few-shot примеров подмешивать.
    """

    def __init__(self, llm: LLMClient, db_schema: dict | None = None,
                 store=None, k_shots: int = 3, calibration_hints: bool = True, **kwargs):
        super().__init__(db_schema=db_schema, **kwargs)
        self.llm = llm
        self.store = store
        self.k_shots = k_shots
        self.calibration_hints = calibration_hints

    def _schema_block(self) -> str:
        """@brief Компактное описание схемы для промпта (строка / dict / Table-объекты)."""
        schema = getattr(self, "db_schema", None)
        if not schema:
            return ""
        if isinstance(schema, str):
            return "\n\n### Схема БД:\n" + schema
        lines = ["\n\n### Схема БД (используй ТОЛЬКО эти таблицы и колонки):"]
        for tname, tinfo in schema.items():
            if hasattr(tinfo, "column_names"):                 # schema.models.Table
                cols = ", ".join(tinfo.column_names())
            elif isinstance(tinfo, dict):
                raw = tinfo.get("columns", tinfo)
                seq = raw if isinstance(raw, (list, tuple)) else list(raw.keys())
                cols = ", ".join(c["name"] if isinstance(c, dict) else str(c) for c in seq)
            elif isinstance(tinfo, (list, tuple)):
                cols = ", ".join(str(c) for c in tinfo)
            else:
                cols = str(tinfo)
            lines.append(f"- {tname}({cols})")
        return "\n".join(lines)

    def _fewshot_block(self, task_description: str) -> str:
        """@brief Блок позитивных few-shot (безопасные NL→SQL) по близости к задаче."""
        if not self.store:
            return ""
        shots = self.store.retrieve_positive(task_description, k=self.k_shots)
        if not shots:
            return ""
        lines = ["\n\n### Примеры безопасных запросов (ориентир «как надо»):"]
        for ex in shots:
            lines.append(f"-- {ex.nl}\n{ex.sql}")
        return "\n".join(lines)

    # ── Negative-калибровка: компактный список того, что аудитор откинет.
    # Каждая строка соответствует регексу Phase-1 (R001..R013) в audit/auditor.py.
    # Отдаём генератору ДО первой попытки → не приходится править на ретрае.
    _CALIBRATION_HINTS = (
        "\n\n### Запрещённые паттерны (аудитор отклонит — НЕ используй):\n"
        "- R001 SELECT * — перечисляй колонки явно (`SELECT id, name, ...`).\n"
        "- R002/R003 UPDATE/DELETE без WHERE (или WHERE 1=1) — массовая порча.\n"
        "- R004 SELECT без LIMIT И без WHERE — это безусловный дамп (DoS).\n"
        "- R005 UNION SELECT NULL,... и UNION к pg_catalog / information_schema.\n"
        "- R006 pg_sleep() — time-based blind injection.\n"
        "- R007 SECURITY DEFINER без SET search_path = pg_catalog, pg_temp.\n"
        "- R008 декартово (запятая в FROM без JOIN..ON), LIKE '%...', функция от "
        "колонки в WHERE (lower/upper/substr), OFFSET ≥ 1000.\n"
        "- R009 чувствительные колонки (passport/snils/inn/phone/email/check_account/"
        "card/cvv) сырыми — только агрегаты (count/sum) или маскирование "
        "`LEFT(col,4)||'***'` / `digest(col,'sha256')`.\n"
        "- R011 конкатенация ввода в SQL-литералы — параметризуй ($1).\n"
        "- R012/R013 EXECUTE с `||` или `format('...%s', var)` — используй "
        "`EXECUTE '...' USING $1` / `%L` для литералов, `%I` для идентификаторов.\n"
        "- R014 DROP / TRUNCATE — NL→SQL не генерирует деструктивный DDL.\n"
        "- R015 GRANT / REVOKE — NL→SQL не управляет доступом (это задача DBA).\n"
        "- R016 SELECT из pg_catalog / information_schema / pg_authid / pg_shadow / "
        "pg_user — не обращайся к системным каталогам.\n"
    )

    def _security_hints_block(self) -> str:
        return self._CALIBRATION_HINTS if self.calibration_hints else ""

    def _system_prompt(self, reflection: list[Lesson], task_description: str) -> str:
        base = (
            "Ты — генератор PostgreSQL-запросов по описанию задачи и схеме БД. "
            "Возвращай только безопасный SQL в блоке ```sql.\n"
            "Правила: при TOP-N / «первые N» / LIMIT ВСЕГДА добавляй ORDER BY со "
            "стабильным tie-break (обычно `id ASC`; для запросов с GROUP BY tie-break — "
            "по grouped-колонке типа name, НЕ по id). Иначе результат недетерминирован. "
            "Для join используй FK-связи из комментариев схемы (поля `-- FK:tbl.col`)."
        )
        base += self._security_hints_block()
        base += self._schema_block()
        base += self._fewshot_block(task_description)
        if reflection:
            lessons = "\n".join(f"- {l}" for l in reflection)
            base += (
                "\n\n### Reflection memory (уроки прошлых попыток, НЕ повторяй):\n"
                + lessons
            )
        return base

    def _retry_block(self, sql_history: list[str] | None,
                     audit_feedback: AuditResult | None) -> str:
        """@brief Конкретная обратная связь ретрая: отклонённый SQL + найденные проблемы.

        Без неё модель не «видит», что именно отклонено, и повторяет ту же ошибку
        (обобщённых уроков в system недостаточно под явный запрос пользователя)."""
        if not audit_feedback or audit_feedback.approved:
            return ""
        last = (sql_history or [""])[-1]
        probs = "\n".join(f"  - {v.vuln_class}: {v.description}"
                          for v in audit_feedback.vulnerabilities)
        return (
            "\n\nВАЖНО: твой предыдущий запрос ОТКЛОНЁН аудитором безопасности:\n"
            f"{last}\n"
            "Проблемы:\n" + probs +
            "\n\nИсправь ИМЕННО эти проблемы. Чувствительные поля (ИНН, телефон, email, "
            "паспорт, номер счёта) НЕ выбирай сырыми — маскируй (например LEFT(col,4)||'***') "
            "или агрегируй (count/sum). Любой SELECT строк обязан иметь LIMIT."
        )

    def generate(
        self,
        task_description: str,
        sql_history: list[str] | None = None,
        audit_feedback: AuditResult | None = None,
        iteration: int = 1,
        reflection: list[Lesson] | None = None,
    ) -> str:
        """
        @brief NL-задача (+ positive few-shot + reflection + обратная связь аудита) → SQL.
        @param reflection      Накопленные уроки (in-context reflection-loop).
        @param audit_feedback  Результат прошлого аудита — для конкретной правки.
        @return SQL-строка.
        """
        user = task_description + self._retry_block(sql_history, audit_feedback)
        messages = [
            {"role": "system", "content": self._system_prompt(reflection or [], task_description)},
            {"role": "user", "content": user},
        ]
        resp = self.llm.chat(messages, temperature=0.3)
        return _strip_sql_fence(resp.text)
