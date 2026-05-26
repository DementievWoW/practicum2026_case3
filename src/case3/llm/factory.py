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


def make_llm():
    """@brief Возвращает LLMClient согласно env (OpenAI-compat / Colab / mock)."""
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL"):
        from case3.llm.openai_compat import OpenAICompatLLMClient
        return OpenAICompatLLMClient()
    if os.environ.get("COLAB_URL"):
        from case3.llm.colab import ColabLLMClient
        return ColabLLMClient()
    from case3.llm.mock import MockLLMClient
    return MockLLMClient(scenario="evolve")
