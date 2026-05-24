from rules.registry import RULES


def run_rules(sql: str):

    findings = []

    for rule in RULES:

        result = rule(sql)

        if result:
            findings.append(result)

    return findings