"""
@file build_dataset.py
@brief Сборка финального датасета: SEED → back-translation → dataset_v1.jsonl.

@details
    Пайплайн (ADR-0006):
      1. Берём SEED (seed_examples.py).
      2. Back-translation: на каждую версию SQL генерим NL-формулировку.
         СЕЙЧАС — mock (intent → 2 стиля). В проде — LLM (Qwen / GPT-4o-mini).
      3. Раскладываем в DatasetRecord:
         - sql_good  → vuln_class="safe",  is_vulnerable=False
         - sql_bad   → vuln_class=<класс>, is_vulnerable=True
      4. Стратифицированный split train/eval (seed=42).
      5. Сохраняем JSONL.

    Запуск:
        python dataset/build_dataset.py
        python dataset/build_dataset.py --out data/dataset_v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from case3.dataset.models import DatasetRecord  # noqa: E402
from seed_examples import SEED  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Back-translation (SQL → NL)
# ─────────────────────────────────────────────────────────────────────────────
def mock_back_translate(intent: str, sql: str) -> list[str]:
    """
    @brief Mock SQL→NL: из intent делает 2 NL-формулировки (short + long).
    @details
        В проде здесь LLM-вызов: «опиши SQL и дай 2 NL-вопроса аналитика».
        Mock детерминирован — берёт готовый intent и парафразит.
    @return  Список из 2 NL-строк.
    """
    short = intent
    # «развёрнутая» формулировка — добавляем разговорную обёртку
    long = f"мне нужно {intent}, подготовь, пожалуйста, запрос"
    return [short, long]


# ─────────────────────────────────────────────────────────────────────────────
# Сборка записей
# ─────────────────────────────────────────────────────────────────────────────
def build_records() -> list[DatasetRecord]:
    """@brief SEED → список DatasetRecord (по 1-2 NL на каждую версию SQL)."""
    records: list[DatasetRecord] = []
    for seed in SEED:
        # Безопасная версия — всегда есть. vuln_class="safe".
        for nl in mock_back_translate(seed.intent, seed.sql_good):
            records.append(DatasetRecord(
                seed_id=seed.id, nl=nl, sql=seed.sql_good,
                vuln_class="safe", is_vulnerable=False,
                difficulty=seed.difficulty, tables=seed.tables,
            ))
        # Уязвимая версия — если есть. Тот же intent, но с проблемой.
        if seed.sql_bad is not None:
            # Для уязвимой версии хватит 1 NL (нужна для Recall судьи).
            nl = mock_back_translate(seed.intent, seed.sql_bad)[0]
            records.append(DatasetRecord(
                seed_id=seed.id, nl=nl, sql=seed.sql_bad,
                vuln_class=seed.vuln_class, is_vulnerable=True,
                difficulty=seed.difficulty, tables=seed.tables,
            ))
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Стратифицированный split
# ─────────────────────────────────────────────────────────────────────────────
def split_records(records: list[DatasetRecord], eval_ratio: float = 0.2,
                  seed: int = 42) -> None:
    """@brief Проставляет record.split ('train'|'eval') стратифицированно по vuln_class."""
    rng = random.Random(seed)
    by_class: dict[str, list[DatasetRecord]] = {}
    for r in records:
        by_class.setdefault(r.vuln_class, []).append(r)
    for vc, items in by_class.items():
        rng.shuffle(items)
        n_eval = max(1, int(len(items) * eval_ratio))
        for i, r in enumerate(items):
            r.split = "eval" if i < n_eval else "train"


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка датасета NL→SQL")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "dataset_v1.jsonl"))
    args = ap.parse_args()

    records = build_records()
    split_records(records)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    # Отчёт
    n_train = sum(1 for r in records if r.split == "train")
    n_eval = sum(1 for r in records if r.split == "eval")
    n_vuln = sum(1 for r in records if r.is_vulnerable)
    print(f"Записей: {len(records)}  (train={n_train}, eval={n_eval})")
    print(f"  safe-записей:        {len(records) - n_vuln}")
    print(f"  vulnerable-записей:  {n_vuln}")
    print("\nПо классам (eval):")
    eval_by_class: dict[str, int] = {}
    for r in records:
        if r.split == "eval":
            eval_by_class[r.vuln_class] = eval_by_class.get(r.vuln_class, 0) + 1
    for vc, n in sorted(eval_by_class.items()):
        print(f"  {vc:18s} {n}")
    print(f"\nСохранено: {args.out}")
    print("\n⚠️  Это MOCK back-translation (intent→NL). В проде заменить на LLM-вызов.")
    print("⚠️  Seed = 14 примеров (образец). Цель — 300 (роль «Данные»).")


if __name__ == "__main__":
    main()
