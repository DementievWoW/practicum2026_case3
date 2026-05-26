"""
@file service.py
@brief HTTP-сервис: POST /audit, GET /healthz, GET /metrics. Участник 4.

@details
    Это «дверь» наружу — то, что разворачивается в compose и видит пользователь.
    Под капотом — `run_instrumented` из runtime.py (пайплайн + метрики + трейсы).

    Endpoints
        POST /audit  {"task": "..."}        → SystemResult JSON + audit_log
        GET  /healthz                       → {"status":"ok"}  (для compose/k8s)
        GET  /metrics                       → текст Prometheus exposition

    Метрики поднимаются на :9100 при старте (стандартная практика — отдельный
    порт от бизнес-API, чтобы /metrics не торчал наружу через reverse-proxy).

    Запуск:
        uvicorn case3.infra.service:app --host 0.0.0.0 --port 8000
    Или через Dockerfile (CMD уже прописан).
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from case3.infra import metrics as m
from case3.infra.runtime import run_instrumented

# ─── метрики /metrics на :9100 поднимаются один раз при импорте модуля ──────
# (в multi-worker uvicorn каждый воркер поднимет свой порт → запускаем
# с --workers 1 в Dockerfile)
_METRICS_PORT = int(os.environ.get("METRICS_PORT", "9100"))
try:
    m.serve_metrics(port=_METRICS_PORT)
except OSError:
    # порт занят (например, повторный импорт в тестах) — не фатально
    pass

app = FastAPI(
    title="SQL Security Multi-Agent",
    description="NL→SQL с аудитом (gen→judge→fix loop). Артефакт: SQL + audit_log.",
    version="0.1.0",
)


class AuditRequest(BaseModel):
    """@brief Вход: NL-задача от пользователя."""
    task: str = Field(..., min_length=3, max_length=2000,
                      description="Описание задачи на естественном языке")
    max_iterations: int | None = Field(None, ge=1, le=10,
                                       description="Лимит итераций (по умолч. из baseline)")


class VulnOut(BaseModel):
    vuln_class: str
    risk_score: float
    description: str
    recommendation: str


class AuditResponse(BaseModel):
    """@brief Выход: то, что отдаём по контракту кейса (SQL + audit_log)."""
    final_sql: str
    approved: bool
    iterations_used: int
    risk_trajectory: list[float]
    vulnerabilities: list[VulnOut]
    audit_log: str
    metadata: dict[str, Any]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """@brief Liveness-проба для compose/k8s."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics_text() -> Any:
    """@brief Prometheus exposition (дубль для удобства — основной канал :9100)."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(m.app_metrics.render(),
                             media_type="text/plain; version=0.0.4")


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest) -> AuditResponse:
    """
    @brief Главный endpoint: NL-задача → (SQL + audit_log).
    @details
        Артефакт системы по ТЗ — НЕ исполнение SQL, а сам SQL и аудит-лог.
        Прогон через run_instrumented: метрики и трейсы пишутся автоматически.
    """
    try:
        res = run_instrumented(
            req.task,
            max_iterations=req.max_iterations,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")

    # последний аудит = из последней итерации (там итоговые вердикты)
    last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
    vulns = [VulnOut(vuln_class=v.vuln_class, risk_score=v.risk_score,
                     description=v.description, recommendation=v.recommendation)
             for v in (last_audit.vulnerabilities if last_audit else [])]

    return AuditResponse(
        final_sql=res.final_sql,
        approved=res.approved,
        iterations_used=res.iterations_used,
        risk_trajectory=res.metadata.get("risk_trajectory", []),
        vulnerabilities=vulns,
        audit_log=res.audit_log,
        metadata=res.metadata,
    )
