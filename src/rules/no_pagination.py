from judge.models import RuleFinding


def check(sql: str):

    sql_upper = sql.upper()

    is_select = "SELECT" in sql_upper

    has_limit = "LIMIT" in sql_upper

    if is_select and not has_limit:

        return RuleFinding(
            rule="NO_PAGINATION",
            severity=4,
            message="SELECT без LIMIT может вернуть слишком много строк.",
            evidence=sql,
            rule_source="deterministic_rule"
        )

    return None