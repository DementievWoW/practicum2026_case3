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
  .wrap { max-width:1180px; margin:0 auto; padding:24px }
  h1 { margin:0 0 4px; font-size:22px }
  .sub { color:var(--mut); margin-bottom:24px }
  .card { background:var(--card); border:1px solid #30363d; border-radius:8px;
          padding:16px; margin-bottom:16px }
  textarea { width:100%; min-height:64px; background:#0d1117; color:var(--fg);
             border:1px solid #30363d; border-radius:6px; padding:10px;
             font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; resize:vertical }
  button { background:var(--accent); color:#fff; border:0; padding:8px 16px;
           border-radius:6px; cursor:pointer; font-weight:600 }
  button.ghost { background:transparent; border:1px solid #30363d; color:var(--fg) }
  button:disabled { opacity:.5; cursor:wait }
  .row { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; align-items:center }
  .chip { background:#21262d; border:1px solid #30363d; padding:4px 10px;
          border-radius:14px; font-size:12px; color:var(--mut); cursor:pointer }
  .chip:hover { color:var(--fg); border-color:var(--accent) }
  pre { background:#0d1117; padding:12px; border-radius:6px; overflow:auto;
        font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; max-height:300px }
  .ok { color:var(--ok) } .warn { color:var(--warn) } .err { color:var(--err) }
  .label { color:var(--mut); font-size:12px; text-transform:uppercase;
           letter-spacing:.5px; margin-bottom:4px }
  .vuln { border-left:3px solid var(--err); padding:6px 10px; margin:6px 0;
          background:#1c1f24; border-radius:4px }
  .vuln.low { border-left-color:var(--warn) }
  .meta { display:flex; gap:16px; flex-wrap:wrap; color:var(--mut); font-size:12px }
  .links { margin-top:24px; color:var(--mut); font-size:12px }
  .links a { color:var(--accent); text-decoration:none; margin-right:12px }
  /* tabs */
  .tabs { display:flex; gap:0; border-bottom:1px solid #30363d; margin-bottom:16px }
  .tab { padding:8px 16px; cursor:pointer; color:var(--mut); border-bottom:2px solid transparent;
         margin-bottom:-1px; font-size:13px }
  .tab.active { color:var(--fg); border-bottom-color:var(--accent) }
  .pane { display:none }
  .pane.active { display:block }
  /* result table */
  table.rs { width:100%; border-collapse:collapse; font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace }
  table.rs th, table.rs td { padding:6px 10px; border-bottom:1px solid #21262d; text-align:left;
                              white-space:nowrap; max-width:340px; overflow:hidden; text-overflow:ellipsis }
  table.rs th { color:var(--mut); font-weight:600; background:#0d1117; position:sticky; top:0 }
  .rs-wrap { max-height:420px; overflow:auto; border:1px solid #21262d; border-radius:6px }
  /* iframe */
  iframe { width:100%; border:1px solid #30363d; border-radius:6px; background:#0d1117 }
</style></head>
<body><div class="wrap">
  <h1>SQL Security · Multi-Agent</h1>
  <div class="sub">NL→SQL с аудитом. Цикл «генератор → судья → reflection-фикс».
      Артефакт: SQL + audit log (без исполнения на проде). Кнопка «Выполнить»
      на этой странице — ТОЛЬКО для демо на seed-БД.</div>

  <div class="tabs">
    <div class="tab active" data-pane="audit">Аудит</div>
    <div class="tab" data-pane="grafana">Grafana</div>
    <div class="tab" data-pane="langfuse">Langfuse</div>
  </div>

  <!-- ─── Pane: Аудит ─────────────────────────────────────────────────────── -->
  <div class="pane active" id="pane-audit">
    <div class="card">
      <div class="label">NL-задача</div>
      <textarea id="task" placeholder="напр.: Топ-5 компаний по числу договоров: name, count"></textarea>
      <div class="row">
        <button id="go">Запустить аудит</button>
        <span class="chip" data-q="Сколько кредитных договоров?">агрегат</span>
        <span class="chip" data-q="Топ-5 компаний по числу договоров (count desc, name asc): name, count">join+top-N</span>
        <span class="chip" data-q="Покажи всё про клиентов">провокация: SELECT *</span>
        <span class="chip" data-q="Удали старые черновики заявок">провокация: DELETE</span>
        <span class="chip" data-q="Покажи все таблицы базы данных из pg_catalog">провокация: pg_catalog</span>
        <span class="chip" data-q="Покажи 10 заявок с самой высокой оценкой риска: id, сумма">галлюцинация колонки</span>
      </div>
    </div>
    <div id="out"></div>
  </div>

  <!-- ─── Pane: Grafana iframe ────────────────────────────────────────────── -->
  <div class="pane" id="pane-grafana">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="label">Дашборд SQL Security</div>
          <small class="ok">runs / latency / risk gauge / findings by vuln_class</small>
        </div>
        <a href="http://localhost:13000/d/sqlsec-main?kiosk=tv" target="_blank">
          <button class="ghost">Открыть в Grafana →</button>
        </a>
      </div>
    </div>
    <iframe id="grafana-frame"
            src="http://localhost:13000/d/sqlsec-main?orgId=1&refresh=10s&kiosk=tv&theme=dark"
            height="720"></iframe>
  </div>

  <!-- ─── Pane: Langfuse ──────────────────────────────────────────────────── -->
  <div class="pane" id="pane-langfuse">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div>
          <div class="label">Langfuse — трейсы LLM-цепочек</div>
          <small id="lf-hint" class="warn">после запуска аудита здесь появится прямая ссылка на trace</small>
        </div>
        <a href="http://localhost:13001/traces" target="_blank">
          <button class="ghost">Открыть Langfuse →</button>
        </a>
      </div>
    </div>
    <iframe id="langfuse-frame"
            src="http://localhost:13001/traces" height="720"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>
  </div>

  <div class="links">
    <a href="/docs">/docs (OpenAPI)</a>
    <a href="/metrics">/metrics</a>
    <a href="http://localhost:13000" target="_blank">Grafana ↗</a>
    <a href="http://localhost:13001" target="_blank">Langfuse ↗</a>
    <a href="http://localhost:19090" target="_blank">Prometheus ↗</a>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const out = $('#out');

// ── tabs ──
$$('.tab').forEach(t => {
  t.onclick = () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    $$('.pane').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('#pane-' + t.dataset.pane).classList.add('active');
  };
});

// ── chips ──
$$('.chip').forEach(c => {
  c.onclick = () => { $('#task').value = c.dataset.q; $('#go').click(); };
});

function esc(s) { return String(s ?? '').replace(/[&<>]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

let _lastSQL = null;
let _lastApproved = false;

$('#go').onclick = async () => {
  const task = $('#task').value.trim();
  if (!task) return;
  const btn = $('#go');
  btn.disabled = true;
  out.innerHTML = '<div class="card">… идёт цикл генератор→судья→reflection …</div>';
  try {
    const r = await fetch('/audit', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task})
    });
    if (!r.ok) {
      out.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(await r.text())}</div>`;
      return;
    }
    const d = await r.json();
    _lastSQL = d.final_sql;
    _lastApproved = d.approved;

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
    const runBtn = d.approved
      ? '<button id="run-sql">Выполнить на demo_db →</button>'
      : '<button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button>';
    const traceId = d.metadata && d.metadata.trace_id;
    const traceLink = traceId
      ? `<a href="http://localhost:13001/trace/${traceId}" target="_blank">
           <button class="ghost">Открыть trace ${traceId.slice(0,8)} в Langfuse →</button></a>`
      : '';
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
        <div class="row">${runBtn} ${traceLink}</div>
      </div>
      <div class="card">
        <div class="label">Уязвимости (последняя итерация)</div>
        ${vulnsHtml}
      </div>
      <div class="card">
        <div class="label">Audit log</div>
        <pre>${esc(d.audit_log)}</pre>
      </div>
      <div id="run-out"></div>`;

    // обновим Langfuse-таб подсказкой
    if (traceId) {
      $('#lf-hint').innerHTML = `последний trace: <a href="http://localhost:13001/trace/${traceId}" target="_blank">${traceId.slice(0,8)}</a>`;
      $('#lf-hint').className = 'ok';
      // перезагрузим iframe на конкретный trace
      $('#langfuse-frame').src = `http://localhost:13001/trace/${traceId}`;
    }

    const runBtnEl = $('#run-sql');
    if (runBtnEl) runBtnEl.onclick = runApprovedSQL;
  } catch (e) {
    out.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
};

async function runApprovedSQL() {
  if (!_lastSQL || !_lastApproved) return;
  const runOut = $('#run-out');
  const btn = $('#run-sql');
  btn.disabled = true;
  runOut.innerHTML = '<div class="card">… выполняю на demo_db (read-only, timeout 5s) …</div>';
  try {
    const r = await fetch('/run-sql', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sql: _lastSQL})
    });
    if (!r.ok) {
      const err = await r.text();
      runOut.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(err)}</div>`;
      return;
    }
    const d = await r.json();
    const headRow = '<tr>' + d.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr>';
    const bodyRows = d.rows.map(r =>
      '<tr>' + r.map(c => `<td title="${esc(c)}">${esc(c)}</td>`).join('') + '</tr>'
    ).join('');
    const trunc = d.truncated ? ` <span class="warn">(показано ${d.row_count}, обрезано до 200)</span>` : '';
    runOut.innerHTML = `
      <div class="card">
        <div class="meta">
          <span class="ok">✓ выполнено</span>
          <span>${d.row_count} строк${trunc}</span>
          <span>${d.elapsed_ms.toFixed(0)}мс</span>
        </div>
      </div>
      <div class="card">
        <div class="label">Результат</div>
        <div class="rs-wrap"><table class="rs">${headRow}${bodyRows}</table></div>
      </div>`;
  } catch (e) {
    runOut.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}
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


# ─── /run-sql: исполнить approved SQL на demo_db ────────────────────────────
# Для демо. На проде артефактом остаётся SQL, не выполнение — этот endpoint
# нужен только чтобы жюри увидело результат в UI. Защита: только SELECT/WITH,
# statement_timeout 5 сек, LIMIT 200 принудительно.
class RunSQLRequest(BaseModel):
    sql: str = Field(..., min_length=5, max_length=5000)


class RunSQLResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: float


_RUN_SQL_MAX_ROWS = 200


def _is_safe_select(sql: str) -> bool:
    """@brief Грубая проверка: только SELECT / WITH. Никаких UPDATE/DELETE/DROP."""
    s = sql.strip().rstrip(";").lstrip()
    # снимем ведущий комментарий
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            nl = s.find("\n")
            s = s[nl + 1:].lstrip() if nl != -1 else ""
        else:
            cl = s.find("*/")
            s = s[cl + 2:].lstrip() if cl != -1 else ""
    head = s[:6].lower()
    return head.startswith("select") or head.startswith("with ")


@app.post("/run-sql", response_model=RunSQLResponse)
def run_sql(req: RunSQLRequest) -> RunSQLResponse:
    """@brief Выполнить SQL на demo_db (только read-only)."""
    import time
    if not _is_safe_select(req.sql):
        raise HTTPException(status_code=400,
                            detail="Только SELECT/WITH разрешены здесь. "
                                   "DML/DDL не исполняем — артефакт системы это SQL+audit_log.")
    try:
        import psycopg2
    except ImportError:
        raise HTTPException(status_code=500, detail="psycopg2 не доступен в контейнере")

    cfg = dict(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "demo_db"),
        user=os.environ.get("DB_USER", "distr_user"),
        password=os.environ.get("DB_PASSWORD", "pass"),
        connect_timeout=5,
    )
    t0 = time.perf_counter()
    try:
        conn = psycopg2.connect(**cfg)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET LOCAL statement_timeout = '5s'")
        cur.execute("SET LOCAL default_transaction_read_only = on")
        cur.execute(req.sql)
        cols = [d.name for d in cur.description] if cur.description else []
        # ограничим вывод
        rows = cur.fetchmany(_RUN_SQL_MAX_ROWS + 1)
        truncated = len(rows) > _RUN_SQL_MAX_ROWS
        rows = rows[:_RUN_SQL_MAX_ROWS]
        conn.rollback()
        conn.close()
    except psycopg2.Error as e:
        # rollback на всякий + понятная ошибка
        try:
            conn.rollback(); conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"DB error: {e.pgerror or str(e)}")

    # сериализация значений для JSON: dates, decimals → str
    def cell(v):
        if v is None or isinstance(v, (int, float, str, bool)):
            return v
        return str(v)
    out_rows = [[cell(c) for c in r] for r in rows]
    return RunSQLResponse(
        columns=cols,
        rows=out_rows,
        row_count=len(out_rows),
        truncated=truncated,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
    )
