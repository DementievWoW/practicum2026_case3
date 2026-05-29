"""
@file test_infra_metrics.py
@brief Тесты метрик: Counter / Gauge / Histogram + рендер в Prometheus формат.

@details
    Реестр приложения (app_metrics) глобальный, поэтому ему даём собственные
    счётчики через локальный MetricsRegistry, чтобы не задеть состояние
    долгоживущих метрик в case3.infra.metrics.
"""
from __future__ import annotations

from case3.infra.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)


class TestCounter:
    def test_inc_default_one(self):
        c = Counter("c_default", "doc")
        c.inc()
        c.inc()
        assert c._values[()] == 2.0

    def test_inc_with_label(self):
        c = Counter("c_labeled", "doc", ["status"])
        c.inc(status="ok")
        c.inc(status="ok")
        c.inc(status="err")
        assert c._values[("ok",)] == 2.0
        assert c._values[("err",)] == 1.0

    def test_inc_with_amount(self):
        c = Counter("c_amount", "doc")
        c.inc(2.5)
        c.inc(1.5)
        assert c._values[()] == 4.0


class TestGauge:
    def test_set_and_read(self):
        g = Gauge("g", "doc")
        g.set(42.0)
        assert g._values[()] == 42.0
        g.set(7.0)
        assert g._values[()] == 7.0

    def test_inc_dec(self):
        g = Gauge("g2", "doc")
        g.set(10.0)
        g.inc(3.0)
        g.dec(5.0)
        assert g._values[()] == 8.0


class TestHistogram:
    def test_observe_into_buckets(self):
        h = Histogram("h", "doc", buckets=(1, 2, 5))
        h.observe(0.5)
        h.observe(1.5)
        h.observe(3.0)
        h.observe(10.0)
        # 4 наблюдения всего
        assert h._count[()] == 4
        assert h._sum[()] == 15.0
        # бакеты кумулятивные:
        # le=1: только 0.5 → 1
        # le=2: 0.5, 1.5 → 2
        # le=5: 0.5, 1.5, 3.0 → 3
        # le=+Inf: все 4
        buckets = h._bucket_counts[()]
        assert buckets[0] == 1   # 0.5 ≤ 1
        assert buckets[1] == 2   # 0.5, 1.5 ≤ 2
        assert buckets[2] == 3   # 0.5, 1.5, 3.0 ≤ 5
        assert buckets[3] == 4   # +Inf — все

    def test_time_context_manager(self):
        h = Histogram("h_timer", "doc")
        import time
        with h.time():
            time.sleep(0.01)
        assert h._count[()] == 1
        assert h._sum[()] > 0


class TestMetricsRegistry:
    def test_register_via_factory_methods(self):
        r = MetricsRegistry()
        c = r.counter("c1", "doc")
        g = r.gauge("g1", "doc")
        h = r.histogram("h1", "doc")
        assert isinstance(c, Counter)
        assert isinstance(g, Gauge)
        assert isinstance(h, Histogram)
        # Реестр держит все три
        assert len(r._metrics) == 3

    def test_render_emits_help_and_type_lines(self):
        r = MetricsRegistry()
        c = r.counter("requests_total", "Всего запросов", ["status"])
        c.inc(status="ok")
        text = r.render()
        assert "# HELP requests_total Всего запросов" in text
        assert "# TYPE requests_total counter" in text
        assert 'requests_total{status="ok"}' in text

    def test_render_histogram_has_bucket_sum_count(self):
        r = MetricsRegistry()
        h = r.histogram("latency_seconds", "latency", buckets=(0.1, 1))
        h.observe(0.05)
        h.observe(0.5)
        text = r.render()
        # должны быть _bucket, _sum, _count строки
        assert "latency_seconds_bucket" in text
        assert "latency_seconds_sum" in text
        assert "latency_seconds_count" in text
        # бакет +Inf обязателен
        assert 'le="+Inf"' in text

    def test_render_gauge_outputs_current_value(self):
        r = MetricsRegistry()
        g = r.gauge("temperature", "doc")
        g.set(36.6)
        text = r.render()
        assert "temperature 36.6" in text
