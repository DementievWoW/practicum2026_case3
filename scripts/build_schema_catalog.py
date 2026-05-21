"""
@file build_schema_catalog.py
@brief CLI: data_model.sql → schema_catalog.json + краткий отчёт.

Запуск:
    python scripts/build_schema_catalog.py
    python scripts/build_schema_catalog.py --in <ddl> --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Делаем src/ импортируемым без установки пакета
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from case3.schema.parser import parse_file  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка машиночитаемого каталога схемы")
    ap.add_argument(
        "--in",
        dest="src",
        default=os.path.join(ROOT, "data_model_sql", "data_model.sql"),
        help="путь к дампу DDL",
    )
    ap.add_argument(
        "--out",
        dest="dst",
        default=os.path.join(ROOT, "data", "schema_catalog.json"),
        help="куда сохранить JSON",
    )
    args = ap.parse_args()

    catalog = parse_file(args.src)
    os.makedirs(os.path.dirname(args.dst), exist_ok=True)
    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(catalog.to_dict(), f, ensure_ascii=False, indent=2)

    stats = catalog.stats()
    print("Каталог схемы собран:")
    for k, v in stats.items():
        print(f"  {k:24s} {v}")
    print(f"\nСохранено: {args.dst}")

    # Покажем пример одной таблицы для sanity-check
    sample = catalog.get("credit_contract") or (catalog.tables[0] if catalog.tables else None)
    if sample:
        print(f"\nПример таблицы '{sample.name}':")
        print(f"  comment: {sample.comment}")
        print(f"  PK:      {sample.primary_key}")
        print(f"  колонок: {len(sample.columns)}  (первые 5: {sample.column_names()[:5]})")
        print(f"  FK:      {len(sample.foreign_keys)}")
        if sample.foreign_keys:
            fk = sample.foreign_keys[0]
            print(f"           пример: {fk.column} -> {fk.ref_table}.{fk.ref_column}")


if __name__ == "__main__":
    main()
