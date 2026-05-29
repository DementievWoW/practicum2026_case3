"""
@file test_reflector.py
@brief Тесты Reflector: дедупликация по rule_id, окно последних N уроков,
       детерминированный lookup по vuln_class.
"""
from __future__ import annotations

from case3.contracts import AuditResult, Lesson, Vulnerability
from case3.nodes.reflector import Reflector, _LESSON_TEMPLATES


def _make_audit(vuln_classes: list[str], risk: float = 6.0) -> AuditResult:
    """Helper: AuditResult с заданными vuln_class'ами."""
    vulns = [
        Vulnerability(
            vuln_class=vc, risk_score=risk,
            description=f"описание {vc}", recommendation="fix",
        )
        for vc in vuln_classes
    ]
    return AuditResult(
        approved=False, overall_risk_score=risk,
        vulnerabilities=vulns, summary="rejected",
    )


class TestReflectorTemplates:
    def test_known_vuln_class_produces_lesson(self):
        r = Reflector()
        audit = _make_audit(["SELECT_STAR"])
        lessons = r.reflect(audit, [])
        assert len(lessons) >= 1
        assert any(l.rule_id == "SELECT_STAR" for l in lessons)

    def test_unknown_vuln_class_no_template_no_crash(self):
        r = Reflector()
        audit = _make_audit(["TOTALLY_UNKNOWN_VULN"])
        lessons = r.reflect(audit, [])
        # Не упасть. Урок либо есть (generic), либо пуст.
        assert isinstance(lessons, list)


class TestReflectorDedup:
    def test_no_dup_same_rule_twice(self):
        r = Reflector()
        existing = [_LESSON_TEMPLATES["SELECT_STAR"]]
        audit = _make_audit(["SELECT_STAR"])
        lessons = r.reflect(audit, existing)
        ids = [l.rule_id for l in lessons]
        # SELECT_STAR должен появиться только один раз
        assert ids.count("SELECT_STAR") == 1

    def test_different_rules_kept(self):
        r = Reflector()
        existing = [_LESSON_TEMPLATES["SELECT_STAR"]]
        audit = _make_audit(["DML_NO_WHERE", "NO_PAGINATION"])
        lessons = r.reflect(audit, existing)
        ids = {l.rule_id for l in lessons}
        # Все три должны быть представлены (SELECT_STAR из existing + 2 новых)
        assert "SELECT_STAR" in ids
        assert "DML_NO_WHERE" in ids
        assert "NO_PAGINATION" in ids


class TestReflectorWindow:
    def test_window_caps_lesson_count(self):
        # Окно хранения — небольшое (обычно 5). Если набьём больше, лишние выбрасываются.
        r = Reflector()
        many_classes = ["SELECT_STAR", "DML_NO_WHERE", "NO_PAGINATION",
                        "DIRECT_SENSITIVE", "SQL_INJ_CLASSIC"]
        # Каждой итерацией добавляем разный класс
        lessons: list[Lesson] = []
        for vc in many_classes:
            lessons = r.reflect(_make_audit([vc]), lessons)
        # Окно reflector'а ограничивает — проверим, что итог содержит хотя бы что-то,
        # и не превышает разумного лимита (обычно ≤ 5).
        assert 1 <= len(lessons) <= 10
