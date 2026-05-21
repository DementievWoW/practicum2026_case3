"""
@file auditor.py
@brief Гибридный аудитор: Phase 1 (детерминированные правила) + Phase 2 (LLM-триаж).

@details
    Реализует контракт baseline.SecurityAuditor (ADR-0004).
      - Phase 1 — РЕАЛЬНЫЕ правила (regex, не мок): R001-R012. Дают list[Finding].
      - Phase 2 — LLM-судья: триаж findings + рекомендации. Сейчас через
        MockLLMClient, в проде — реальный LLM. Phase 2 НЕ понижает риск
        (политика: фичи/LLM только подтверждают, см. ADR-0011).

    Правила перенесены из проверенных regex в simulations/. В проде Phase 1
    переходит на pglast AST (точнее regex), но контракт тот же.

    overall_risk_score = MAX по находкам (ADR-0004 §6): одна критичная
    уязвимость не размывается мелкими.
"""

from __future__ import annotations

import re

from case3.contracts import AuditResult, Finding, SecurityAuditor
from case3.audit.sensitive import detect_column, detect_pii_in_literals
from case3.llm.client import LLMClient


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — детерминированные правила. Каждая → list[Finding].
# ─────────────────────────────────────────────────────────────────────────────
def _rule_select_star(sql: str) -> list[Finding]:
    if re.search(r"select\s+\*", sql, re.I) or re.search(r"\b\w+\.\*", sql):
        if re.search(r"count\s*\(\s*\*\s*\)", sql, re.I) and not re.search(r"select\s+\*", sql, re.I):
            return []
        return [Finding("R001-select-star", "SELECT_STAR", "medium", 5.0,
                        "SELECT * — выбираются все колонки, включая возможно чувствительные",
                        ["CWE-1295"])]
    return []


def _rule_dml_no_where(sql: str) -> list[Finding]:
    is_upd = bool(re.match(r"\s*update\b", sql, re.I))
    is_del = bool(re.match(r"\s*delete\b", sql, re.I))
    if not (is_upd or is_del):
        return []
    where = re.search(r"\bwhere\b(.*?)(?:returning|;|$)", sql, re.I | re.S)
    rid = "R002-update-no-where" if is_upd else "R003-delete-no-where"
    if where is None:
        return [Finding(rid, "DML_NO_WHERE", "high", 9.0,
                        f"{'UPDATE' if is_upd else 'DELETE'} без WHERE — затрагивает все строки",
                        ["CWE-1284"])]
    wc = where.group(1).strip().rstrip(";").strip()
    if re.match(r"^\s*1\s*=\s*1\s*$", wc) or re.match(r"^\s*true\s*$", wc, re.I):
        return [Finding(rid, "DML_NO_WHERE", "high", 9.0,
                        f"WHERE {wc!r} — всегда истинно (маскировка)", ["CWE-1284"])]
    return []


def _rule_no_limit(sql: str) -> list[Finding]:
    if not re.match(r"\s*select\b", sql, re.I):
        return []
    if re.search(r"\b(count|sum|avg|min|max|group\s+by)\b", sql, re.I):
        return []
    if re.search(r"\blimit\b", sql, re.I):
        return []
    return [Finding("R004-no-limit", "NO_PAGINATION", "low", 4.0,
                    "SELECT без LIMIT — потенциальный DoS на больших таблицах", ["CWE-770"])]


def _rule_union(sql: str) -> list[Finding]:
    if not re.search(r"\bunion\b", sql, re.I):
        return []
    if re.search(r"union\s+(all\s+)?select\s+(null\s*,?\s*)+", sql, re.I):
        return [Finding("R005-union-suspicious", "SQL_INJ_UNION", "high", 8.0,
                        "UNION SELECT NULL,... — probe-паттерн", ["CWE-89", "CAPEC-66"])]
    if re.search(r"union\s+(all\s+)?select.*?\bfrom\s+(sys_object|sys_obj_type|information_schema|pg_catalog|pg_authid)",
                 sql, re.I | re.S):
        return [Finding("R005-union-suspicious", "SQL_INJ_UNION", "high", 9.0,
                        "UNION к системной/чужой таблице", ["CWE-89", "CAPEC-66"])]
    return []


def _rule_pg_sleep(sql: str) -> list[Finding]:
    if re.search(r"\bpg_sleep\w*\s*\(", sql, re.I):
        is_case = bool(re.search(r"case\s+when.*?pg_sleep", sql, re.I | re.S))
        return [Finding("R006-pg-sleep", "SQL_INJ_TIME", "high", 9.0 if is_case else 8.0,
                        "pg_sleep() — индикатор time-based blind injection", ["CWE-89", "CAPEC-7"])]
    return []


