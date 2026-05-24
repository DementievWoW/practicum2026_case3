from judge.models import JudgeInput
from judge.judge_agent import judge


payload = JudgeInput(
    task="поиск договора",
    generated_sql="""
        SELECT * FROM credit_contract
        WHERE id = ' + user_input + '
    """,
    iteration=1
)

result = judge(payload)

print(
    result.model_dump_json(
        indent=2,
        ensure_ascii=False
    )
)