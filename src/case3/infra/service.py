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

import json as _json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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
  /* chat */
  .msgs { display:flex; flex-direction:column; gap:12px; margin-bottom:12px }
  .msg { max-width:78%; padding:10px 14px; border-radius:10px; font-size:13px }
  .msg.user { align-self:flex-end; background:#1f2937; border:1px solid #30363d }
  .msg.bot  { align-self:flex-start; background:#161b22; border:1px solid #30363d }
  .msg.bot.clarify { border-left:3px solid var(--accent) }
  .msg.warn { align-self:stretch; background:#2b1d10; border:1px solid #d29922; color:#ffd28b }
  .options { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px }
  .opt { background:#21262d; border:1px solid #30363d; color:var(--fg); padding:5px 10px;
         border-radius:14px; font-size:12px; cursor:pointer }
  .opt:hover { border-color:var(--accent) }
  .answer-row { display:flex; gap:6px; margin-top:8px }
  .answer-row input { flex:1; background:#0d1117; color:var(--fg); border:1px solid #30363d;
                       border-radius:6px; padding:6px 10px; font:13px ui-monospace,Menlo,monospace }
  /* feedback */
  .fb-btn { background:#21262d; border:1px solid #30363d; color:var(--fg);
            padding:8px 14px; border-radius:6px; cursor:pointer; font-size:14px;
            transition:all .15s }
  .fb-btn:hover { border-color:var(--accent) }
  .fb-btn.up.active { background:#1a4a2a; border-color:var(--ok); color:var(--ok) }
  .fb-btn.down.active { background:#4a1a1a; border-color:var(--err); color:var(--err) }
  .fb-comment { width:100%; margin-top:8px; background:#0d1117; color:var(--fg);
                border:1px solid #30363d; border-radius:6px; padding:8px 10px;
                font:13px ui-monospace,Menlo,monospace; min-height:50px; resize:vertical }
  .fb-thanks { color:var(--ok); font-size:13px; margin-top:8px }
  /* thinking */
  .think { font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--mut);
           padding-left:24px; border-left:2px dashed #30363d; margin:6px 0 12px 4px }
  .think .step { padding:3px 0; opacity:0; animation:fadeIn .25s forwards }
  @keyframes fadeIn { to { opacity: 1 } }
  .think .step.gen  { color:#79c0ff }
  .think .step.aud  { color:#ffa657 }
  .think .step.ref  { color:#d2a8ff }
  .think .step.iter { color:var(--fg); font-weight:600; margin-top:6px }
  .think .step.err  { color:var(--err) }
  .think .step .t   { color:var(--mut); font-size:11px; margin-left:6px }
  .think pre { background:#0d1117; padding:6px 10px; border-radius:4px;
               margin:4px 0; max-height:100px; overflow:auto; font-size:11px }
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

  <!-- ─── Pane: Аудит (chat-стиль) ───────────────────────────────────────── -->
  <div class="pane active" id="pane-audit">
    <div class="card">
      <div class="label">NL-задача (новый диалог)</div>
      <textarea id="task" placeholder="напр.: Удали старые черновики заявок"></textarea>
      <div class="row">
        <button id="go">Начать</button>
        <button class="ghost" id="go-stream" title="показать поток мыслей пайплайна (SSE)">🧠 Live</button>
        <button class="ghost" id="reset" style="display:none">Сбросить диалог</button>
        <span class="chip" data-q="Сколько кредитных договоров?">агрегат</span>
        <span class="chip" data-q="Топ-5 компаний по числу договоров (count desc, name asc): name, count">join+top-N</span>
        <span class="chip" data-q="Удали старые черновики заявок">DELETE (clarify)</span>
        <span class="chip" data-q="Покажи активных клиентов">«активный» (clarify)</span>
        <span class="chip" data-q="Покажи всё про клиентов">провокация: SELECT *</span>
        <span class="chip" data-q="Покажи все таблицы базы данных из pg_catalog">провокация: pg_catalog</span>
      </div>
    </div>
    <div id="msgs" class="msgs"></div>
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

  <!-- ─── Pane: Langfuse (без iframe — CSP frame-ancestors=none) ───────────── -->
  <div class="pane" id="pane-langfuse">
    <div class="card">
      <div class="label">Langfuse — трейсы LLM-цепочек</div>
      <p style="color:var(--mut);font-size:13px;margin:8px 0">
        Langfuse self-host блокирует встраивание через iframe (CSP frame-ancestors=none).
        После прогона из таба «Аудит» здесь появится прямая ссылка на trace.
      </p>
      <div id="lf-hint" class="warn">пока трейсов нет — запусти любой аудит сначала</div>
      <div class="row" style="margin-top:12px">
        <a href="http://localhost:13001/traces" target="_blank">
          <button>Открыть список trace'ов →</button>
        </a>
        <a href="http://localhost:13001" target="_blank">
          <button class="ghost">Главная Langfuse →</button>
        </a>
      </div>
    </div>
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
// Глобальный обработчик ошибок: рисуем баннер сверху, чтобы видеть
// JS-ошибки даже без открытой DevTools. Полезно для коллег-новичков.
window.addEventListener('error', e => {
  const banner = document.getElementById('js-err-banner') || (() => {
    const b = document.createElement('div');
    b.id = 'js-err-banner';
    b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;'
                    + 'background:#f85149;color:#fff;padding:10px;font:13px monospace;'
                    + 'max-height:200px;overflow:auto';
    document.body.prepend(b);
    return b;
  })();
  banner.textContent = `JS ERROR: ${e.message} @ ${e.filename}:${e.lineno}:${e.colno}`;
});

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

// ── state диалога ──
let _task = '';                 // оригинальная NL-задача
let _history = [];              // массив ChatTurn'ов (assistant clarify + user content)
let _lastSQL = null;
let _lastApproved = false;
const msgs = $('#msgs');

function renderUser(text) {
  msgs.insertAdjacentHTML('beforeend',
    `<div class="msg user">${esc(text)}</div>`);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
}
function renderBot(html, cls='bot') {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.innerHTML = html;
  msgs.appendChild(div);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
  return div;
}
function renderWarnings(warnings) {
  if (!warnings || !warnings.length) return;
  const html = warnings.map(w =>
    `<b>${esc(w.code)}</b> · ${esc(w.severity)}<br>${esc(w.message)}<br><small>${esc(w.hint)}</small>`
  ).join('<hr style="border:0;border-top:1px solid #6e4500;margin:8px 0">');
  renderBot('⚠ NL-валидатор предупреждает:<br>' + html, 'warn');
}
function resetDialog() {
  _task = ''; _history = []; _lastSQL = null; _lastApproved = false;
  msgs.innerHTML = '';
  out.innerHTML = '';
  $('#task').value = '';
  $('#reset').style.display = 'none';
}
const _reset_btn = $('#reset');
if (_reset_btn) _reset_btn.onclick = resetDialog;

// Рендер "thinking"-потока (SSE-события из pipeline)
function appendThink(thinkEl, cls, text, time_s) {
  const t = time_s != null ? `<span class="t">${time_s.toFixed(1)}s</span>` : '';
  thinkEl.insertAdjacentHTML('beforeend',
    `<div class="step ${cls}">${text} ${t}</div>`);
  msgs.scrollIntoView({behavior:'smooth', block:'end'});
}

// Live-режим только когда нет clarify-истории (первый ход).
// SSE рисует поток мыслей, в конце даёт финальный SQL.
async function sendStream() {
  out.innerHTML = '';
  // bubble для thinking-стрима
  const bot = renderBot('<b>🧠 thinking…</b><div class="think" id="think-box"></div>', 'bot');
  const thinkEl = bot.querySelector('#think-box');
  const t0 = performance.now();
  let finalEv = null;

  try {
    const r = await fetch('/chat/stream', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: _task, history: []})
    });
    if (!r.ok || !r.body) {
      appendThink(thinkEl, 'err', `HTTP ${r.status}`);
      return;
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream:true});
      let nl;
      while ((nl = buf.indexOf('\\n\\n')) !== -1) {
        const chunk = buf.slice(0, nl);
        buf = buf.slice(nl + 2);
        if (!chunk.startsWith('data: ')) continue;
        const ev = JSON.parse(chunk.slice(6));
        const dt = (performance.now() - t0) / 1000;
        if (ev.event === 'nl_warnings') {
          renderWarnings(ev.warnings);
        } else if (ev.event === 'iter_start') {
          appendThink(thinkEl, 'iter', `── Итерация ${ev.iteration} ──`, dt);
        } else if (ev.event === 'generator_start') {
          const lessons = (ev.lessons && ev.lessons.length)
            ? ` (учтены уроки: ${ev.lessons.length})` : '';
          appendThink(thinkEl, 'gen', `🧮 генератор пишет SQL${lessons}…`, dt);
        } else if (ev.event === 'generator_done') {
          appendThink(thinkEl, 'gen', `✓ SQL готов <pre>${esc(ev.sql.slice(0,300))}</pre>`, dt);
        } else if (ev.event === 'auditor_start') {
          appendThink(thinkEl, 'aud', `🛡 аудитор проверяет…`, dt);
        } else if (ev.event === 'auditor_done') {
          const v = ev.vulnerabilities || [];
          const ok = ev.approved ? '<span class="ok">approved</span>' : '<span class="err">rejected</span>';
          const vlist = v.length ? ' · ' + v.map(x => `${x.vuln_class}(${x.risk_score.toFixed(1)})`).join(', ') : '';
          appendThink(thinkEl, 'aud', `${ok} · риск ${ev.risk.toFixed(1)}${vlist}`, dt);
        } else if (ev.event === 'reflector_start') {
          appendThink(thinkEl, 'ref', `🧠 reflection пишет урок…`, dt);
        } else if (ev.event === 'reflector_done') {
          const ls = (ev.lessons || []).map(esc).join('<br>');
          appendThink(thinkEl, 'ref', `✓ урок: ${ls || '—'}`, dt);
        } else if (ev.event === 'final') {
          finalEv = ev;
        } else if (ev.event === 'error') {
          appendThink(thinkEl, 'err', `error: ${esc(ev.message)}`, dt);
        }
      }
    }
  } catch (e) {
    appendThink(thinkEl, 'err', `network error: ${esc(e.message)}`);
    return;
  }

  // Финал: показываем карточки SQL / vulns / audit_log
  if (!finalEv) return;
  _lastSQL = finalEv.final_sql;
  _lastApproved = finalEv.approved;
  const verdict = finalEv.approved
    ? '<span class="ok">✓ approved</span>'
    : '<span class="err">✗ rejected</span>';
  const traj = (finalEv.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
  renderBot(`SQL готов · ${verdict} · итераций <b>${finalEv.iterations_used}</b>
             · риск <b>${traj}</b>`);
  const vulnsHtml = (finalEv.vulnerabilities || []).map(v => `
    <div class="vuln ${v.risk_score < 4 ? 'low':''}">
      <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
      ${esc(v.description)}<br>
      <small class="ok">↳ ${esc(v.recommendation || '')}</small>
    </div>`).join('') || '<div class="ok">⚑ уязвимостей не найдено</div>';
  const runBtn = finalEv.approved
    ? '<button id="run-sql">Выполнить на demo_db →</button>'
    : '<button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button>';
  const traceId = finalEv.trace_id;
  const traceLink = traceId
    ? `<a href="http://localhost:13001/trace/${traceId}" target="_blank">
         <button class="ghost">Открыть trace ${traceId.slice(0,8)} →</button></a>` : '';
  out.innerHTML = `
    <div class="card">
      <div class="label">Финальный SQL</div>
      <pre>${esc(finalEv.final_sql)}</pre>
      <div class="row">${runBtn} ${traceLink}</div>
    </div>
    <div class="card">
      <div class="label">Уязвимости (последняя итерация)</div>
      ${vulnsHtml}
    </div>
    <div class="card">
      <div class="label">Audit log</div>
      <pre>${esc(finalEv.audit_log)}</pre>
    </div>
    <div id="run-out"></div>
    ${renderFeedback(finalEv)}`;
  if (traceId) {
    $('#lf-hint').innerHTML = `последний trace: <a href="http://localhost:13001/trace/${traceId}" target="_blank">${traceId.slice(0,8)}</a>`;
    $('#lf-hint').className = 'ok';
    const lf = $("#langfuse-frame"); if (lf) lf.src = `http://localhost:13001/trace/${traceId}`;
  }
  const runBtnEl = $('#run-sql');
  if (runBtnEl) runBtnEl.onclick = runApprovedSQL;
  bindFeedback(finalEv);
  $('#reset').style.display = '';
}

// ── отправить очередной ход в /chat ──
async function sendChat(answer /* optional — текстовый ответ юзера на clarify */) {
  if (answer) {
    _history.push({role:'user', content: answer});
    renderUser(answer);
  }
  out.innerHTML = '<div class="card">… запрос идёт …</div>';
  try {
    const r = await fetch('/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: _task, history: _history})
    });
    if (!r.ok) {
      out.innerHTML = `<div class="card err">HTTP ${r.status}: ${esc(await r.text())}</div>`;
      return;
    }
    const d = await r.json();
    if (d.nl_warnings && d.nl_warnings.length) renderWarnings(d.nl_warnings);

    if (d.type === 'clarify') {
      // assistant задал уточняющий вопрос → запоминаем в history и рисуем
      _history.push({role:'assistant', question: d.question, options: d.options || []});
      const opts = (d.options || []).map(o =>
        `<span class="opt" data-a="${esc(o)}">${esc(o)}</span>`).join('');
      const free = `<div class="answer-row">
                      <input type="text" placeholder="свой ответ…" id="free-answer">
                      <button id="free-send">→</button>
                    </div>`;
      renderBot(`<b>Уточнение:</b><br>${esc(d.question)}<div class="options">${opts}</div>${free}`,
                'bot clarify');
      out.innerHTML = '';
      // обработчики
      msgs.querySelectorAll('.opt').forEach(o => {
        o.onclick = () => sendChat(o.dataset.a);
      });
      const fa = $('#free-answer'), fb = $('#free-send');
      const submitFree = () => {
        const a = fa.value.trim();
        if (a) sendChat(a);
      };
      fa.onkeydown = e => { if (e.key === 'Enter') submitFree(); };
      fb.onclick = submitFree;
      return;
    }

    // d.type === 'sql' — финальный результат
    _lastSQL = d.final_sql;
    _lastApproved = d.approved;
    const verdict = d.approved
      ? '<span class="ok">✓ approved</span>'
      : '<span class="err">✗ rejected</span>';
    const traj = (d.risk_trajectory || []).map(x => x.toFixed(1)).join(' → ');
    renderBot(`SQL готов · ${verdict} · итераций <b>${d.iterations_used}</b>
               · риск <b>${traj}</b>`);

    const vulnsHtml = (d.vulnerabilities || []).map(v => `
      <div class="vuln ${v.risk_score < 4 ? 'low':''}">
        <b>${esc(v.vuln_class)}</b> · risk ${v.risk_score.toFixed(1)}<br>
        ${esc(v.description)}<br>
        <small class="ok">↳ ${esc(v.recommendation || '')}</small>
      </div>`).join('') || '<div class="ok">⚑ уязвимостей не найдено</div>';
    const runBtn = d.approved
      ? '<button id="run-sql">Выполнить на demo_db →</button>'
      : '<button class="ghost" disabled>SQL отклонён аудитором — выполнить нельзя</button>';
    const traceId = d.trace_id;
    const traceLink = traceId
      ? `<a href="http://localhost:13001/trace/${traceId}" target="_blank">
           <button class="ghost">Открыть trace ${traceId.slice(0,8)} в Langfuse →</button></a>`
      : '';
    out.innerHTML = `
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
      <div id="run-out"></div>
      ${renderFeedback(d)}`;
    if (traceId) {
      $('#lf-hint').innerHTML = `последний trace: <a href="http://localhost:13001/trace/${traceId}" target="_blank">${traceId.slice(0,8)}</a>`;
      $('#lf-hint').className = 'ok';
      const lf = $("#langfuse-frame"); if (lf) lf.src = `http://localhost:13001/trace/${traceId}`;
    }
    const runBtnEl = $('#run-sql');
    if (runBtnEl) runBtnEl.onclick = runApprovedSQL;
    bindFeedback(d);
    $('#reset').style.display = '';
  } catch (e) {
    out.innerHTML = `<div class="card err">network error: ${esc(e.message)}</div>`;
  }
}

// ── старт нового диалога ──
const _go_btn = $('#go');
if (_go_btn) _go_btn.onclick = () => {
  const t = $('#task').value.trim();
  if (!t) return;
  resetDialog();
  _task = t;
  $('#task').value = t;
  renderUser(t);
  sendChat();
};

// ── Live-режим: SSE с потоком мыслей (без clarify) ──
const _stream_btn = $('#go-stream');
if (_stream_btn) _stream_btn.onclick = () => {
  const t = $('#task').value.trim();
  if (!t) return;
  resetDialog();
  _task = t;
  $('#task').value = t;
  renderUser(t);
  sendStream();
};

// ── feedback (👍/👎 + комментарий) ──
function renderFeedback(d) {
  return `
    <div class="card" id="fb-card">
      <div class="label">Оцените результат</div>
      <div class="row" style="margin-top:8px">
        <button class="fb-btn up"   data-rating="up">👍 Сработал</button>
        <button class="fb-btn down" data-rating="down">👎 Не сработал</button>
      </div>
      <textarea class="fb-comment" id="fb-comment"
                placeholder="опц.: что не так / что улучшить (для дообучения)"></textarea>
      <div class="row" style="margin-top:8px">
        <button id="fb-send" disabled>Отправить отзыв</button>
        <small style="color:var(--mut)">данные пишутся в data/feedback.jsonl + Langfuse score</small>
      </div>
    </div>`;
}

function bindFeedback(d) {
  const card = $('#fb-card');
  if (!card) return;
  let chosen = null;
  card.querySelectorAll('.fb-btn').forEach(b => {
    b.onclick = () => {
      card.querySelectorAll('.fb-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      chosen = b.dataset.rating;
      $('#fb-send').disabled = false;
    };
  });
  $('#fb-send').onclick = async () => {
    if (!chosen) return;
    const btn = $('#fb-send');
    btn.disabled = true;
    btn.textContent = '…';
    try {
      const r = await fetch('/feedback', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          task: _task,
          final_sql: d.final_sql,
          rating: chosen,
          comment: $('#fb-comment').value.trim() || null,
          trace_id: d.trace_id || null,
          iterations_used: d.iterations_used,
          approved: d.approved,
        })
      });
      const j = await r.json();
      const langSync = j.langfuse_synced ? ' (+ Langfuse score)' : '';
      card.innerHTML = `<div class="fb-thanks">✓ спасибо за отзыв${langSync}</div>`;
    } catch (e) {
      btn.disabled = false; btn.textContent = 'Отправить отзыв';
      card.insertAdjacentHTML('beforeend',
        `<div class="err" style="margin-top:8px">network error: ${esc(e.message)}</div>`);
    }
  };
}

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


# ─── /chat: multi-turn с clarification ──────────────────────────────────────
# Stateless: UI шлёт всю историю каждый раз. Сервер либо возвращает clarify
# (question + options), либо запускает полный pipeline (run_instrumented).
# До MAX_CLARIFY_ROUNDS=2 уточнений; на третьем — force_sql.
MAX_CLARIFY_ROUNDS = 2


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str | None = None          # для user.content или assistant.sql
    question: str | None = None         # assistant.clarify
    options: list[str] | None = None    # assistant.clarify


class ChatRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000,
                      description="Оригинальная NL-задача (первое сообщение)")
    history: list[ChatTurn] = Field(default_factory=list,
                                    description="Раунды clarify, если уже были")


