"""
@file auditor.py
@brief Гибридный аудитор: каркас (тимлид) + Phase 1 правила (ЗАГЛУШКИ, роль «Тулзы»).

@details
    Каркас HybridAuditor.audit() и run_phase1() — зона ТИМЛИДА (склейка,
    реализует контракт baseline.SecurityAuditor).

    Правила Phase 1 (R001-R013) — ЗАГЛУШКИ. Сейчас работают только две
    (SELECT * и no-LIMIT) — чтобы сквозной demo-цикл сходился. Остальные —
    плейсхолдеры, возвращают []. Реальные правила (на pglast AST) пишет
    роль «Тулзы».

    Phase 2 (LLM-триаж) — через LLMClient (сейчас MockLLMClient).

    Реальные правила в git: тег `reference-impl-v1`
        git show reference-impl-v1:src/case3/nodes/auditor.py

@todo (роль «Тулзы»): R002/R003 (DML без WHERE), R005 (UNION), R006 (pg_sleep),
    R007 (SECURITY DEFINER), R011 (injection marker), R012/R013 (PL/pgSQL),
    EXPLAIN-анализ; перевести с regex на pglast.
"""

from __future__ import annotations

import re

from case3.contracts import AuditResult, Finding, SecurityAuditor
from case3.audit.sensitive import detect_column, detect_pii_in_literals
from case3.llm.client import LLMClient


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — ЗАГЛУШКИ правил (роль «Тулзы»). Каждое → list[Finding].
# ─────────────────────────────────────────────────────────────────────────────
def _rule_select_star(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА-ПРИМЕР R001 (рабочая, для demo). @todo Тулзы: pglast AST."""
    if re.search(r"select\s+\*", sql, re.I) or re.search(r"\b\w+\.\*", sql):
        return [Finding("R001-select-star", "SELECT_STAR", "medium", 5.0,
                        "SELECT * — выбираются все колонки", ["CWE-1295"])]
    return []


def _rule_no_limit(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА-ПРИМЕР R004 (рабочая, для demo). @todo Тулзы: pglast AST."""
    if not re.match(r"\s*select\b", sql, re.I):
        return []
    if re.search(r"\b(count|sum|avg|group\s+by)\b", sql, re.I) or re.search(r"\blimit\b", sql, re.I):
        return []
    return [Finding("R004-no-limit", "NO_PAGINATION", "low", 4.0,
                    "SELECT без LIMIT", ["CWE-770"])]


def _rule_sensitive_columns(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R009 — через заглушку detect_column. @todo Тулзы: полный детектор."""
    findings: list[Finding] = []
    sel = re.search(r"select\s+(.*?)\s+from\b", sql, re.I | re.S)
    if sel:
        for token in re.findall(r"\b[a-zA-Zа-яА-Я_]\w*\b", sel.group(1)):
            hit = detect_column(token)
            if hit:
                findings.append(Finding("R009-sensitive-columns", "DIRECT_SENSITIVE",
                                        hit.severity, float(hit.risk_score),
                                        f"Чувствительная колонка {token!r}", ["CWE-200"]))
    return findings


# --- ПЛЕЙСХОЛДЕРЫ (роль «Тулзы» реализует; пока возвращают []) ---
def _rule_dml_no_where(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R002/R003. @todo Тулзы: UPDATE/DELETE без WHERE + always-true."""
    return []  # TODO


def _rule_union(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R005. @todo Тулзы: probe-паттерны + системные таблицы."""
    return []  # TODO


def _rule_pg_sleep(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R006. @todo Тулзы: pg_sleep в CASE."""
    return []  # TODO


def _rule_security_definer(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R007. @todo Тулзы: SECURITY DEFINER без search_path."""
    return []  # TODO


def _rule_plpgsql_concat(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R012/R013. @todo Тулзы: EXECUTE || и format(%s)."""
    return []  # TODO


def _rule_injection_marker(sql: str) -> list[Finding]:
    """@brief ЗАГЛУШКА R011. @todo Тулзы: маркеры конкатенации ввода."""
    return []  # TODO


PHASE1_RULES = [
    _rule_select_star, _rule_no_limit, _rule_sensitive_columns,  # рабочие заглушки
    _rule_dml_no_where, _rule_union, _rule_pg_sleep,             # плейсхолдеры
    _rule_security_definer, _rule_plpgsql_concat, _rule_injection_marker,
]


def run_phase1(sql: str) -> list[Finding]:
    """@brief Каркас (тимлид): прогон всех правил Phase 1. @return list[Finding]."""
    findings: list[Finding] = []
    for rule in PHASE1_RULES:
        findings.extend(rule(sql))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Каркас гибридного аудитора (зона ТИМЛИДА) — реализует baseline.SecurityAuditor
# ─────────────────────────────────────────────────────────────────────────────
class HybridAuditor(SecurityAuditor):
    """
    @brief Phase 1 (правила-заглушки) + Phase 2 (LLM-триаж через мок).
    @param llm        LLMClient для Phase 2 (рекомендации). Опц.
    @param threshold  Порог одобрения (по умолчанию baseline = 4.0).
    """

    def __init__(self, llm: LLMClient | None = None, threshold: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        self.threshold = threshold if threshold is not None else self.RISK_THRESHOLD

    def audit(self, sql_query: str, db_schema: dict | None = None) -> AuditResult:
        findings = run_phase1(sql_query)

        recommendation = ""
        if self.llm and findings:
            resp = self.llm.chat([
                {"role": "system", "content": "Ты security-судья (auditor) PostgreSQL."},
                {"role": "user", "content":
                    f"SQL: {sql_query}\nНаходки: {[f.rule_id for f in findings]}. "
                    "Дай краткую рекомендацию."},
            ])
            recommendation = resp.text

        vulns = [f.to_vulnerability(recommendation) for f in findings]
        overall = max((v.risk_score for v in vulns), default=0.0)
        approved = overall < self.threshold

        if approved:
            summary = "Запрос одобрен: критичных уязвимостей не найдено."
        else:
            classes = sorted({v.vuln_class for v in vulns})
            summary = f"Отклонён (риск {overall:.1f} ≥ {self.threshold}): {', '.join(classes)}."

        return AuditResult(
            approved=approved,
            vulnerabilities=vulns,
            overall_risk_score=overall,
            summary=summary,
        )
