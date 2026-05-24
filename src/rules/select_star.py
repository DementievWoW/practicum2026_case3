from judge.models import RuleFinding


def check(sql: str):

    sql_upper = sql.upper()

    if "SELECT *" in sql_upper:

        return RuleFinding(
            rule="SELECT_STAR",
            severity=5,
            message="Использование SELECT * может раскрыть лишние данные.",
            evidence="SELECT *",
            rule_source="deterministic_rule"
        )

    return None