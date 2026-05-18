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


def main() -> None:
    """@brief Генерирует все .ipynb в simulations/."""
    save_notebook(build_01(), "01_sql_injection_classic.ipynb")
    save_notebook(build_02(), "02_sql_injection_union.ipynb")
    save_notebook(build_03(), "03_sql_injection_time_blind.ipynb")
    save_notebook(build_04(), "04_dml_no_where.ipynb")
    save_notebook(build_05(), "05_privilege_escalation.ipynb")
    save_notebook(build_06(), "06_plpgsql_unsafe_execute.ipynb")
    save_notebook(build_07(), "07_direct_sensitive_access.ipynb")
    save_notebook(build_08(), "08_select_star.ipynb")
    save_notebook(build_09(), "09_no_pagination.ipynb")
    print(f"\nГотово — 9 ноутбуков в {os.path.dirname(os.path.abspath(__file__))}/")


if __name__ == "__main__":
    main()
