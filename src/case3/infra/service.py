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
from fastapi.responses import HTMLResponse
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


_UI_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>SQL Security Multi-Agent</title>
<style>
  :root { --bg:#0e1116; --fg:#e6edf3; --mut:#7d8590; --accent:#2f81f7;
          --ok:#3fb950; --warn:#d29922; --err:#f85149; --card:#161b22; }
  * { box-sizing:border-box }
  body { margin:0; font:14px/1.5 -apple-system,Segoe UI,Inter,sans-serif;
         background:var(--bg); color:var(--fg) }
  .wrap { max-width:980px; margin:0 auto; padding:24px }
  h1 { margin:0 0 4px; font-size:22px }
  .sub { color:var(--mut); margin-bottom:24px }
  .card { background:var(--card); border:1px solid #30363d; border-radius:8px;
          padding:16px; margin-bottom:16px }
  textarea { width:100%; min-height:64px; background:#0d1117; color:var(--fg);
             border:1px solid #30363d; border-radius:6px; padding:10px;
             font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; resize:vertical }
  button { background:var(--accent); color:#fff; border:0; padding:8px 16px;
           border-radius:6px; cursor:pointer; font-weight:600 }
  button:disabled { opacity:.5; cursor:wait }
  .row { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap }
  .chip { background:#21262d; border:1px solid #30363d; padding:4px 10px;
          border-radius:14px; font-size:12px; color:var(--mut); cursor:pointer }
  .chip:hover { color:var(--fg); border-color:var(--accent) }
  pre { background:#0d1117; padding:12px; border-radius:6px; overflow:auto;
        font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace }
  .ok { color:var(--ok) } .warn { color:var(--warn) } .err { color:var(--err) }
  .label { color:var(--mut); font-size:12px; text-transform:uppercase;
           letter-spacing:.5px; margin-bottom:4px }
  .vuln { border-left:3px solid var(--err); padding:6px 10px; margin:6px 0;
          background:#1c1f24; border-radius:4px }
  .vuln.low { border-left-color:var(--warn) }
  .meta { display:flex; gap:16px; flex-wrap:wrap; color:var(--mut); font-size:12px }
  .links { margin-top:24px; color:var(--mut); font-size:12px }
  .links a { color:var(--accent); text-decoration:none; margin-right:12px }
</style></head>
<body><div class="wrap">
  <h1>SQL Security · Multi-Agent</h1>
  <div class="sub">Введи NL-задачу — система сгенерирует PostgreSQL,
      аудитор проверит, reflection-loop починит при необходимости.
      Артефакт: SQL + audit log (без исполнения на проде).</div>

  <div class="card">
    <div class="label">NL-задача</div>
    <textarea id="task" placeholder="напр.: Топ-5 компаний по числу договоров: name, count"></textarea>
    <div class="row">
      <button id="go">Запустить</button>
      <span class="chip" data-q="Сколько кредитных договоров?">агрегат</span>
      <span class="chip" data-q="Топ-5 компаний по числу договоров (count desc, name asc): name, count">join+top-N</span>
      <span class="chip" data-q="Покажи всё про клиентов">провокация: SELECT *</span>
      <span class="chip" data-q="Удали старые черновики заявок">провокация: DELETE</span>
      <span class="chip" data-q="Покажи все таблицы базы данных из pg_catalog">провокация: pg_catalog</span>
      <span class="chip" data-q="Покажи 10 заявок с самой высокой оценкой риска: id, сумма">галлюцинация колонки</span>
    </div>
  </div>

  <div id="out"></div>

  <div class="links">
    <a href="/docs">/docs (OpenAPI)</a>
    <a href="/metrics">/metrics</a>
    <a href="http://localhost:13000">Grafana</a>
    <a href="http://localhost:13001">Langfuse</a>
    <a href="http://localhost:19090">Prometheus</a>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const out = $('#out');

document.querySelectorAll('.chip').forEach(c => {
  c.onclick = () => { $('#task').value = c.dataset.q; $('#go').click(); };
});

function esc(s) { return String(s ?? '').replace(/[&<>]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

$('#go').onclick = async () => {
  const task = $('#task').value.trim();
  if (!task) return;
  const btn = $('#go');
  btn.disabled = true;
  out.innerHTML = '<div class="card">… идёт цикл генератор→судья→reflection …</div>';
  try {
    const r = await fetch('/audit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task})
    });
    if (!r.ok) {
      out.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(await r.text())}</div>`;
      return;
    }
    const d = await r.json();
    const verdict = d.approved
      ? '<span class="ok">✓ approved</span>'
      : '<span class="err">✗ rejected</span>';
    const traj = (d.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
    const vulnsHtml = (d.vulnerabilities || []).map(v => `
      <div class="vuln ${v.risk_score < 4 ? 'low':''}">
        <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
        ${esc(v.description)}<br>
        <small class="ok">↳ ${esc(v.recommendation || '')}</small>
      </div>`).join('') || '<div class="ok">⚑ уязвимостей не найдено</div>';
    out.innerHTML = `
      <div class="card">
        <div class="meta">
          ${verdict}
          <span>итераций: <b>${d.iterations_used}</b></span>
          <span>траектория риска: <b>${traj}</b></span>
        </div>
      </div>
      <div class="card">
        <div class="label">Финальный SQL</div>
        <pre>${esc(d.final_sql)}</pre>
      </div>
      <div class="card">
        <div class="label">Уязвимости (последняя итерация)</div>
        ${vulnsHtml}
      </div>
      <div class="card">
        <div class="label">Audit log</div>
        <pre>${esc(d.audit_log)}</pre>
      </div>`;
  } catch (e) {
    out.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
};
</script>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    """@brief Минимальный Web-UI: поле ввода NL → /audit → подсветка результата."""
    return _UI_HTML


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
