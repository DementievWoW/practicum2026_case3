"""
@file client.py
@brief Контракт LLM-клиента (OpenAI-совместимый) — единая точка для всех узлов.

@details
    Все LLM-узлы (generator, judge Phase 2, reflector) ходят через этот
    интерфейс. Источник модели прозрачен: mock / облачный API (DeepInfra,
    OpenRouter) / локальный vLLM / Colab-туннель — подменяется одной
    реализацией, без изменения узлов (ADR-0008).

    Контракт намеренно минимален (chat), чтобы любую реализацию (включая
    mock) было тривиально подставить — это и есть walking-skeleton-подход.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ChatResponse:
    """@brief Ответ LLM + телеметрия (для бюджета/латентности, ADR-0008/0009)."""
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_seconds: float = 0.0
    model: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMClient(Protocol):
    """
    @brief Минимальный контракт LLM-клиента.
    @details
        Реализации:
          - MockLLMClient   (llm/mock.py) — заглушка для walking skeleton;
          - OpenAICompatClient (позже)    — DeepInfra/OpenRouter/vLLM/Colab.
    """

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> ChatResponse:
        """
        @brief Один chat-completion вызов.
        @param messages         [{"role": "system"|"user"|"assistant", "content": ...}]
        @param temperature      сэмплинг.
        @param max_tokens       лимит вывода.
        @param response_format  напр. {"type": "json_object"} для structured output.
        @return ChatResponse.
        """
        ...
