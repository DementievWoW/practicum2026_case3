"""
@file colab.py
@brief ColabLLMClient — реальный LLMClient поверх Colab-bridge (Qwen-Coder за cloudflared-туннелем).

@details
    Реализует тот же контракт LLMClient (client.py), что и MockLLMClient, поэтому
    подставляется в любой узел (generator / judge Phase 2 / reflector) без правок:

        from case3.llm.colab import ColabLLMClient
        from case3.nodes.generator import LLMGenerator
        gen = LLMGenerator(llm=ColabLLMClient())          # URL/токен из env
        sql = gen.generate("выгрузи активные кредитные договоры")

    Это «вариант A»: пайплайн крутится локально, в Colab только инференс модели.
    MCP-мост (colab_mcp_server.py) при этом — отдельная история, для интерактивной
    отладки из Claude; самому пайплайну он не нужен.

    Конфиг через env (или аргументы конструктора):
        COLAB_URL   — публичный URL туннеля (https://...trycloudflare.com)
        COLAB_TOKEN — общий секрет (печатает Colab-ноутбук при старте)
"""
from __future__ import annotations

import os
import time

import requests

from .client import ChatResponse


class ColabLLMClient:
    """@brief LLM-клиент, проксирующий chat-запросы на Colab-bridge."""

    def __init__(self, url: str | None = None, token: str | None = None,
                 model: str = "qwen-coder", timeout: int = 180):
        self.url = (url or os.environ.get("COLAB_URL", "")).rstrip("/")
        self.token = token or os.environ.get("COLAB_TOKEN", "")
        self.model = model
        self.timeout = timeout
        if not self.url:
            raise ValueError("COLAB_URL не задан — передайте url=... или выставьте env COLAB_URL.")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> ChatResponse:
        """@brief Один chat-completion через Colab /chat. response_format bridge'ом не
        поддерживается (обычная HF-модель) — для JSON просите формат в промпте."""
        t0 = time.time()
        resp = requests.post(
            f"{self.url}/chat",
            json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        text = resp.json().get("text", "")
        user = " ".join(m.get("content", "") for m in messages)
        return ChatResponse(
            text=text,
            tokens_in=len(user) // 4,
            tokens_out=len(text) // 4,
            latency_seconds=time.time() - t0,
            model=self.model,
            meta={"backend": "colab", "url": self.url},
        )

    def health(self) -> dict:
        """@brief Проверка bridge: модель, GPU, доступность."""
        r = requests.get(f"{self.url}/health",
                         headers={"Authorization": f"Bearer {self.token}"}, timeout=15)
        r.raise_for_status()
        return r.json()