def _rule_security_definer(sql: str) -> list[Finding]:
    if re.search(r"security\s+definer", sql, re.I) and not re.search(r"set\s+search_path", sql, re.I):
        return [Finding("R007-security-definer-no-search-path", "PRIV_ESCALATE", "high", 8.0,
                        "SECURITY DEFINER без SET search_path — privilege escalation",
                        ["CWE-269", "CAPEC-470"])]
    return []


def _rule_plpgsql_concat(sql: str) -> list[Finding]:
    if re.search(r"execute\s+['\"].*?\|\|", sql, re.I | re.S):
        return [Finding("R012-plpgsql-execute-concat", "PLPGSQL_UNSAFE", "high", 8.0,
                        "EXECUTE с конкатенацией || — SQL injection в PL/pgSQL", ["CWE-89", "CAPEC-66"])]
    if re.search(r"execute\s+format\s*\(\s*['\"].*?%s", sql, re.I | re.S):
        return [Finding("R013-plpgsql-format-percent-s", "PLPGSQL_UNSAFE", "high", 7.0,
                        "format() с %s — эквивалент конкатенации, нужен %L/USING", ["CWE-89"])]
    return []


def _rule_injection_marker(sql: str) -> list[Finding]:
    # Склейка пользовательского ввода в строковый литерал (host-код маркер)
    if re.search(r"['\"]\s*\+\s*\w+\s*\+\s*['\"]", sql) or re.search(r"=\s*['\"]\s*\"\s*\+", sql):
        return [Finding("R011-injection-marker", "SQL_INJ_CLASSIC", "high", 10.0,
                        "Конкатенация ввода в SQL — классическая инъекция",
                        ["CWE-89", "CAPEC-66"])]
    return []


def _rule_sensitive_columns(sql: str) -> list[Finding]:
    findings: list[Finding] = []
    sel = re.search(r"select\s+(.*?)\s+from\b", sql, re.I | re.S)
    if sel:
        # не флагуем колонки под маскирующими функциями
        sel_part = sel.group(1)
        for token in re.findall(r"\b[a-zA-Zа-яА-Я_]\w*\b", sel_part):
            hit = detect_column(token)
            if hit and not re.search(rf"\b(left|right|substr|substring|md5|coalesce|mask|digest)\s*\([^)]*{re.escape(token)}",
                                     sel_part, re.I):
                findings.append(Finding("R009-sensitive-columns", "DIRECT_SENSITIVE",
                                        hit.severity, float(hit.risk_score),
                                        f"Чувствительная колонка {token!r} ({hit.category})",
                                        ["CWE-200", "CWE-359"]))
    if detect_pii_in_literals(sql):
        findings.append(Finding("R009b-pii-in-literal", "DIRECT_SENSITIVE", "high", 7.0,
                                "PII в значениях запроса (подтверждено checksum)", ["CWE-200"]))
    # дедуп по (rule_id, message)
    seen = set()
    out = []
    for f in findings:
        key = (f.rule_id, f.message)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


PHASE1_RULES = [
    _rule_select_star, _rule_dml_no_where, _rule_no_limit, _rule_union,
    _rule_pg_sleep, _rule_security_definer, _rule_plpgsql_concat,
    _rule_injection_marker, _rule_sensitive_columns,
]


def run_phase1(sql: str) -> list[Finding]:
    """@brief Прогон всех детерминированных правил. @return list[Finding]."""
    findings: list[Finding] = []
    for rule in PHASE1_RULES:
        findings.extend(rule(sql))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Гибридный аудитор (реализует baseline.SecurityAuditor)
# ─────────────────────────────────────────────────────────────────────────────
class HybridAuditor(SecurityAuditor):
    """
    @brief Phase 1 (правила) + Phase 2 (LLM-триаж).
    @param llm        LLMClient для Phase 2 (объяснения/рекомендации). Опц.
    @param threshold  Порог одобрения (по умолчанию из baseline = 4.0).
    """

    def __init__(self, llm: LLMClient | None = None, threshold: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        self.threshold = threshold if threshold is not None else self.RISK_THRESHOLD

    def audit(self, sql_query: str, db_schema: dict | None = None) -> AuditResult:
        # Phase 1 — детерминированно
        findings = run_phase1(sql_query)

        # Phase 2 — LLM-триаж (объяснение/рекомендация). НЕ понижает риск.
        recommendation = ""
        if self.llm and findings:
            resp = self.llm.chat([
                {"role": "system", "content": "Ты security-судья (auditor) PostgreSQL."},
                {"role": "user", "content":
                    f"SQL: {sql_query}\nНаходки: {[f.rule_id for f in findings]}. "
                    "Дай краткую рекомендацию по исправлению."},
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
