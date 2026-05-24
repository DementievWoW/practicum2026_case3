from judge.models import RuleFinding


def check(sql: str):
    sql_upper = sql.upper()

    if (
        sql_upper.startswith("UPDATE")
        and "WHERE" not in sql_upper
    ):
        return RuleFinding(
            rule="DML_NO_WHERE",
            severity=9,
            message="UPDATE без WHERE обновит все строки.",
            evidence=sql,
            rule_source="deterministic_rule"
        )

    if (
        sql_upper.startswith("DELETE")
        and "WHERE" not in sql_upper
    ):
        return RuleFinding(
            rule="DML_NO_WHERE",
            severity=9,
            message="DELETE без WHERE удалит все строки.",
            evidence=sql,
            rule_source="deterministic_rule"
        )

    return None