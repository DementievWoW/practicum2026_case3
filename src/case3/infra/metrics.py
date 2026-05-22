"""
@file metrics.py
@brief Заглушка Prometheus-метрик (только stdlib). Участник 4 (инфраструктура).

@details
    Лёгкий реестр метрик в формате экспозиции Prometheus. Поддерживает
    Counter / Gauge / Histogram с метками и отдаёт текст по HTTP /metrics —
    Prometheus может скрейпить его уже сейчас, Grafana строить дашборды.

    Это МОК на stdlib (http.server), чтобы инфра-зона работала без внешних
    зависимостей (важно для 2 ГБ VPS / локали). Реальная версия — библиотека
    prometheus_client; имена метрик те же, поэтому подмена drop-in.

    Реестр приложения (app_metrics) и его метрики объявлены внизу —
    их дёргает infra/runtime.py на каждом прогоне пайплайна.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Iterable


def _num(x: float) -> str:
    """@brief Формат числа для Prometheus-экспозиции."""
    if x == float("inf"):
        return "+Inf"
    if x == float("-inf"):
        return "-Inf"
    return repr(x)


def _fmt_labels(labelnames: tuple[str, ...], values: tuple[str, ...]) -> str:
    if not labelnames:
        return ""
    inner = ",".join(f'{n}="{v}"' for n, v in zip(labelnames, values))
    return "{" + inner + "}"


class _Metric:
    """@brief База: имя, help, набор меток, потокобезопасное хранилище."""

    type = "untyped"

    def __init__(self, name: str, documentation: str, labelnames: Iterable[str] = ()):
        self.name = name
        self.documentation = documentation
        self.labelnames = tuple(labelnames)
        self._lock = threading.Lock()

    def _key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.labelnames)


class Counter(_Metric):
    """@brief Монотонно растущий счётчик."""

    type = "counter"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._values: dict[tuple[str, ...], float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with self._lock:
            k = self._key(labels)
            self._values[k] = self._values.get(k, 0.0) + amount


class Gauge(_Metric):
    """@brief Значение, которое может расти и падать."""

    type = "gauge"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._values: dict[tuple[str, ...], float] = {}

    def set(self, value: float, **labels: str) -> None:
        with self._lock:
            self._values[self._key(labels)] = float(value)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with self._lock:
            k = self._key(labels)
            self._values[k] = self._values.get(k, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)


class _Timer:
    """@brief Контекст-менеджер: измеряет длительность блока в Histogram."""

    def __init__(self, hist: "Histogram", labels: dict[str, str]):
        self._hist = hist
        self._labels = labels

    def __enter__(self):
        import time
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        import time
        self._hist.observe(time.perf_counter() - self._t0, **self._labels)
        return False


class Histogram(_Metric):
    """@brief Гистограмма: кумулятивные бакеты + _sum + _count."""

    type = "histogram"
    DEFAULT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name, documentation, labelnames=(), buckets=None):
        super().__init__(name, documentation, labelnames)
        b = tuple(buckets) if buckets else self.DEFAULT_BUCKETS
        self.buckets = tuple(sorted(b)) + (float("inf"),)
        self._bucket_counts: dict[tuple[str, ...], list[int]] = {}
        self._sum: dict[tuple[str, ...], float] = {}
        self._count: dict[tuple[str, ...], int] = {}

    def observe(self, value: float, **labels: str) -> None:
        with self._lock:
            k = self._key(labels)
            if k not in self._bucket_counts:
                self._bucket_counts[k] = [0] * len(self.buckets)
                self._sum[k] = 0.0
                self._count[k] = 0
            for i, ub in enumerate(self.buckets):
                if value <= ub:
                    self._bucket_counts[k][i] += 1  # бакеты кумулятивны
            self._sum[k] += value
            self._count[k] += 1

    def time(self, **labels: str) -> _Timer:
        """@brief `with hist.time(): ...` — замерить длительность блока."""
        return _Timer(self, labels)


class MetricsRegistry:
    """@brief Реестр метрик с рендером в формат экспозиции Prometheus."""

    def __init__(self):
        self._metrics: list[_Metric] = []

    def _reg(self, m: _Metric) -> _Metric:
        self._metrics.append(m)
        return m

    def counter(self, *a, **kw) -> Counter:
        return self._reg(Counter(*a, **kw))  # type: ignore[return-value]

    def gauge(self, *a, **kw) -> Gauge:
        return self._reg(Gauge(*a, **kw))  # type: ignore[return-value]

    def histogram(self, *a, **kw) -> Histogram:
        return self._reg(Histogram(*a, **kw))  # type: ignore[return-value]

    def render(self) -> str:
        """@brief Текст в формате Prometheus exposition (text/plain; 0.0.4)."""
        lines: list[str] = []
        for m in self._metrics:
            lines.append(f"# HELP {m.name} {m.documentation}")
            lines.append(f"# TYPE {m.name} {m.type}")
            if isinstance(m, Histogram):
                with m._lock:
                    for k in m._count:
                        for i, ub in enumerate(m.buckets):
                            le = _num(ub)
                            labels = m.labelnames + ("le",)
                            lines.append(
                                f"{m.name}_bucket{_fmt_labels(labels, k + (le,))} "
                                f"{m._bucket_counts[k][i]}"
                            )
                        lines.append(f"{m.name}_sum{_fmt_labels(m.labelnames, k)} {_num(m._sum[k])}")
                        lines.append(f"{m.name}_count{_fmt_labels(m.labelnames, k)} {m._count[k]}")
            else:
                with m._lock:
                    for k, v in m._values.items():  # type: ignore[attr-defined]
                        lines.append(f"{m.name}{_fmt_labels(m.labelnames, k)} {_num(v)}")
        return "\n".join(lines) + "\n"

    def serve(self, port: int = 9100, addr: str = "0.0.0.0") -> HTTPServer:
        """@brief Поднять /metrics в фоновом daemon-потоке. Возвращает HTTPServer."""
        registry = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path.rstrip("/") in ("/metrics", ""):
                    body = registry.render().encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a):  # тишина в stdout
                pass

        httpd = HTTPServer((addr, port), _Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd


# ─────────────────────────────────────────────────────────────────────────────
# Реестр приложения + метрики (их пишет infra/runtime.py)
# ─────────────────────────────────────────────────────────────────────────────
app_metrics = MetricsRegistry()

RUNS = app_metrics.counter("sqlsec_runs_total", "Всего прогонов пайплайна", ["approved"])
ITERATIONS = app_metrics.histogram("sqlsec_iterations", "Число итераций на прогон", buckets=(1, 2, 3, 4, 5))
LATENCY = app_metrics.histogram("sqlsec_latency_seconds", "Латентность прогона, сек")
LAST_RISK = app_metrics.gauge("sqlsec_last_risk", "Итоговый risk последнего прогона")
FINDINGS = app_metrics.counter("sqlsec_findings_total", "Найдено уязвимостей по классам", ["vuln_class"])


def serve_metrics(port: int = 9100) -> HTTPServer:
    """@brief Поднять /metrics приложения (по умолчанию :9100)."""
    return app_metrics.serve(port=port)


if __name__ == "__main__":
    RUNS.inc(approved="true")
    ITERATIONS.observe(2)
    LATENCY.observe(0.42)
    LAST_RISK.set(0.0)
    FINDINGS.inc(vuln_class="SELECT_STAR")
    print(app_metrics.render())
