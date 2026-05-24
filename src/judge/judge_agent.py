from judge.recommendations import RECOMMENDATIONS

from judge.models import (
    JudgeInput,
    JudgeOutput,
    Finding
)

from judge.pipeline import run_rules


def judge(payload: JudgeInput) -> JudgeOutput:

    rule_findings = run_rules(payload.generated_sql)

    findings = []

    for idx, rf in enumerate(rule_findings):

        findings.append(
            Finding(
                id=f"finding-{idx + 1}",
                vuln_class=rf.rule,
                severity=rf.severity,
                confidence=0.95,
                message=rf.message,
                evidence=rf.evidence,
                recommendation=RECOMMENDATIONS.get(
                    rf.rule,
                    "Исправьте проблему безопасности."
                ),
                rule_source=rf.rule_source
            )
        )

    # ДЕДУПЛИКАЦИЯ
    unique = {}
    deduped = []

    for f in findings:
        if f.vuln_class not in unique:
            unique[f.vuln_class] = True
            deduped.append(f)

    findings = deduped

    approved = len(findings) == 0

    return JudgeOutput(
        approved=approved,
        iteration=payload.iteration,
        risk_score=max([f.severity for f in findings], default=0),
        findings=findings,
        summary=(
            "SQL-запрос безопасен."
            if approved
            else "Обнаружены проблемы безопасности."
        ),
        approved_reason=(
            "Все проверки пройдены."
            if approved
            else None
        )
    )