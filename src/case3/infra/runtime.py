"""
@file runtime.py
@brief Инфра-обёртка: прогон пайплайна с метриками и трейсингом. Участник 4.

@details
    run_instrumented() = run_pipeline() + Prometheus-метрики + Langfuse-трейс.
    Базовый цикл (pipeline.run) НЕ трогается — наблюдаемость навешана снаружи,
    в зоне инфраструктуры. Это МОК-стек: метрики и трейсы на заглушках, но
    интерфейс боевой (Grafana уже видит /metrics).

    Демо:
        python -m case3.infra.runtime
    Поднимет /metrics на :9100 и прогонит несколько задач. Затем подними
    стек наблюдаемости (deploy/observability: `docker compose up`) и смотри
    дашборд «SQL Security» в Grafana на http://localhost:3000.
"""
from __future__ import annotations

import time

from case3.infra import metrics as m
from case3.infra.tracing import Tracer, get_tracer
from case3.pipeline import run_pipeline


def run_instrumented(
    task_description: str,
    *,
    llm=None,
    tracer: Tracer | None = None,
    **kw,
):
    """
    @brief Прогон пайплайна с наблюдаемостью.
    @param task_description  NL-запрос.
    @param llm  LLMClient (None → MockLLMClient внутри run_pipeline).
    @param tracer  Tracer (None → глобальный StubTracer).
    @return SystemResult по контракту baseline (наблюдаемость ничего не меняет).
    """
    tracer = tracer or get_tracer()
    with tracer.trace("sql_security_pipeline", input=task_description) as tr:
        t0 = time.perf_counter()
        res = run_pipeline(task_description, llm=llm, **kw)
        dt = time.perf_counter() - t0

        # ── метрики Prometheus ──
        m.RUNS.inc(approved=str(res.approved).lower())
        m.ITERATIONS.observe(res.iterations_used)
        m.LATENCY.observe(dt)
        traj = res.metadata.get("risk_trajectory") or [0.0]
        m.LAST_RISK.set(traj[-1])
        for il in res.iterations_log:
            for v in il.audit_result.vulnerabilities:
                m.FINDINGS.inc(vuln_class=v.vuln_class)

        # ── трейс Langfuse ──
        tr.update(
            output=res.final_sql,
            approved=res.approved,
            iterations=res.iterations_used,
            risk_trajectory=traj,
        )
        tr.score("final_risk", float(traj[-1]))
        tr.score("approved", 1.0 if res.approved else 0.0)

        # пробросим trace_id в metadata — UI делает deep-link на Langfuse
        tid = None
        for attr_path in ("_tr.id", "_tr.trace_id", "id"):
            o = tr
            ok = True
            for p in attr_path.split("."):
                o = getattr(o, p, None)
                if o is None:
                    ok = False
                    break
            if ok and isinstance(o, str):
                tid = o
                break
        if tid:
            res.metadata["trace_id"] = tid
    return res


def _demo() -> None:
    import itertools

    server = m.serve_metrics(port=9100)
    print("· /metrics → http://localhost:9100/metrics")
    tracer = get_tracer()

    tasks = [
        "покажи договоры с просрочкой по платежам",
        "выгрузи все колонки клиентов",
        "удали старые заявки",
    ]
    for task in itertools.islice(itertools.cycle(tasks), 9):
        res = run_instrumented(task, tracer=tracer)
        print(f"  task={task[:30]:32} approved={res.approved} iters={res.iterations_used}")
        time.sleep(0.3)

    print("\n=== Langfuse (stub) трейсы ===")
    tracer.print_summary()
    print("\n=== /metrics (срез) ===")
    print(m.app_metrics.render())
    print("Сервер /metrics крутится. Ctrl+C для выхода.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    _demo()