class NLWarningOut(BaseModel):
    code: str
    severity: str
    message: str
    hint: str = ""


class ChatResponse(BaseModel):
    type: str = Field(..., pattern="^(clarify|sql)$")
    # для type=clarify:
    question: str | None = None
    options: list[str] | None = None
    # для type=sql:
    final_sql: str | None = None
    approved: bool | None = None
    iterations_used: int | None = None
    risk_trajectory: list[float] | None = None
    vulnerabilities: list[VulnOut] | None = None
    audit_log: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] | None = None
    # NL-warnings (информационные, не блокирующие)
    nl_warnings: list[NLWarningOut] = Field(default_factory=list)


_CLARIF_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "data", "clarifications.jsonl")


def _persist_clarification(task: str, history: list[ChatTurn],
                           final_sql: str | None, approved: bool | None) -> None:
    """@brief Запись в data/clarifications.jsonl — для будущего few-shot/RLHF.
    Никакой PII (текст пользователя) фильтровать не пытаемся: это локальная
    разработка, в проде поверх — anon-pipeline."""
    import datetime
    import logging
    import uuid
    try:
        os.makedirs(os.path.dirname(_CLARIF_LOG), exist_ok=True)
        with open(_CLARIF_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "id": uuid.uuid4().hex[:12],
                "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "task": task,
                "history": [h.model_dump(exclude_none=True) for h in history],
                "final_sql": final_sql,
                "approved": approved,
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        # Не валим запрос пользователя, но фиксируем в логах — нам важно
        # видеть когда persist ломается (это собирает датасет для будущего fine-tune).
        logging.getLogger("uvicorn.error").warning("clarif persist failed: %r", e)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """@brief Multi-turn с clarification. Stateless (history от UI каждый раз)."""
    # 1) NL-валидация — только на первом ходу (history пустой)
    nl_warnings: list[NLWarningOut] = []
    if not req.history:
        try:
            from case3.audit.nl_validator import validate_nl
            for w in validate_nl(req.task):
                nl_warnings.append(NLWarningOut(
                    code=w.code, severity=w.severity,
                    message=w.message, hint=w.hint))
        except Exception:
            pass

    # 2) Подсчёт уже состоявшихся раундов clarify
    n_clarifies = sum(1 for h in req.history if h.role == "assistant" and h.question)
    force_sql = n_clarifies >= MAX_CLARIFY_ROUNDS

    # 3) LLM генератор — спрашиваем либо clarify, либо SQL
    try:
        from case3.llm.factory import make_llm
        from case3.schema.linker import SchemaLinker
        from case3.nodes.generator import LLMGenerator
        llm = make_llm()
        db_schema = SchemaLinker().link_text(req.task, k=4, max_cols=12, fk_closure=False)
        gen = LLMGenerator(llm=llm, db_schema=db_schema)
        # переведём history в формат, который понимает generate_or_clarify
        clar_hist = [
            {"role": h.role,
             "question": h.question or "",
             "options": h.options or [],
             "content": h.content or ""}
            for h in req.history
        ]
        out = gen.generate_or_clarify(req.task, clarify_history=clar_hist,
                                      force_sql=force_sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generator error: {e}")

    # 4) Если clarify — возвращаем сразу, pipeline не запускаем
    if out.get("type") == "clarify":
        return ChatResponse(type="clarify",
                            question=out.get("question"),
                            options=out.get("options") or [],
                            nl_warnings=nl_warnings)

    # 5) Иначе — собираем «расширенную» задачу для pipeline (NL + ответы пользователя)
    final_task = req.task
    for h in req.history:
        if h.role == "user" and h.content:
            final_task += f"\nУточнение: {h.content}"

    # 6) Полный пайплайн (тот же что для /audit) — на расширенной задаче
    try:
        res = run_instrumented(final_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline error: {e}")

    last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
    vulns = [VulnOut(vuln_class=v.vuln_class, risk_score=v.risk_score,
                     description=v.description, recommendation=v.recommendation)
             for v in (last_audit.vulnerabilities if last_audit else [])]

    # 7) Сохраним диалог в jsonl — это будущий positive few-shot
    if req.history:
        _persist_clarification(req.task, req.history, res.final_sql, res.approved)

    return ChatResponse(
        type="sql",
        final_sql=res.final_sql,
        approved=res.approved,
        iterations_used=res.iterations_used,
        risk_trajectory=res.metadata.get("risk_trajectory", []),
        vulnerabilities=vulns,
        audit_log=res.audit_log,
        trace_id=res.metadata.get("trace_id"),
        metadata=res.metadata,
        nl_warnings=nl_warnings,
    )


# ─── /chat/stream: SSE-стрим этапов пайплайна (live thinking) ───────────────
# Возвращает text/event-stream. UI парсит через fetch+ReadableStream.
# Каждое событие — JSON-объект с полем "event": iter_start / generator_start /
# generator_done / auditor_done / reflector_done / final.
#
# Pipeline.run() — синхронный (тяжёлые LLM-вызовы). Запускаем его в
# threadpool через run_in_executor, шлём события через asyncio.Queue,
# event loop FastAPI не блокируется и SSE-чанки уходят в браузер по мере
# появления.
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """@brief SSE-стрим этапов pipeline'а — для 'thinking' UI."""
    import asyncio

    # NL-валидация — первым событием
    nl_warnings: list[dict] = []
    try:
        from case3.audit.nl_validator import validate_nl
        for w in validate_nl(req.task):
            nl_warnings.append({
                "code": w.code, "severity": w.severity,
                "message": w.message, "hint": w.hint
            })
    except Exception:
        pass

    # Расширим task ответами пользователя из history
    final_task = req.task
    for h in req.history:
        if h.role == "user" and h.content:
            final_task += f"\nУточнение: {h.content}"

    loop = asyncio.get_running_loop()
    q: "asyncio.Queue[dict]" = asyncio.Queue()
    SENTINEL = object()

    def emit_threadsafe(ev: dict) -> None:
        # вызывается из worker-потока pipeline; шлём в event-loop коректно
        loop.call_soon_threadsafe(q.put_nowait, ev)

    def worker_blocking() -> None:
        try:
            res = run_instrumented(final_task, on_event=emit_threadsafe)
            last_audit = res.iterations_log[-1].audit_result if res.iterations_log else None
            emit_threadsafe({
                "event": "final",
                "approved": res.approved,
                "iterations_used": res.iterations_used,
                "risk_trajectory": res.metadata.get("risk_trajectory", []),
                "final_sql": res.final_sql,
                "audit_log": res.audit_log,
                "trace_id": res.metadata.get("trace_id"),
                "vulnerabilities": [
                    {"vuln_class": v.vuln_class, "risk_score": v.risk_score,
                     "description": v.description,
                     "recommendation": v.recommendation}
                    for v in (last_audit.vulnerabilities if last_audit else [])
                ],
            })
        except Exception as e:
            emit_threadsafe({"event": "error", "message": str(e)})
        finally:
            loop.call_soon_threadsafe(q.put_nowait, SENTINEL)

    async def stream():
        # NL-warnings первыми
        if nl_warnings:
            yield "data: " + _json.dumps(
                {"event": "nl_warnings", "warnings": nl_warnings},
                ensure_ascii=False) + "\n\n"
        # запускаем pipeline в threadpool
        loop.run_in_executor(None, worker_blocking)
        while True:
            ev = await q.get()
            if ev is SENTINEL:
                break
            yield "data: " + _json.dumps(ev, ensure_ascii=False) + "\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


# ─── /feedback: оценка финального SQL — RLHF-датасет + Langfuse score ──────
# Складывается в data/feedback.jsonl. Если есть LANGFUSE_PUBLIC_KEY и trace_id —
# параллельно посылается score в Langfuse (filterable в UI: thumbs_up / down).
_FEEDBACK_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "data", "feedback.jsonl")


class FeedbackRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    final_sql: str | None = None
    rating: str = Field(..., pattern="^(up|down)$",
                        description="up = сработал, down = не сработал")
    comment: str | None = Field(None, max_length=1000)
    trace_id: str | None = None
    iterations_used: int | None = None
    approved: bool | None = None


class FeedbackResponse(BaseModel):
    ok: bool
    langfuse_synced: bool


def _persist_feedback(req: FeedbackRequest) -> None:
    """@brief Запись в data/feedback.jsonl — RLHF/eval-данные."""
    import datetime
    import logging
    import uuid
    try:
        os.makedirs(os.path.dirname(_FEEDBACK_LOG), exist_ok=True)
        with open(_FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "id": uuid.uuid4().hex[:12],
                "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                **req.model_dump(exclude_none=True),
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("feedback persist failed: %r", e)


def _sync_langfuse_score(req: FeedbackRequest) -> bool:
    """@brief Послать score в Langfuse (если ключи есть и trace_id известен)."""
    if not req.trace_id:
        return False
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return False
    try:
        from langfuse import Langfuse
        lf = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST", "http://langfuse:3000"),
        )
        # score: 1.0 = сработал, 0.0 = не сработал
        lf.score(trace_id=req.trace_id,
                 name="user_thumbs",
                 value=1.0 if req.rating == "up" else 0.0,
                 comment=req.comment or "")
        lf.flush()
        return True
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "langfuse score sync failed: %r", e)
        return False


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest) -> FeedbackResponse:
    """@brief Оценка финального SQL пользователем (для RLHF/обучения и Langfuse UI)."""
    _persist_feedback(req)
    synced = _sync_langfuse_score(req)
    return FeedbackResponse(ok=True, langfuse_synced=synced)


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
