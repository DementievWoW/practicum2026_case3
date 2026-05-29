"""
@file pipeline.py
@brief Оркестратор цикла генератор→судья→reflector. Реализует baseline-контракт.

@details
    Это «сердце» системы (ADR-0002). Цикл:
      1. generator пишет SQL (с учётом reflection-уроков);
      2. auditor проверяет (Phase 1 правила + Phase 2 LLM);
      3. approved? → finalize; иначе → reflector пишет уроки → шаг 1;
      4. лимит max_iterations.

    Сейчас узлы — на моках (MockLLMClient), но цикл, лог итераций и
    reflection-память РЕАЛЬНЫЕ. Когда подключим настоящий LLM/LangGraph,
    меняется только реализация узлов — контракт baseline.run() тот же.

    На MVP это простой Python-цикл (не LangGraph) — walking skeleton.
    LangGraph + PostgresSaver добавим, когда цикл стабилизируется.
"""

from __future__ import annotations

import re
from datetime import datetime

from case3.contracts import (
    AuditResult,
    IterationLog,
    SystemResult,
    SQLSecuritySystem,
    Vulnerability,
)
from case3.nodes.auditor import HybridAuditor
from case3.nodes.generator import LLMGenerator, _SQL_KEYWORDS
from case3.nodes.reflector import Reflector


_SQL_KW_RE = re.compile(r"\b(" + "|".join(_SQL_KEYWORDS) + r")\b", re.I)


def _has_sql_keyword(text: str) -> bool:
    """@brief Есть ли в тексте признак SQL-стейтмента (SELECT/WITH/...)."""
    return bool(_SQL_KW_RE.search(text or ""))


