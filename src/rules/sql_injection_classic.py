from judge.models import RuleFinding


def check(sql: str):

    sql_upper = sql.upper()

    # 1. Конкатенация через +
    if "+" in sql and ("WHERE" in sql_upper or "SELECT" in sql_upper):
        if "USER_INPUT" in sql_upper or "INPUT" in sql_upper:
            return RuleFinding(
                rule="SQL_INJ_CLASSIC",
                severity=10,
                message="Обнаружена возможная SQL-инъекция через конкатенацию строк.",
                evidence=sql,
                rule_source="deterministic_rule"
            )

    # 2. SQL через || (PostgreSQL concat)
    if "||" in sql:
        return RuleFinding(
            rule="SQL_INJ_CLASSIC",
            severity=10,
            message="Возможна SQL-инъекция через строковую конкатенацию (||).",
            evidence="||",
            rule_source="deterministic_rule"
        )

    # 3. EXECUTE с динамической строкой
    if "EXECUTE" in sql_upper and "+" in sql:
        return RuleFinding(
            rule="SQL_INJ_CLASSIC",
            severity=10,
            message="Опасный динамический EXECUTE с конкатенацией.",
            evidence=sql,
            rule_source="deterministic_rule"
        )

    return None