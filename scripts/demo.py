"""
@file demo.py
@brief Демонстрация цикла генератор→судья→reflector (на моках).

Запуск:
    python scripts/demo.py
    python scripts/demo.py "выгрузи всех клиентов с паспортами"
    python scripts/demo.py --scenario always_bad   # упереться в лимит итераций
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from case3.pipeline import run_pipeline  # noqa: E402
from case3.llm.mock import MockLLMClient  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Demo: цикл генерация+аудит SQL (на моках)")
    ap.add_argument("task", nargs="?", default="покажи активные кредитные договоры",
                    help="NL-описание задачи")
    ap.add_argument("--scenario", default="evolve",
                    choices=["evolve", "always_good", "always_bad"],
                    help="поведение мок-генератора")
    args = ap.parse_args()

    print(f"Задача: {args.task}\nСценарий мока: {args.scenario}\n")
    res = run_pipeline(args.task, llm=MockLLMClient(scenario=args.scenario))

    print(res.audit_log)
    print("\n" + "=" * 50)
    print("ИТОГ")
    print("=" * 50)
    print(f"Финальный SQL:   {res.final_sql}")
    print(f"Одобрено:        {res.approved}")
    print(f"Итераций:        {res.iterations_used}")
    print(f"Динамика риска:  {res.metadata['risk_trajectory']}")
    if res.metadata.get("reflection_final"):
        print("Уроки в памяти:")
        for l in res.metadata["reflection_final"]:
            print(f"  - {l}")


if __name__ == "__main__":
    main()