class SQLSecurityPipeline(SQLSecuritySystem):
    """
    @brief Реализация цикла поверх baseline.SQLSecuritySystem.
    @param generator  LLMGenerator.
    @param auditor    HybridAuditor.
    @param reflector  Reflector (in-context reflection-loop).
    @param max_iterations  Лимит (по умолчанию из baseline = 5).
    """

    def __init__(self, generator, auditor, reflector=None, max_iterations=None):
        super().__init__(
            generator=generator,
            auditor=auditor,
            max_iterations=max_iterations or self.DEFAULT_MAX_ITERATIONS,
        )
        self.reflector = reflector or Reflector()

    def run(self, task_description: str, on_event=None) -> SystemResult:
        """@brief Цикл генератор→судья→reflector.

        @param on_event Опц. callback(dict) — вызывается на ключевых шагах
                        пайплайна. Используется SSE-endpoint'ом для
                        live-streaming мыслей в UI. Если None — поведение
                        как раньше.
        """
        emit = on_event or (lambda ev: None)
        sql_history: list[str] = []
        iterations_log: list[IterationLog] = []
        reflection = []  # list[Lesson] — растёт между итерациями
        last_sql = ""
        last_audit = None

        for it in range(1, self.max_iterations + 1):
            emit({"event": "iter_start", "iteration": it})

            # 1. Генерация (с reflection-памятью)
            emit({"event": "generator_start", "iteration": it,
                  "lessons": [str(l) for l in reflection]})
            sql = self.generator.generate(
                task_description=task_description,
                sql_history=sql_history,
                audit_feedback=last_audit,
                iteration=it,
                reflection=reflection,
            )
            sql_history.append(sql)
            emit({"event": "generator_done", "iteration": it, "sql": sql})

            # 1b. Sanity-check: модель вернула вообще что-то похожее на SQL?
            #     Если нет (вернула приветствие / прозу / мета-ответ) — нет смысла
            #     гонять аудит и тратить итерации; раньше выходим с понятной причиной.
            if not _has_sql_keyword(sql):
                emit({"event": "non_sql_output", "iteration": it,
                      "model_text": (sql or "")[:500]})
                v = Vulnerability(
                    vuln_class="NOT_A_QUERY",
                    risk_score=10.0,
                    description=(
                        "Модель не вернула SQL — ответ похож на свободный текст. "
                        "Из этого запроса нельзя построить SQL, нужно больше контекста "
                        "или переформулировать задачу."
                    ),
                    recommendation=(
                        "Опиши конкретно, какие данные нужны: «покажи …», «сколько …», "
                        "«топ-N … по …». Укажи таблицу/сущность, если знаешь."
                    ),
                )
                fake_audit = AuditResult(
                    approved=False,
                    overall_risk_score=10.0,
                    vulnerabilities=[v],
                    summary="Не похоже на SQL-задачу — нужно больше контекста.",
                )
                iterations_log.append(IterationLog(
                    timestamp=datetime.now(),
                    iteration=it,
                    sql_query=sql,
                    audit_result=fake_audit,
                    revision_notes="ранний выход: не-SQL ответ модели",
                ))
                last_sql, last_audit = sql, fake_audit
                break

            # 2. Аудит
            emit({"event": "auditor_start", "iteration": it})
            audit = self.auditor.audit(sql)
            last_sql, last_audit = sql, audit
            emit({"event": "auditor_done", "iteration": it,
                  "approved": audit.approved,
                  "risk": audit.overall_risk_score,
                  "vulnerabilities": [
                      {"vuln_class": v.vuln_class, "risk_score": v.risk_score,
                       "description": v.description}
                      for v in audit.vulnerabilities
                  ]})

            # 3. Лог итерации
            revision = ""
            if reflection:
                revision = "Учтены уроки: " + ", ".join(l.rule_id for l in reflection)
            iterations_log.append(IterationLog(
                timestamp=datetime.now(),
                iteration=it,
                sql_query=sql,
                audit_result=audit,
                revision_notes=revision,
            ))

            # 4. Одобрено? → выходим
            if audit.approved:
                break

            # 5. Reflection — формируем уроки на следующую итерацию
            emit({"event": "reflector_start", "iteration": it})
            reflection = self.reflector.reflect(audit, reflection)
            emit({"event": "reflector_done", "iteration": it,
                  "lessons": [str(l) for l in reflection]})

        # Сборка человекочитаемого лога
        audit_log = self._render_log(iterations_log)

        non_sql_exit = any(
            v.vuln_class == "NOT_A_QUERY"
            for il in iterations_log
            for v in il.audit_result.vulnerabilities
        )
        return SystemResult(
            final_sql=last_sql,
            approved=last_audit.approved if last_audit else False,
            iterations_used=len(iterations_log),
            iterations_log=iterations_log,
            audit_log=audit_log,
            metadata={
                "risk_trajectory": [il.audit_result.overall_risk_score for il in iterations_log],
                "reflection_final": [str(l) for l in reflection],
                "early_exit": "non_sql_output" if non_sql_exit else None,
            },
        )

    @staticmethod
    def _render_log(iterations_log: list[IterationLog]) -> str:
        """@brief Человекочитаемый аудит-лог (требование ТЗ — прозрачность)."""
        lines = ["=== AUDIT LOG ==="]
        for il in iterations_log:
            a = il.audit_result
            lines.append(f"\n--- Итерация {il.iteration} ---")
            lines.append(f"SQL: {il.sql_query}")
            lines.append(f"Риск: {a.overall_risk_score:.1f}  Одобрено: {a.approved}")
            if il.revision_notes:
                lines.append(f"Правки: {il.revision_notes}")
            for v in a.vulnerabilities:
                lines.append(f"  ⚠ {v.vuln_class} ({v.risk_score:.1f}): {v.description}")
                if v.recommendation:
                    lines.append(f"      ↳ фикс: {v.recommendation}")
            lines.append(f"Вердикт: {a.summary}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Удобный entrypoint (как в baseline.run_sql_security_pipeline)
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(
    task_description: str,
    *,
    llm=None,
    db_schema: dict | None = None,
    max_iterations: int | None = None,
    on_event=None,
) -> SystemResult:
    """
    @brief Собирает узлы (на моках по умолчанию) и прогоняет цикл.
    @param llm  LLMClient; если None — MockLLMClient(scenario="evolve").
    @param on_event Опц. callback для SSE-streaming (см. SQLSecurityPipeline.run).
    @return SystemResult по контракту baseline.
    """
    if llm is None:
        from case3.llm.factory import make_llm
        llm = make_llm()   # OpenAI-compat / Colab / mock — по .env

    # Schema linking (ADR-0003): если схему не передали — выбираем релевантные
    # таблицы из 60 под задачу (иначе всю схему в промпт не вложить).
    if db_schema is None:
        try:
            from case3.schema.linker import SchemaLinker
            # компактно: top-4 таблицы, до 12 колонок, без FK-взрыва (бюджет промпта/VRAM)
            db_schema = SchemaLinker().link_text(task_description, k=4, max_cols=12,
                                                 fk_closure=False)
        except Exception:
            db_schema = None

    # Асимметричный few-shot store (ADR-0012): positives → генератору, negatives → судье.
    store = None
    try:
        from case3.retrieval import FewShotStore
        store = FewShotStore()  # train-сплит data/dataset_v1.jsonl
        if not (store.positives or store.negatives):
            store = None
    except Exception:
        store = None

    generator = LLMGenerator(llm=llm, db_schema=db_schema, store=store)
    auditor = HybridAuditor(llm=llm, store=store)
    reflector = Reflector()
    pipeline = SQLSecurityPipeline(generator, auditor, reflector, max_iterations)
    return pipeline.run(task_description, on_event=on_event)
