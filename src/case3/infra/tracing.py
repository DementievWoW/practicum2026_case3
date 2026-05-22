"""
@file tracing.py
@brief Заглушка Langfuse (трейсинг цикла генератор→судья). Участник 4.

@details
    Повторяет форму API Langfuse: client.trace() → trace.span() → trace.score().
    Пишет трейсы в память (не шлёт по сети), умеет export()/print_summary().

    Это МОК. Реальная версия — langfuse SDK, меняется только конструктор:
        tracer = Langfuse(public_key=..., secret_key=..., host=...)
    Вместо:
        tracer = StubTracer()
    Узлы дёргают одни и те же методы (Protocol Tracer), поэтому подмена drop-in.

    Trace и Span — контекст-менеджеры: `with tracer.trace(...) as tr:` и
    `with tr.span(...) as sp:` сами проставляют длительность.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Span:
    """@brief Шаг внутри трейса (генерация, аудит, рефлексия...)."""
    name: str
    start: float
    end: float | None = None
    input: Any = None
    output: Any = None
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return ((self.end or time.perf_counter()) - self.start) * 1000

    def update(self, *, output: Any = None, **metadata) -> None:
        if output is not None:
            self.output = output
        self.metadata.update(metadata)

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, *exc) -> bool:
        self.end = time.perf_counter()
        return False


@dataclass
class Trace:
    """@brief Один прогон пайплайна: набор спанов + скоринги."""
    name: str
    id: str
    start: float
    end: float | None = None
    input: Any = None
    output: Any = None
    spans: list[Span] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def span(self, name: str, *, input: Any = None, **metadata) -> Span:
        sp = Span(name=name, start=time.perf_counter(), input=input, metadata=metadata)
        self.spans.append(sp)
        return sp

    def score(self, name: str, value: float) -> None:
        self.scores[name] = value

    def update(self, *, output: Any = None, **metadata) -> None:
        if output is not None:
            self.output = output
        self.metadata.update(metadata)

    @property
    def duration_ms(self) -> float:
        return ((self.end or time.perf_counter()) - self.start) * 1000

    def __enter__(self) -> "Trace":
        return self

    def __exit__(self, *exc) -> bool:
        self.end = time.perf_counter()
        return False


class Tracer(Protocol):
    """@brief Контракт трейсера. Реальная реализация — langfuse SDK."""

    def trace(self, name: str, *, input: Any = None, **metadata) -> Trace: ...


class StubTracer:
    """@brief МОК Langfuse: трейсы в память, ничего по сети не шлёт."""

    def __init__(self) -> None:
        self.traces: list[Trace] = []

    def trace(self, name: str, *, input: Any = None, **metadata) -> Trace:
        tr = Trace(
            name=name,
            id=str(uuid.uuid4())[:8],
            start=time.perf_counter(),
            input=input,
            metadata=metadata,
        )
        self.traces.append(tr)
        return tr

    def export(self) -> list[dict]:
        """@brief Трейсы в виде словарей (как ушло бы в Langfuse)."""
        return [
            {
                "id": t.id,
                "name": t.name,
                "duration_ms": round(t.duration_ms, 1),
                "input": t.input,
                "output": t.output,
                "scores": t.scores,
                "spans": [
                    {"name": s.name, "duration_ms": round(s.duration_ms, 1), "output": s.output}
                    for s in t.spans
                ],
            }
            for t in self.traces
        ]

    def print_summary(self) -> None:
        for t in self.export():
            print(f"⊙ trace {t['id']} «{t['name']}» {t['duration_ms']}ms scores={t['scores']}")
            for s in t["spans"]:
                print(f"   └ {s['name']}: {s['duration_ms']}ms")


_default = StubTracer()


def get_tracer() -> Tracer:
    """@brief Глобальный трейсер (по умолчанию StubTracer)."""
    return _default
