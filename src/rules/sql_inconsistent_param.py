from judge.models import RuleFinding


def check(sql: str):

    if "$1" in sql and "'$1'" in sql:

        return RuleFinding(
            rule="SQL_INCONSISTENT_PARAMETERIZATION",
            severity=7,
            message="Некорректная параметризация: $1 в кавычках",
            evidence=sql,
            rule_source="deterministic_rule"
        )

    return None