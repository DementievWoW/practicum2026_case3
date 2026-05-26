"""
@file openai_compat.py
@brief LLMClient поверх любого OpenAI-совместимого /chat/completions.

@details
    Подходит к OpenRouter, российским провайдерам, `vllm serve`, локальным
    серверам — всё, что отдаёт OpenAI-совместимый API. Реализует тот же контракт
    LLMClient, что mock/colab → подставляется в любой узел без правок.

    Конфиг через env (или аргументы):
        LLM_BASE_URL   — напр. https://openrouter.ai/api/v1  или  http://<ip>:8000/v1
        LLM_API_KEY    — ключ провайдера
        LLM_MODEL      — напр. qwen/qwen-2.5-coder-32b-instruct
        LLM_TIMEOUT    — сек (опц., по умолчанию 120)
"""
from __future__ import annotations

import os
import time

import requests

from .client import ChatResponse


class OpenAICompatLLMClient:
    """@brief LLM-клиент к OpenAI-совместимому эндпоинту (chat/completions)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: int | None = None,
                 extra_headers: dict | None = None):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        # Ключ: явный аргумент → env LLM_API_KEY → файл LLM_API_KEY_FILE (docker secrets / k8s).
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        if not self.api_key:
            p = os.environ.get("LLM_API_KEY_FILE")
            if p and os.path.exists(p):
                self.api_key = open(p).read().strip()
        self.model = model or os.environ.get("LLM_MODEL", "")
        self.timeout = timeout or int(os.environ.get("LLM_TIMEOUT", "120"))
        self.extra_headers = extra_headers or {}
        if not self.base_url or not self.model:
            raise ValueError("Нужны LLM_BASE_URL и LLM_MODEL (env или аргументы).")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> ChatResponse:
        t0 = time.time()
        payload: dict = {"model": self.model, "messages": messages,
                         "temperature": temperature, "max_tokens": max_tokens}
        if response_format:                      # structured output, если провайдер умеет
            payload["response_format"] = response_format
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json", **self.extra_headers}
        r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                          headers=headers, timeout=self.timeout)
        r.raise_for_status()
        d = r.json()
        text = (d["choices"][0]["message"].get("content") or "")
        usage = d.get("usage", {}) or {}
        return ChatResponse(
            text=text,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_seconds=time.time() - t0,
            model=self.model,
            meta={"backend": "openai_compat", "url": self.base_url},
        )
