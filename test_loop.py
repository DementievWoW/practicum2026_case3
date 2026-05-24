from judge.models import JudgeInput
from judge.judge_agent import judge
from fixer.agent import fix_sql


sql = """
SELECT * FROM credit_contract
WHERE id = ' + user_input + '
"""

MAX_ITERATIONS = 3

previous_sql = None

for i in range(MAX_ITERATIONS):

    print("\n====================")
    print(f"ITERATION {i}")
    print("====================")

    # ─────────────────────────────
    # 1. JUDGE (судья)
    # ─────────────────────────────
    result = judge(
        JudgeInput(
            task="test",
            generated_sql=sql,
            iteration=i + 1
        )
    )

    print("RISK:", result.risk_score)

    # ─────────────────────────────
    # 2. STOP CONDITION (успех)
    # ─────────────────────────────
    if result.approved:
        print("APPROVED SQL:")
        print(sql)
        break

    # ─────────────────────────────
    # 3. FIXER (Алена v1)
    # ─────────────────────────────
    previous_sql = sql
    sql = fix_sql(sql, result)

    print("FIXED SQL:")
    print(sql)

    # ─────────────────────────────
    # 4. SAFETY CHECK (нет прогресса)
    # ─────────────────────────────
    if sql == previous_sql:
        print("Fixer made no changes → stopping early")
        break