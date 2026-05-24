from judge.models import JudgeOutput


def fix_sql(original_sql: str, judge_result: JudgeOutput) -> str:
    sql = original_sql

    for f in judge_result.findings:

        # 1. SELECT *
        if f.vuln_class == "SELECT_STAR":
            # минимально безопасный MVP фикс
            sql = sql.replace("SELECT *", "SELECT id")

        # 2. NO PAGINATION
        elif f.vuln_class == "NO_PAGINATION":
            if "limit" not in sql.lower():
                sql = sql.strip() + " LIMIT 1000"

        # 3. SQL INJECTION
        elif f.vuln_class == "SQL_INJ_CLASSIC":
            sql = sql.replace("' + user_input + '", "$1")
            sql = sql.replace("+ user_input +", "$1")

            # нормализация кавычек
            sql = sql.replace("'$1'", "$1")
            sql = sql.replace("= '$1'", "= $1")

        # 4. DML NO WHERE
        elif f.vuln_class == "DML_NO_WHERE":
            # MVP: добавляем заглушку WHERE (лучше чем ничего)
            if "where" not in sql.lower():
                sql = sql.strip() + " WHERE id = $1"

        # 5. DIRECT SENSITIVE
        elif f.vuln_class == "DIRECT_SENSITIVE":
            # правильнее: убрать поля из SELECT
            sql = sql.replace("password", "")
            sql = sql.replace("token", "")
            sql = sql.replace(",,", ",")  # чистка

    return sql