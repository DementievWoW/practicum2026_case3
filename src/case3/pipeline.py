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

from datetime import datetime

from case3.contracts import (
    IterationLog,
    SystemResult,
    SQLSecuritySystem,
)
from case3.nodes.auditor import HybridAuditor
from case3.nodes.generator import LLMGenerator
from case3.nodes.reflector import Reflector


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

    def run(self, task_description: str) -> SystemResult:
        sql_history: list[str] = []
        iterations_log: list[IterationLog] = []
        reflection = []  # list[Lesson] — растёт между итерациями
        last_sql = ""
        last_audit = None

        for it in range(1, self.max_iterations + 1):
            # 1. Генерация (с reflection-памятью)
            sql = self.generator.generate(
                task_description=task_description,
                sql_history=sql_history,
                audit_feedback=last_audit,
                iteration=it,
                reflection=reflection,
            )
            sql_history.append(sql)

            # 2. Аудит
            audit = self.auditor.audit(sql)
            last_sql, last_audit = sql, audit

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
            reflection = self.reflector.reflect(audit, reflection)

        # Сборка человекочитаемого лога
        audit_log = self._render_log(iterations_log)

        return SystemResult(
            final_sql=last_sql,
            approved=last_audit.approved if last_audit else False,
            iterations_used=len(iterations_log),
            iterations_log=iterations_log,
            audit_log=audit_log,
            metadata={
                "risk_trajectory": [il.audit_result.overall_risk_score for il in iterations_log],
                "reflection_final": [str(l) for l in reflection],
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
) -> SystemResult:
    """
    @brief Собирает узлы (на моках по умолчанию) и прогоняет цикл.
    @param llm  LLMClient; если None — MockLLMClient(scenario="evolve").
    @return SystemResult по контракту baseline.
    """
    if llm is None:
        from case3.llm.mock import MockLLMClient
        llm = MockLLMClient(scenario="evolve")

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
    return pipeline.run(task_description)
