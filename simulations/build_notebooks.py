"""
@file build_notebooks.py
@brief Runner — собирает все 9 ноутбуков.

Запуск:  python simulations/build_notebooks.py
"""

from __future__ import annotations

import os
import sys

# Чтобы import работал из любого cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_helpers import save_notebook  # noqa: E402
from build_part1 import build_01, build_02, build_03  # noqa: E402
from build_part2 import build_04, build_05, build_06  # noqa: E402
from build_part3 import build_07, build_08, build_09  # noqa: E402
from build_part4 import build_10, build_11, build_12  # noqa: E402
from build_part5 import build_13, build_14, build_15  # noqa: E402


def main() -> None:
    """@brief Генерирует все .ipynb в simulations/{vulnerabilities,engineering}/."""
    # Уязвимости (9)
    save_notebook(build_01(), "vulnerabilities/01_sql_injection_classic.ipynb")
    save_notebook(build_02(), "vulnerabilities/02_sql_injection_union.ipynb")
    save_notebook(build_03(), "vulnerabilities/03_sql_injection_time_blind.ipynb")
    save_notebook(build_04(), "vulnerabilities/04_dml_no_where.ipynb")
    save_notebook(build_05(), "vulnerabilities/05_privilege_escalation.ipynb")
    save_notebook(build_06(), "vulnerabilities/06_plpgsql_unsafe_execute.ipynb")
    save_notebook(build_07(), "vulnerabilities/07_direct_sensitive_access.ipynb")
    save_notebook(build_08(), "vulnerabilities/08_select_star.ipynb")
    save_notebook(build_09(), "vulnerabilities/09_no_pagination.ipynb")
    # Инженерные вызовы (6)
    save_notebook(build_10(), "engineering/10_schema_linking.ipynb")
    save_notebook(build_11(), "engineering/11_reflection_loop.ipynb")
    save_notebook(build_12(), "engineering/12_synthetic_dataset.ipynb")
    save_notebook(build_13(), "engineering/13_llm_judge_unreliability.ipynb")
    save_notebook(build_14(), "engineering/14_latency_budget.ipynb")
    save_notebook(build_15(), "engineering/15_model_size.ipynb")
    print(f"\nГотово — 15 ноутбуков в {os.path.dirname(os.path.abspath(__file__))}/")


if __name__ == "__main__":
    main()
