"""
Хелперы для генерации .ipynb из Python-описаний ячеек.

@file build_helpers.py
@brief Минимальная утилита для сборки Jupyter-notebooks без зависимости от nbformat.
@details
    Каждый ноутбук — это JSON-файл (расширение .ipynb). Мы формируем его
    вручную: список ячеек (markdown / code) + minimal metadata.

    Никаких внешних библиотек не требуется — только stdlib (json, os).
"""

from __future__ import annotations

import json
import os
from textwrap import dedent


OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def md(text: str) -> dict:
    """
    @brief Markdown-ячейка.
    @param text Содержимое (готовый markdown).
    @return dict в формате nbformat 4.5.
    """
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip("\n") + "\n"}


def code(text: str) -> dict:
    """
    @brief Кодовая ячейка.
    @param text Python-код (multi-line).
    @return dict в формате nbformat 4.5.
    """
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(text).strip("\n") + "\n",
    }


def save_notebook(cells: list, filename: str) -> str:
    """
    @brief Записывает список ячеек как .ipynb.
    @param cells Список dict-ов от md() / code().
    @param filename Имя файла (без пути).
    @return Полный путь к созданному файлу.
    """
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"✓ {filename}")
    return path


# ---------------------------------------------------------------------------
# Общий блок кода — импорты и pretty-print хелперы.
# Каждый ноутбук начинается с этой ячейки → ноутбуки САМОДОСТАТОЧНЫ.
# ---------------------------------------------------------------------------
COMMON_PREAMBLE = '''\
"""
@brief Подготовка окружения и mock-БД через in-memory SQLite.
@details
    Никаких внешних зависимостей кроме stdlib + sqlite3 (есть в Colab из коробки).
    SQLite используем как «упрощённую модель PostgreSQL» — он умеет
    почти весь стандартный SQL, что достаточно для демонстраций уязвимостей.
@note
    Реальная система работает на PostgreSQL (см. ADR-0001),
    использует pglast для AST-парсинга. Здесь, для наглядности,
    эмулируем аудитор через `re` (регулярки) и простой pattern matching.
"""
import sqlite3
import re
import time
from textwrap import dedent


def section(title):
    """@brief Печатает заголовок секции."""
    print("\\n" + "=" * 72)
    print(title)
    print("=" * 72)


def show_result(rows, max_rows=10):
    """@brief Печатает результаты запроса в виде таблицы."""
    if not rows:
        print("  (нет строк)")
        return
    for i, r in enumerate(rows[:max_rows]):
        print(f"  {i + 1:>3}. {r}")
    if len(rows) > max_rows:
        print(f"  ... ещё {len(rows) - max_rows} строк")


def print_finding(f):
    """@brief Красиво печатает Finding от нашего аудитора."""
    print(f"  ⚠️  {f['rule_id']}")
    print(f"      vuln_class:  {f['vuln_class']}")
    print(f"      severity:    {f['severity']}")
    print(f"      risk_score:  {f['risk_score']}/10")
    print(f"      message:     {f['message']}")
    if f.get("evidence_refs"):
        print(f"      ссылки:      {', '.join(f['evidence_refs'])}")
'''


# ---------------------------------------------------------------------------
# Универсальный «футер» — последняя ячейка с резюме и ссылками.
# ---------------------------------------------------------------------------
def footer_cell(problem_dir: str) -> dict:
    """
    @brief Возвращает md-ячейку с финальными ссылками.
    @param problem_dir Имя папки в problems/vulnerabilities/, напр.
                       '01-sql-injection-classic'.
    """
    return md(f"""\
        ## Итог

        Мы увидели одно и то же на двух функциях:

        - **Уязвимая** — украли данные / повредили БД / поднялись в правах.
        - **Безопасная** — та же атака уходит в пустоту.

        Между ними — **один аудитор** с конкретным правилом, которое можно
        запустить детерминированно (без LLM) на каждом сгенерированном SQL.

        ## Куда дальше

        - **Описание уязвимости (под микроскопом):** [problems/vulnerabilities/{problem_dir}/README.md](../problems/vulnerabilities/{problem_dir}/README.md)
        - **Варианты решения + почему так:** [problems/vulnerabilities/{problem_dir}/solutions.md](../problems/vulnerabilities/{problem_dir}/solutions.md)
        - **Архитектура цикла:** [docs/adr/0002-loop-architecture-langgraph.md](../docs/adr/0002-loop-architecture-langgraph.md)
        - **Гибридный аудитор (pglast + LLM):** [docs/adr/0004-hybrid-auditor-ast-plus-llm.md](../docs/adr/0004-hybrid-auditor-ast-plus-llm.md)
        """)
