"""
@file embeddings.py
@brief Embeddings-клиент с дисковым кэшем + HF Inference fallback на лексический.

@details
    Используется в SchemaLinker и FewShotStore для семантического ранкинга
    (вместо лексического Jaccard). bge-m3 — мультиязычная модель от BAAI
    (1024 dim, 8k токенов контекста, отлично работает на русском).

    Бэкенды (порядок предпочтения):
        1) HuggingFace Inference Providers (нужен HF_TOKEN) — основной.
           Бесплатный rate limit ~30k chars/min, нам хватает с запасом.
        2) sentence-transformers локально (если установлен)
           — для off-net окружений.
        3) None — клиент возвращает None, вызывающая сторона
           откатывается на лексический ранкинг (graceful fallback).

    Дисковый кэш (data/embeddings_cache.json) хранит embeddings для
    строк, которые мы видели. Это превращает «60 таблиц × API-вызов
    при каждом старте» в «60 хитов кэша + 1 API на пользовательский
    запрос». Кэш bge-m3-specific (ключ включает имя модели).
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
from typing import Optional

import requests

_log = logging.getLogger(__name__)

_HF_DEFAULT_MODEL = "BAAI/bge-m3"
_HF_URL_TMPL = "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_DEFAULT_CACHE_PATH = os.path.join(_ROOT, "data", "embeddings_cache.json")


class EmbeddingsClient:
    """
    @brief HF-Inference клиент с локальным кэшем. Размерность — `dim` (1024 для bge-m3).

    @details
        Использование:
            ec = EmbeddingsClient.from_env()
            if ec.available():
                v = ec.embed("текст")        # list[float] | None
                vs = ec.embed_batch([...])   # list[Optional[list[float]]]
        cosine: статический метод `EmbeddingsClient.cosine(a, b)`.
    """

    def __init__(
        self,
        model: str = _HF_DEFAULT_MODEL,
        hf_token: str | None = None,
        cache_path: str = _DEFAULT_CACHE_PATH,
        timeout: float = 30.0,
    ):
        self.model = model
        self.hf_token = hf_token or ""
        self.cache_path = cache_path
        self.timeout = timeout
        self._cache: dict[str, list[float]] = self._load_cache()
        self._cache_lock = threading.Lock()
        self._dirty = False

    @classmethod
    def from_env(cls) -> "EmbeddingsClient":
        return cls(
            model=os.environ.get("HF_EMBEDDING_MODEL", _HF_DEFAULT_MODEL),
            hf_token=os.environ.get("HF_TOKEN", ""),
        )

    def available(self) -> bool:
        """@brief Есть ли валидный HF_TOKEN. Без него клиент тихо возвращает None."""
        return bool(self.hf_token)

    # ── основной API ────────────────────────────────────────────────────────
    def embed(self, text: str) -> Optional[list[float]]:
        """@brief Эмбеддинг строки. None при ошибке/отсутствии токена."""
        if not text or not text.strip():
            return None
        key = self._cache_key(text)
        with self._cache_lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached
        if not self.available():
            return None
        v = self._call_hf([text])
        if v and isinstance(v[0], list):
            with self._cache_lock:
                self._cache[key] = v[0]
                self._dirty = True
            return v[0]
        return None

    def embed_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """@brief Эмбеддинги для списка. Сначала кэш, потом ОДИН батч-запрос."""
        out: list[Optional[list[float]]] = [None] * len(texts)
        missing: list[tuple[int, str]] = []          # (idx, text)
        with self._cache_lock:
            for i, t in enumerate(texts):
                if not t or not t.strip():
                    continue
                k = self._cache_key(t)
                cached = self._cache.get(k)
                if cached is not None:
                    out[i] = cached
                else:
                    missing.append((i, t))

        if missing and self.available():
            vs = self._call_hf([t for _, t in missing])
            if vs is None:
                return out
            for (i, t), v in zip(missing, vs):
                if isinstance(v, list):
                    out[i] = v
                    with self._cache_lock:
                        self._cache[self._cache_key(t)] = v
                        self._dirty = True
        return out

    def save_cache(self) -> None:
        """@brief Сохранить кэш на диск (idempotent)."""
        with self._cache_lock:
            if not self._dirty:
                return
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
            self._dirty = False

    # ── косинус (статически — чтобы можно было звать без клиента) ───────────
    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    # ── внутренности ────────────────────────────────────────────────────────
    def _cache_key(self, text: str) -> str:
        return f"{self.model}::{text}"

    def _load_cache(self) -> dict[str, list[float]]:
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _call_hf(self, texts: list[str]) -> Optional[list[list[float]]]:
        """@brief Запрос к HF Inference. Возвращает list[list[float]] или None."""
        url = _HF_URL_TMPL.format(model=self.model)
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.hf_token}"},
                json={"inputs": texts, "options": {"wait_for_model": True}},
                timeout=self.timeout,
            )
            if r.status_code != 200:
                _log.warning("HF embeddings %s: %s", r.status_code, r.text[:200])
                return None
            data = r.json()
            # bge-m3 возвращает либо [dim] (один input), либо [N][dim] (батч)
            if isinstance(data, list) and data and isinstance(data[0], float):
                return [data]                   # один input → оборачиваем
            return data                          # уже [N][dim]
        except Exception as e:
            _log.warning("HF embeddings request failed: %s", e)
            return None


# Module-level singleton — удобно для линкера/fewshot, чтобы не передавать клиент сквозь.
_singleton: Optional[EmbeddingsClient] = None


def get_embeddings_client() -> EmbeddingsClient:
    """@brief Глобальный синглтон (lazy)."""
    global _singleton
    if _singleton is None:
        _singleton = EmbeddingsClient.from_env()
    return _singleton
