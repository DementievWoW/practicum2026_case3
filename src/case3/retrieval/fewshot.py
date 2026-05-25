"""
@file fewshot.py
@brief Асимметричный few-shot store (ADR-0012) поверх датасета NL→SQL.

@details
    Ядро идеи: ДВА непересекающихся индекса из train-сплита датасета —
      - positives (is_vulnerable=False) → отдаём ТОЛЬКО генератору
        («как надо»: безопасные/эталонные примеры для имитации);
      - negatives (is_vulnerable=True + vuln_class) → отдаём ТОЛЬКО судье
        («на что ловить»: known-bad паттерны для обогащения триажа/объяснения).

    Так контексты ролей не смешиваются (генератор не видит payload'ы —
    согласуется с политикой ADR-0005), а сигнал good/bad из датасета
    используется по назначению.

    Ретрив — лексический (Jaccard по токенам nl+sql), без внешних зависимостей:
    детерминирован и запускается где угодно. В проде заменяется на
    e5-multilingual + FAISS (ADR-0003/0005), интерфейс тот же.

    Анти-leakage: индекс строится из split=="train", метрики меряются на eval.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "dataset_v1.jsonl")

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b) if inter else 0.0


@dataclass
class Example:
    """@brief Один few-shot пример из датасета."""
    nl: str
    sql: str
    vuln_class: str
    is_vulnerable: bool
    tables: list[str]


class FewShotStore:
    """
    @brief Асимметричный few-shot store: positives (генератору) / negatives (судье).
    @param path   Путь к dataset_v1.jsonl.
    @param split  Какой сплит индексировать (по умолчанию train — анти-leakage).
    """

    def __init__(self, path: str | None = None, split: str = "train"):
        self.positives: list[Example] = []
        self.negatives: list[Example] = []
        self._tok_cache: dict[int, set[str]] = {}
        path = path or _DEFAULT_PATH
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if split and r.get("split") != split:
                    continue
                ex = Example(
                    nl=r.get("nl", ""), sql=r.get("sql", ""),
                    vuln_class=r.get("vuln_class", "safe"),
                    is_vulnerable=bool(r.get("is_vulnerable")),
                    tables=r.get("tables", []),
                )
                (self.negatives if ex.is_vulnerable else self.positives).append(ex)

    # ── генератору: похожие БЕЗОПАСНЫЕ примеры («как надо») ──────────────────
    def retrieve_positive(self, query: str, k: int = 3) -> list[Example]:
        """@brief top-k безопасных примеров по лексической близости к запросу."""
        return self._rank(self.positives, _tokens(query), k)

    # ── судье: похожие УЯЗВИМЫЕ примеры нужных классов («на что ловить») ─────
    def retrieve_negative(self, query: str, k: int = 3,
                          classes: list[str] | None = None) -> list[Example]:
        """
        @brief top-k уязвимых примеров (опц. отфильтрованных по vuln_class) по близости.
        @param classes  если задан — берём только эти классы (находки Phase 1).
        """
        pool = self.negatives
        if classes:
            cset = set(classes)
            pool = [e for e in pool if e.vuln_class in cset] or self.negatives
        return self._rank(pool, _tokens(query), k)

    # ── ранжирование по Jaccard(query, nl+sql) ──────────────────────────────
    def _rank(self, pool: list[Example], q: set[str], k: int) -> list[Example]:
        scored = []
        for e in pool:
            key = id(e)
            et = self._tok_cache.get(key)
            if et is None:
                et = _tokens(e.nl + " " + e.sql)
                self._tok_cache[key] = et
            scored.append((_jaccard(q, et), e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for s, e in scored[:k] if s > 0]

    def stats(self) -> dict[str, int]:
        return {"positives": len(self.positives), "negatives": len(self.negatives)}
