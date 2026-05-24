from judge.models import RuleFinding


SENSITIVE_KEYWORDS = [
    "password",
    "token",
    "secret",
    "passport",
    "snils",
    "card_number",
    "cvv",
    "credit_amount"
]


def check(sql: str):

    sql_lower = sql.lower()

    for keyword in SENSITIVE_KEYWORDS:

        if keyword in sql_lower:

            return RuleFinding(
                rule="DIRECT_SENSITIVE",
                severity=6,
                message=f"Обнаружен доступ к чувствительному полю: {keyword}",
                evidence=keyword,
                rule_source="deterministic_rule"
            )

    return None