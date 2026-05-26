"""
@file factory.py
@brief Выбор LLM-клиента по окружению (.env-driven) — единая точка для пайплайна.

@details
    Приоритет:
      1. LLM_BASE_URL + LLM_MODEL  → OpenAICompatLLMClient (OpenRouter/провайдер/vLLM)
      2. COLAB_URL                 → ColabLLMClient (Colab-туннель)
      3. иначе                     → MockLLMClient (walking skeleton, без сети)

    Так передача команде = просто .env: вписал base_url/ключ/модель — система
    пошла на реальную LLM; пусто — работает на моках (самодостаточно).
"""
from __future__ import annotations

import os


def _has_llm_api_key() -> bool:
    """@brief Есть ли API-ключ для OpenAI-compat (env или файл-секрет docker secret)."""
    if os.environ.get("LLM_API_KEY"):
        return True
    p = os.environ.get("LLM_API_KEY_FILE")
    if p and os.path.exists(p):
        # пустой файл-секрет (compose-плейсхолдер) считаем за «нет ключа»
        try:
            return bool(open(p).read().strip())
        except Exception:
            return False
    return False


def make_llm():
    """@brief Возвращает LLMClient согласно env (OpenAI-compat / Colab / mock).

    @details
        Порядок выбора:
          1. LLM_BASE_URL + LLM_MODEL + (LLM_API_KEY или непустой LLM_API_KEY_FILE)
             → OpenAICompatLLMClient (OpenRouter/провайдер/vLLM).
          2. COLAB_URL → ColabLLMClient (Colab-туннель).
          3. Иначе → MockLLMClient (walking skeleton, без сети).

        Главное правило: если base_url есть, но ключа нет — НЕ ходим в провайдер
        (тот вернёт 401, пайплайн упадёт 500). Молча откатываемся на mock —
        свежий клон без .env должен работать out-of-the-box.
    """
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL") and _has_llm_api_key():
        from case3.llm.openai_compat import OpenAICompatLLMClient
        return OpenAICompatLLMClient()
    if os.environ.get("COLAB_URL"):
        from case3.llm.colab import ColabLLMClient
        return ColabLLMClient()
    from case3.llm.mock import MockLLMClient
    return MockLLMClient(scenario="evolve")
