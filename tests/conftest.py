"""
@file conftest.py
@brief Общая настройка для pytest: путь к src/ + ленивые импорты.

Тесты гоняются командой:
    PYTHONPATH=src pytest tests -q
или просто `pytest` после установки пакета.
"""
from __future__ import annotations

import os
import sys

# Добавляем src/ в sys.path, чтобы импорты `from case3 import ...` работали
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, os.pardir, "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
